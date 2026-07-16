"""结构化步骤执行器 - 按预设步骤列表回放"""
from log.logger import LoggerUtil
from browser.snapshot import PageSnapshot

logger = LoggerUtil.get_logger()


class StepExecutor:
    """按结构化步骤执行测试（兼容旧模式）"""

    def __init__(self, page):
        self.page = page
        self.variables = {}

    def execute_steps(self, steps):
        """按步骤列表顺序执行"""
        results = []
        for i, step in enumerate(steps, 1):
            action = step.get('action', '')
            params = step.get('params', {})
            logger.info(f"执行步骤 {i}: {action}")

            try:
                if action == 'go_url':
                    self.page.goto(params['url'])
                    results.append({'step': i, 'passed': True, 'message': f'导航到 {params["url"]}'})

                elif action == 'click':
                    self.page.locator(params['selector']).click()
                    results.append({'step': i, 'passed': True, 'message': f'点击 {params["selector"]}'})

                elif action == 'fill':
                    text = self._replace_vars(params.get('text', ''))
                    self.page.locator(params['selector']).fill(text)
                    results.append({'step': i, 'passed': True, 'message': f'输入 {text}'})

                elif action == 'assert_text':
                    body = self.page.inner_text('body')
                    passed = params['text'] in body
                    results.append({'step': i, 'passed': passed, 'message': f'断言文本"{params["text"]}": {"通过" if passed else "失败"}'})

                elif action == 'wait':
                    self.page.wait_for_timeout(params.get('ms', 1000))
                    results.append({'step': i, 'passed': True, 'message': f'等待 {params.get("ms", 1000)}ms'})

                else:
                    results.append({'step': i, 'passed': False, 'message': f'未知操作: {action}'})

            except Exception as e:
                results.append({'step': i, 'passed': False, 'message': f'执行失败: {str(e)}'})

        return results

    def _replace_vars(self, text):
        if not isinstance(text, str):
            return text
        for k, v in self.variables.items():
            text = text.replace(f'${{{k}}}', str(v))
        return text
