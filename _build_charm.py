# -*- coding: utf-8 -*-
"""把 Charm 的四个预览页复刻成一个零外部依赖、悬浮切换器四选一的单文件 HTML。

源：`Charm Design Skill File _ TypeUI*_files/{components,marketing,application,ecommerce}.html`
    （saved from https://charm-typeui-b08baaa4.vercel.app/<page>）

这些保存件不能直接用：依赖 3 个外部 CSS 与 40 多个 Next.js chunk，字体指向已失效的
外链，且它们只是**首屏静态快照**——modal / drawer / 下拉菜单的 DOM 在文件里根本不
存在（React 当时没渲染）。本脚本对每一页做同样的五件事：

  1. 字节级切出根节点并清洗外链（四页互跳外链改写成 `#p=<slug>` 路由）；
  2. 用字符串锚点补回缺失的隐藏态 DOM（内容逐字取自各页的编译产物 chunk）；
  3. 逐 <svg> 给内部 id 加页前缀，消除跨页 / 页内的 id 冲突；
  4. 收集 class 白名单；
  5. 组装进带 `.pv` 包裹层的外壳，底部一个悬浮切换器切页。

CSS 按原 <link> 的 data-precedence 顺序合并：字体 → 令牌 → 站点样式（四页并集白名单
切片）→ 组件库样式 → 外壳补丁。

每一步都带 assert：源页面若更新导致锚点失效，会立刻报错而不是静默产出坏页面。

运行：
    python3 "_build_charm.py"                     # 合并版 charm-preview.html
    python3 "_build_charm.py" --only=components   # 单页版（components → charm-components.html）
    python3 "_build_charm.py" --all               # 合并版 + 四个单页版（像素回归要用）
    python3 "_build_charm.py" --fonts=cjk         # 中文字体版 charm-preview-cjk.html
                                                  # （字体包先由 _make_cjk_fonts.py 生成）

验证：
    NODE_PATH=<装了 puppeteer-core 的 node_modules> node "_verify_charm.mjs"
"""
from __future__ import annotations

import base64
import hashlib
import json
import re
import sys
from dataclasses import dataclass, field
from pathlib import Path

HERE = Path(__file__).resolve().parent
DIR_COMPONENTS = HERE / "Charm Design Skill File _ TypeUI_files"
DIR_MARKETING = HERE / "Charm Design Skill File _ TypeUI1_files"
DIR_APPLICATION = HERE / "Charm Design Skill File _ TypeUI2_files"
DIR_ECOMMERCE = HERE / "Charm Design Skill File _ TypeUI3_files"

# 四目录里这两个文件内容完全相同（已核 sha256），统一从 components 目录读
F_CSS_TOKENS = DIR_COMPONENTS / "4309ev1le5xnp.css"   # 设计令牌 + reset（+ 失效的 @font-face）
F_CSS_SITE = DIR_COMPONENTS / "1mf3-ztrcgvjb.css"     # 四页共用的站点样式，按白名单切片
F_CSS_DS = DIR_COMPONENTS / "1l8ijtal3t07p.css"       # 组件库文档页样式，components 独有，全量
F_FONTS = HERE / "_charm_fonts.json"                  # 预先下载的 latin 子集 woff2（base64）
F_FONTS_CJK = HERE / "_charm_fonts_cjk.json"          # 中文字体包（全量 CJK），_make_cjk_fonts.py 生成
F_FONTS_CJK_GB = HERE / "_charm_fonts_cjk_gb.json"    # 同上的 GB2312 子集版（--gb2312）

OUT_STEM_MERGED = "charm-preview"
OUT_STEM_SINGLE = {"components": "charm-components"}  # 其余单页产物用 charm-single-<slug>

BODY_END_ANCHOR = '<script src="./42clt6zq0u6gl.js"'   # 四页正文都止于这个 chunk 标签
VERCEL = r'https://charm-typeui-[\w-]+\.vercel\.app'

# 页面级 id 之外，svg 内部 id 一律改名；这是识别「元素 id」的正则，
# 必须排除 data-recharts-item-id= 这类以 `-id=` 结尾的属性
RE_ID = r'(?<![-\w])id="([^"]*)"'


def need(cond, msg):
    if not cond:
        sys.exit(f"[构建失败] {msg}")


# ------------------------------------------------ 从编译产物里机械提取文案的工具
# 菜单文案、FAQ、定价这些都从各页的 chunk 里正则提取，绝不手抄——错一个词
# 不会有任何东西报警。
RE_JS_STR = r'"((?:[^"\\]|\\.)*)"'


def esc(s: str) -> str:
    """React SSR 对文本节点的转义规则：& < >。"""
    return s.replace('&', '&amp;').replace('<', '&lt;').replace('>', '&gt;')


def _bracket_end(s: str, i: int) -> int:
    """返回 s[i] 处 '[' 的匹配 ']' 的下标（跳过字符串字面量内的括号）。"""
    depth, k = 0, i
    while k < len(s):
        c = s[k]
        if c == '"':
            k = re.compile(RE_JS_STR).match(s, k).end() - 1
        elif c in '[{':
            depth += 1
        elif c in ']}':
            depth -= 1
            if depth == 0:
                return k
        k += 1
    need(False, "JS 数组字面量未闭合")


def js_array(js: str, pattern: str) -> list:
    """按 pattern（须以 `=` 结尾的变量名锚点）取一个纯字符串数组字面量。"""
    m = re.search(pattern + r'\[', js)
    need(m, f"找不到数组字面量 {pattern}")
    start = m.end() - 1
    return re.findall(RE_JS_STR, js[start:_bracket_end(js, start) + 1])


# lucide 图标：React 端的序列化是确定的，直接从 chunk 里的 iconNode 定义生成，
# 与快照里已渲染的那些逐字节一致（build 时有对照断言，见 check_icons）。
LUCIDE_HEAD = ('<svg xmlns="http://www.w3.org/2000/svg" width="24" height="24" viewBox="0 0 24 24" '
               'fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" '
               'stroke-linejoin="round" class="lucide lucide-{name}{extra}" aria-hidden="true">')


def lucide_svg(js: str, name: str, extra: str = "") -> str:
    m = re.search(r'\("' + re.escape(name) + r'",\[', js)
    need(m, f"chunk 里找不到 lucide 图标 {name}")
    start = m.end() - 1
    node = js[start:_bracket_end(js, start) + 1]
    kids = []
    for em in re.finditer(r'\["(\w+)",\{([^}]*)\}\]', node):
        attrs = re.findall(r'(\w+):"([^"]*)"', em.group(2))
        need(len(attrs) == em.group(2).count(':'), f"图标 {name} 的属性里出现了非字符串值")
        pairs = "".join(f' {re.sub(r"(?<=[a-z])(?=[A-Z])", "-", k).lower()}="{v}"'
                        for k, v in attrs if k != "key")
        kids.append(f'<{em.group(1)}{pairs}></{em.group(1)}>')
    need(kids, f"图标 {name} 解析出 0 个子元素")
    return LUCIDE_HEAD.format(name=name, extra=f' {extra}' if extra else '') + "".join(kids) + "</svg>"


# ================================================================== 声明式规则
@dataclass(frozen=True)
class CleanRule:
    """一条带命中数区间断言的正则替换。lo/hi 都是闭区间。"""
    label: str
    pattern: str
    repl: str
    lo: int
    hi: int
    flags: int = 0

    def apply(self, s: str) -> str:
        out, n = re.subn(self.pattern, self.repl, s, flags=self.flags)
        need(self.lo <= n <= self.hi, f"[清洗·{self.label}] 命中 {n} 次，期望 {self.lo}–{self.hi}")
        return out


@dataclass(frozen=True)
class Restore:
    """把快照里缺失的隐藏态 DOM 插回去。

    anchor 是正则，必须恰好命中 count 次；payloads 与命中按序一一对应，插在命中之后。
    rewrite 作用于命中文本自身（用来给触发按钮补 aria-* 关联）。
    """
    label: str
    anchor: str
    payloads: tuple
    count: int = 1
    rewrite: tuple = ()      # (pattern, repl)，对每个命中各执行一次
    flags: int = 0

    def apply(self, s: str) -> str:
        ms = list(re.finditer(self.anchor, s, self.flags))
        need(len(ms) == self.count,
             f"[还原·{self.label}] 锚点命中 {len(ms)} 次，期望 {self.count}")
        need(len(self.payloads) == self.count,
             f"[还原·{self.label}] payload 数 {len(self.payloads)} 与命中数 {self.count} 不符")
        for m, payload in zip(reversed(ms), reversed(self.payloads)):   # 从后往前插，偏移不失效
            hit = m.group(0)
            if self.rewrite:
                hit, n = re.subn(self.rewrite[0], self.rewrite[1], hit, count=1)
                need(n == 1, f"[还原·{self.label}] rewrite 未命中")
            s = s[:m.start()] + hit + payload + s[m.end():]
        return s


@dataclass(frozen=True)
class MenuSpec:
    """一份下拉面板模板。

    key 是**触发器判别式**（aria-label 优先，否则按钮纯文本），不是序号——
    序号会随 DOM 微调而错位，且 application 的 21 个触发器里 10 个是同一模板
    在表格行里的复用。key 以 `*` 结尾表示前缀匹配（`Actions for *`）。
    """
    key: str
    panel: str


@dataclass(frozen=True)
class PageSpec:
    slug: str
    label: str                      # tab 上的文案
    title: str                      # 单页模式下的 <title>
    src_dir: Path
    src_html: str
    root_anchor: str                # 正文起点，字面量
    id_prefix: str                  # svg id 改名用的两字母前缀
    clean: tuple = ()               # 页面专属清洗（在通用清洗之前执行）
    restores: tuple = ()
    menus: tuple = ()               # MenuSpec 列表；按触发器判别式插回下拉面板
    patch_css: str = ""             # 该页专属的还原补丁 CSS
    js: str = ""                    # 该页专属的交互层
    inline_imgs: bool = False       # <img src="./x.svg"> → data: URI
    fix_recharts: bool = False      # 拆掉 recharts 的零尺寸中间层
    extra_css: tuple = ()           # 该页独有的 CSS 文件（全量并入）
    expect_class_counts: tuple = ()  # 机械预言机：(class, 期望出现次数)


@dataclass(frozen=True)
class FontPack:
    """一套内嵌字体，外加它要写进 :root 的三个字族令牌值。

    四页的字体栈形如 `var(--font-inter), "Inter", ui-sans-serif, …`——被内嵌字体
    占据的永远是第一顺位的那个令牌，所以换字体只需改这三个值，**一条页面 CSS
    规则都不用碰**，也就不会动到布局以外的任何东西。
    """
    key: str
    file: Path
    sans: str            # --font-inter：正文
    display: str         # --font-display：标题
    mono: str            # --font-fragment-mono：等宽
    suffix: str = ""     # 产物文件名后缀，空串即默认产物
    label: str = ""      # 内嵌字体那段 CSS 的注释文案
    font_note: str = ""  # 产物说明块里「已知差异」的第 1 条


FONT_PACKS = {
    "latin": FontPack(
        "latin", F_FONTS, '"Inter"', '"DM Sans"', '"Fragment Mono"',
        label="latin 子集，可变字重",
        font_note="""  1. 标题字体用 DM Sans —— 原设计首选商业字体 Circular Std，
     规范本身即以 DM Sans 作为其免费替代。""",
    ),
    "cjk": FontPack(
        "cjk", F_FONTS_CJK, '"Noto Sans SC"', '"Noto Sans SC"', '"Sarasa Mono SC"',
        suffix="-cjk",
        label="全量 CJK，静态字重",
        font_note="""  1. 字体全部换成中文字体：正文与标题 Noto Sans SC，等宽 Sarasa Mono SC。
     等宽之所以不一并用 Noto Sans SC：它的拉丁是比例字体，拿来做等宽会让
     components 页的代码示例失去列对齐；更纱黑体把汉字宽度做成拉丁的整二倍，
     中英混排也不破列。两者均为全量 CJK 覆盖，因此产物体积远大于拉丁版。
     原版字体（Inter / DM Sans / Fragment Mono）见 charm-preview.html。""",
    ),
    "cjk-gb": FontPack(
        "cjk-gb", F_FONTS_CJK_GB, '"Noto Sans SC"', '"Noto Sans SC"', '"Sarasa Mono SC"',
        suffix="-cjk-gb",
        label="GB2312 子集，静态字重",
        font_note="""  1. 字体全部换成中文字体：正文与标题 Noto Sans SC，等宽 Sarasa Mono SC
     （更纱黑体，汉字宽度为拉丁的整二倍，中英混排不破列）。
     字形按 GB2312 子集化：收录 6763 个常用汉字 + 682 个符号，另加拉丁、
     标点、全角形式各区，以及拉丁版产物里在用的每一个字符。
     ⚠ 生僻字、繁体字、日文假名不在其中，遇到会回退到系统字体。
     全量 CJK 版见 charm-preview-cjk.html，原版字体见 charm-preview.html。""",
    ),
}


# ============================================================ 人工资产：外壳
# 顶部 tab bar 直接复用 Charm 自己的 .segmented / .segmented__btn，
# 零新增组件 CSS；`.pv-switch` 与 `.pv` 是本复刻唯一新增的两个布局 class。
SHELL_PATCH_CSS = """
/* ==== 外壳补丁（合并版新增的唯一一段 CSS） ====
   切换器是 position:fixed 的悬浮层，**完全不参与布局**——这是刻意的：
   只要它占了布局，被它挤掉的那一维就要在四页里逐处补偿。占顶部（竖向）
   要改写 .ds/.page/.appshell 的 100vh 与 8 个 fixed 浮层的 inset；占侧边
   （横向）更糟，共享 CSS 里有 21 个宽度断点、0 个高度断点，横向缩一截会
   让每一个断点都与真实内容宽度错位。做成浮层后，.pv 恢复整个视口，
   原页面的 100vh 与所有浮层定位原样成立，一条都不用改。 */
html,body{height:100%}
body{overflow:hidden}

/* 每页一个独立滚动容器。四个 root 的 display 各异（.page/.appshell 是 flex），
   直接给 root 挂 [hidden] 会被自身的 display 覆盖，故必须包一层 wrapper。 */
.pv{height:100%;overflow:auto;position:relative}
.pv[hidden]{display:none!important}
.pv [hidden]{display:none!important}

/* 切换器：位置与样式照搬原站自己的预览切换器（见
   `Charm Design Skill File _ TypeUI.html` 里 data-preview-surface 那组按钮），
   括号里是它对应的 Tailwind 类。
   ⚠ 这是 typeui.sh 的**站点 chrome，不是 Charm 组件**，故意用字面值而非
   Charm 令牌——深色玻璃一眼可辨"这是外壳、不是被预览的页面"。不要"修正"它。
   贴底而非贴顶也是原站的选择：顶部那条正是四页各自安放常驻导航的地方
   （实测贴顶会盖住 ecommerce 的语言选择 + 5 个主导航项）。
   z-index 高于原页面最高的浮层（.modal-scrim 是 300）。 */
.pv-switch{z-index:500;position:fixed;bottom:16px;left:50%;transform:translateX(-50%);
  max-width:calc(100% - 2rem);
  gap:4px;padding:4px;align-items:center;display:flex;
  border:1px solid #ffffff1a;border-radius:1.4rem;background:#00000080;
  box-shadow:0 10px 15px -3px #0000001a,0 4px 6px -4px #0000001a;
  -webkit-backdrop-filter:blur(4px);backdrop-filter:blur(4px);
  overflow-x:auto;overscroll-behavior-x:contain;scrollbar-width:none}
.pv-switch::-webkit-scrollbar{display:none}
.pv-switch__btn{flex:none;height:32px;padding-inline:12px;
  border:0;border-radius:9999px;background:0 0;cursor:pointer;color:#ffffffcc;
  font-family:var(--font-sans-stack);font-size:14px;font-weight:500;white-space:nowrap;
  justify-content:center;align-items:center;display:inline-flex;
  transition:background-color .2s,color .2s}
.pv-switch__btn:hover{background:#ffffff1a;color:#fff}
.pv-switch__btn:focus-visible{outline:2px solid #fff;outline-offset:2px}
.pv-switch__btn.is-active{background:#fff;color:#000}
.pv-switch__btn.is-active:hover{background:#f4f4f5}
@media (min-width:640px){.pv-switch__btn{padding-inline:16px}}
@media (min-width:768px){.pv-switch{bottom:24px;max-width:calc(100% - 3rem)}}
"""

SHELL_JS = r"""
/* ==== 外壳：悬浮切换器 + 路由 ====
   状态只存在 DOM 上（[hidden] / aria-selected / dataset.scroll），不设 JS 变量。
   切换器是 position:fixed 浮层（见 SHELL_PATCH_CSS），不参与布局，因此这里
   只管开合与路由，不需要为它预留任何尺寸。
   路由只认 `#p=<slug>`：四页里有 13 个形如 #components / #overview 的页内死锚点，
   裸 slug 会与它们撞名，其余 hash 一律交给浏览器做页内跳转。 */
(function () {
  'use strict';
  var bar = document.querySelector('.pv-switch');
  var panels = [].slice.call(document.querySelectorAll('.pv'));
  if (!bar || !panels.length) return;
  var tabs = [].slice.call(bar.querySelectorAll('[role="tab"]'));

  function show(slug) {
    if (!panels.some(function (p) { return p.dataset.page === slug; })) return false;
    panels.forEach(function (p) {
      var on = p.dataset.page === slug;
      if (!on && !p.hidden) p.dataset.scroll = String(p.scrollTop);
      p.hidden = !on;
      if (on) p.scrollTop = parseInt(p.dataset.scroll || '0', 10) || 0;
    });
    tabs.forEach(function (t) {
      var on = t.dataset.goto === slug;
      t.setAttribute('aria-selected', String(on));
      t.classList.toggle('is-active', on);
      t.tabIndex = on ? 0 : -1;
    });
    return true;
  }

  function fromHash() {
    var m = /(?:^|[#&])p=([a-z]+)/.exec(location.hash);
    return m ? m[1] : null;
  }

  document.addEventListener('click', function (e) {
    var t = e.target.closest && e.target.closest('[data-goto],a[href^="#p="]');
    if (!t) return;
    var slug = t.dataset.goto || t.getAttribute('href').slice(3);
    if (!show(slug)) return;
    e.preventDefault();
    history.replaceState(null, '', '#p=' + slug);   /* 不污染后退栈 */
  });

  /* 左右方向键在 tab 之间移动（role=tablist 的标准键盘行为） */
  bar.addEventListener('keydown', function (e) {
    var i = tabs.indexOf(document.activeElement);
    if (i < 0 || (e.key !== 'ArrowRight' && e.key !== 'ArrowLeft')) return;
    var next = tabs[(i + (e.key === 'ArrowRight' ? 1 : tabs.length - 1)) % tabs.length];
    e.preventDefault();
    show(next.dataset.goto);
    next.focus();
  });

  window.addEventListener('hashchange', function () {
    var s = fromHash();
    if (s) show(s);
  });

  show(fromHash() || bar.dataset.default);
})();
"""


# ====================================================== 人工资产：components
# 缺失的隐藏态 DOM。逐字对应 3_5xni4gaqisd.js 里的 JSX，仅把 React 的「条件渲染」
# 改写为 [hidden] 切换（见 PATCH_CSS）。图标沿用页面内已有的 SVG 序列化形式。
ICON_X = ('<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" '
          'stroke-linecap="round" aria-hidden="true"><path d="M18 6 6 18M6 6l12 12"></path></svg>')
ICON_USER = ('<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" '
             'stroke-linecap="round" aria-hidden="true"><path d="M20 21a8 8 0 1 0-16 0"></path>'
             '<circle cx="12" cy="7" r="4"></circle></svg>')
ICON_CARD = ('<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" '
             'stroke-linecap="round" aria-hidden="true"><rect x="2" y="5" width="20" height="14" rx="3">'
             '</rect><path d="M2 10h20"></path></svg>')
# 页面快照里唯一没出现过的图标，从 JS 转写
ICON_LOGOUT = ('<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" '
               'stroke-linecap="round" aria-hidden="true"><path d="M9 21H5a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h4">'
               '</path><path d="m16 17 5-5-5-5M21 12H9"></path></svg>')

DD_PANEL = (
    '<button class="ds__dd-scrim" aria-hidden="true" tabindex="-1" hidden></button>'
    '<div class="ds__dd-panel" role="menu" hidden>'
    f'<button class="ds__menu-item" role="menuitem">{ICON_USER} Profile</button>'
    f'<button class="ds__menu-item" role="menuitem">{ICON_CARD} Billing</button>'
    '<div class="ds__menu-divider" role="separator"></div>'
    f'<button class="ds__menu-item ds__menu-item--danger" role="menuitem">{ICON_LOGOUT} Sign out</button>'
    '</div>'
)

MODAL = (
    '<div class="ds__scrim" data-close="ds-modal" hidden></div>'
    '<div class="ds__modal" id="ds-modal" role="dialog" aria-modal="true" aria-labelledby="ds-modal-t" hidden>'
    '<div class="ds__overlay-head">'
    '<h4 class="ds__overlay-title" id="ds-modal-t">Remove this account?</h4>'
    f'<button class="ds__x" aria-label="Close" data-close="ds-modal">{ICON_X}</button>'
    '</div>'
    '<p style="margin-bottom:20px">The account loses access immediately. Invoices already paid stay on the record.</p>'
    '<div style="display:flex;gap:12px">'
    '<button class="btn btn--secondary btn--sm" data-close="ds-modal"><span>Cancel</span></button>'
    '<button class="btn btn--primary btn--sm" data-close="ds-modal"><span>Remove</span></button>'
    '</div></div>'
)

DRAWER = (
    '<div class="ds__scrim" data-close="ds-drawer" hidden></div>'
    '<aside class="ds__drawer" id="ds-drawer" role="dialog" aria-modal="true" aria-labelledby="ds-drawer-t" hidden>'
    '<div class="ds__overlay-head">'
    '<h4 class="ds__overlay-title" id="ds-drawer-t">Settings</h4>'
    f'<button class="ds__x" aria-label="Close" data-close="ds-drawer">{ICON_X}</button>'
    '</div>'
    '<div class="ds__field">'
    '<label class="ds__label" for="ds-drawer-name">Workspace</label>'
    '<input id="ds-drawer-name" class="ds__input" value="Northwind">'
    '</div>'
    '<label class="ds__opt"><span class="ds__toggle"><input type="checkbox" checked>'
    '<span class="ds__track"><span class="ds__thumb"></span></span></span>Email notifications</label>'
    '<button class="btn btn--primary btn--sm" data-close="ds-drawer"><span>Save</span></button>'
    '</aside>'
)

ACC_PANEL = ('<div class="ds__acc-panel" id="ds-acc-{i}" role="region" '
             'aria-labelledby="ds-acc-t-{i}" hidden>{a}</div>')
ACC_ANSWERS = {
    1: "Yes. One invoice can be split across payers, and each payer only sees their own share.",
    2: "It is yours. Export every record as CSV or PDF at any time, without asking us.",
}

ALERT_RESTORE = ('<button class="btn btn--secondary btn--sm" data-alerts-restore hidden>'
                 '<span>Bring the alerts back</span></button>')

# 唯一新增的 CSS。React 原本卸载节点，这里改为 [hidden] 切换，而 .ds__drawer /
# .ds__alert / .btn 都带 display:flex|inline-flex，会盖掉 UA 的 [hidden]{display:none}。
DS_PATCH_CSS = """
/* ==== reconstruction patch（本复刻新增的唯一一条规则） ====
   原实现靠 React 卸载节点来隐藏浮层，这里改用 [hidden] 切换；
   .ds__drawer/.ds__alert/.btn 的 display 会覆盖 UA 默认，故需强制。 */
.ds [hidden]{display:none!important}
"""

# 交互层。状态只存在 DOM 上（aria-* / .is-open / hidden），不设 JS 变量：
# 既无同步 bug，验证脚本也能直接读属性断言。
DS_JS = r"""
(function () {
  'use strict';
  var root = document.querySelector('.ds');
  if (!root) return;
  var $  = function (s, c) { return (c || root).querySelector(s); };
  var $$ = function (s, c) { return Array.prototype.slice.call((c || root).querySelectorAll(s)); };

  /* tabs 是换文本而非换节点，与原实现一致 */
  var TAB_COPY = {
    Overview: 'Everything at a glance: what is live, what is queued, what needs a decision.',
    Billing:  'Invoices, payment methods and the current plan.',
    Team:     'Seats, roles and pending invitations.'
  };

  function setOverlay(id, open) {
    var panel = document.getElementById(id);
    if (!panel) return;
    $$('[data-close="' + id + '"]').forEach(function (el) {
      if (el.classList.contains('ds__scrim')) el.hidden = !open;
    });
    panel.hidden = !open;
    var opener = $('[aria-controls="' + id + '"]');
    if (opener) opener.setAttribute('aria-expanded', String(open));
    /* 不主动移动焦点：原 React 实现也没有焦点管理，自动 focus 会让 ✕
       落上浏览器默认的蓝色焦点环，那不是 Charm 的 --focus-ring */
  }

  function setDropdown(open) {
    var dd = $('.ds__dd');
    if (!dd) return;
    $('button[aria-haspopup="menu"]', dd).setAttribute('aria-expanded', String(open));
    $('.ds__dd-panel', dd).hidden = !open;
    $('.ds__dd-scrim', dd).hidden = !open;
  }

  function syncRange(input) {
    var out = document.getElementById('ds-range-out');
    input.style.setProperty('--fill', input.value + '%');
    if (out) out.textContent = input.value;
  }

  root.addEventListener('click', function (e) {
    var t = e.target, el;

    /* 浮层：开 / 关（scrim、✕、页脚按钮都带 data-close） */
    if ((el = t.closest('[data-close]'))) { setOverlay(el.getAttribute('data-close'), false); return; }
    if ((el = t.closest('[aria-haspopup="dialog"]'))) { setOverlay(el.getAttribute('aria-controls'), true); return; }

    /* 下拉菜单：切换 / 点菜单项或点外面都关闭 */
    if ((el = t.closest('.ds__dd > button[aria-haspopup="menu"]'))) {
      setDropdown(el.getAttribute('aria-expanded') !== 'true'); return;
    }
    if (t.closest('.ds__dd-scrim') || t.closest('.ds__menu-item')) { setDropdown(false); return; }

    /* 手风琴：单开，再点收起 */
    if ((el = t.closest('.ds__acc-trigger'))) {
      var item = el.closest('.ds__acc-item');
      var wasOpen = item.classList.contains('is-open');
      $$('.ds__acc-item', el.closest('.ds__acc')).forEach(function (it) {
        it.classList.remove('is-open');
        var trig = $('.ds__acc-trigger', it), pan = $('.ds__acc-panel', it);
        if (trig) trig.setAttribute('aria-expanded', 'false');
        if (pan) pan.hidden = true;
      });
      if (!wasOpen) {
        item.classList.add('is-open');
        el.setAttribute('aria-expanded', 'true');
        var p = $('.ds__acc-panel', item); if (p) p.hidden = false;
      }
      return;
    }

    /* 标签页：填充式一组可交互（下划线那组原页面就是写死的，保持不动） */
    if ((el = t.closest('.ds__tabs[aria-label="Filled tabs"] .ds__tab'))) {
      var list = el.parentNode;
      $$('.ds__tab', list).forEach(function (b) { b.setAttribute('aria-selected', String(b === el)); });
      var panel = list.parentNode.querySelector('.ds__panel');
      if (panel) panel.textContent = TAB_COPY[el.textContent.trim()] || panel.textContent;
      return;
    }

    /* 分段按钮组 */
    if ((el = t.closest('.ds__group[aria-label="Timeframe"] .ds__seg'))) {
      $$('.ds__seg', el.parentNode).forEach(function (b) { b.setAttribute('aria-pressed', String(b === el)); });
      return;
    }

    /* 数字步进器：按容器内顺序判断加减（减在前、加在后），下限 0 */
    if ((el = t.closest('.ds__stepper button'))) {
      var box = el.parentNode;
      var inp = $('input', box);
      var step = $$('button', box).indexOf(el) === 0 ? -1 : 1;
      inp.value = Math.max(0, (parseInt(inp.value, 10) || 0) + step);
      return;
    }

    /* 警告条：逐条关闭；全部关闭后露出复位按钮 */
    if ((el = t.closest('button[aria-label^="Dismiss "]'))) {
      var alert = el.closest('.ds__alert');
      alert.hidden = true;
      var stage = alert.parentNode;
      if ($$('.ds__alert', stage).every(function (a) { return a.hidden; })) {
        var btn = $('[data-alerts-restore]', stage); if (btn) btn.hidden = false;
      }
      return;
    }
    if ((el = t.closest('[data-alerts-restore]'))) {
      $$('.ds__alert', el.parentNode).forEach(function (a) { a.hidden = false; });
      el.hidden = true;
      return;
    }
  });

  root.addEventListener('input', function (e) {
    if (e.target.classList.contains('ds__range')) syncRange(e.target);
  });

  /* 导航高亮：与原实现相同的 rootMargin */
  var sections = $$('section.ds__cat');
  var links = $$('.ds__nav-link');
  if (sections.length && links.length && window.IntersectionObserver) {
    sections.forEach(function (s) {
      new IntersectionObserver(function (entries) {
        entries.forEach(function (en) {
          if (!en.isIntersecting) return;
          links.forEach(function (a) {
            a.setAttribute('aria-current', String(a.getAttribute('href') === '#' + en.target.id));
          });
        });
      }, { root: s.closest('.pv'), rootMargin: '-45% 0px -50% 0px' }).observe(s);
    });
  }

  document.addEventListener('keydown', function (e) {
    if (e.key !== 'Escape') return;
    if (!$('.ds__dd-panel').hidden) { setDropdown(false); return; }
    ['ds-drawer', 'ds-modal'].forEach(function (id) {
      var p = document.getElementById(id);
      if (p && !p.hidden) setOverlay(id, false);
    });
  });

  var range = $('.ds__range'); if (range) syncRange(range);
})();
"""

PAGE_COMPONENTS = PageSpec(
    slug="components",
    label="Components",
    title="Charm · The component library",
    src_dir=DIR_COMPONENTS,
    src_html="components.html",
    root_anchor='<div class="ds">',
    id_prefix="co",
    clean=(
        # Range 标签里 `Seats: <!-- -->40`：去注释后三个文本节点会并成一个，
        # 无法只更新数字，故用 span 包住数值（本复刻对原 DOM 唯一的结构改动）
        CleanRule("Range 数值包 span", r'Seats: <!-- -->(\d+)',
                  r'Seats: <span id="ds-range-out">\1</span>', 1, 1),
    ),
    restores=(
        Restore("下拉面板",
                r'<button class="btn btn--outline btn--sm" aria-haspopup="menu"[^>]*>.*?</button>',
                (DD_PANEL,)),
        Restore("手风琴答案 2", r'id="ds-acc-t-1".*?</h4>',
                (ACC_PANEL.format(i=1, a=ACC_ANSWERS[1]),), flags=re.S),
        Restore("手风琴答案 3", r'id="ds-acc-t-2".*?</h4>',
                (ACC_PANEL.format(i=2, a=ACC_ANSWERS[2]),), flags=re.S),
        Restore("Modal", r'<button class="btn btn--\w+"><span>Open modal</span></button>',
                (MODAL,),
                rewrite=(r'<button ',
                         '<button aria-haspopup="dialog" aria-controls="ds-modal" aria-expanded="false" ')),
        Restore("Drawer", r'<button class="btn btn--\w+"><span>Open drawer</span></button>',
                (DRAWER,),
                rewrite=(r'<button ',
                         '<button aria-haspopup="dialog" aria-controls="ds-drawer" aria-expanded="false" ')),
        Restore("Alert 复位按钮",
                r'<div class="ds__stage ds__stage--stack">(?:(?!</div></div>).)*?Dismiss danger alert.*?</div>(?=</div>)',
                (ALERT_RESTORE,), flags=re.S),
    ),
    patch_css=DS_PATCH_CSS,
    js=DS_JS,
    extra_css=(F_CSS_DS,),
    expect_class_counts=(
        ("ds__cat", 8), ("ds__block", 37), ("ds__alert", 4),
        ("ds__acc-item", 3), ("ds__acc-panel", 3), ("ds__menu-item", 3),
    ),
)

# ============================================== 人工资产：跨页共享的交互层
# 三个「站点页」（marketing / application / ecommerce）共用同一批组件，
# 因此交互也只写一份：document 级委托 + 规则表，靠选择器天然复用。
def menu_html(items, width, align=None, sync_label=False, label=None, keep_open=False):
    """生成一个 .menu 下拉面板。

    结构逐字对应 2t6zzw8wl1772.js 里的 Dropdown：`<div class="menu" role="menu">`
    包一组 `.menu__item`。唯一的差别是**不用 portal**：面板作为触发器的紧邻兄弟
    内联——`position:fixed` 不受祖先影响（已核祖先链无 transform/filter/contain），
    随 `.pv[hidden]` 自动隐藏，还省掉一堆 aria-controls id。
    """
    parts = []
    for it in items:
        if it == "divider":
            parts.append('<div class="menu__divider" role="separator"></div>')
            continue
        label_html = f'<span class="menu__label">{esc(it["label"])}</span>'
        if it.get("check"):      # Filters 那份用 <label> + checkbox，不是 <button>
            parts.append('<label class="menu__item menu__item--check">'
                         f'<input type="checkbox" class="checkbox"{" checked" if it.get("active") else ""}>'
                         f'{label_html}</label>')
            continue
        role = it.get("role", "menuitem")
        cls = "menu__item"
        if it.get("active"):
            cls += " menu__item--active"
        if it.get("danger"):
            cls += " menu__item--danger"
        attrs = f' role="{role}"'
        if role in ("menuitemradio", "menuitemcheckbox"):
            attrs += f' aria-checked="{"true" if it.get("active") else "false"}"'
        icon = it.get("icon", "")
        parts.append(f'<button class="{cls}"{attrs}>{icon}{" " if icon else ""}{label_html}</button>')
    a = f' data-align="{align}"' if align else ""
    s = " data-sync-label" if sync_label else ""
    k = " data-keep-open" if keep_open else ""
    lab = f' aria-label="{label}"' if label else ""
    return (f'<div class="menu" role="menu"{a}{s}{k}{lab} style="width:{width}px" hidden>'
            + "".join(parts) + "</div>")


SHARED_JS = r"""
/* ==== 跨页共享交互：document 级委托 + 规则表 ====
   选择器不带 data-page 的规则天然被多页共用（.menu 三页、.segmented 三页、
   .menu-toggle 两页）；只属于某一页的行为用 [data-page="xxx"] 限定。
   状态一律只存在 DOM 上。 */
(function () {
  'use strict';
  var slice = function (x) { return Array.prototype.slice.call(x); };

  /* ---------------- 下拉菜单（移植自 2t6zzw8wl1772.js 的 Dropdown） ---------------- */
  function panelOf(trigger) {
    var p = trigger.nextElementSibling;
    return p && p.classList.contains('menu') ? p : null;
  }

  /* 定位算法逐行照搬：默认贴触发器左下 8px，align=end 时右对齐，
     左右各留 8px 安全边，装不下就翻到触发器上方。 */
  function place(trigger, panel) {
    var r = trigger.getBoundingClientRect();
    var w = panel.offsetWidth;
    var left = panel.dataset.align === 'end' ? r.right - w : r.left;
    left = Math.max(8, Math.min(left, window.innerWidth - w - 8));
    var top = r.bottom + 8, h = panel.offsetHeight;
    if (h && top + h > window.innerHeight - 8) top = Math.max(8, r.top - 8 - h);
    panel.style.top = top + 'px';
    panel.style.left = left + 'px';
  }

  function openMenus() { return slice(document.querySelectorAll('.menu:not([hidden])')); }

  function closeMenus(except) {
    openMenus().forEach(function (p) {
      if (p === except) return;
      p.hidden = true;
      p.previousElementSibling.setAttribute('aria-expanded', 'false');
    });
  }

  /* 滚动发生在 .pv 上而非 window，必须用捕获阶段才收得到 */
  function reposition() {
    openMenus().forEach(function (p) { place(p.previousElementSibling, p); });
  }
  window.addEventListener('scroll', reposition, true);
  window.addEventListener('resize', reposition);

  /* ---------------- 点击规则表 ---------------- */
  document.addEventListener('click', function (e) {
    var t = e.target, el;
    if (!t.closest) return;

    /* 下拉：触发器开合 */
    if ((el = t.closest('[aria-haspopup="menu"]')) && panelOf(el)) {
      var panel = panelOf(el);
      if (el.getAttribute('aria-expanded') === 'true') { closeMenus(); return; }
      closeMenus();
      panel.hidden = false;                       /* 先显示再量尺寸，否则 offsetWidth 为 0 */
      el.setAttribute('aria-expanded', 'true');
      place(el, panel);
      return;
    }

    /* 下拉：选中一项。原实现 closeOnSelect 默认 true，点面板内任何位置都关；
       Filters 那份显式传了 closeOnSelect:false，这里对应 data-keep-open。 */
    if ((el = t.closest('.menu'))) {
      var item = t.closest('.menu__item');
      if (item && item.getAttribute('role') === 'menuitemradio') {
        slice(el.querySelectorAll('[role="menuitemradio"]')).forEach(function (b) {
          var on = b === item;
          b.setAttribute('aria-checked', String(on));
          b.classList.toggle('menu__item--active', on);
        });
        /* 语言下拉会把选中项写回触发器（原实现的 setLang），
           标签是触发器里唯一的裸文本节点 */
        if (el.hasAttribute('data-sync-label')) {
          var trig = el.previousElementSibling;
          slice(trig.childNodes).forEach(function (n) {
            if (n.nodeType === 3 && n.textContent.trim()) n.textContent = item.textContent;
          });
        }
      }
      if (!el.hasAttribute('data-keep-open')) closeMenus();
      return;
    }

    /* 分段控件（.segmented）：顶部 tab bar 与页内筛选共用 */
    if ((el = t.closest('.segmented__btn'))) {
      slice(el.parentNode.children).forEach(function (b) {
        var on = b === el;
        b.classList.toggle('is-active', on);
        if (b.hasAttribute('aria-selected')) b.setAttribute('aria-selected', String(on));
      });
      return;   /* 不 closeMenus：tab bar 上的点击不应影响页内下拉 */
    }

    /* 移动端汉堡菜单（marketing / ecommerce） */
    if ((el = t.closest('.menu-toggle'))) {
      var nav = (el.closest('header') || document).querySelector('.mobile-menu');
      if (nav) {
        var open = el.getAttribute('aria-expanded') !== 'true';
        el.setAttribute('aria-expanded', String(open));
        nav.hidden = !open;
      }
      return;
    }

    /* ecommerce：筛选抽屉。.pdrawer 自带 visibility/transform 过渡，
       故只切 .is-open，不用 [hidden]。 */
    if ((el = t.closest('[data-pdrawer]'))) {
      var pv = el.closest('.pv') || document;
      var open2 = el.dataset.pdrawer === 'open';
      var drawer = pv.querySelector('.pdrawer'), scrim = pv.querySelector('.pdrawer-scrim');
      drawer.classList.toggle('is-open', open2);
      drawer.setAttribute('aria-hidden', String(!open2));
      scrim.hidden = !open2;
      pv.querySelector('[data-pdrawer="open"]').setAttribute('aria-expanded', String(open2));
      return;
    }

    closeMenus();   /* 点到别处：关掉所有下拉（原实现挂在 window 的 mousedown 上） */
  });

  document.addEventListener('keydown', function (e) {
    if (e.key !== 'Escape') return;
    var open = openMenus();
    if (open.length) { open[0].previousElementSibling.focus(); closeMenus(); }
  });

  /* ---------------- 范围滑块：--fill 与联动的数字输入 ---------------- */
  document.addEventListener('input', function (e) {
    var el = e.target, box = el.closest('.pdrawer');
    if (!box) return;
    var range = box.querySelector('input[type="range"].range');
    var to = box.querySelector('input[aria-label="Price to"]');
    if (!range) return;
    if (el === range && to) to.value = el.value;
    else if (el === to) range.value = el.value;
    else return;
    range.style.setProperty('--fill', (range.value / (range.max || 100) * 100) + '%');
  });
})();
"""


# ====================================================== 人工资产：ecommerce
# 文案全部从 3zk0obozhoq-1.js 的数组字面量取，不手打。
EC_LANGS = ["English (US)", "Deutsch", "Français", "Español"]
EC_SORTS = ["Most popular", "Price: low to high", "Price: high to low", "Top rated", "Newest"]
EC_NAV = ["Home", "Marketplace", "Features", "Products", "Team", "Contact"]

EC_LANG_MENU = menu_html(
    [{"label": s, "role": "menuitemradio", "active": i == 0} for i, s in enumerate(EC_LANGS)],
    width=176, sync_label=True)
EC_SORT_MENU = menu_html(
    [{"label": s, "role": "menuitemradio", "active": i == 0} for i, s in enumerate(EC_SORTS)],
    width=160, align="end")
EC_MOBILE_MENU = ('<nav class="mobile-menu" aria-label="Store mobile" hidden>'
                  + "".join(f'<a href="#grid">{s}</a>' for s in EC_NAV) + '</nav>')
EC_SCRIM = '<div class="pdrawer-scrim" aria-hidden="true" data-pdrawer="close" hidden></div>'

EC_PATCH_CSS = """
/* ==== ecommerce 还原补丁 ====
   .mobile-menu / .pdrawer-scrim 原本由 React 条件渲染，这里改 [hidden] 切换；
   两者的 display:flex / position:fixed 会盖掉 UA 的 [hidden]{display:none}。 */
.mobile-menu[hidden],.pdrawer-scrim[hidden],.menu[hidden]{display:none!important}
"""

PAGE_ECOMMERCE = PageSpec(
    slug="ecommerce",
    label="E-commerce",
    title="Charm · Store",
    src_dir=DIR_ECOMMERCE,
    src_html="ecommerce.html",
    root_anchor='<div class="page page--shop">',
    id_prefix="ec",
    clean=(
        # 抽屉开关：给触发按钮、关闭按钮打上 data-pdrawer 标记，交互层据此委托
        CleanRule("Filters 触发按钮",
                  r'<button class="btn btn--outline btn--sm">((?:(?!</button>).)*?<span>Filters</span></button>)',
                  r'<button class="btn btn--outline btn--sm" data-pdrawer="open" aria-expanded="false">\1',
                  1, 1, flags=re.S),
        CleanRule("抽屉关闭按钮",
                  r'<button class="iconbtn" aria-label="Close filters">',
                  '<button class="iconbtn" aria-label="Close filters" data-pdrawer="close">', 1, 1),
    ),
    restores=(
        Restore("移动端菜单", r'<button class="menu-toggle".*?</button></div></div>',
                (EC_MOBILE_MENU,), flags=re.S),
        Restore("抽屉遮罩", r'(?=<aside class="pdrawer")', (EC_SCRIM,)),
    ),
    menus=(
        MenuSpec("English (US)", EC_LANG_MENU),
        MenuSpec("Sort", EC_SORT_MENU),
    ),
    patch_css=EC_PATCH_CSS,
    expect_class_counts=(
        ("pcell", 16), ("topcat-tile", 16), ("menu", 2), ("menu__item", 9),
        ("mobile-menu", 1), ("pdrawer", 1), ("pdrawer-scrim", 1), ("segmented__btn", 3),
    ),
)

# ====================================================== 人工资产：marketing
MK_JS = (DIR_MARKETING / "0ggs8-d57fqd2.js").read_text(encoding="utf-8", errors="replace")


def extract_faq(js: str) -> list:
    """→ [(类别名, [(问, [答段落…]), …]), …]"""
    need('\\' not in js[js.find('{key:"Getting started"'):], "FAQ 文案里出现了转义，提取逻辑需升级")
    cats = []
    for m in re.finditer(r'\{key:' + RE_JS_STR + r',Icon:[\w.$]+,items:\[', js):
        start = m.end() - 1
        block = js[start:_bracket_end(js, start) + 1]
        items = []
        for q in re.finditer(r'\{q:' + RE_JS_STR + r',a:\[', block):
            a_start = q.end() - 1
            items.append((q.group(1), re.findall(RE_JS_STR, block[a_start:_bracket_end(block, a_start) + 1])))
        cats.append((m.group(1), items))
    return cats


MK_FAQ = extract_faq(MK_JS)
need(len(MK_FAQ) == 4 and sum(len(c[1]) for c in MK_FAQ) == 40,
     f"FAQ 提取异常：{[(c[0], len(c[1])) for c in MK_FAQ]}")

MK_TIERS = re.findall(r'\{key:' + RE_JS_STR + r',price:' + RE_JS_STR + r',fine:' + RE_JS_STR + r'\}', MK_JS)
need(len(MK_TIERS) == 3, f"定价档位提取异常：{MK_TIERS}")

MK_NAV = re.findall(RE_JS_STR, re.search(r'let l=\[([^\]]*)\]', MK_JS).group(1))
need(MK_NAV == ["Home", "Products", "Blog", "Contact"], f"导航文案异常：{MK_NAV}")

# 两个图标的序列化形式逐字取自快照里已渲染的那一份
MK_ICON_Q = ('<svg xmlns="http://www.w3.org/2000/svg" width="24" height="24" viewBox="0 0 24 24" fill="none" '
             'stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" '
             'class="lucide lucide-circle-question-mark faq__q-icon" aria-hidden="true">'
             '<circle cx="12" cy="12" r="10"></circle>'
             '<path d="M9.09 9a3 3 0 0 1 5.83 1c0 2-3 3-3 3"></path><path d="M12 17h.01"></path></svg>')
MK_ICON_CHEV = ('<svg xmlns="http://www.w3.org/2000/svg" width="24" height="24" viewBox="0 0 24 24" fill="none" '
                'stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" '
                'class="lucide lucide-chevron-down faq__chev" aria-hidden="true">'
                '<path d="m6 9 6 6 6-6"></path></svg>')


def faq_panel(items, open_first: bool, hidden: bool) -> str:
    """一个 FAQ 分类面板。四个分类的面板全部渲染进 DOM（三个 hidden）：

    既符合「状态只在 DOM 上」，也让 Ctrl+F 能搜到全部 40 条问答，代价约 +25 KB。
    """
    out = []
    for i, (q, answers) in enumerate(items):
        opened = open_first and i == 0
        out.append(
            f'<div class="faq__item{" is-open" if opened else ""}">'
            f'<button class="faq__q" aria-expanded="{"true" if opened else "false"}">'
            f'{MK_ICON_Q}<span class="faq__q-text">{esc(q)}</span>{MK_ICON_CHEV}</button>'
            '<div class="faq__a-wrap"><div class="faq__a"><div class="faq__a-body">'
            + "".join(f'<p>{esc(a)}</p>' for a in answers) +
            '</div></div></div></div>')
    return f'<div class="faq__panel"{" hidden" if hidden else ""}>' + "".join(out) + '</div>'


MK_EXTRA_PANELS = "".join(faq_panel(items, open_first=False, hidden=True)
                          for _, items in MK_FAQ[1:])
MK_MOBILE_MENU = ('<nav class="mobile-menu" aria-label="Primary mobile" hidden>'
                  + "".join(f'<a href="#features">{s}</a>' for s in MK_NAV) + '</nav>')

MK_PATCH_CSS = """
/* ==== marketing 还原补丁 ====
   .faq__panel/.mobile-menu 都是 display:flex，会盖掉 UA 的 [hidden]{display:none}。 */
.faq__panel[hidden],.mobile-menu[hidden]{display:none!important}
"""

MK_JS_CODE = r"""
/* ==== marketing 专属交互 ==== */
(function () {
  'use strict';
  var page = document.querySelector('[data-page="marketing"]') || document;
  var slice = function (x) { return Array.prototype.slice.call(x); };

  page.addEventListener('click', function (e) {
    var t = e.target, el;
    if (!t.closest) return;

    /* FAQ 分类：按位置对应面板（第 n 个按钮 ↔ 第 n 个面板），不用 id 关联 */
    if ((el = t.closest('.faq__cat'))) {
      var cats = slice(el.parentNode.children);
      var panels = slice(el.closest('.faq__grid').querySelectorAll('.faq__panel'));
      var i = cats.indexOf(el);
      cats.forEach(function (b, k) {
        b.classList.toggle('is-active', k === i);
        b.setAttribute('aria-selected', String(k === i));
      });
      panels.forEach(function (p, k) { p.hidden = k !== i; });
      return;
    }

    /* FAQ 手风琴：单开，再点收起（原实现 onClick 是 o(t?-1:s)） */
    if ((el = t.closest('.faq__q'))) {
      var item = el.parentNode, was = item.classList.contains('is-open');
      slice(item.parentNode.children).forEach(function (it) {
        it.classList.remove('is-open');
        it.querySelector('.faq__q').setAttribute('aria-expanded', 'false');
      });
      if (!was) { item.classList.add('is-open'); el.setAttribute('aria-expanded', 'true'); }
      return;
    }

    /* 计费周期：三档价格写在按钮的 data-price / data-fine 上 */
    if ((el = t.closest('.offer .segmented__btn'))) {
      var offer = el.closest('.offer');
      offer.querySelector('.offer__price strong').textContent = el.dataset.price;
      offer.querySelector('.offer__fine').textContent = el.dataset.fine;
      return;   /* is-active / aria-selected 由共享的 .segmented__btn 规则处理 */
    }

    /* 功能展示的分段控件：原实现只切高亮，卡片三张始终全渲染 */
    if ((el = t.closest('.fshow__seg-btn'))) {
      slice(el.parentNode.children).forEach(function (b) {
        var on = b === el;
        b.classList.toggle('is-active', on);
        b.setAttribute('aria-selected', String(on));
      });
      return;
    }
  });
})();
"""

PAGE_MARKETING = PageSpec(
    slug="marketing",
    label="Marketing",
    title="Charm · Marketing",
    src_dir=DIR_MARKETING,
    src_html="marketing.html",
    root_anchor='<div class="page">',
    id_prefix="ma",
    clean=tuple(
        CleanRule(f"定价档位 {key}",
                  r'(<button role="tab" aria-selected="(?:true|false)" class="segmented__btn(?: is-active)?)"'
                  r'>' + re.escape(key) + r'</button>',
                  r'\1" data-price="' + price + r'" data-fine="' + fine + r'">' + key + '</button>', 1, 1)
        for key, price, fine in MK_TIERS
    ),
    restores=(
        Restore("移动端菜单", r'<button class="menu-toggle".*?</button></div></div>',
                (MK_MOBILE_MENU,), flags=re.S),
        Restore("FAQ 后三个分类面板", r'(?=</div><div class="faq__foot">)', (MK_EXTRA_PANELS,)),
    ),
    patch_css=MK_PATCH_CSS,
    js=MK_JS_CODE,
    inline_imgs=True,
    expect_class_counts=(
        ("faq__cat", 4), ("faq__panel", 4), ("faq__item", 40), ("faq__q", 40),
        ("mobile-menu", 1), ("segmented__btn", 3), ("fshow__seg-btn", 4),
        ("logoband__logo", 6), ("trust-logo", 5),
    ),
)

# ==================================================== 人工资产：application
AP_JS = (DIR_APPLICATION / "3cqgvb_keqluz.js").read_text(encoding="utf-8", errors="replace")


def page_scripts(page_dir: Path, html_name: str) -> str:
    """把该页 <script src> 引用的 chunk 拼起来——图标定义散落在多个 chunk 里
    （credit-card / trending-up / x 在共享的 2t6zzw8wl1772.js）。
    只拼这一页真正加载的那些，不扫整个目录。"""
    html = (page_dir / html_name).read_text(encoding="utf-8", errors="replace")
    names = re.findall(r'<script src="\./([^"]+)"', html)
    need(names, f"{html_name} 里找不到 <script src>")
    return "\n".join((page_dir / n).read_text(encoding="utf-8", errors="replace")
                     for n in names if (page_dir / n).exists())


AP_ICON_JS = page_scripts(DIR_APPLICATION, "application.html")


def ico(name: str) -> str:
    return lucide_svg(AP_ICON_JS, name)


# 五份文案列表，全部是 chunk 里干净的数组字面量
AP_ACTIONS = js_array(AP_JS, r'(?<![\w$])ej=')          # Actions 菜单
AP_FILTERS = js_array(AP_JS, r'(?<![\w$])eO=')          # Filters 菜单（多选）
AP_PERPAGE = js_array(AP_JS, r'(?<![\w$])eA=')          # 每页行数
AP_WIDGET = js_array(AP_JS, r'(?<![\w$])Ox=')           # 单个 widget 的操作
AP_RANGES = js_array(AP_JS, r'(?<![\w$])Of=')           # 时间范围
need([len(AP_ACTIONS), len(AP_FILTERS), len(AP_PERPAGE), len(AP_WIDGET), len(AP_RANGES)] == [3, 5, 4, 3, 4],
     f"application 文案列表长度异常：{[AP_ACTIONS, AP_FILTERS, AP_PERPAGE, AP_WIDGET, AP_RANGES]}")


def range_menu(width, align=None, active=None):
    return menu_html([{"label": s, "role": "menuitemradio", "active": s == active} for s in AP_RANGES],
                     width=width, align=align)


AP_MENUS = (
    # 账户菜单（右上角头像）
    MenuSpec("Account menu", menu_html([
        {"label": "Profile", "icon": ico("user")},
        {"label": "Settings", "icon": ico("settings")},
        {"label": "Billing", "icon": ico("credit-card")},
        "divider",
        {"label": "Sign out", "icon": ico("log-out"), "danger": True},
    ], width=244, align="end")),
    # 表格工具条
    MenuSpec("Actions", menu_html([{"label": s} for s in AP_ACTIONS], width=200)),
    MenuSpec("Filters", menu_html([{"label": s, "check": True} for s in AP_FILTERS],
                                  width=220, keep_open=True)),   # 原实现 closeOnSelect:!1
    MenuSpec("10", menu_html([{"label": s, "role": "menuitemradio", "active": i == 0}
                              for i, s in enumerate(AP_PERPAGE)], width=144)),
    # 每一行的操作菜单（10 行复用同一份模板）
    MenuSpec("Actions for *", menu_html([
        {"label": "Archive staff", "icon": ico("archive")},
        {"label": "Edit staff", "icon": ico("pencil")},
        {"label": "Delete staff", "icon": ico("trash-2"), "danger": True},
    ], width=188, align="end")),
    # 各 widget 的时间范围（宽度 / 对齐 / 选中项都逐个对应源码里的 props）
    MenuSpec("Widget options", menu_html(
        [{"label": s, "danger": s == "Delete widget"} for s in AP_WIDGET], width=188, align="end")),
    MenuSpec("Last 7 days", range_menu(176, active="Last 7 days")),
    MenuSpec("Last week", range_menu(176, align="end", active="Last 7 days")),
    MenuSpec("Last 12 months", range_menu(188, align="end", active="Last 90 days")),
    MenuSpec("This week", range_menu(176)),
)

# —— Revenue details modal（`Ol` 组件，快照里完全不存在） ——
AP_MONTHS = re.findall(r'\{m:"(\w+)",now:(\d+),prev:(\d+)\}', AP_JS)
need(len(AP_MONTHS) == 12, f"月度营收数据提取异常：{len(AP_MONTHS)} 条")
AP_MODAL_ROWS = "".join(
    f'<tr><td>{m}</td><td>${now}k</td><td>${prev}k</td><td>'
    f'<span class="badge badge--success">{ico("trending-up")} +'
    f'{int((int(now) - int(prev)) / int(prev) * 100 + 0.5)}%</span></td></tr>'
    for m, now, prev in reversed(AP_MONTHS[-6:])          # [...Oh].reverse().slice(0,6)
)
AP_MODAL = (
    '<div class="modal-scrim" data-modal="close" hidden>'
    '<div class="modal" role="dialog" aria-modal="true" aria-label="Revenue details" tabindex="-1">'
    '<div class="modal__head"><h2 class="modal__title">Revenue details</h2>'
    f'<button class="modal__close" aria-label="Close dialog" data-modal="close">{ico("x")}</button></div>'
    '<div class="modal__body">'
    '<p class="modal__intro">Monthly revenue across all centers, most recent first.</p>'
    '<table class="ovw-table"><thead><tr><th>Month</th><th>This year</th><th>Last year</th>'
    f'<th>Change</th></tr></thead><tbody>{AP_MODAL_ROWS}</tbody></table></div>'
    '<div class="modal__foot">'
    '<button class="btn btn--primary btn--sm" data-modal="close"><span>Close</span></button>'
    '</div></div></div>'
)

AP_SIDEBAR_SCRIM = '<div class="appsidebar-scrim" aria-hidden="true" data-sidebar="close" hidden></div>'
AP_BILLING_SUB = ('<div class="appsidebar__children" hidden>'
                  '<a href="#invoices">Invoices</a><a href="#payouts">Payouts</a></div>')
AP_SELECTED = (f'<p class="dtx__selected" hidden>{ico("eye")} '
               '<span data-selected-count>0</span> selected</p>')

AP_PATCH_CSS = """
/* ==== application 还原补丁 ====
   这些浮层原本由 React 条件渲染，这里改 [hidden] 切换；它们的
   display:flex|grid / position:fixed 都会盖掉 UA 的 [hidden]{display:none}。 */
.modal-scrim[hidden],.appsidebar-scrim[hidden],.appsidebar__children[hidden],
.dtx__selected[hidden],.menu[hidden]{display:none!important}
"""

AP_JS_CODE = r"""
/* ==== application 专属交互 ==== */
(function () {
  'use strict';
  var page = document.querySelector('[data-page="application"]') || document;
  var slice = function (x) { return Array.prototype.slice.call(x); };

  /* 表格选中态不存 Set，直接从 DOM 数 :checked —— 没有第二份状态可失同步 */
  function syncTable(table) {
    var rows = slice(table.querySelectorAll('tbody tr'));
    var n = 0;
    rows.forEach(function (tr) {
      var on = tr.querySelector('.dtable__pick input').checked;
      tr.classList.toggle('is-picked', on);
      if (on) n++;
    });
    table.querySelector('thead .dtable__pick input').checked = n === rows.length;
    var tag = table.closest('.dtx, [data-page], body').querySelector('.dtx__selected');
    if (tag) {
      tag.hidden = n === 0;
      tag.querySelector('[data-selected-count]').textContent = String(n);
    }
  }

  page.addEventListener('change', function (e) {
    var box = e.target.closest && e.target.closest('.dtable__pick input');
    if (!box) return;
    var table = box.closest('table');
    if (box.closest('thead')) {
      slice(table.querySelectorAll('tbody .dtable__pick input')).forEach(function (b) {
        b.checked = box.checked;
      });
    }
    syncTable(table);
    /* promote 那一列的开关是纯 CSS :checked 驱动的，不需要 JS */
  });

  page.addEventListener('click', function (e) {
    var t = e.target, el;
    if (!t.closest) return;

    /* 侧栏可折叠分组：按钮之后紧跟它的 .appsidebar__children */
    if ((el = t.closest('.appsidebar__item[aria-expanded]'))) {
      var open = el.getAttribute('aria-expanded') !== 'true';
      el.setAttribute('aria-expanded', String(open));
      el.classList.toggle('is-active', open);
      el.querySelector('.chev').classList.toggle('is-open', open);
      var kids = el.nextElementSibling;
      if (kids && kids.classList.contains('appsidebar__children')) kids.hidden = !open;
      return;
    }

    /* 窄屏侧栏：汉堡开、遮罩关 */
    if ((el = t.closest('[aria-label="Open sidebar"],[data-sidebar]'))) {
      var on = !el.hasAttribute('data-sidebar');
      page.querySelector('.appsidebar').classList.toggle('is-open', on);
      page.querySelector('.appsidebar-scrim').hidden = !on;
      page.querySelector('[aria-label="Open sidebar"]').setAttribute('aria-expanded', String(on));
      return;
    }

    /* Revenue details 弹窗 */
    if ((el = t.closest('[data-modal]'))) {
      /* 点 scrim 只有落在 scrim 本身时才关（原实现判的是 e.target===e.currentTarget） */
      if (el.classList.contains('modal-scrim') && t !== el) return;
      page.querySelector('.modal-scrim').hidden = true;
      return;
    }
    if ((el = t.closest('.ovw__actions .btn')) && /Details/.test(el.textContent)) {
      var scrim = page.querySelector('.modal-scrim');
      scrim.hidden = false;
      scrim.querySelector('.modal').focus();
      return;
    }
  });

  document.addEventListener('keydown', function (e) {
    if (e.key !== 'Escape') return;
    var scrim = page.querySelector('.modal-scrim');
    if (scrim && !scrim.hidden) scrim.hidden = true;
  });
})();
"""

PAGE_APPLICATION = PageSpec(
    slug="application",
    label="Application",
    title="Charm · Application",
    src_dir=DIR_APPLICATION,
    src_html="application.html",
    root_anchor='<div class="appshell">',
    id_prefix="ap",
    restores=(
        Restore("侧栏遮罩", r'(?=<aside class="appsidebar")', (AP_SIDEBAR_SCRIM,)),
        Restore("Billing 子菜单",
                r'<button class="appsidebar__item" aria-expanded="false">.*?Billing.*?</button>',
                (AP_BILLING_SUB,), flags=re.S),
        Restore("Revenue details 弹窗", r'<span>Details</span></button>', (AP_MODAL,)),
        Restore("已选计数", r'(?=</div></main>)', (AP_SELECTED,)),
    ),
    menus=AP_MENUS,
    patch_css=AP_PATCH_CSS,
    js=AP_JS_CODE,
    fix_recharts=True,
    expect_class_counts=(
        ("menu", 21), ("dtx__dots", 10), ("recharts-surface", 8),
        ("appsidebar__children", 2), ("appsidebar-scrim", 1),
        ("modal", 1), ("modal-scrim", 1), ("dtx__selected", 1), ("toggle", 10),
    ),
)

PAGES = (PAGE_MARKETING, PAGE_APPLICATION, PAGE_ECOMMERCE, PAGE_COMPONENTS)
DEFAULT_SLUG = "marketing"       # 默认打开的 tab：与原站 tab 顺序的第一项一致


# ================================================================== 构建管线
def slice_body(html: str, page: PageSpec) -> str:
    """步骤 A：字节级切出根节点。"""
    i = html.find(page.root_anchor)
    j = html.find(BODY_END_ANCHOR)
    need(i > 0 and j > i, f"[{page.slug}] 找不到正文边界锚点，源页面结构可能已变")
    body = html[i:j]
    body = re.sub(r'<!--\$--><!--/\$-->\s*$', '', body).rstrip()   # Next.js 结尾残留
    need('<script' not in body, f"[{page.slug}] 正文内不应残留 <script>")
    need(body.count('<div') >= body.count('</div>') - 1, f"[{page.slug}] div 开闭明显不平衡")
    return body


def clean_body(body: str, page: PageSpec) -> str:
    """步骤 B：跑页面专属清洗 → 外链改写 → 去 React 文本分隔注释。"""
    for rule in page.clean:
        body = rule.apply(body)

    # 自身页内锚点：绝对 URL 还原为 `#xxx`
    body, n_self = re.subn(VERCEL + '/' + page.slug + '#', '#', body)
    # 其余（含指向自身但无 hash 的品牌链接）→ tab 路由
    body, n_cross = re.subn(VERCEL + r'/(\w+)', r'#p=\1', body)
    need(n_self + n_cross >= 8, f"[{page.slug}] 外链改写数异常：自身 {n_self} + 跨页 {n_cross}")
    need('vercel.app' not in body, f"[{page.slug}] 仍有 vercel 外链残留")

    body = body.replace('<!-- -->', '')      # 纯静态文本的拼接分隔符，去掉即合并文本节点
    need('<!--' not in body, f"[{page.slug}] 仍有未处理的 HTML 注释")
    return body


def restore_hidden(body: str, page: PageSpec) -> str:
    """步骤 C：补回被 React 卸载、未出现在快照里的 DOM。"""
    for r in page.restores:
        body = r.apply(body)
    return body


RE_MENU_TRIGGER = r'<button[^>]*aria-haspopup="menu"[^>]*>(?:(?!</button>).)*</button>'


def restore_menus(body: str, page: PageSpec) -> str:
    """步骤 C2：给每个下拉触发器插回它的面板。

    双向断言：没有触发器落空，也没有模板闲置——这两条中任何一条被打破，
    都说明源页面变了或模板表写漏了。
    """
    if not page.menus:
        return body

    def match(key):
        for ms in page.menus:
            if ms.key.endswith('*') and key.startswith(ms.key[:-1]):
                return ms
            if ms.key == key:
                return ms
        return None

    hits = list(re.finditer(RE_MENU_TRIGGER, body, re.S))
    need(hits, f"[{page.slug}] 找不到任何下拉触发器")
    used, plan = set(), []
    for m in hits:
        btn = m.group(0)
        al = re.search(r'aria-label="([^"]*)"', btn)
        key = al.group(1) if al else re.sub(r'<[^>]+>', '', btn).strip()
        ms = match(key)
        need(ms, f"[{page.slug}] 触发器「{key}」没有对应的菜单模板")
        used.add(ms.key)
        plan.append((m.end(), ms.panel))
    idle = [ms.key for ms in page.menus if ms.key not in used]
    need(not idle, f"[{page.slug}] 有模板未被任何触发器用到：{idle}")

    for pos, panel in reversed(plan):      # 从后往前插，偏移不失效
        body = body[:pos] + panel + body[pos:]
    return body


def inline_images(body: str, page: PageSpec) -> str:
    """步骤 D：<img src="./x.svg"> → data: URI。"""
    names = sorted(set(re.findall(r'src="\./([^"]+)"', body)))
    need(names, f"[{page.slug}] inline_imgs=True 但正文里没有 ./ 引用")
    for name in names:
        f = page.src_dir / name
        need(f.exists(), f"[{page.slug}] 缺少图片资源 {name}")
        mime = {'svg': 'image/svg+xml', 'png': 'image/png',
                'jpg': 'image/jpeg', 'webp': 'image/webp'}[name.rsplit('.', 1)[1].lower()]
        b64 = base64.b64encode(f.read_bytes()).decode()
        body = body.replace(f'src="./{name}"', f'src="data:{mime};base64,{b64}"')
    return body


def fix_recharts(body: str) -> str:
    """步骤 E：让 recharts 的图表跟着容器缩放。

    `<svg class="recharts-surface">` 本就带 viewBox + width:100%，所以病灶不在它：
      ① ResponsiveContainer 在服务端渲染出一个 `width:0;height:0;overflow:visible`
         的中间层，子元素的 100% 于是等于 0；
      ② `.recharts-wrapper` 被写死成快照当时的像素尺寸（798×320 等）。
    两处都改成 100% 即可，不引入 recharts 库。
    """
    body, n1 = re.subn(r'<div style="width:0;height:0;overflow:visible">',
                       '<div style="width:100%;height:100%">', body)
    body, n2 = re.subn(
        r'(class="recharts-wrapper" style="position: relative; cursor: default;) '
        r'width: \d+px; height: \d+px;', r'\1 width: 100%; height: 100%;', body)
    need(n1 == n2 == 8, f"recharts 容器修复命中异常：零尺寸盒 {n1} 个 / wrapper {n2} 个，期望各 8")
    return body


def rename_svg_ids(body: str, page: PageSpec) -> tuple:
    """步骤 E：逐 <svg> 给内部 id 加页前缀 + svg 序号。

    实测四页的 `url(#x)` 引用全部落在定义 x 的那个 <svg> 内部（跨 svg 引用 = 0），
    且 svg 无嵌套、引用形式只有 fill="url(#x)" 一种 —— 所以逐 svg 局部改名即充分。

    坚持字节级 regex，不引入 HTML parser：parser 重新序列化会把 <clippath> /
    <lineargradient> 这类 SVG 标签名的大小写破坏，导致引用静默失效。
    """
    parts, out, idx, renamed = [], [], 0, 0
    pos = 0
    for m in re.finditer(r'<svg\b.*?</svg>', body, re.S):
        need(m.group(0).count('<svg') == 1, f"[{page.slug}] 出现嵌套 <svg>，逐 svg 改名不再成立")
        need('xlink:href' not in m.group(0) and not re.search(r'(?<!\w)href="#', m.group(0)),
             f"[{page.slug}] svg 内出现 href 引用，需扩展改名规则")
        out.append(body[pos:m.start()])
        sv = m.group(0)
        ids = re.findall(RE_ID, sv)
        if ids:
            idx += 1
            for old in ids:
                new = f'{page.id_prefix}{idx}_{old}'
                sv = sv.replace(f'id="{old}"', f'id="{new}"')
                sv = sv.replace(f'url(#{old})', f'url(#{new})')
                renamed += 1
        out.append(sv)
        pos = m.end()
    out.append(body[pos:])
    body = ''.join(out)

    # 改完之后，正文里不应再有不带页前缀的 url(#…)
    stray = [x for x in re.findall(r'url\(#([^)]*)\)', body) if not x.startswith(page.id_prefix)]
    need(not stray, f"[{page.slug}] 仍有未改名的 svg 引用：{stray[:5]}")
    return body, renamed


def check_page(body: str, page: PageSpec) -> None:
    """机械预言机：class 出现次数必须与预期完全一致。"""
    for cls, expect in page.expect_class_counts:
        got = len(re.findall(r'class="[^"]*(?<![\w-])' + re.escape(cls) + r'(?![\w-])', body))
        need(got == expect, f"[{page.slug}] class .{cls} 出现 {got} 次，期望 {expect}")
    if not page.inline_imgs:
        need('src=' not in body, f"[{page.slug}] 正文内不应有 src=（图标全为内联 SVG）")
    # 每个下拉触发器后面都必须紧跟它的面板（components 走自己的 .ds__dd 机制）
    for m in re.finditer(RE_MENU_TRIGGER, body, re.S):
        nxt = body[m.end():m.end() + 40]
        need(re.match(r'<(?:div|button) class="(?:menu|ds__dd-scrim)\b', nxt),
             f"[{page.slug}] 下拉触发器后面没有面板：…{body[m.start():m.start() + 90]}")


def check_icons(js: str, snapshot: str, names) -> None:
    """预言机：凡是快照里已渲染过的图标，生成结果必须与之逐字节相同。

    这样才敢用同一个生成器去补 archive / pencil / trash-2 / log-out 这四个
    快照里根本没出现过的图标。
    """
    for name in names:
        want = re.search(r'<svg[^>]*class="lucide lucide-' + name + r'"[^>]*>.*?</svg>',
                         snapshot, re.S)
        need(want, f"快照里找不到已渲染的 lucide-{name}，无法对照")
        need(lucide_svg(js, name) == want.group(0),
             f"图标 lucide-{name} 生成结果与快照不一致：\n  生成 {lucide_svg(js, name)}\n  快照 {want.group(0)}")


def build_page(page: PageSpec) -> str:
    f = page.src_dir / page.src_html
    need(f.exists(), f"缺少源文件 {page.src_html}")
    html = f.read_text(encoding="utf-8", errors="replace")
    if page.slug == "application":
        check_icons(AP_ICON_JS, html, ("user", "settings", "credit-card", "eye", "x", "ellipsis"))
    body = restore_menus(restore_hidden(clean_body(slice_body(html, page), page), page), page)
    if page.inline_imgs:
        body = inline_images(body, page)
    if page.fix_recharts:
        body = fix_recharts(body)
    body, _ = rename_svg_ids(body, page)
    check_page(body, page)
    return body


# ------------------------------------------------------------------ CSS 组装
def classes_in(html: str) -> set:
    out = set()
    for m in re.findall(r'class="([^"]*)"', html):
        out.update(m.split())
    return out


def filter_css_by_classes(css: str, allowed: set) -> str:
    """按 class token 集合过滤规则；递归进 @media。

    判据是「选择器里出现的每个 class 都在白名单内」，而非子串匹配——
    后者会漏掉 .card__title，又会误收 .lcard__actions .btn 之类。
    """
    def keep_selector_list(sel_list: str) -> str:
        kept = []
        for sel in sel_list.split(','):
            toks = re.findall(r'\.(-?[_a-zA-Z][\w-]*)', sel)
            if toks and all(t in allowed for t in toks):
                kept.append(sel.strip())
        return ','.join(kept)

    out, i, n = [], 0, len(css)
    while i < n:
        if css[i] == '@':
            j = css.find('{', i)
            if j < 0:
                break
            at = css[i:j].strip()
            depth, k = 1, j + 1
            while k < n and depth:
                if css[k] == '{':
                    depth += 1
                elif css[k] == '}':
                    depth -= 1
                k += 1
            if at.startswith(('@media', '@supports')):
                inner = filter_css_by_classes(css[j + 1:k - 1], allowed)
                if inner.strip():
                    out.append(f'{at}{{{inner}}}')
            i = k
            continue
        j = css.find('{', i)
        if j < 0:
            break
        k = css.find('}', j)
        if k < 0:
            break
        sel = keep_selector_list(css[i:j])
        if sel:
            out.append(f'{sel}{{{css[j + 1:k].strip()}}}')
        i = k + 1
    return ''.join(out)


def build_font_css(pack: FontPack) -> str:
    """内嵌 woff2（base64），产物零外部请求。

    latin 包是可变字体，一族一个文件，字重区间恒为 100–900；
    cjk 包是一堆静态字面，字重区间由 _make_cjk_fonts.py 逐文件算好写在条目里。
    """
    need(pack.file.exists(), f"缺少字体数据 {pack.file.name}"
         + ("（先跑 python3 _make_cjk_fonts.py 生成）" if pack.key == "cjk" else ""))
    fonts = json.loads(pack.file.read_text())
    css = [f"/* ==== 内嵌字体（{pack.label}）：产物零外部请求 ==== */"]
    for f in fonts:
        css.append(
            f"@font-face{{font-family:'{f['family']}';font-style:normal;"
            f"font-weight:{f.get('weight', '100 900')};font-display:swap;"
            f"src:url(data:font/woff2;base64,{f['b64']}) format('woff2')}}"
        )
    return '\n'.join(css)


def build_tokens_css(pack: FontPack) -> str:
    tok = F_CSS_TOKENS.read_text(encoding="utf-8", errors="replace")
    i = tok.find(':root{--heading:')
    need(i > 0, "找不到 :root 令牌块")
    css = tok[i:]
    need('url(' not in css, "令牌块内不应有 url()")
    # 原本由 <html> 上的 CSS-module 哈希类注入，这里直接定义，产物中不再有哈希类
    return css + (f'\n:root{{--font-inter:{pack.sans};--font-fragment-mono:{pack.mono};'
                  f'--font-display:{pack.display}}}')


def build_site_css(used: set) -> str:
    raw = F_CSS_SITE.read_text(encoding="utf-8", errors="replace")
    # lucide-* / recharts-* 是第三方运行时打上的 class，两份 CSS 里都没有对应规则
    # （靠祖先选择器上色）。把它们排除在白名单外，证明不会漏掉任何规则。
    need('lucide' not in raw and 'recharts' not in raw,
         "站点 CSS 里出现了 lucide/recharts 选择器，白名单不能再排除它们")
    allowed = {c for c in used if not c.startswith(('lucide', 'recharts'))}
    css = filter_css_by_classes(raw, allowed)
    need('@media' in css, "CSS-2 应包含 @media 内的规则")
    return css


def strip_missing_bg(css: str) -> str:
    """.hero-pattern / .shero-pattern 引用的 hero-pattern-swirl.svg 四目录皆无。

    只删这一条 background-image 声明，保留 opacity / mask —— 不自造替代纹理：
    那是设计资产，猜错比没有更糟。
    """
    css, n = re.subn(r'background-image:url\([^)]*hero-pattern-swirl[^)]*\);?', '', css)
    need(n <= 2, f"hero 纹理声明命中 {n} 次，超出预期的 .hero-pattern/.shero-pattern 两处")
    need('hero-pattern-swirl' not in css, "仍有 hero 纹理引用残留")
    return css


# ------------------------------------------------------------------ 页面组装
def render_note(pages: tuple, merged: bool, pack: FontPack, font_css_len: int) -> str:
    lines = []
    for p in pages:
        sha = hashlib.sha256((p.src_dir / p.src_html).read_bytes()).hexdigest()[:16]
        lines.append(f"        {p.src_html:<18} sha256:{sha}…")
    src_list = "\n".join(lines)
    if not merged:
        p = pages[0]
        sha = hashlib.sha256((p.src_dir / p.src_html).read_bytes()).hexdigest()[:16]
        extra = ("""  4. 交互由约 150 行原生 JS 重写，状态只存放在 DOM 属性上。
     刻意未加：body 滚动锁、focus trap、下划线标签页交互
     （原页面该组本就是静态的）。
""" if p.slug == "components" else """  4. 交互由原生 JS 重写，状态只存放在 DOM 属性上。
  5. 每个 <svg> 内部的 id 都加了页前缀（见合并版说明）。
""")
        return f"""<!--
  Charm · {p.title} 单文件复刻版
  ---------------------------------------------------------------
  来源：https://charm-typeui-b08baaa4.vercel.app/{p.slug}
        （本地保存件 {p.src_html}, sha256:{sha}…）
  生成：design skill/_build_charm.py --only={p.slug}

  这是**单页版**：没有顶部 tab bar，供像素回归对照用
  （合并版见 charm-preview.html）。

  与原页面的已知差异：
{pack.font_note}
  2. modal / drawer / 下拉菜单等浮层在保存的快照里并不存在
     （React 未渲染），此处按该页的编译产物 chunk 逐字还原。
  3. 原实现靠卸载节点隐藏浮层，本复刻改用 [hidden] 切换。
{extra}
  需要 Chrome/Edge 119+、Safari 16.4+、Firefox 128+
  （用到 color-mix()、rgb(from …) 与 :has()）。
  全部资源已内嵌，可离线双击打开。
-->"""
    return f"""<!--
  Charm 预览页合集 · 单文件复刻版
  ---------------------------------------------------------------
  来源：https://charm-typeui-b08baaa4.vercel.app/{{marketing,application,ecommerce,components}}
        本地保存件：
{src_list}
  生成：design skill/_build_charm.py

  底部居中的悬浮切换器四选一（位置与样式沿用原站），深链形如
  `<file>#p=ecommerce`。切换器是 position:fixed 浮层、不参与布局，
  因此四页的几何与各自的单页版完全一致。
  合并成一个文件而非四个的理由：{human(font_css_len)} 的内嵌字体只需出现一次。

  与原页面的已知差异：
{pack.font_note}
  2. modal / drawer / 下拉菜单等浮层在保存的快照里并不存在
     （React 未渲染），此处按各页的编译产物 chunk 逐字还原；
     原实现靠卸载节点隐藏，本复刻改用 [hidden] 切换。
  3. 交互由原生 JS 重写，状态只存放在 DOM 属性上。
  4. 每个 <svg> 内部的 id 都加了页前缀以消除跨页冲突。
     ⚠ 这顺带修掉了原页面的一个 bug：E-commerce 页的 chBg1/chBg7 各被
     定义了两次，导致其中 2 个商品图取到了别人的渐变。改名后各自独立，
     因此这两张图与原站有可见色差——是修正，不是回归。
  5. .hero-pattern / .shero-pattern 的底纹图片（hero-pattern-swirl.svg）
     不在保存件里，只删掉了那一条 background-image，未自造替代纹理。
  6. application 的 recharts 图表：ResponsiveContainer 在快照里留下一个
     零尺寸中间层、wrapper 被写死成当时的像素宽高，两处都改成 100%，
     图表因此跟随容器缩放（未引入 recharts 运行时）。

  需要 Chrome/Edge 119+、Safari 16.4+、Firefox 128+
  （用到 color-mix()、rgb(from …) 与 :has()）。
  全部资源已内嵌，可离线双击打开。
-->"""


def render_shell(pages: tuple, bodies: dict) -> str:
    # 按钮用自己的 .pv-switch__btn 而非页面里的 .segmented__btn：外壳与被预览的
    # 设计系统必须分家，否则 SHARED_JS 里那条 .segmented__btn 规则会顺带命中外壳
    # 按钮，与 SHELL_JS 的 show() 重复做同一件事。
    tabs = "".join(
        f'<button class="pv-switch__btn" type="button" role="tab" id="pv-tab-{p.slug}" '
        f'aria-controls="pv-{p.slug}" aria-selected="false" tabindex="-1" '
        f'data-goto="{p.slug}">{p.label}</button>'
        for p in pages
    )
    head = (f'<div class="pv-switch" role="tablist" aria-label="Preview surface" '
            f'data-default="{DEFAULT_SLUG}">{tabs}</div>')
    panels = "\n".join(
        f'<div class="pv" id="pv-{p.slug}" data-page="{p.slug}" role="tabpanel" '
        f'aria-labelledby="pv-tab-{p.slug}" hidden>{bodies[p.slug]}</div>'
        for p in pages
    )
    return head + "\n" + panels


def assemble(pages: tuple, bodies: dict, merged: bool, pack: FontPack) -> str:
    used = set()
    for p in pages:
        used |= classes_in(bodies[p.slug])
    if merged:
        used |= classes_in(render_shell(pages, {p.slug: "" for p in pages}))

    css_site = strip_missing_bg(build_site_css(used))
    css_extra = []
    for p in pages:
        for f in p.extra_css:
            css_extra.append(f.read_text(encoding="utf-8", errors="replace"))
    for c in css_extra:
        need('url(' not in c, "组件库 CSS 不应有 url()")

    # 完备性预言机：CSS 里定义过的 ds__* 若在 DOM 中一个都没出现，说明还原漏了
    if any(p.slug == "components" for p in pages):
        defined = set(re.findall(r'\.(ds__[\w-]+)\b', "".join(css_extra)))
        missing = sorted(c for c in defined if c not in used)
        need(not missing, "以下 class 有样式却无 DOM，隐藏态还原不完整：" + ", ".join(missing))

    # 合并顺序必须与原 <link> 的 data-precedence 一致：
    # .btn:focus-visible 在 CSS-2，.btn.is-focus 在 CSS-3，颠倒会改变焦点表现
    css_font = build_font_css(pack)          # cjk 包有几十 MB，只解一次，供调用方复用
    chunks = [css_font, build_tokens_css(pack), css_site] + css_extra
    chunks += [p.patch_css for p in pages if p.patch_css]
    if merged:
        chunks.append(SHELL_PATCH_CSS)
    css = "\n".join(chunks)

    js_parts = [p.js for p in pages if p.js]
    if any(p.slug != "components" for p in pages):
        js_parts.append(SHARED_JS)
    if merged:
        body = render_shell(pages, bodies)
        title = "Charm · Preview"
        js_parts.append(SHELL_JS)
    else:
        body = bodies[pages[0].slug]
        title = pages[0].title
    js = "\n".join(js_parts)

    return f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>{title}</title>
{render_note(pages, merged, pack, len(css_font))}
<style>
{css}
</style>
</head>
<body>
{body}
<script>
{js}
</script>
</body>
</html>
""", css_site, css_extra, css_font


def final_checks(out: str) -> None:
    # 只检查真正会发起网络请求的位置：注释里的来源说明与 data: URI 都不算
    probe = re.sub(r'<!--.*?-->', '', out, flags=re.S)
    need(not re.search(r'\ssrc\s*=\s*["\'](?!data:)', probe), "产物中仍有 src= 外部引用")
    need(not re.search(r'<link\b', probe), "产物中仍有 <link>")
    # url( 后面可能带引号，data: URI（.select 的下拉箭头）与 svg 内部引用 url(#x) 都合法
    need(not re.search(r'url\(\s*(?!["\']?data:)(?!#)', probe), "产物 CSS 中仍有非 data: 的 url()")
    need(not re.search(r'href\s*=\s*["\'](?!#)', probe), "产物中仍有非页内锚点的 href")
    ids = re.findall(RE_ID, probe)
    dup = sorted({i for i in ids if ids.count(i) > 1})
    need(not dup, f"产物中 id 重复：{dup[:8]}")


def human(n: int) -> str:
    return f"{n / 1048576:.1f} MB" if n >= 1048576 else f"{n / 1024:.0f} KB"


def build_one(only=None, pack: FontPack = FONT_PACKS["latin"]):
    pages = PAGES
    if only:
        pages = tuple(p for p in PAGES if p.slug == only)
        need(pages, f"--only={only} 没有匹配的页面（可选：{[p.slug for p in PAGES]}）")

    bodies = {p.slug: build_page(p) for p in pages}
    merged = only is None
    out, css_site, css_extra, css_font = assemble(pages, bodies, merged, pack)
    final_checks(out)

    stem = OUT_STEM_MERGED if merged else OUT_STEM_SINGLE.get(only, f"charm-single-{only}")
    dst = HERE / f"{stem}{pack.suffix}.html"
    dst.write_text(out, encoding="utf-8")

    print(f"已生成 {dst.name}（{human(len(out.encode()))}，字体包 {pack.key}）"
          f"  页面：{', '.join(p.slug for p in pages)}")
    print(f"  字体 {human(len(css_font))} · 令牌 {len(build_tokens_css(pack)) / 1024:.1f} KB · "
          f"站点切片 {len(css_site) / 1024:.1f} KB · 额外 CSS {sum(map(len, css_extra)) / 1024:.1f} KB")
    for p in pages:
        print(f"  {p.slug:<12} 正文 {len(bodies[p.slug]) / 1024:6.1f} KB")


def main(argv):
    only, do_all, pack = None, False, FONT_PACKS["latin"]
    for a in argv[1:]:
        if a.startswith("--only="):
            only = a.split("=", 1)[1]
        elif a.startswith("--fonts="):
            key = a.split("=", 1)[1]
            need(key in FONT_PACKS, f"未知字体包 {key}（可选：{'/'.join(FONT_PACKS)}）")
            pack = FONT_PACKS[key]
        elif a == "--all":
            do_all = True
        else:
            sys.exit(f"未知参数 {a}"
                     f"（可用：--only=<slug> / --all / --fonts=<{'/'.join(FONT_PACKS)}>）")

    build_one(only, pack)
    if do_all:                       # 顺带出四个单页版，供 _verify_charm.mjs 做像素回归
        for p in PAGES:
            build_one(p.slug, pack)


if __name__ == "__main__":
    main(sys.argv)
