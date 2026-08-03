"""Agent 浏览器工具 - Function Calling 规范与执行函数"""
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


def _find_visible_in_locator(locator, max_check=20):
    """遍历 locator 的所有匹配，返回第一个可见元素"""
    count = locator.count()
    for i in range(min(count, max_check)):
        el = locator.nth(i)
        try:
            if el.is_visible(timeout=300):
                return el
        except Exception:
            continue
    return None


def _try_css_round(page, selector):
    """第一轮：CSS 选择器策略（精确 → 包含 → 文本兜底）"""
    strategies = [
        # 精确匹配优先
        ('css', selector),
        ('aria_label', f'[aria-label="{selector}"]'),
        ('placeholder', f'[placeholder="{selector}"]'),
        ('alt_text', f'[alt="{selector}"]'),
        ('title', f'[title="{selector}"]'),
        # 包含匹配
        ('aria_label_contains', f'[aria-label*="{selector}"]'),
        ('placeholder_contains', f'[placeholder*="{selector}"]'),
        ('alt_contains', f'[alt*="{selector}"]'),
        ('title_contains', f'[title*="{selector}"]'),
        # 非标准输入框兜底：div 充当 input（contenteditable / role=textbox）
        ('contenteditable', '[contenteditable="true"]'),
        ('aria_role_textbox', '[role="textbox"]'),
        # 文本匹配兜底（最宽泛，放最后）
        ('text', f'text={selector}'),
        ('has_text', f':has-text("{selector}")'),
    ]
    # 去标签化：input[name='wd'] → [name='wd']（匹配 div 伪装的输入框）
    if '[' in selector:
        bracket = selector.index('[')
        prefix = selector[:bracket].strip()
        if prefix and prefix.replace('-', '').isalpha():
            strategies.insert(-2, ('tagless', selector[bracket:]))
    for name, s in strategies:
        try:
            locator = page.locator(s)
            if locator.count() > 0:
                visible = _find_visible_in_locator(locator)
                if visible:
                    return visible, name
                return locator.first, name
        except Exception:
            continue
    return None, None


# def _try_pw_round(page, selector):
#     """第二轮：Playwright 内置智能定位器（仅当 selector 为纯文本时有效）"""
#     # CSS/XPath 选择器不适用 Playwright 文本定位器，直接跳过
#     if any(c in selector for c in ('[', '#', '.', ':', '/')):
#         return None, None

#     pw_strategies = [
#         ('get_by_label', lambda: page.get_by_label(selector)),
#         ('get_by_text', lambda: page.get_by_text(selector)),
#         ('get_by_placeholder', lambda: page.get_by_placeholder(selector)),
#         ('get_by_alt_text', lambda: page.get_by_alt_text(selector)),
#     ]
#     # get_by_role：尝试多种常见 role，name 用 selector 作为可访问名称
#     for role in ['button', 'link', 'textbox', 'checkbox', 'combobox', 'option', 'menuitem', 'listitem']:
#         pw_strategies.append(
#             (f'get_by_role_{role}', lambda r=role: page.get_by_role(r, name=selector))
#         )
#     for name, factory in pw_strategies:
#         try:
#             locator = factory()
#             if locator.count() > 0:
#                 visible = _find_visible_in_locator(locator)
#                 if visible:
#                     return visible, name
#                 return locator.first, name
#         except Exception:
#             continue
#     return None, None


def _try_fuzzy_round(page, selector):
    """第三轮：遍历所有可见元素，模糊文本匹配（限制遍历数量防卡死）"""
    try:
        all_elements = page.locator('*').all()
        # 限制遍历数量，防止大页面卡死
        element_limit = 200
        checked = 0
        for el in all_elements:
            if checked >= element_limit:
                break
            checked += 1
            try:
                if not el.is_visible(timeout=200):
                    continue
                text = (el.inner_text() or '').strip()
                if text and selector.lower() in text.lower():
                    return el, 'fuzzy_all'
            except Exception:
                continue
    except Exception:
        pass
    return None, None


def _try_infer_round(page, selector):
    """第四轮：根据选择器语义推断元素类型"""
    try:
        sel_lower = selector.lower()
        # 用正则做词边界匹配，避免 'pass' 匹配到 'bypass'/'passport'
        is_password = any(kw in sel_lower for kw in ['password', '密码'])
        if not is_password:
            import re
            is_password = bool(re.search(r'\bpass\b', sel_lower))
        if any(kw in sel_lower for kw in ['input', 'text', 'username', 'user', 'name', 'account', '账号', 'password', '密码']) or is_password:
            if is_password:
                for try_sel in ['input[type="password"]', 'input:last-of-type']:
                    loc = page.locator(try_sel)
                    if loc.count() > 0:
                        return loc.first, 'infer_input_pass'
            else:
                for try_sel in ['input[type="text"]', 'input:first-of-type']:
                    loc = page.locator(try_sel)
                    if loc.count() > 0:
                        return loc.first, 'infer_input_text'
        if any(kw in sel_lower for kw in ['button', 'btn', 'submit', 'click', '登录', '注册', 'search']):
            for try_sel in ['button', 'input[type="submit"]', '[role="button"]']:
                loc = page.locator(try_sel)
                if loc.count() > 0:
                    return loc.first, 'infer_button'
        if any(kw in sel_lower for kw in ['a[href]', 'link', 'a:has-text']):
            loc = page.locator('a[href]')
            if loc.count() > 0:
                return loc.first, 'infer_link'
    except Exception:
        pass
    return None, None



# 有序的定位轮次
_ROUNDS = [
    ('css', _try_css_round),
    ('fuzzy', _try_fuzzy_round),
    ('infer', _try_infer_round),
]


def _locate_element(page, selector, timeout=10000):
    """一次调用返回所有三轮定位的候选元素列表
    
    返回: [(locator, strategy_name), ...]  非空列表，调用方依此尝试
    """
    candidates = []
    for _, try_fn in _ROUNDS:
        result = try_fn(page, selector)
        if result is not None:
            candidates.append(result)
    if not candidates:
        logger.warning(f"元素定位失败，所有策略均无效: {selector}")
    return candidates


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
    """点击元素（4轮定位 × 4级点击兜底）"""
    try:
        page = _get_page()
        selector = args['selector']
        logger.info(f"点击元素: {selector}")

        candidates = _locate_element(page, selector)
        if not candidates:
            return {'success': False, 'error': f'无法定位元素: {selector}'}

        # 对每个候选依次尝试四级点击
        for locator, strategy in candidates:
            try:
                locator.scroll_into_view_if_needed(timeout=3000)
                page.wait_for_timeout(300)
            except Exception:
                pass

            # 1. 标准点击
            try:
                locator.click(timeout=3000)
                logger.info(f"点击成功: {selector} [策略={strategy}]")
                return {'success': True, 'result': f"已点击元素: {selector} [策略={strategy}]"}
            except Exception:
                pass

            # 2. 强制点击
            try:
                locator.click(force=True, timeout=3000)
                logger.info(f"点击成功: {selector} [策略={strategy}]")
                return {'success': True, 'result': f"已点击元素: {selector} [策略={strategy}]"}
            except Exception:
                pass

            # 3. dispatchEvent
            try:
                locator.dispatch_event('click')
                page.wait_for_timeout(300)
                logger.info(f"点击成功: {selector} [策略={strategy}]")
                return {'success': True, 'result': f"已点击元素: {selector} [策略={strategy}]"}
            except Exception:
                pass

            # 4. 原生 DOM 点击（最终兜底）
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
                logger.info(f"点击成功: {selector} [策略={strategy}]")
                return {'success': True, 'result': f"已点击元素: {selector} [策略={strategy}]"}
            except Exception:
                pass

        return {'success': False, 'error': f'所有定位策略点击均失败: {selector}'}
    except Exception as e:
        logger.error(f"点击失败: {args.get('selector', '?')} - {str(e)}")
        return {'success': False, 'error': f"点击失败: {str(e)}"}


def execute_browser_fill(args):
    """填入文本（遍历所有候选定位器）"""
    try:
        page = _get_page()
        selector = args['selector']
        text = args['text']
        logger.info(f"填入文本: {selector} = {text}")

        candidates = _locate_element(page, selector)
        if not candidates:
            return {'success': False, 'error': f'无法定位输入框: {selector}'}

        for locator, strategy in candidates:
            try:
                locator.fill(text)
                logger.info(f"填入成功: {selector} [策略={strategy}]")
                return {'success': True, 'result': f"已填入文本: {text} [策略={strategy}]"}
            except Exception:
                continue

        return {'success': False, 'error': f'所有定位策略填入均失败: {selector}'}
    except Exception as e:
        logger.error(f"填入文本失败: {args.get('selector', '?')} - {str(e)}")
        return {'success': False, 'error': f"填入文本失败: {str(e)}"}


def execute_browser_get_text(args):
    """获取元素文本（遍历所有候选定位器）"""
    try:
        page = _get_page()
        selector = args['selector']

        candidates = _locate_element(page, selector)
        if not candidates:
            return {'success': False, 'error': f'无法定位元素: {selector}'}

        for locator, strategy in candidates:
            try:
                text = locator.inner_text()
                logger.info(f"获取文本: {selector} => {text[:100]} [策略={strategy}]")
                return {'success': True, 'result': text[:500], 'strategy': strategy}
            except Exception:
                continue

        return {'success': False, 'error': f'所有定位策略获取文本均失败: {selector}'}
    except Exception as e:
        logger.error(f"获取文本失败: {args.get('selector', '?')} - {str(e)}")
        return {'success': False, 'error': f"获取文本失败: {str(e)}"}


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
    """选择下拉框（走4轮定位回退）"""
    try:
        page = _get_page()
        selector = args.get('selector', '')
        value = args['value']
        logger.info(f"选择下拉框: {selector} = {value}")

        candidates = _locate_element(page, selector)
        if not candidates:
            # 回退：直接使用原始 selector
            try:
                page.select_option(selector, value)
                return {'success': True, 'result': f"已选择选项: {value}"}
            except Exception as e:
                return {'success': False, 'error': f'无法定位下拉框且直接选择失败: {str(e)}'}

        for locator, strategy in candidates:
            try:
                # Playwright 的 select_option 需要 select 元素上的 locator
                locator.select_option(value)
                return {'success': True, 'result': f"已选择选项: {value} [策略={strategy}]"}
            except Exception:
                continue

        return {'success': False, 'error': f'所有定位策略选择均失败: {selector}'}
    except Exception as e:
        logger.error(f"选择失败: {args.get('selector', '?')} - {str(e)}")
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
    # 'browser_screenshot': execute_browser_screenshot,
    'browser_wait': execute_browser_wait,
    'browser_select_option': execute_browser_select_option,
    'browser_press_key': execute_browser_press_key,
}
