"""执行结果记录器 - 将 Agent 执行结果持久化"""
import os
import json
from datetime import datetime
from log.logger import LoggerUtil
from cases.case_models import TestCase

logger = LoggerUtil.get_logger()


class ResultRecorder:
    """执行结果记录器"""

    def __init__(self, results_dir='data/results'):
        self.results_dir = results_dir
        os.makedirs(self.results_dir, exist_ok=True)

    def save(self, result: dict):
        """保存执行结果"""
        try:
            case = TestCase(
                name=result.get('task', '未命名任务')[:50],
                task=result.get('task', ''),
                passed=result.get('success', False),
                steps_log=result.get('steps', []),
                screenshots=result.get('screenshots', []),
                elapsed_seconds=result.get('elapsed_seconds', 0),
                conclusion=result.get('report', '')[:500]
            )
            # 保存到 cases 目录
            from cases.case_manager import CaseManager
            cm = CaseManager()
            cm.save_case(case)

            # 同时保存原始结果到 results 目录
            filepath = os.path.join(self.results_dir, f'{case.id}.json')
            with open(filepath, 'w', encoding='utf-8') as f:
                json.dump(result, f, ensure_ascii=False, indent=2)

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
