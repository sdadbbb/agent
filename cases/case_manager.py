"""测试用例 CRUD 管理器，基于 JSON 文件存储"""
import os
import json
from datetime import datetime
from typing import List, Optional
from cases.case_models import TestCase
from log.logger import LoggerUtil

logger = LoggerUtil.get_logger()


class CaseManager:
    """用例管理器，负责增删改查"""

    def __init__(self, data_dir='data/cases'):
        self.data_dir = data_dir
        os.makedirs(self.data_dir, exist_ok=True)

    def _get_filepath(self, case_id):
        return os.path.join(self.data_dir, f'{case_id}.json')

    def save_case(self, case: TestCase) -> TestCase:
        """保存用例，如果已存在则覆盖"""
        filepath = self._get_filepath(case.id)
        with open(filepath, 'w', encoding='utf-8') as f:
            json.dump(case.to_dict(), f, ensure_ascii=False, indent=2)
        logger.info(f"用例已保存: {case.name} ({case.id})")
        return case

    def get_case(self, case_id: str) -> Optional[TestCase]:
        """获取单个用例"""
        filepath = self._get_filepath(case_id)
        if not os.path.exists(filepath):
            return None
        try:
            with open(filepath, 'r', encoding='utf-8') as f:
                data = json.load(f)
            return TestCase.from_dict(data)
        except Exception as e:
            logger.error(f"读取用例失败 {case_id}: {str(e)}")
            return None

    def delete_case(self, case_id: str) -> bool:
        """删除用例"""
        filepath = self._get_filepath(case_id)
        if os.path.exists(filepath):
            os.remove(filepath)
            logger.info(f"用例已删除: {case_id}")
            return True
        return False

    def list_cases(self, page=1, page_size=10, keyword='', status=''):
        """分页查询用例列表"""
        files = os.listdir(self.data_dir)
        cases = []

        for fname in files:
            if not fname.endswith('.json'):
                continue
            try:
                with open(os.path.join(self.data_dir, fname), 'r', encoding='utf-8') as f:
                    data = json.load(f)
                # 搜索过滤
                if keyword:
                    kw = keyword.lower()
                    if kw not in data.get('name', '').lower() and kw not in data.get('task', '').lower():
                        continue
                # 状态过滤
                if status == 'passed' and not data.get('passed'):
                    continue
                if status == 'failed' and data.get('passed'):
                    continue
                cases.append({
                    'id': data.get('id', ''),
                    'name': data.get('name', ''),
                    'description': data.get('description', ''),
                    'passed': data.get('passed', False),
                    'elapsed_seconds': data.get('elapsed_seconds', 0),
                    'created_at': data.get('created_at', ''),
                    'tags': data.get('tags', []),
                    'step_count': len(data.get('steps_log', [])),
                    'screenshot_count': len(data.get('screenshots', []))
                })
            except Exception as e:
                logger.warning(f"读取用例文件失败 {fname}: {str(e)}")

        # 按时间降序
        cases.sort(key=lambda x: x.get('created_at', ''), reverse=True)

        total = len(cases)
        start = (page - 1) * page_size
        end = start + page_size
        paginated = cases[start:end]

        return {
            'data': paginated,
            'total': total,
            'page': page,
            'page_size': page_size,
            'total_pages': (total + page_size - 1) // page_size if total > 0 else 1
        }

    def get_stats(self):
        """获取统计概览"""
        all_cases = self.list_cases(page=1, page_size=9999)
        total = all_cases['total']
        # 需要遍历所有文件计算通过数
        passed = 0
        failed = 0
        for item in all_cases['data']:
            if item.get('passed'):
                passed += 1
            else:
                failed += 1
        return {
            'total_cases': total,
            'passed': passed,
            'failed': failed,
            'pass_rate': round((passed / total * 100) if total > 0 else 0, 1)
        }
