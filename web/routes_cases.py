"""测试用例管理 API"""
from flask import Blueprint, request, jsonify
from log.logger import LoggerUtil
from cases.case_manager import CaseManager
from cases.exporter import CaseExporter

logger = LoggerUtil.get_logger()
cases_bp = Blueprint('cases', __name__)
case_manager = CaseManager()
case_exporter = CaseExporter()


@cases_bp.route('/api/cases', methods=['GET'])
def list_cases():
    """分页查询用例列表"""
    page = request.args.get('page', 1, type=int)
    page_size = request.args.get('page_size', 10, type=int)
    keyword = request.args.get('keyword', '').strip()
    status = request.args.get('status', '').strip()
    result = case_manager.list_cases(page=page, page_size=page_size, keyword=keyword, status=status)
    return jsonify({'success': True, 'data': result})


@cases_bp.route('/api/cases/<case_id>', methods=['GET'])
def get_case(case_id):
    """获取用例详情"""
    case = case_manager.get_case(case_id)
    if case:
        return jsonify({'success': True, 'data': case.to_dict()})
    return jsonify({'success': False, 'message': '用例不存在'})


@cases_bp.route('/api/cases/<case_id>', methods=['DELETE'])
def delete_case(case_id):
    """删除用例"""
    if case_manager.delete_case(case_id):
        return jsonify({'success': True, 'message': '删除成功'})
    return jsonify({'success': False, 'message': '删除失败'})


@cases_bp.route('/api/cases/<case_id>', methods=['PUT'])
def update_case(case_id):
    """更新用例"""
    data = request.get_json() or {}
    case = case_manager.get_case(case_id)
    if not case:
        return jsonify({'success': False, 'message': '用例不存在'})
    if 'tags' in data:
        case.tags = data['tags']
    if 'description' in data:
        case.description = data['description']
    case_manager.save_case(case)
    return jsonify({'success': True, 'data': case.to_dict()})


@cases_bp.route('/api/cases/export/<case_id>', methods=['GET'])
def export_case(case_id):
    """导出用例"""
    fmt = request.args.get('format', 'csv')
    if fmt == 'xlsx':
        filepath, filename = case_exporter.export_to_xlsx(case_id)
    else:
        filepath, filename = case_exporter.export_to_csv(case_id)
    if filepath:
        return jsonify({'success': True, 'filename': filename})
    return jsonify({'success': False, 'message': filename})


@cases_bp.route('/api/stats/overview', methods=['GET'])
def stats_overview():
    """统计概览"""
    stats = case_manager.get_stats()
    return jsonify({'success': True, 'data': stats})
