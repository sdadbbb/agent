"""Agent 浏览器工具 - Function Calling 规范与执行函数"""
import base64
import os
from datetime import datetime
from log.logger import LoggerUtil
from browser.snapshot import PageSnapshot

logger = LoggerUtil.get_logger()

# 当前页面对象（由引擎在初始化时设置）
_current_page = None


def set_page(page):
    """设置当前页面对象"""
    global _current_page
    _current_page = page


# ==================== 工具规范 ====================

BROWSER_TOOLS_SPEC = [
    {
        "type": "function",
        "function": {
            "name": "browser_navigate",
            "description": "打开一个URL，导航到指定页面",
            "parameters": {
                "type": "object",
                "properties": {
                    "url": {"type": "string", "description": "要打开的完整URL，如 https://example.com/login"}
                },
                "required": ["url"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "browser_get_page_state",
            "description": "获取当前页面的完整状态，包含URL、标题、可见文本和可交互元素列表",
            "parameters": {
                "type": "object",
                "properties": {}
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "browser_click",
            "description": "点击页面上的某个元素，通过CSS选择器定位",
            "parameters": {
                "type": "object",
                "properties": {
                    "selector": {"type": "string", "description": "CSS选择器，如 #login-btn, button:has-text('登录'), input[name='username']"}
                },
                "required": ["selector"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "browser_fill",
            "description": "在输入框中填入文本（会先清空再填入）",
            "parameters": {
                "type": "object",
                "properties": {
                    "selector": {"type": "string", "description": "CSS选择器"},
                    "text": {"type": "string", "description": "要填入的文本"}
                },
                "required": ["selector", "text"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "browser_get_text",
            "description": "获取页面中指定元素的可见文本",
            "parameters": {
                "type": "object",
                "properties": {
                    "selector": {"type": "string", "description": "CSS选择器"}
                },
                "required": ["selector"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "browser_wait",
            "description": "等待一段时间，用于页面加载或动画完成",
            "parameters": {
                "type": "object",
                "properties": {
                    "ms": {"type": "integer", "description": "等待毫秒数，如 2000 表示等待2秒"}
                },
                "required": ["ms"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "browser_select_option",
            "description": "选择下拉框中的选项",
            "parameters": {
                "type": "object",
                "properties": {
                    "selector": {"type": "string", "description": "下拉框元素的CSS选择器"},
                    "value": {"type": "string", "description": "要选择的值（option的value属性）"}
                },
                "required": ["selector", "value"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "browser_press_key",
            "description": "模拟键盘按键操作",
            "parameters": {
                "type": "object",
                "properties": {
                    "key": {"type": "string", "description": "按键名称，如 Enter, Escape, Tab, ArrowDown"}
                },
                "required": ["key"]
            }
        }
    }
]


# ==================== 工具执行函数 ====================

def _get_page():
    """获取当前页面"""
    if _current_page is None:
        raise RuntimeError("浏览器页面未初始化")
    return _current_page


def _locate_element(page, selector, timeout=10000):
    """3层兜底定位元素：CSS选择器 → 文本匹配 → 语义属性

    返回: (locator, 使用的策略名称) 或 (None, None)
    """
    page.wait_for_load_state('networkidle')

    # 策略列表：去掉 is_css_like 过滤，所有策略都试一遍
    strategies = [
        ('css', selector),
        ('text', f'text={selector}'),
        ('has_text', f':has-text("{selector}")'),
        ('aria_label', f'[aria-label="{selector}"]'),
        ('placeholder', f'[placeholder="{selector}"]'),
        ('alt_text', f'[alt="{selector}"]'),
        ('title', f'[title="{selector}"]'),
        # 包含匹配：LLM 猜"用户名"但页面可能是"请输入用户名"
        ('placeholder_contains', f'[placeholder*="{selector}"]'),
        ('aria_label_contains', f'[aria-label*="{selector}"]'),
        ('alt_contains', f'[alt*="{selector}"]'),
        ('title_contains', f'[title*="{selector}"]'),
    ]

    for name, strategy_selector in strategies:
        try:
            locator = page.locator(strategy_selector)
            if locator.count() > 0:
                first = locator.first
                try:
                    if first.is_visible(timeout=1000):
                        logger.info(f"元素定位成功 [策略={name}]: {strategy_selector}")
                        return first, name
                except Exception:
                    pass
                # 不可见也返回，让 click/fill 自行尝试
                logger.info(f"元素定位成功 [策略={name}, 可能不可见]: {strategy_selector}")
                return first, name
        except Exception:
            continue

    # 第二轮：Playwright 内置智能定位器（按标签文本、角色）
    try:
        label_locator = page.get_by_label(selector)
        if label_locator.count() > 0:
            logger.info(f"元素定位成功 [策略=get_by_label]: {selector}")
            return label_locator.first, 'get_by_label'
    except Exception:
        pass

    try:
        role_locator = page.get_by_role('button', name=selector)
        if role_locator.count() > 0:
            logger.info(f"元素定位成功 [策略=get_by_role]: {selector}")
            return role_locator.first, 'get_by_role'
    except Exception:
        pass

    try:
        alt_locator = page.get_by_alt_text(selector)
        if alt_locator.count() > 0:
            logger.info(f"元素定位成功 [策略=get_by_alt]: {selector}")
            return alt_locator.first, 'get_by_alt'
    except Exception:
        pass

    # 最终兜底：遍历页面 ALL 可见元素，模糊匹配文本
    try:
        all_elements = page.locator('*').all()
        for el in all_elements:
            try:
                if not el.is_visible(timeout=500):
                    continue
                text = (el.inner_text() or '').strip()
                tag = el.evaluate('el => el.tagName.toLowerCase()')
                if text and selector.lower() in text.lower():
                    logger.info(f"元素定位成功 [策略=fuzzy_all]: tag={tag} text='{text[:50]}'")
                    return el, 'fuzzy_all'
            except Exception:
                continue
    except Exception:
        pass

    # 终极兜底：根据选择器推断元素类型，尝试通用定位
    try:
        sel_lower = selector.lower()
        # 推断为输入框
        if any(kw in sel_lower for kw in ['input', 'text', 'username', 'user', 'name', 'account', '账号', '密码', 'password', 'pass']):
            if 'pass' in sel_lower or '密码' in sel_lower:
                for try_sel in ['input[type="password"]', 'input:last-of-type']:
                    loc = page.locator(try_sel)
                    if loc.count() > 0:
                        logger.info(f"元素定位成功 [策略=infer_input_pass]: {try_sel}")
                        return loc.first, 'infer_input_pass'
            else:
                for try_sel in ['input[type="text"]', 'input:first-of-type']:
                    loc = page.locator(try_sel)
                    if loc.count() > 0:
                        logger.info(f"元素定位成功 [策略=infer_input_text]: {try_sel}")
                        return loc.first, 'infer_input_text'
        # 推断为按钮
        if any(kw in sel_lower for kw in ['button', 'btn', 'submit', 'click', '登录', '注册', 'search']):
            for try_sel in ['button', 'input[type="submit"]', '[role="button"]']:
                loc = page.locator(try_sel)
                if loc.count() > 0:
                    logger.info(f"元素定位成功 [策略=infer_button]: {try_sel}")
                    return loc.first, 'infer_button'
        # 推断为链接
        if any(kw in sel_lower for kw in ['a[href]', 'link', 'a:has-text']):
            loc = page.locator('a[href]')
            if loc.count() > 0:
                logger.info(f"元素定位成功 [策略=infer_link]: a[href]")
                return loc.first, 'infer_link'
    except Exception:
        pass

    logger.warning(f"元素定位失败，所有策略均无效: {selector}")
    return None, None


def execute_browser_navigate(args):
    """导航到URL"""
    try:
        page = _get_page()
        url = args['url']
        logger.info(f"导航到: {url}")
        page.goto(url, timeout=30000, wait_until='networkidle')
        snapshot = PageSnapshot(page)
        state = snapshot.get_page_state()
        logger.info(f"导航成功: {state.get('title', '')} - {url}")
        return {
            'success': True,
            'result': {
                'url': state['url'],
                'title': state['title'],
                'visible_text': state['visible_text'][:500],
                'interactive_elements': state['interactive_elements'][:15]
            }
        }
    except Exception as e:
        logger.error(f"导航失败: {str(e)}")
        return {'success': False, 'error': f"导航失败: {str(e)}"}


def execute_browser_get_page_state(args):
    """获取页面状态"""
    try:
        page = _get_page()
        snapshot = PageSnapshot(page)
        state = snapshot.get_page_state()
        logger.info(f"页面状态: {state.get('title', '')} - {state.get('url', '')}")
        return {
            'success': True,
            'result': {
                'url': state['url'],
                'title': state['title'],
                'visible_text': state['visible_text'][:1000],
                'interactive_elements': state['interactive_elements']
            }
        }
    except Exception as e:
        logger.error(f"获取页面状态失败: {str(e)}")
        return {'success': False, 'error': f"获取页面状态失败: {str(e)}"}


def execute_browser_click(args):
    """点击元素（3层兜底定位 + 3层点击策略）"""
    try:
        page = _get_page()
        selector = args['selector']
        logger.info(f"点击元素: {selector}")

        locator, strategy = _locate_element(page, selector)
        if locator is None:
            return {'success': False, 'error': f'无法定位元素: {selector}'}

        # 四级点击兜底
        # 点击前尝试滚动到可视区域
        try:
            locator.scroll_into_view_if_needed(timeout=3000)
            page.wait_for_timeout(300)
        except Exception:
            pass

        # 1. 标准点击
        try:
            locator.click(timeout=3000)
            click_success = True
        except Exception as e1:
            logger.warning(f"标准点击失败: {selector} - {e1}, 尝试强制点击...")
            # 2. 强制点击（绕过可见性/重叠检查）
            try:
                locator.click(force=True, timeout=3000)
                click_success = True
            except Exception as e2:
                logger.warning(f"强制点击失败: {selector} - {e2}, 尝试 dispatchEvent...")
                # 3. Playwright dispatchEvent（绕过可见性检查）
                try:
                    locator.dispatch_event('click')
                    click_success = True
                except Exception as e3:
                    logger.warning(f"dispatchEvent 失败: {selector} - {e3}, 尝试原生DOM点击...")
                    # 4. 原生 DOM 点击（最终兜底，绕过一切检查）
                    try:
                        locator.evaluate('''el => {
                            el.scrollIntoView({block: "center"});
                            el.focus();
                            const r = el.getBoundingClientRect();
                            const cx = r.left + r.width/2, cy = r.top + r.height/2;
                            el.dispatchEvent(new PointerEvent("pointerdown", {bubbles: true, clientX: cx, clientY: cy}));
                            el.dispatchEvent(new PointerEvent("pointerup", {bubbles: true, clientX: cx, clientY: cy}));
                            el.dispatchEvent(new MouseEvent("click", {bubbles: true, cancelable: true, clientX: cx, clientY: cy}));
                        }''')
                        page.wait_for_timeout(500)
                        click_success = True
                    except Exception as e4:
                        return {'success': False, 'error': f'四级点击全部失败: {e4}'}

        logger.info(f"点击成功: {selector} [策略={strategy}]")
        return {'success': True, 'result': f"已点击元素: {selector} [策略={strategy}]"}
    except Exception as e:
        logger.error(f"点击失败: {selector} - {str(e)}")
        return {'success': False, 'error': f"点击失败: {str(e)}"}


def execute_browser_fill(args):
    """填入文本（3层兜底定位）"""
    try:
        page = _get_page()
        selector = args['selector']
        text = args['text']
        logger.info(f"填入文本: {selector} = {text}")

        locator, strategy = _locate_element(page, selector)
        if locator is None:
            return {'success': False, 'error': f'无法定位输入框: {selector}'}

        locator.fill(text)
        logger.info(f"填入成功: {selector} [策略={strategy}]")
        return {'success': True, 'result': f"已填入文本: {text} [策略={strategy}]"}
    except Exception as e:
        logger.error(f"填入文本失败: {selector} - {str(e)}")
        return {'success': False, 'error': f"填入文本失败: {str(e)}"}


def execute_browser_get_text(args):
    """获取元素文本（3层兜底定位）"""
    try:
        page = _get_page()
        selector = args['selector']

        locator, strategy = _locate_element(page, selector)
        if locator is None:
            return {'success': False, 'error': f'无法定位元素: {selector}'}

        text = locator.inner_text()
        logger.info(f"获取文本: {selector} => {text[:100]} [策略={strategy}]")
        return {'success': True, 'result': text[:500]}
    except Exception as e:
        logger.error(f"获取文本失败: {selector} - {str(e)}")
        return {'success': False, 'error': f"获取文本失败: {str(e)}"}


def execute_browser_screenshot(args):
    """截图并保存文件，返回base64"""
    try:
        page = _get_page()
        logger.info(f"截图: {page.url}")

        # 保存截图文件
        ts = datetime.now().strftime('%Y%m%d_%H%M%S')
        os.makedirs('data/screenshots', exist_ok=True)
        filepath = f'data/screenshots/{ts}.png'
        page.screenshot(path=filepath)

        # 返回 base64 用于前端显示
        screenshot_bytes = page.screenshot(type='png', full_page=False)
        b64 = base64.b64encode(screenshot_bytes).decode('utf-8')
        return {
            'success': True,
            'result': {
                'type': 'image_base64',
                'data': b64,
                'description': f"当前页面截图 ({page.url})"
            },
            'screenshot_path': filepath
        }
    except Exception as e:
        logger.error(f"截图失败: {str(e)}")
        return {'success': False, 'error': f"截图失败: {str(e)}"}


def execute_browser_wait(args):
    """等待"""
    try:
        page = _get_page()
        ms = args.get('ms', 1000)
        logger.info(f"等待: {ms}ms")
        page.wait_for_timeout(ms)
        return {'success': True, 'result': f"已等待 {ms}ms"}
    except Exception as e:
        logger.error(f"等待失败: {str(e)}")
        return {'success': False, 'error': str(e)}


def execute_browser_select_option(args):
    """选择下拉框"""
    try:
        page = _get_page()
        selector = args['selector']
        value = args['value']
        logger.info(f"选择下拉框: {selector} = {value}")
        page.select_option(selector, value)
        return {'success': True, 'result': f"已选择选项: {value}"}
    except Exception as e:
        logger.error(f"选择失败: {selector} - {str(e)}")
        return {'success': False, 'error': f"选择失败: {str(e)}"}


def execute_browser_press_key(args):
    """键盘按键"""
    try:
        page = _get_page()
        key = args['key']
        logger.info(f"按键: {key}")
        page.keyboard.press(key)
        return {'success': True, 'result': f"已按键: {key}"}
    except Exception as e:
        logger.error(f"按键失败: {key} - {str(e)}")
        return {'success': False, 'error': f"按键失败: {str(e)}"}


# ==================== 执行器映射 ====================

BROWSER_TOOL_EXECUTORS = {
    'browser_navigate': execute_browser_navigate,
    'browser_get_page_state': execute_browser_get_page_state,
    'browser_click': execute_browser_click,
    'browser_fill': execute_browser_fill,
    'browser_get_text': execute_browser_get_text,
    'browser_screenshot': execute_browser_screenshot,
    'browser_wait': execute_browser_wait,
    'browser_select_option': execute_browser_select_option,
    'browser_press_key': execute_browser_press_key,
}
