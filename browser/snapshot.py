"""页面状态捕获 - 将页面状态转为 LLM 可理解的格式"""
from log.logger import LoggerUtil

logger = LoggerUtil.get_logger()


class PageSnapshot:
    """从 Playwright Page 捕获页面快照"""

    def __init__(self, page):
        self.page = page

    def get_page_state(self):
        """获取页面完整状态"""
        try:
            return {
                'url': self.page.url,
                'title': self.page.title(),
                'visible_text': self.get_visible_text(2000),
                'interactive_elements': self.get_interactive_elements(),
                'screenshot_base64': self.take_screenshot_base64()
            }
        except Exception as e:
            logger.error(f"获取页面状态失败: {str(e)}")
            return {'error': str(e)}

    def get_visible_text(self, max_length=2000):
        """获取页面可见文本（供LLM理解页面内容）"""
        try:
            text = self.page.inner_text('body')
            text = ' '.join(text.split())
            if len(text) > max_length:
                text = text[:max_length] + '...'
            return text
        except Exception:
            return ''

    def get_interactive_elements(self):
        """获取页面中所有可交互元素（含弹窗/对话框上下文）"""
        elements = []
        try:
            elements = self.page.evaluate('''() => {
                const results = [];
                const tags = 'button, a[href], input:not([type="hidden"]), select, textarea, [role="button"], [role="dialog"], [role="alertdialog"], [role="option"], [tabindex], dialog';

                function getContainer(el) {
                    let parent = el.parentElement;
                    while (parent && parent !== document.body) {
                        const role = parent.getAttribute('role') || '';
                        const tag = parent.tagName.toLowerCase();
                        const cls = (parent.className || '').toString().toLowerCase();
                        const style = window.getComputedStyle(parent);
                        const zIndex = parseInt(style.zIndex) || 0;
                        const position = style.position || '';
                        // 角色/标签检测
                        if (role.includes('dialog') || tag === 'dialog' || role.includes('alertdialog')) {
                            return (parent.getAttribute('aria-label') || parent.id || tag + (cls ? '.' + cls.split(' ')[0] : '')).slice(0, 40);
                        }
                        // 常见 UI 框架 class 检测
                        if (cls.includes('modal') || cls.includes('dialog') || cls.includes('popup') ||
                            cls.includes('drawer') || cls.includes('overlay') || cls.includes('mask') ||
                            cls.includes('layer')) {
                            return (parent.getAttribute('aria-label') || parent.id || tag + (cls ? '.' + cls.split(' ')[0] : '')).slice(0, 40);
                        }
                        // 高 z-index 的 fixed/absolute 元素（自定义弹窗）
                        if ((position === 'fixed' || position === 'absolute') && zIndex > 100) {
                            return (parent.getAttribute('aria-label') || parent.id || tag + (cls ? '.' + cls.split(' ')[0] : '')).slice(0, 40);
                        }
                        parent = parent.parentElement;
                    }
                    return 'page';
                }

                document.querySelectorAll(tags).forEach(el => {
                    const rect = el.getBoundingClientRect();
                    if (rect.width === 0 && rect.height === 0) return;
                    const container = getContainer(el);
                    results.push({
                        tag: el.tagName.toLowerCase(),
                        type: el.type || '',
                        placeholder: el.placeholder || '',
                        name: el.name || '',
                        id: el.id || '',
                        text: (el.innerText || '').trim().slice(0, 50),
                        value: el.value || '',
                        aria_label: el.getAttribute('aria-label') || '',
                        href: el.getAttribute('href') || '',
                        title: el.getAttribute('title') || '',
                        container: container,
                        role: el.getAttribute('role') || '',
                        class: (el.className || '').toString().slice(0, 30)
                    });
                });
                return results;
            }''')
            for el in elements:
                base = self._build_selector(el['tag'], el, el['text'])
                # 弹窗内元素：加容器前缀，确保选择器只命中弹窗内的元素
                container = el.get('container', 'page')
                if container != 'page' and base:
                    el['selector'] = _scope_selector(container, base)
                else:
                    el['selector'] = base
        except Exception as e:
            logger.error(f"获取交互元素失败: {str(e)}")
        # 按容器分组输出日志
        containers = {}
        for e in elements:
            c = e.get('container', 'page')
            containers.setdefault(c, []).append(e['tag'])
        container_summary = ', '.join([f"{c}({len(v)}个)" for c, v in containers.items()])
        logger.info(f"捕获到 {len(elements)} 个交互元素（容器: {container_summary}）")
        return elements

    def _build_selector(self, tag, attrs, text):
        """构建元素选择器"""
        selectors = []
        if attrs.get('id'):
            selectors.append(f'#{attrs["id"]}')
        if attrs.get('aria_label'):
            selectors.append(f'{tag}[aria-label="{attrs["aria_label"]}"]')
        if text and len(text) < 80:
            # 规范化空白：多个连续空白→单个空格，保留中文字符间的真实空格
            clean_text = ' '.join(text.split())
            if tag == 'button':
                selectors.append(f'button:has-text("{clean_text}")')
            elif tag == 'a':
                selectors.append(f'a:has-text("{clean_text}")')
            else:
                selectors.append(f'{tag}:has-text("{clean_text}")')
        if attrs.get('placeholder'):
            selectors.append(f'{tag}[placeholder="{attrs["placeholder"]}"]')
        if attrs.get('name'):
            selectors.append(f'{tag}[name="{attrs["name"]}"]')
        if attrs.get('href') and tag == 'a':
            selectors.append(f'a[href="{attrs["href"]}"]')
        # 新增：value 属性（适用于 input[type="submit"]、input[value="百度一下"] 等）
        if attrs.get('value'):
            selectors.append(f'{tag}[value="{attrs["value"]}"]')
        # 新增：type 属性（适用于 input[type="text"]、input[type="password"] 等）
        if attrs.get('type'):
            selectors.append(f'{tag}[type="{attrs["type"]}"]')
        return selectors[0] if selectors else None

    def take_screenshot_base64(self):
        """截图并返回 base64"""
        try:
            return self.page.screenshot(type='png', full_page=False)
        except Exception:
            return None

    def get_dom_snapshot(self):
        """获取精简 DOM 语义树"""
        try:
            return self.page.evaluate('''() => {
                function getSimplifiedDom(el, depth=0) {
                    if (depth > 5) return '';
                    const tag = el.tagName.toLowerCase();
                    const hidden = ['script', 'style', 'noscript', 'svg', 'path'];
                    if (hidden.includes(tag)) return '';

                    let result = '';
                    const indent = '  '.repeat(depth);
                    const text = (el.innerText || '').trim().slice(0, 60);

                    const interactive = ['a', 'button', 'input', 'select', 'textarea'];
                    const meaningful = ['h1','h2','h3','h4','h5','h6','p','li','label','span','div','nav','header','footer','section','article','aside','main','form','table','tr','td','th'];

                    if (interactive.includes(tag) || meaningful.includes(tag)) {
                        const id = el.id ? '#'+el.id : '';
                        const cls = el.className && typeof el.className === 'string' ? '.'+el.className.split(' ')[0] : '';
                        const aria = el.getAttribute('aria-label') ? '['+el.getAttribute('aria-label')+']' : '';
                        const label = text ? `: "${text}"` : '';
                        result += indent + '<' + tag + id + cls + aria + label + '>\\n';
                    }

                    for (const child of el.children) {
                        result += getSimplifiedDom(child, depth+1);
                    }
                    return result;
                }
                return getSimplifiedDom(document.body);
            }''')
        except Exception:
            return ''


def _scope_selector(container, base):
    """将容器名转为 CSS 前缀，生成弹窗内唯一选择器
    
    container 格式如: div.ant-modal, div#myModal, div.modal.fade
    → 提取为 .ant-modal, #myModal, .modal.fade 作为前缀
    """
    parts = container.split('.')
    tag = parts[0]
    if '#' in tag:
        id_part = '#' + tag.split('#', 1)[1]
        return f'{id_part} {base}'
    if len(parts) > 1:
        cls = '.'.join(parts[1:])
        return f'.{cls} {base}'
    return f'{container} {base}'
