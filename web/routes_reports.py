"""报告查看 API"""
import os
from flask import Blueprint, jsonify, send_file
from log.logger import LoggerUtil

logger = LoggerUtil.get_logger()
reports_bp = Blueprint('reports', __name__)

SCREENSHOTS_DIR = 'data/screenshots'


@reports_bp.route('/api/reports/screenshots/<filename>')
def get_screenshot(filename):
    """获取截图文件"""
    filepath = os.path.join(SCREENSHOTS_DIR, filename)
    if os.path.exists(filepath):
        return send_file(filepath, mimetype='image/png')
    return jsonify({'success': False, 'message': '文件不存在'})


@reports_bp.route('/api/reports/case/<case_id>/report')
def get_case_report(case_id):
    """获取用例的完整报告（包含截图列表）"""
    from cases.case_manager import CaseManager
    cm = CaseManager()
    case = cm.get_case(case_id)
    if not case:
        return jsonify({'success': False, 'message': '用例不存在'})

    screenshots = []
    for sp in case.screenshots:
        if os.path.exists(sp):
            screenshots.append(os.path.basename(sp))

    return jsonify({
        'success': True,
        'data': {
            **case.to_dict(),
            'screenshots': screenshots
        }
    })
