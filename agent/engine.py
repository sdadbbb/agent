"""Agent 执行引擎 - ReAct 单步循环"""
import json
import re
import os
from datetime import datetime
from log.logger import LoggerUtil
from browser.manager import browser_manager
from browser.snapshot import PageSnapshot
from agent.prompts import build_navigate_prompt, build_step_prompt
from agent.browser_tools import BROWSER_TOOLS_SPEC, BROWSER_TOOL_EXECUTORS, set_page
from agent.case_tools import CASE_TOOLS_SPEC, CASE_TOOL_EXECUTORS
from executor.result_recorder import ResultRecorder

logger = LoggerUtil.get_logger()

# 合并所有工具规范和执行器
ALL_TOOLS_SPEC = BROWSER_TOOLS_SPEC + CASE_TOOLS_SPEC
ALL_TOOL_EXECUTORS = {}
ALL_TOOL_EXECUTORS.update(BROWSER_TOOL_EXECUTORS)
ALL_TOOL_EXECUTORS.update(CASE_TOOL_EXECUTORS)


class AgentEngine:
    """Agent 执行引擎 - ReAct 单步模式：每步都获取最新页面状态让 LLM 决策"""

    MAX_STEPS = 50

    def __init__(self, llm_client):
        self.llm_client = llm_client
        self.page = None
        self.step_log = []
        self.screenshots = []
        self.start_time = None
        self.task_description = ''
        self._stopped = False
        self._on_step_callback = None

    def set_callback(self, callback):
        self._on_step_callback = callback

    def stop(self):
        self._stopped = True

    def execute(self, task_description):
        """执行测试任务 - ReAct 单步循环"""
        self.task_description = task_description
        self.start_time = datetime.now()
        self.step_log = []
        self.screenshots = []
        self._stopped = False

        try:
            # 1. 初始化浏览器
            self._emit('status', '正在启动浏览器...')
            browser_manager.launch(headless=False)
            self.page = browser_manager.new_page()
            set_page(self.page)

            # 2. 提取 URL 并导航
            self._emit('step', '正在分析任务并打开页面...')
            url = self._extract_url(task_description)
            if not url:
                return {'success': False, 'error': '无法从任务中提取URL', 'task': task_description, 'steps': self.step_log}

            self._emit('action', f'打开页面: {url}')
            nav_executor = BROWSER_TOOL_EXECUTORS.get('browser_navigate')
            nav_result = nav_executor({'url': url})
            self.step_log.append({
                'step': 1, 'action': 'browser_navigate',
                'params': {'url': url}, 'result': nav_result,
                'passed': nav_result.get('success', False)
            })
            if not nav_result.get('success', False):
                return {'success': False, 'error': f'导航失败: {url}', 'task': task_description, 'steps': self.step_log}
            self._emit('result', '页面打开成功')

            # 保存初始页面截图
            self._wait_and_screenshot('init')

            # 3. ReAct 单步循环（支持批量执行）
            step_count = len(self.step_log)
            while step_count < self.MAX_STEPS and not self._stopped:
                # 3a. 获取当前页面最新状态
                self._emit('step', f'正在获取页面状态（步骤 {step_count + 1} 决策）...')
                state_executor = BROWSER_TOOL_EXECUTORS.get('browser_get_page_state')
                page_state = state_executor({})

                # 3b. LLM 决定下一步（可能返回批量步骤）
                self._emit('step', f'分析页面状态，决定下一步操作...')
                next_steps = self._ask_llm_for_next_steps(task_description, page_state)

                # 3c. 批量执行所有步骤
                done_reason = None
                batch_failed = False
                for next_step in next_steps:
                    tool_name = next_step.get('tool', '')
                    args = next_step.get('args', {})

                    # 检查是否完成
                    if tool_name == 'done':
                        done_reason = args.get('report', '任务已完成')
                        self._emit('status', f'任务完成: {done_reason}')
                        break

                    # 执行工具
                    step_count += 1
                    batch_label = f' (第{next_steps.index(next_step)+1}/{len(next_steps)}步)' if len(next_steps) > 1 else ''
                    self._emit('action', f'步骤 {step_count}{batch_label}: {tool_name}')

                    executor = ALL_TOOL_EXECUTORS.get(tool_name)
                    if not executor:
                        self._emit('result', f'未知工具: {tool_name}')
                        self.step_log.append({
                            'step': step_count, 'action': tool_name,
                            'params': args, 'result': {'success': False, 'error': f'未知工具: {tool_name}'},
                            'passed': False
                        })
                        continue

                    exec_result = executor(args)
                    passed = exec_result.get('success', False)

                    self.step_log.append({
                        'step': step_count, 'action': tool_name,
                        'params': args, 'result': exec_result,
                        'passed': passed
                    })

                    if passed:
                        self._wait_and_screenshot(f'step_{step_count}')
                        self._emit('result', f'步骤 {step_count}{batch_label} 成功: {tool_name}')
                    else:
                        error_msg = exec_result.get('error', '执行失败')
                        self._emit('result', f'步骤 {step_count}{batch_label} 失败: {tool_name} - {error_msg}')
                        self._emit('status', '批次中有步骤失败，基于当前页面状态重新规划...')
                        batch_failed = True
                        break  # 跳出批量执行，让 LLM 重新决策

                # 检查 done 信号
                if done_reason:
                    break

                # 批次全部成功但可能因为达到上限或停止信号
                if step_count >= self.MAX_STEPS or self._stopped:
                    break

                # 批次全部执行完成（成功或部分失败），下一轮循环自动获取最新页面状态

            if step_count >= self.MAX_STEPS:
                self._emit('status', f'已达最大步骤数({self.MAX_STEPS})，终止执行')

            # 4. 生成报告
            self._emit('status', '执行完成，正在生成报告...')
            report = self._generate_report()

            elapsed = (datetime.now() - self.start_time).total_seconds()
            all_passed = all(s.get('passed', False) for s in self.step_log) if self.step_log else False
            result = {
                'success': all_passed,
                'task': task_description,
                'report': report,
                'steps': self.step_log,
                'step_count': len(self.step_log),
                'screenshots': self.screenshots,
                'elapsed_seconds': round(elapsed, 1),
                'start_time': self.start_time.strftime('%Y-%m-%d %H:%M:%S')
            }

            self._auto_save(result)
            return result

        except Exception as e:
            logger.error(f"Agent 执行异常: {str(e)}")
            return {
                'success': False,
                'error': str(e),
                'task': task_description,
                'steps': self.step_log
            }
        finally:
            self._cleanup()

    def _wait_and_screenshot(self, name):
        """等待页面加载稳定后截图"""
        try:
            self.page.wait_for_timeout(1500)
            self.page.wait_for_load_state('load', timeout=15000)
        except Exception:
            pass
        try:
            os.makedirs('data/screenshots', exist_ok=True)
            ss_path = f'data/screenshots/{name}_{datetime.now().strftime("%Y%m%d_%H%M%S")}.png'
            self.page.screenshot(path=ss_path)
            self.screenshots.append(ss_path)
            self._emit('screenshot', ss_path)
        except Exception:
            pass

    def _extract_url(self, task_description):
        """从任务中提取 URL"""
        url_match = re.search(r'https?://[^\s,，。；;]+', task_description)
        if url_match:
            return url_match.group(0).rstrip('/')

        prompt = build_navigate_prompt(task_description)
        content = self.llm_client.chat([{'role': 'user', 'content': prompt}])
        url = content.strip()
        if url.startswith('http'):
            return url

        self._emit('info', '未能从任务中提取 URL，使用默认搜索')
        return 'https://www.baidu.com'

    def _extract_json(self, text):
        """从 LLM 回复中提取 JSON（支持对象 {} 或数组 []）"""
        match = re.search(r'```(?:json)?\s*([\s\S]*?)```', text)
        if match:
            text = match.group(1)
        # 先尝试找 {}
        match = re.search(r'\{[\s\S]*\}', text)
        if match:
            return match.group(0).strip()
        # 再尝试找 []
        match = re.search(r'\[[\s\S]*\]', text)
        if match:
            return match.group(0).strip()
        return text.strip()

    def _ask_llm_for_next_steps(self, task_description, page_state):
        """让 LLM 决定下一步操作（支持批量返回多个步骤）"""
        history = [s for s in self.step_log if s.get('action') != 'browser_get_page_state']
        prompt = build_step_prompt(task_description, page_state, history)
        messages = [{'role': 'user', 'content': prompt}]

        content = self.llm_client.chat(messages)
        self._emit('info', f'LLM 决策: {content[:200]}')

        try:
            json_str = self._extract_json(content)
            parsed = json.loads(json_str)

            # 兼容单对象和数组格式
            if isinstance(parsed, dict):
                steps = [parsed]
            elif isinstance(parsed, list):
                steps = parsed
            else:
                raise ValueError("非对象/数组格式")

            step_names = [s.get('tool', '?') for s in steps]
            logger.info(f"LLM 批量步骤 ({len(steps)}): {step_names}")
            return steps
        except (json.JSONDecodeError, ValueError) as e:
            logger.error(f"解析 LLM 决策失败: {str(e)}, 原始: {content[:300]}")
            return [{'tool': 'done', 'args': {'report': f'LLM 决策解析失败: {str(e)}'}}]

    def _generate_report(self):
        """生成最终测试报告"""
        steps_summary = '\n'.join([
            f"  {s['step']}. {s['action']} - {'通过' if s.get('passed') else '失败'}"
            for s in self.step_log
        ])
        passed_count = sum(1 for s in self.step_log if s.get('passed'))
        total_count = len(self.step_log)

        report = (
            f'## 测试报告\n\n'
            f'- 执行任务: {self.task_description}\n'
            f'- 执行时间: {self.start_time.strftime("%Y-%m-%d %H:%M:%S")}\n'
            f'- 执行步骤: {total_count} 步\n'
            f'- 通过: {passed_count} / 失败: {total_count - passed_count}\n\n'
            f'### 执行详情\n\n{steps_summary}'
        )
        return report

    def _auto_save(self, result):
        try:
            recorder = ResultRecorder()
            recorder.save(result)
        except Exception as e:
            logger.error(f"自动保存结果失败: {str(e)}")

    def _cleanup(self):
        try:
            browser_manager.close_context()
        except Exception:
            pass
        set_page(None)

    def _emit(self, event_type, data):
        timestamp = datetime.now().strftime('%H:%M:%S')
        if event_type in ('status', 'step'):
            logger.info(f"[{event_type}] {data}")
        elif event_type == 'action':
            logger.info(f"[执行] {data}")
        elif event_type == 'result':
            logger.info(f"[结果] {data}")
        elif event_type == 'error':
            logger.error(f"[错误] {data}")
        elif event_type == 'info':
            logger.info(f"[分析] {data}")
        elif event_type == 'screenshot':
            logger.info(f"[截图] {data}")
        if self._on_step_callback:
            self._on_step_callback({
                'type': event_type,
                'data': data,
                'timestamp': timestamp
            })
