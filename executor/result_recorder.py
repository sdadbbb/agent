"""执行结果记录器 - 将 Agent 执行结果分别保存到用例和报告"""
import os
import json
from cases.case_models import TestCase, ReportResult
from log.logger import LoggerUtil

logger = LoggerUtil.get_logger()


class ResultRecorder:
    """执行结果记录器"""

    def __init__(self, results_dir='data/results'):
        self.results_dir = results_dir
        os.makedirs(self.results_dir, exist_ok=True)

    def save(self, result: dict):
        """保存执行结果（用例 + 报告分开存储，steps_log 归用例）"""
        try:
            from cases.case_manager import CaseManager
            cm = CaseManager()

            task = result.get('task', '未命名任务')
            name = task[:50] if task else '未命名任务'

            # 1. 保存用例（含执行步骤）
            case = TestCase(
                name=name,
                task=task,
                steps_log=result.get('steps', []),
            )
            cm.save_case(case)

            # 2. 保存报告（结果+截图，不含步骤）
            report = ReportResult(
                case_id=case.id,
                passed=result.get('success', False),
                screenshots=result.get('screenshots', []),
                conclusion=result.get('report', '')[:500],
                elapsed_seconds=result.get('elapsed_seconds', 0),
            )
            cm.save_result(report)

            logger.info(f"执行结果已保存: {case.id}")
            return case.id
        except Exception as e:
            logger.error(f"保存执行结果失败: {str(e)}")
            return None

    def get_result(self, case_id: str) -> dict:
        """获取原始执行结果"""
        filepath = os.path.join(self.results_dir, f'{case_id}.json')
        if os.path.exists(filepath):
            with open(filepath, 'r', encoding='utf-8') as f:
                return json.load(f)
        return {}
