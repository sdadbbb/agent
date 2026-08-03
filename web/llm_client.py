"""大模型客户端 - 兼容 OpenAI Chat Completions API"""
import json
import time
import requests
from log.logger import LoggerUtil

logger = LoggerUtil.get_logger()


class LLMClient:
    """大模型客户端"""

    def __init__(self, config):
        self.api_key = config.get('api_key', '')
        self.base_url = config.get('base_url', 'https://api.openai.com').rstrip('/')
        self.model = config.get('model', 'gpt-4o-mini')
        self.timeout = config.get('timeout', 120)
        self.max_tokens = config.get('max_tokens')
        self.temperature = config.get('temperature', 0.3)
        self.max_retries = 3

    def is_configured(self):
        return bool(self.api_key)

    def _build_payload(self, messages, tools=None, temperature=None):
        """构建请求 payload，兼容 DeepSeek 等不同 API"""
        payload = {
            'model': self.model,
            'messages': messages,
            'temperature': temperature if temperature is not None else self.temperature,
        }
        # 只有 max_tokens 不为 None 且不为 0 时才加入
        if self.max_tokens:
            payload['max_tokens'] = self.max_tokens
        # 如果有工具，加入工具定义
        if tools:
            payload['tools'] = tools
            # 不传 tool_choice，让 API 自动决定
            # 某些 API（如 DeepSeek）不支持显式设置 tool_choice
        return payload

    def _request(self, payload):
        """发送请求并处理错误"""
        url = f"{self.base_url}/chat/completions"
        headers = {
            'Authorization': f'Bearer {self.api_key}',
            'Content-Type': 'application/json'
        }
        logger.info(f"请求模型: {self.model}, 消息数: {len(payload.get('messages', []))}, 工具数: {len(payload.get('tools', [])) if payload.get('tools') else 0}")

        try:
            resp = requests.post(url, headers=headers, json=payload, timeout=self.timeout)
            resp.raise_for_status()
            return resp.json()
        except requests.exceptions.HTTPError as e:
            status_code = e.response.status_code
            try:
                error_body = e.response.text
            except Exception:
                error_body = '无法读取响应体'
            logger.error(f"API 请求失败 [HTTP {status_code}]: {error_body}")
            logger.error(f"请求 payload: {json.dumps(payload, ensure_ascii=False)[:2000]}")
            raise Exception(f"API 返回错误 [HTTP {status_code}]: {error_body}")
        except requests.exceptions.Timeout:
            logger.error(f"API 请求超时 (timeout={self.timeout}s)")
            raise Exception(f"API 请求超时，请检查网络连接或增大 timeout 配置")
        except requests.exceptions.ConnectionError as e:
            logger.error(f"API 连接失败: {str(e)}")
            raise Exception(f"无法连接到 {self.base_url}，请检查 base_url 配置")

    def chat(self, messages, temperature=None):
        """普通对话（含重试）"""
        if not self.is_configured():
            raise ValueError('请在 config/config.yml 中配置 llm.api_key')
        payload = self._build_payload(messages, temperature=temperature)
        last_error = None
        for attempt in range(self.max_retries):
            try:
                data = self._request(payload)
                content = data['choices'][0]['message']['content']
                logger.info(f"回复长度: {len(content)} 字符")
                return content
            except Exception as e:
                last_error = e
                if attempt < self.max_retries - 1:
                    wait = 2 ** attempt
                    logger.warning(f"LLM 请求失败（第{attempt+1}次），{wait}s 后重试: {str(e)[:100]}")
                    time.sleep(wait)
        raise last_error

    def chat_with_tools(self, messages, tools=None, temperature=None):
        """带工具调用的对话"""
        if not self.is_configured():
            raise ValueError('请在 config/config.yml 中配置 llm.api_key')
        payload = self._build_payload(messages, tools=tools, temperature=temperature)
        data = self._request(payload)
        logger.info(data)
        choice = data['choices'][0]
        message = choice['message']

        result = {
            'content': message.get('content'),
            'tool_calls': message.get('tool_calls', []),
            'raw_response': data
        }

        if result['tool_calls']:
            logger.info(f"LLM 调用了 {len(result['tool_calls'])} 个工具")
            for tc in result['tool_calls']:
                logger.info(f"  工具: {tc['function']['name']}")
        else:
            logger.info(f"LLM 直接回复文本, 长度: {len(result.get('content', ''))} 字符")

        return result
