"""测试用例 CRUD 管理器，基于 JSON 文件存储"""
import os
import json
from datetime import datetime
from typing import Optional
from cases.case_models import TestCase, ReportResult
from log.logger import LoggerUtil

logger = LoggerUtil.get_logger()


class CaseManager:
    """用例管理器，负责增删改查"""

    def __init__(self, data_dir='data/cases'):
        self.data_dir = data_dir
        self.results_dir = 'data/results'
        os.makedirs(self.data_dir, exist_ok=True)
        os.makedirs(self.results_dir, exist_ok=True)

    def _get_filepath(self, case_id):
        return os.path.join(self.data_dir, f'{case_id}.json')

    def _get_result_path(self, case_id):
        return os.path.join(self.results_dir, f'{case_id}.json')

    # ─── 用例元数据操作 ──────────────────────────────

    def save_case(self, case: TestCase) -> TestCase:
        """保存用例元数据"""
        filepath = self._get_filepath(case.id)
        with open(filepath, 'w', encoding='utf-8') as f:
            json.dump(case.to_dict(), f, ensure_ascii=False, indent=2)
        logger.info(f"用例已保存: {case.name} ({case.id})")
        return case

    def get_case(self, case_id: str) -> Optional[TestCase]:
        """获取用例元数据"""
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
        """删除用例（用例管理用）"""
        # 先删除关联的报告
        self.delete_report(case_id)
        case_path = self._get_filepath(case_id)
        if os.path.exists(case_path):
            os.remove(case_path)
            logger.info(f"用例已删除: {case_id}")
        return True

    def list_cases(self, page=1, page_size=10, keyword=''):
        """分页查询用例列表（仅元数据）"""
        files = os.listdir(self.data_dir)
        cases = []

        for fname in files:
            if not fname.endswith('.json'):
                continue
            try:
                with open(os.path.join(self.data_dir, fname), 'r', encoding='utf-8') as f:
                    data = json.load(f)
                if keyword:
                    kw = keyword.lower()
                    if kw not in data.get('name', '').lower():
                        continue
                cases.append({
                    'id': data.get('id', ''),
                    'name': data.get('name', ''),
                    'description': data.get('description', ''),
                    'task': data.get('task', ''),
                    'created_at': data.get('created_at', ''),
                    'tags': data.get('tags', []),
                    'step_count': len(data.get('steps_log', [])),
                })
            except Exception as e:
                logger.warning(f"读取用例文件失败 {fname}: {str(e)}")

        cases.sort(key=lambda x: x.get('created_at', ''), reverse=True)

        total = len(cases)
        start = (page - 1) * page_size
        end = start + page_size

        return {
            'data': cases[start:end],
            'total': total,
            'page': page,
            'page_size': page_size,
            'total_pages': (total + page_size - 1) // page_size if total > 0 else 1
        }

    # ─── 报告（执行结果）操作 ──────────────────────────

    def save_result(self, result: ReportResult):
        """保存执行结果到 results/ 目录"""
        filepath = self._get_result_path(result.case_id)
        with open(filepath, 'w', encoding='utf-8') as f:
            json.dump(result.to_dict(), f, ensure_ascii=False, indent=2)
        logger.info(f"执行结果已保存: {result.case_id}")

    def get_result(self, case_id: str) -> Optional[ReportResult]:
        """获取执行结果"""
        filepath = self._get_result_path(case_id)
        if not os.path.exists(filepath):
            return None
        try:
            with open(filepath, 'r', encoding='utf-8') as f:
                data = json.load(f)
            return ReportResult.from_dict(data)
        except Exception as e:
            logger.error(f"读取结果失败 {case_id}: {str(e)}")
            return None

    def get_report(self, case_id: str) -> Optional[dict]:
        """获取完整报告（用例元数据 + 执行结果合并）"""
        case = self.get_case(case_id)
        result = self.get_result(case_id)
        if not case:
            return None
        # steps_log 来自用例，其余来自报告结果
        report = case.to_dict()
        if result:
            report.update({
                'passed': result.passed,
                'screenshots': result.screenshots,
                'conclusion': result.conclusion,
                'elapsed_seconds': result.elapsed_seconds,
                'executed_at': result.executed_at,
            })
        else:
            report.update({
                'passed': False,
                'screenshots': [],
                'conclusion': '',
                'elapsed_seconds': 0.0,
                'executed_at': '',
            })
        return report

    def list_reports(self, page=1, page_size=10, keyword='', status=''):
        """查询报告列表（仅已执行的）"""
        files = os.listdir(self.results_dir)
        reports = []

        for fname in files:
            if not fname.endswith('.json'):
                continue
            try:
                with open(os.path.join(self.results_dir, fname), 'r', encoding='utf-8') as f:
                    result_data = json.load(f)
                case_id = result_data.get('case_id', '')
                case = self.get_case(case_id)

                if keyword:
                    kw = keyword.lower()
                    name = case.name.lower() if case else ''
                    if kw not in name:
                        continue
                if status == 'passed' and not result_data.get('passed'):
                    continue
                if status == 'failed' and result_data.get('passed'):
                    continue

                reports.append({
                    'id': case_id,
                    'name': case.name if case else '未知用例',
                    'passed': result_data.get('passed', False),
                    'step_count': len(case.steps_log) if case else 0,
                    'screenshot_count': len(result_data.get('screenshots', [])),
                    'elapsed_seconds': result_data.get('elapsed_seconds', 0),
                    'executed_at': result_data.get('executed_at', ''),
                })
            except Exception as e:
                logger.warning(f"读取结果文件失败 {fname}: {str(e)}")

        reports.sort(key=lambda x: x.get('executed_at', ''), reverse=True)

        total = len(reports)
        start = (page - 1) * page_size
        end = start + page_size

        return {
            'data': reports[start:end],
            'total': total,
            'page': page,
            'page_size': page_size,
            'total_pages': (total + page_size - 1) // page_size if total > 0 else 1
        }

    def delete_report(self, case_id: str) -> bool:
        """删除报告（只删结果+截图，保留用例）"""
        result = self.get_result(case_id)

        # 删除截图
        if result and result.screenshots:
            for sp in result.screenshots:
                try:
                    if os.path.exists(sp):
                        os.remove(sp)
                        logger.info(f"截图已删除: {sp}")
                except Exception as e:
                    logger.warning(f"删除截图失败 {sp}: {str(e)}")

        # 删除结果文件
        result_path = self._get_result_path(case_id)
        if os.path.exists(result_path):
            try:
                os.remove(result_path)
                logger.info(f"结果文件已删除: {case_id}")
            except Exception as e:
                logger.warning(f"删除结果文件失败 {case_id}: {str(e)}")

        return True

    def get_stats(self):
        """获取统计概览（基于结果文件）"""
        files = [f for f in os.listdir(self.results_dir) if f.endswith('.json')]
        total = len(files)
        passed = 0
        for fname in files:
            try:
                with open(os.path.join(self.results_dir, fname), 'r', encoding='utf-8') as f:
                    data = json.load(f)
                if data.get('passed'):
                    passed += 1
            except Exception:
                pass
        return {
            'total_cases': total,
            'passed': passed,
            'failed': total - passed,
            'pass_rate': round((passed / total * 100) if total > 0 else 0, 1)
        }
