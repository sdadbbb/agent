"""导出为 CSV/XLSX/HTML 报告"""
import os
import csv
import json
from datetime import datetime
from log.logger import LoggerUtil
from cases.case_manager import CaseManager

logger = LoggerUtil.get_logger()
case_manager = CaseManager()


class CaseExporter:
    """用例导出器"""

    def __init__(self, export_dir='data/exports'):
        self.export_dir = export_dir
        os.makedirs(self.export_dir, exist_ok=True)

    def export_to_csv(self, case_id):
        """导出单个用例为CSV"""
        report = case_manager.get_report(case_id)
        if not report:
            return None, '用例不存在'

        filename = f'{report["name"]}_{case_id[:8]}.csv'
        filepath = os.path.join(self.export_dir, filename)

        with open(filepath, 'w', encoding='utf-8-sig', newline='') as f:
            writer = csv.writer(f)
            writer.writerow(['字段', '内容'])
            writer.writerow(['用例名称', report['name']])
            writer.writerow(['描述', report.get('description', '')])
            writer.writerow(['执行结果', '通过' if report.get('passed') else '失败'])
            writer.writerow(['执行时间', report.get('executed_at', report.get('created_at', ''))])
            writer.writerow(['耗时(秒)', report.get('elapsed_seconds', 0)])
            writer.writerow([])
            writer.writerow(['步骤', '操作', '结果'])
            for i, step in enumerate(report.get('steps_log', []), 1):
                passed = '通过' if step.get('passed', False) else '失败'
                desc = step.get('description', step.get('action', ''))
                result = json.dumps(step.get('result', {}), ensure_ascii=False)[:200]
                writer.writerow([i, desc, f'{passed} | {result}'])
            writer.writerow([])
            writer.writerow(['测试结论', report.get('conclusion', '')])

        logger.info(f"CSV导出成功: {filepath}")
        return filepath, filename

    def export_to_xlsx(self, case_id):
        """导出为XLSX"""
        try:
            from openpyxl import Workbook
            report = case_manager.get_report(case_id)
            if not report:
                return None, '用例不存在'

            filename = f'{report["name"]}_{case_id[:8]}.xlsx'
            filepath = os.path.join(self.export_dir, filename)

            wb = Workbook()
            ws = wb.active
            ws.title = '测试报告'

            ws.append(['测试用例报告'])
            ws.append([])
            ws.append(['用例名称', report['name']])
            ws.append(['描述', report.get('description', '')])
            ws.append(['执行结果', '通过' if report.get('passed') else '失败'])
            ws.append(['执行时间', report.get('executed_at', report.get('created_at', ''))])
            ws.append(['耗时(秒)', report.get('elapsed_seconds', 0)])
            ws.append([])
            ws.append(['步骤', '操作', '参数', '结果'])
            for i, step in enumerate(report.get('steps_log', []), 1):
                ws.append([i, step.get('action', ''), json.dumps(step.get('params', {}), ensure_ascii=False), json.dumps(step.get('result', {}), ensure_ascii=False)[:200]])
            ws.append([])
            ws.append(['测试结论', report.get('conclusion', '')])

            wb.save(filepath)
            logger.info(f"XLSX导出成功: {filepath}")
            return filepath, filename
        except ImportError:
            return None, '请安装 openpyxl: pip install openpyxl'

    def list_exports(self):
        """列出已导出的文件"""
        files = []
        for fname in os.listdir(self.export_dir):
            fpath = os.path.join(self.export_dir, fname)
            if os.path.isfile(fpath):
                files.append({
                    'filename': fname,
                    'size': os.path.getsize(fpath),
                    'created_at': datetime.fromtimestamp(os.path.getctime(fpath)).strftime('%Y-%m-%d %H:%M:%S')
                })
        files.sort(key=lambda x: x['created_at'], reverse=True)
        return files

    def delete_export(self, filename):
        """删除导出文件"""
        fpath = os.path.join(self.export_dir, filename)
        if os.path.exists(fpath):
            os.remove(fpath)
            return True
        return False
