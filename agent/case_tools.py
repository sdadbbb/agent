"""Agent 用例管理工具 - 保存执行结果与查询历史"""
from log.logger import LoggerUtil
from cases.case_manager import CaseManager
from cases.case_models import TestCase, ReportResult

logger = LoggerUtil.get_logger()
case_manager = CaseManager()


CASE_TOOLS_SPEC = [
    {
        "type": "function",
        "function": {
            "name": "save_test_result",
            "description": "保存当前的测试执行结果到用例库，包含执行步骤和截图",
            "parameters": {
                "type": "object",
                "properties": {
                    "case_name": {"type": "string", "description": "测试用例名称"},
                    "description": {"type": "string", "description": "测试用例描述"},
                    "task": {"type": "string", "description": "原始测试任务"},
                    "passed": {"type": "boolean", "description": "测试是否通过"},
                    "steps_summary": {"type": "string", "description": "执行步骤摘要，每步一行"},
                    "conclusion": {"type": "string", "description": "测试结论"}
                },
                "required": ["case_name", "passed", "steps_summary", "conclusion"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "query_test_history",
            "description": "查询历史测试执行记录",
            "parameters": {
                "type": "object",
                "properties": {
                    "keyword": {"type": "string", "description": "搜索关键字（可选）"},
                    "page": {"type": "integer", "description": "页码，默认1"},
                    "page_size": {"type": "integer", "description": "每页条数，默认10"}
                }
            }
        }
    }
]


def execute_save_test_result(args):
    """保存测试结果"""
    try:
        # 1. 保存用例（含执行步骤摘要）
        case = TestCase(
            name=args['case_name'],
            description=args.get('description', ''),
            task=args.get('task', ''),
            steps_log=[{'action': args.get('steps_summary', ''), 'result': {'success': args['passed']}}],
        )
        saved = case_manager.save_case(case)

        # 2. 保存报告结果
        report = ReportResult(
            case_id=saved.id,
            passed=args['passed'],
            conclusion=args.get('conclusion', ''),
        )
        case_manager.save_result(report)

        logger.info(f"测试结果已保存: {saved.name} ({saved.id}) - {'通过' if args['passed'] else '失败'}")
        return {
            'success': True,
            'result': {
                'case_id': saved.id,
                'case_name': saved.name,
                'passed': args['passed'],
                'message': f'测试结果已保存: {saved.name} (ID: {saved.id})'
            }
        }
    except Exception as e:
        logger.error(f"保存测试结果失败: {str(e)}")
        return {'success': False, 'error': f"保存失败: {str(e)}"}


def execute_query_test_history(args):
    """查询历史"""
    try:
        keyword = args.get('keyword', '')
        page = args.get('page', 1)
        page_size = args.get('page_size', 10)
        logger.info(f"查询历史: keyword={keyword}, page={page}, page_size={page_size}")
        result = case_manager.list_cases(page=page, page_size=page_size, keyword=keyword)
        logger.info(f"查询结果: 共 {result.get('total', 0)} 条")
        return {'success': True, 'result': result}
    except Exception as e:
        logger.error(f"查询历史失败: {str(e)}")
        return {'success': False, 'error': str(e)}


CASE_TOOL_EXECUTORS = {
    'save_test_result': execute_save_test_result,
    'query_test_history': execute_query_test_history,
}
