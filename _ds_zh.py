# -*- coding: utf-8 -*-
"""设计系统层：只作用于 `charm-preview-cjk-gb-zh.html`，是设计改动的试验台。

分层的理由
----------
`_build_charm.py` 是**复刻层**：它的职责是把 typeui.sh 的四页一字不差地搬成单文件，
所以那五个产物必须保持「忠实复刻」——任何设计改动混进去，都会让「与原站一致」这个
可验证的性质失效（像素回归、逐字节比对全都不再有意义）。

设计上的试验因此全部落在这一层，只改 zh 那一个产物：

    _build_charm.py   复刻层    四页 → 五个产物，忠实复刻
    _ds_zh.py         设计层    令牌 / 色板 / 组件          ← 本文件
    _localize_zh.py   内容层    文案
    _build_zh.py      编排      cjk-gb 产物 → 设计层 → 内容层 → zh 产物

怎么加一条新的设计改动
----------------------
往 `LAYERS` 里加一个 `Patch`。每个 Patch 自带命中数断言：锚点失效就报错，
不会静默产出一个「看起来对、其实没改上」的页面——这是从复刻层继承下来的规矩。

色板类改动一律用 `token_value()` 从产物自己的 CSS 里读 hex，**不在代码里手抄**，
免得令牌与色块悄悄走样。
"""
from __future__ import annotations

import colorsys
import re
import sys
from dataclasses import dataclass
from pathlib import Path

HERE = Path(__file__).resolve().parent


def need(cond, msg):
    if not cond:
        sys.exit(f"[设计层失败] {msg}")


@dataclass(frozen=True)
class Patch:
    """一条设计改动：锚点必须命中 `count` 次，payload 插在命中之后（或替换命中）。"""
    label: str
    anchor: str
    payload: str
    count: int = 1
    mode: str = "after"          # after=插在锚点后；replace=替换锚点本身
    flags: int = 0

    def apply(self, s: str) -> str:
        ms = list(re.finditer(self.anchor, s, self.flags))
        need(len(ms) == self.count,
             f"[{self.label}] 锚点命中 {len(ms)} 次，期望 {self.count}")
        for m in reversed(ms):                     # 从后往前，偏移不失效
            rep = self.payload if self.mode == "replace" else m.group(0) + self.payload
            s = s[:m.start()] + rep + s[m.end():]
        return s


# ------------------------------------------------------------------ 取值工具
def token_value(css: str, name: str) -> str:
    """从产物自己的 CSS 里读一个令牌的字面值。色板的 hex 一律这么取，不手抄。"""
    m = re.search(r'--' + re.escape(name) + r':\s*(#[0-9a-fA-F]{3,8})', css)
    need(m, f"产物 CSS 里找不到 --{name}")
    return m.group(1)


def hsl_hex(h: float, s: float, l: float) -> str:
    r, g, b = colorsys.hls_to_rgb(h / 360, l / 100, s / 100)
    return "#%02x%02x%02x" % tuple(round(x * 255) for x in (r, g, b))


def swatch(name: str, hexv: str) -> str:
    return (f'<div class="ds__swatch"><span class="ds__chip" style="background:{hexv}">'
            f'</span><b>{name}</b><span>{hexv}</span></div>')


# ============================================================ 改动一：状态色
# 原设计系统只有 success / danger / warning 三族状态色，没有蓝色。
# 色值不是另挑一套，而是照三族既有的 HSL 关系推出来（实测值见下），
# 这样新族与三族同一手感：
#     strong = base 的 L−9      实测 success −7.8 / danger −9.2 / warning −10.8
#     soft   = L95、S 降到 ~68  实测三族 soft 为 L95.1 / 95.3 / 93.7
#     medium = L90              danger/warning 有 medium，success 没有，这里给全
INFO_HUE, INFO_S = 212, 76       # hue 212：与品牌暖红、三族状态色都拉得开
INFO_HUES = (
    ("info", hsl_hex(INFO_HUE, INFO_S, 52)),
    ("info-strong", hsl_hex(INFO_HUE, INFO_S, 43)),
    ("info-soft", hsl_hex(INFO_HUE, 68, 95)),
    ("info-medium", hsl_hex(INFO_HUE, 68, 90)),
)
INFO_SHOWN = ("info", "info-strong", "info-soft")   # 色板展示前三个，与 success/danger 一致

# 原站把 8 个状态色块塞进同一个网格，靠 auto-fill 自动折行——绿红黄三族被切得七零八落。
# 改成**一族一个 `.ds__swatches`**：`.ds__stage--stack` 是 flex column，多个网格自然纵向排开；
# 而每个网格的列宽都由同一条 `repeat(auto-fill,minmax(150px,1fr))` 算出，容器宽度相同，
# 所以各行的列**天然对齐**。零新增 CSS，只是把 DOM 分组。
STATUS_HEAD = ('<div class="ds__swatches"><div class="ds__swatch">'
               '<span class="ds__chip" style="background:#1ebd66">')
STATUS_TAIL = '<p class="ds__note">Status color means state, never decoration.</p>'
# 绿 → 红 → 黄 → 蓝，每族 base / strong / soft 三色
STATUS_FAMILIES = ("success", "danger", "warning", "info")

STYLE_END = "</style>"          # 令牌追加在产物那唯一一段 <style> 的末尾


def build_layers(css: str) -> tuple:
    """按产物当前的 CSS 生成本层的全部 Patch（hex 从 CSS 里读，故需先传入）。"""
    tokens = ("\n/* ==== 设计层：新增蓝色状态色族 info（_ds_zh.py，非原站） ==== */\n:root{"
              + "".join(f"--{n}:{v};" for n, v in INFO_HUES).rstrip(";") + "}\n")

    # 每族三色。info 的 hex 取自本层自己的定义（此刻还没注入 CSS），其余三族从产物 CSS 读。
    # 原站色板漏了 warning-soft（--warning-soft #fff6df 这个令牌本来就在），一并补齐，
    # 于是四族整齐地各三色。
    info = dict(INFO_HUES)
    rows = []
    for fam in STATUS_FAMILIES:
        cells = []
        for suffix in ("", "-strong", "-soft"):
            name = fam + suffix
            cells.append(swatch(name, info[name] if fam == "info" else token_value(css, name)))
        rows.append('<div class="ds__swatches">' + "".join(cells) + "</div>")
    status_block = "".join(rows) + STATUS_TAIL

    return (
        # 令牌要落在 <style> **内部**，所以是替换 </style> 为「令牌 + </style>」，
        # 不是插在它后面——插后面就跑到样式块外面去了。
        Patch("注入 info 令牌", re.escape(STYLE_END), tokens + STYLE_END,
              mode="replace", count=1),
        # 整段换掉原来那一个网格。末尾原样带回 STATUS_TAIL——内容层要按原文翻译它，
        # 这里若改动一个字，内容层的命中数断言就会当场报错。
        Patch("状态色板：一族一行，补 warning-soft，加 info 族",
              re.escape(STATUS_HEAD) + r".*?" + re.escape(STATUS_TAIL),
              status_block, mode="replace", flags=re.S),
    )


def build_text_layer(html: str) -> tuple:
    """文字色板必须在前面两条改动**之后**再算——否则数不到新增的东西。"""
    census = text_color_census(html)
    block = text_block(census)
    check_subset(block)
    return census, Patch("文字色板", TEXT_ANCHOR, block)


# ============================================================ 改动二：文字色板
# 原站的色板只展示了品牌色、表面色、状态色，**没有一处展示「文字用了哪些颜色」**。
# 这一块把它补出来——而且不是把色值抄进代码，是**从产物自己身上数**：
#   · CSS 里每一条 color: 声明，逐层解开 var() 链求到字面值；
#   · SVG <text> 上的 fill=（marketing 页那张仪表盘插画全靠它）。
# 于是 CSS 一改，色板自动跟着变，不存在「文档说 16 种、实际 19 种」这种走样。
TEXT_ANCHOR = r'<p class="ds__note">Status color means state, never decoration\.</p></div>'


def _norm(h: str) -> str:
    h = h.lower().strip()
    if re.fullmatch(r"#[0-9a-f]{3}", h):
        return "#" + "".join(c * 2 for c in h[1:])
    return h


def _resolve(v: str, tokens: dict, depth: int = 0) -> str:
    """解开 var(--x, fallback) 链，一直求到字面值。"""
    v = v.strip()
    if depth > 12:
        return v
    m = re.fullmatch(r"var\(\s*--([\w-]+)\s*(?:,\s*(.*))?\)", v, re.S)
    if not m:
        return v
    name, fallback = m.group(1), m.group(2)
    if name in tokens:
        return _resolve(tokens[name], tokens, depth + 1)
    return _resolve(fallback, tokens, depth + 1) if fallback else v


def text_color_census(html: str) -> list:
    """数出产物里实际用到的文字颜色。返回 [(色值, [令牌名…], 用量), …]，按用量降序。"""
    css = re.search(r"<style>(.*?)</style>", html, re.S).group(1)
    body = html[html.index("</style>"):]

    tokens = {}
    for m in re.finditer(r"--([\w-]+)\s*:\s*([^;}]+)", css):
        tokens.setdefault(m.group(1), m.group(2).strip())

    use = {}
    for rule in re.finditer(r"([^{}]+)\{([^}]*)\}", css):
        if rule.group(1).strip().startswith(":root"):      # 令牌定义本身不算「用到」
            continue
        for m in re.finditer(r"(?<![-\w])color\s*:\s*([^;}]+)", rule.group(2)):
            v = _norm(_resolve(m.group(1), tokens))
            if v.startswith("#"):
                use[v] = use.get(v, 0) + 1
    for m in re.finditer(r'<text\b[^>]*?fill="([^"]+)"', body):
        v = m.group(1)
        v = _norm(_resolve(v, tokens) if v.startswith("var(") else v)
        if v.startswith("#"):
            use[v] = use.get(v, 0) + 1

    by_value = {}
    for k, v in tokens.items():
        if v.startswith("#"):
            by_value.setdefault(_norm(v), []).append(k)

    need(use, "一条 color: 都没数到，选择器解析大概是坏了")
    return sorted(((c, by_value.get(c, []), n) for c, n in use.items()),
                  key=lambda r: -r[2])


def _lightness(hexv: str) -> float:
    r, g, b = (int(hexv[i:i + 2], 16) / 255 for i in (1, 3, 5))
    return colorsys.rgb_to_hls(r, g, b)[1]


def _saturation(hexv: str) -> float:
    r, g, b = (int(hexv[i:i + 2], 16) / 255 for i in (1, 3, 5))
    return colorsys.rgb_to_hls(r, g, b)[2]


# 按语义分组，而不是按用量排——按用量排出来的是一串灰、红、绿乱插的序列，读不出结构。
# 判据优先看令牌名（最可靠），没有令牌才退回按饱和度猜。
TEXT_GROUPS = ("中性", "品牌", "状态", "其它")


def _hue(hexv: str) -> float:
    r, g, b = (int(hexv[i:i + 2], 16) / 255 for i in (1, 3, 5))
    return colorsys.rgb_to_hls(r, g, b)[0] * 360


# 状态组里必须先按族聚拢再排明度——只按明度排会把绿、红、黄互相插开，读不出族。
# 族的顺序与上面的状态色板一致（绿 → 红 → 黄 → 蓝），全页保持同一套次序。
_FAMILY_HUE = {"success": 147, "danger": 358, "warning": 37, "info": 212}


def _family_rank(hexv: str, names: list) -> int:
    n = " ".join(names)
    for i, fam in enumerate(STATUS_FAMILIES):
        if fam in n:
            return i
    # 裸字面值：归到色相最近的那一族（#ffb020 因此挨着 warning）
    h = _hue(hexv[:7])
    return min(range(len(STATUS_FAMILIES)),
               key=lambda i: min(abs(h - _FAMILY_HUE[STATUS_FAMILIES[i]]),
                                 360 - abs(h - _FAMILY_HUE[STATUS_FAMILIES[i]])))


def _classify(hexv: str, names: list) -> str:
    n = " ".join(names)
    if "brand" in n:
        return "品牌"
    if re.search(r"success|danger|warning|info", n):
        return "状态"
    if re.search(r"heading|body|subtle|disabled|border|card|white|black|page|surface", n):
        return "中性"
    if names:                                   # 有令牌但不属于以上三类：purple / orange 之类
        return "其它"
    return "中性" if _saturation(hexv) < 0.12 else "状态"   # 裸字面值只能按饱和度判


def text_swatches(census: list) -> str:
    """一组一行（同 Status hues 的做法），组内按明度由深到浅排成一道梯度。

    无令牌的裸字面值标注「无令牌」——它们是从色板里漏出去的，值得一眼看见。
    """
    out = []
    for group in TEXT_GROUPS:
        items = [r for r in census if _classify(r[0], r[1]) == group]
        if not items:
            continue
        if group == "状态":
            items.sort(key=lambda r: (_family_rank(r[0], r[1]), _lightness(r[0][:7])))
        else:
            items.sort(key=lambda r: _lightness(r[0][:7]))   # 深 → 浅
        cells = []
        for hexv, names, n in items:
            label = "--" + names[0] if names else hexv
            meta = f"{hexv} · {n}" + ("" if names else " · 无令牌")
            cells.append(f'<div class="ds__swatch"><span class="ds__chip" '
                         f'style="background:{hexv}"></span><b>{label}</b>'
                         f'<span>{meta}</span></div>')
        out.append(f'<span class="ds__kicker">{group} · {len(items)}</span>'
                   f'<div class="ds__swatches">' + "".join(cells) + "</div>")
    return "".join(out)


def check_subset(fragment: str) -> None:
    """本层注入 DOM 的字符必须落在子集字体的覆盖范围内——用了范围外的字，
    会当场掉回「看的人的系统字体」。

    判据直接从 _make_cjk_fonts.py 导入，不在这里另写一份：子集到底收了哪些字
    是那个脚本说了算，两处各写一份迟早对不上。实际覆盖 = GB2312 全集 ∪ 保留区
    （拉丁、标点、全角形式等，`·` 这类就落在这里）∪ 拉丁版产物里在用的字符；
    这里只校验前两项，是偏严的一侧，不会漏报。
    """
    from _make_cjk_fonts import KEEP_RANGES, gb2312_charset

    covered = {ord(c) for c in gb2312_charset()}
    for lo, hi in KEEP_RANGES:
        covered.update(range(lo, hi + 1))
    bad = {c for c in fragment if ord(c) > 0x7F and ord(c) not in covered}
    need(not bad, f"这些字不在子集字体的覆盖内，会掉回系统字体：{''.join(sorted(bad))}")


def text_block(census: list) -> str:
    """标题与说明直接写中文——本层只作用于 zh 产物，没必要绕内容层翻译一道；
    而且说明里带动态数字，放进内容层那张「原文→译文→命中数」的表会很脆。
    色块标签保持英文：它们是设计令牌名，本就不该翻译。"""
    adhoc = sum(1 for _, names, _ in census if not names)
    note = (f"文字实际用到 {len(census)} 种颜色：{len(census) - adhoc} 种有令牌，"
            f"{adhoc} 种是写死的裸字面值。按语义分组，组内由深到浅。本表由本页自己数出，非人工罗列。")
    # text_swatches() 自己按组吐出多个 .ds__swatches，这里不再额外包一层网格
    return ('<div class="ds__block"><div class="ds__block-head">'
            '<h3 class="ds__block-title">文字颜色</h3>'
            '<span class="ds__file">colors.md</span></div>'
            '<div class="ds__stage ds__stage--stack">'
            + text_swatches(census) +
            f'</div><p class="ds__note">{note}</p></div>')


NOTE_ANCHOR = "  需要 Chrome/Edge 119+"
NOTE = """  ⚠ 本文件额外过了一道**设计系统层**（_ds_zh.py），是设计改动的试验台；
     其余四个产物保持忠实复刻，不含以下任何改动。
     · 色板补上 warning-soft。该令牌（#fff6df）原本就存在，只是原站色板漏了它，
       导致 warning 只展示 base 与 strong，与 success / danger 的三色不齐。
     · 新增蓝色状态色族 info：令牌 --info / --info-strong / --info-soft /
       --info-medium，色板展示前三个。原站只有 success / danger / warning 三族。
       色值按三族既有的 HSL 关系推出（hue 212，strong = L−9，soft = L95、S≈68）。
     色板里每个 hex 都从产物自己的 CSS 读出后生成，不存在手抄副本。
     注：原站已有 .ds__alert--info 变体，但它借用品牌红 --ds-brand-soft；
     本层只补了色族本身，未改动该变体的样式。
     · 新增「Text colors」色板：原站的色板展示了品牌色、表面色、状态色，唯独没有
       「文字用了哪些颜色」。这一块把它补出来，共 {n} 种——且不是抄进来的，是从本页
       自己身上数的：CSS 里每条 color: 声明逐层解开 var() 链求到字面值，再加上
       SVG <text> 的 fill=。CSS 一改色板自动跟着变，不会出现文档与实际不符。
       没有对应令牌的裸字面值会标注「无令牌」——它们是从色板里漏出去的。

"""


def apply(html: str) -> str:
    """把设计层的全部改动应用到一份产物 HTML 上。"""
    css_end = html.index(STYLE_END)
    layers = build_layers(html[:css_end])

    need(all(f"--{n}:" not in html[:css_end] for n, _ in INFO_HUES),
         "产物里已经有 info 族令牌，设计层被重复应用了")

    for p in layers:
        html = p.apply(html)

    census, text_patch = build_text_layer(html)
    html = text_patch.apply(html)

    html, n = re.subn(re.escape(NOTE_ANCHOR), NOTE.format(n=len(census)) + NOTE_ANCHOR,
                      html, count=1)
    need(n == 1, "没找到说明块的插入锚点")

    # 色块计数：22 原有 + warning-soft + info ×3 + 文字色板 N 个
    for cls, expect in (("ds__swatch", 26 + len(census)), ("ds__chip", 26 + len(census))):
        got = len(re.findall(r'class="' + cls + r'"', html))
        need(got == expect, f"色块 {cls} 共 {got} 个，期望 {expect}")
    need(len(re.findall(r'class="ds__block"', html)) == 38, "ds__block 数不对（原 37 + 文字色板 1）")

    apply.census = census        # 供 summary() 报数
    return html


def summary() -> str:
    shown = " ".join(f"{n}={dict(INFO_HUES)[n]}" for n in INFO_SHOWN)
    census = getattr(apply, "census", [])
    adhoc = sum(1 for _, names, _ in census if not names)
    return (f"设计层：+warning-soft 色块，+info 族令牌 4 个（{shown}）；"
            f"+文字色板 {len(census)} 种（{len(census) - adhoc} 种有令牌，{adhoc} 种裸字面值）")
