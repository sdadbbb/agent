"""文件管理 API"""
import os
from flask import Blueprint, send_file, jsonify, abort
from log.logger import LoggerUtil
from cases.exporter import CaseExporter

logger = LoggerUtil.get_logger()
files_bp = Blueprint('files', __name__)
case_exporter = CaseExporter()

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SCREENSHOTS_DIR = os.path.join(BASE_DIR, 'data', 'screenshots')


@files_bp.route('/api/files/screenshots/<filename>', methods=['GET'])
def serve_screenshot(filename):
    """提供截图文件访问"""
    filepath = os.path.join(SCREENSHOTS_DIR, filename)
    logger.info(f"截图请求: {filename} -> {filepath}")
    if os.path.exists(filepath):
        return send_file(filepath, mimetype='image/png')
    logger.warning(f"截图文件不存在: {filepath}")
    abort(404)


@files_bp.route('/api/exports', methods=['GET'])
def list_exports():
    """列出导出文件"""
    files = case_exporter.list_exports()
    return jsonify({'success': True, 'data': files})


@files_bp.route('/api/exports/<filename>', methods=['GET'])
def download_export(filename):
    """下载导出文件"""
    filepath = os.path.join(case_exporter.export_dir, filename)
    if os.path.exists(filepath):
        return send_file(filepath, as_attachment=True, download_name=filename)
    return jsonify({'success': False, 'message': '文件不存在'})


@files_bp.route('/api/exports/<filename>', methods=['DELETE'])
def delete_export(filename):
    """删除导出文件"""
    if case_exporter.delete_export(filename):
        return jsonify({'success': True, 'message': '删除成功'})
    return jsonify({'success': False, 'message': '删除失败'})
