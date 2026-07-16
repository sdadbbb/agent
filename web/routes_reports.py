"""报告查看 API"""
import os
from flask import Blueprint, jsonify, send_file, request
from cases.case_manager import CaseManager
from log.logger import LoggerUtil

logger = LoggerUtil.get_logger()
reports_bp = Blueprint('reports', __name__)
cm = CaseManager()

SCREENSHOTS_DIR = 'data/screenshots'


@reports_bp.route('/api/reports', methods=['GET'])
def list_reports():
    """查询报告列表（仅已执行的）"""
    page = request.args.get('page', 1, type=int)
    page_size = request.args.get('page_size', 10, type=int)
    keyword = request.args.get('keyword', '').strip()
    status = request.args.get('status', '').strip()
    result = cm.list_reports(page=page, page_size=page_size, keyword=keyword, status=status)
    return jsonify({'success': True, 'data': result})


@reports_bp.route('/api/reports/screenshots/<filename>')
def get_screenshot(filename):
    """获取截图文件"""
    filepath = os.path.join(SCREENSHOTS_DIR, filename)
    if os.path.exists(filepath):
        return send_file(filepath, mimetype='image/png')
    return jsonify({'success': False, 'message': '文件不存在'})


@reports_bp.route('/api/reports/<case_id>', methods=['GET'])
def get_report(case_id):
    """获取完整报告"""
    report = cm.get_report(case_id)
    if not report:
        return jsonify({'success': False, 'message': '报告不存在'})
    # 处理截图路径为文件名
    screenshots = []
    for sp in report.get('screenshots', []):
        if os.path.exists(sp):
            screenshots.append(os.path.basename(sp))
    report['screenshots'] = screenshots
    return jsonify({'success': True, 'data': report})


@reports_bp.route('/api/reports/<case_id>', methods=['DELETE'])
def delete_report(case_id):
    """删除报告（只删结果+截图，保留用例）"""
    cm.delete_report(case_id)
    return jsonify({'success': True, 'message': '报告已删除，用例已保留'})
