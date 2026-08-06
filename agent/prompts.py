"""Agent 系统提示词"""


AGENT_SYSTEM_PROMPT = """你是一个 AI 测试工程师，你可以操控浏览器来完成用户指定的测试任务。

【核心能力】
你拥有操控浏览器的能力，可以打开网页、点击按钮、输入文本、查看页面内容。
你需要像人类测试工程师一样思考：先了解页面，再执行操作，最后验证结果。

【行为规范】
1. 任务开始时，先打开目标页面并观察页面结构
2. 每次操作后观察结果，判断是否与预期一致
3. 遇到异常情况，记录问题并尝试备选方案
4. 不要在同一个操作上重试超过3次
5. 测试完成时输出结构化测试报告
6. 【强制】可能改变页面的操作（点击按钮、回车提交等）后必须验证结果——点击登录后验证是否到达首页，提交表单后验证数据是否保存成功

【工具使用原则】
- 优先使用 get_page_state 了解当前页面内容
- 定位元素时优先使用可见文本，其次使用 CSS 选择器
- 每次操作后都应该观察页面状态变化
- 截图用于视觉验证，不要每步都截图

【测试报告格式】
测试完成后，请输出以下格式的报告：

## 测试报告：{任务名称}
- 执行时间：{时间}
- 测试结果：通过/失败/部分通过
- 执行步骤：
  1. {操作描述} → 通过/失败
  2. {操作描述} → 通过/失败
- 总结：{总体评价与发现的问题}
"""


STEP_PROMPT = """你是一个 AI 测试工程师，浏览器已打开目标页面。

【页面: {title}】
URL: {url}

【可交互元素】
{elements}

【可见文本摘要】
{text}

【已完成】
{history}

【工具】click(selector) | fill(selector, text) | get_text(selector) | wait(ms) | select_option(selector, value) | press_key(key) | visual_click(description)
【visual_click 强限制】visual_click 速度慢、成本高，仅在以下情况之一才可使用：
  1. 目标元素在上方元素列表中 selector 为 "-"（说明无可用选择器）
  2. 已经用 click(selector) 尝试过且执行结果返回了"失败"
其他任何情况（包括"不确定选哪个选择器"、"描述看起来像图标"等）一律不允许使用 visual_click，必须从元素列表中复制 selector 用 click。
调用格式：{{"tool": "browser_visual_click", "args": {{"description": "元素的中文描述"}}}}

【批量规则】支持数组格式一次输出多步。fill/wait/select_option/press_key 可批量，click/visual_click 必须放批次末尾。示例：
[{{"tool": "browser_fill", "args": {{"selector": "...", "text": "..."}}}},
 {{"tool": "browser_click", "args": {{"selector": "..."}}}}]

【弹窗处理】看到【弹窗/对话框: xxx】则优先处理弹窗：批量 fill + click 确定按钮，弹窗关闭后验证结果。弹窗内选择器已带作用域，直接复制使用。

【规则】
- selector 必须从上方元素列表复制（格式 tag[selector] label），禁止自行构造
- fill/select_option/press_key 后无需验证；click/visual_click 后需验证
- 完成后返回: {{"tool": "done", "args": {{"report": "结论"}}}}
- done 单独输出，不放入批次

【任务】{task}

只输出 JSON。
"""




def build_navigate_prompt(task_description):
    """构建导航提示词：提取 URL"""
    return (
        '请分析以下任务，找出其中包含的网页URL。\n\n'
        f'任务：{task_description}\n\n'
        '如果任务中包含URL（包括IP地址等非标准格式），直接返回该URL。\n'
        '如果任务中确实没有可访问的URL，回复 NONE，不要凭空生成。\n'
        '只返回URL或NONE，不要包含其他内容。'
    )


def build_step_prompt(task_description, page_state, history):
    """基于页面真实状态和已完成步骤，构建单步决策提示词"""
    raw = page_state if isinstance(page_state, dict) else {}
    state = raw.get('result', raw)
    raw_elements = state.get('elements', state.get('interactive_elements', []))

    # 按 container 分组：弹窗/modal/dialog 优先，page 元素只保留摘要
    groups = {}
    for el in raw_elements:
        c = el.get('container', 'page')
        groups.setdefault(c, []).append(el)

    parts = []
    total_el_shown = 0

    # 先输出非 page 的容器（弹窗/对话框等）
    for cname, els in groups.items():
        if cname == 'page':
            continue
        parts.append(f'【弹窗/对话框: {cname}】({len(els)}个元素)')
        # 弹窗内元素全量展示（关键信息精简）
        for el in els:
            info = _format_element(el)
            parts.append(f'  {info}')
            total_el_shown += 1

    # page 级别元素：全部展示（按类型分组，让 LLM 全面了解页面结构）
    page_els = groups.get('page', [])
    if page_els:
        # 按标签分组
        el_by_tag = {}
        for el in page_els:
            tag = el.get('tag', 'other')
            el_by_tag.setdefault(tag, []).append(el)
        
        parts.append(f'【页面主区域】共 {len(page_els)} 个元素')
        # 按重要性排序：input/textarea/select > button > a > 其他
        tag_order = ['input', 'textarea', 'select', 'button', 'a']
        for tag in tag_order:
            if tag in el_by_tag:
                for el in el_by_tag[tag]:
                    parts.append(f'  {_format_element(el)}')
                    total_el_shown += 1
                del el_by_tag[tag]
        # 剩余其他类型
        for tag, els in el_by_tag.items():
            for el in els:
                parts.append(f'  {_format_element(el)}')
                total_el_shown += 1

    elements_text = '\n'.join(parts)

    text = state.get('text', state.get('visible_text', ''))[:800]
    history_text = '\n'.join([
        f"  {s['step']}. {s.get('description', s['action'])} - {'通过' if s.get('passed') else '失败'}"
        for s in history[-10:]
    ]) if history else '  暂无'
    return STEP_PROMPT.format(
        task=task_description,
        title=state.get('title', ''),
        url=state.get('url', ''),
        elements=elements_text,
        text=text,
        history=history_text
    )


def _format_element(el):
    """将单个元素格式化为精简的一行描述"""
    tag = el.get('tag', '')
    text = el.get('text', '')
    placeholder = el.get('placeholder', '')
    aria = el.get('aria_label', '')
    name = el.get('name', '')
    sel = el.get('selector', '')
    role = el.get('role', '')
    dom_label = el.get('label', '')  # DOM 中关联的 <label> 文本

    label = dom_label or aria or placeholder or text or name or role or ''
    return f'{tag}[{sel}] {label}'[:120]
