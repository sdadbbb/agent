"""Agent 执行相关 API"""
import json
import queue
import threading
from flask import Blueprint, request, jsonify, Response, stream_with_context
from log.logger import LoggerUtil
from web.llm_client import LLMClient
from agent.engine import AgentEngine

logger = LoggerUtil.get_logger()
agent_bp = Blueprint('agent', __name__)

# 存储正在运行的 Agent 任务
_active_tasks = {}
_task_queues = {}


def _create_llm_client():
    """创建LLM客户端"""
    from util.file_util import FileUtil
    config = FileUtil.read_yaml(FileUtil.get_config_path())
    llm_config = config.get('llm', {})
    return LLMClient(llm_config)


@agent_bp.route('/api/agent/execute', methods=['POST'])
def execute_agent():
    """启动 Agent 执行"""
    data = request.get_json() or {}
    task = data.get('task', '').strip()
    case_name = data.get('case_name', '').strip()
    if not task:
        return jsonify({'success': False, 'message': '请输入测试任务描述'})

    try:
        llm_client = _create_llm_client()
        engine = AgentEngine(llm_client)
        task_id = f'task_{__import__("datetime").datetime.now().strftime("%Y%m%d%H%M%S%f")}'

        # 创建队列用于 SSE 通信
        msg_queue = queue.Queue()
        _task_queues[task_id] = msg_queue
        _active_tasks[task_id] = engine

        def on_step(data):
            msg_queue.put(data)

        engine.set_callback(on_step)

        # 在后台线程执行
        def run():
            try:
                result = engine.execute(task, case_name=case_name)
                msg_queue.put({'type': 'complete', 'data': result})
            except Exception as e:
                msg_queue.put({'type': 'error', 'data': str(e)})
            finally:
                msg_queue.put({'type': 'done'})

        thread = threading.Thread(target=run, daemon=True)
        thread.start()

        return jsonify({'success': True, 'task_id': task_id})

    except Exception as e:
        return jsonify({'success': False, 'message': f'启动失败: {str(e)}'})


@agent_bp.route('/api/agent/stream/<task_id>')
def stream_agent(task_id):
    """SSE 流式推送 Agent 执行过程"""
    msg_queue = _task_queues.get(task_id)
    if not msg_queue:
        return jsonify({'success': False, 'message': '任务不存在'})

    def generate():
        while True:
            try:
                data = msg_queue.get(timeout=15)
                if data.get('type') == 'done':
                    break
                yield f"data: {json.dumps(data, ensure_ascii=False)}\n\n"
            except queue.Empty:
                # 心跳保持连接
                yield f"data: {json.dumps({'type': 'heartbeat'})}\n\n"

        # 清理
        _task_queues.pop(task_id, None)
        _active_tasks.pop(task_id, None)

    return Response(
        stream_with_context(generate()),
        mimetype='text/event-stream',
        headers={
            'Cache-Control': 'no-cache',
            'X-Accel-Buffering': 'no'
        }
    )


@agent_bp.route('/api/agent/stop/<task_id>', methods=['POST'])
def stop_agent(task_id):
    """停止 Agent 执行"""
    engine = _active_tasks.get(task_id)
    if engine:
        engine.stop()
        return jsonify({'success': True, 'message': '已发送停止信号'})
    return jsonify({'success': False, 'message': '任务不存在或已结束'})
