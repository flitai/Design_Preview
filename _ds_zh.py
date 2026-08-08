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

# Status hues 的最后一个色块，新色块插在它后面
STATUS_ANCHOR = (r'<div class="ds__swatch"><span class="ds__chip" style="background:#d98200">'
                 r'</span><b>warning-strong</b><span>#d98200</span></div>')

STYLE_END = "</style>"          # 令牌追加在产物那唯一一段 <style> 的末尾


def build_layers(css: str) -> tuple:
    """按产物当前的 CSS 生成本层的全部 Patch（hex 从 CSS 里读，故需先传入）。"""
    tokens = ("\n/* ==== 设计层：新增蓝色状态色族 info（_ds_zh.py，非原站） ==== */\n:root{"
              + "".join(f"--{n}:{v};" for n, v in INFO_HUES).rstrip(";") + "}\n")

    # 原站色板展示了 success ×3、danger ×3，warning 却只有 base 与 strong——
    # 而 --warning-soft（#fff6df）这个令牌是**存在**的，纯粹是色板漏了它。补齐。
    additions = swatch("warning-soft", token_value(css, "warning-soft")) + "".join(
        swatch(n, dict(INFO_HUES)[n]) for n in INFO_SHOWN)

    return (
        # 令牌要落在 <style> **内部**，所以是替换 </style> 为「令牌 + </style>」，
        # 不是插在它后面——插后面就跑到样式块外面去了。
        Patch("注入 info 令牌", re.escape(STYLE_END), tokens + STYLE_END,
              mode="replace", count=1),
        Patch("色板：补 warning-soft + 加 info 三色", re.escape(STATUS_ANCHOR), additions),
    )


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

"""


def apply(html: str) -> str:
    """把设计层的全部改动应用到一份产物 HTML 上。"""
    css_end = html.index(STYLE_END)
    layers = build_layers(html[:css_end])

    need(all(f"--{n}:" not in html[:css_end] for n, _ in INFO_HUES),
         "产物里已经有 info 族令牌，设计层被重复应用了")

    for p in layers:
        html = p.apply(html)

    html, n = re.subn(re.escape(NOTE_ANCHOR), NOTE + NOTE_ANCHOR, html, count=1)
    need(n == 1, "没找到说明块的插入锚点")

    # 色板计数：22 原有 + warning-soft + info ×3
    for cls, expect in (("ds__swatch", 26), ("ds__chip", 26)):
        got = len(re.findall(r'class="' + cls + r'"', html))
        need(got == expect, f"色块 {cls} 共 {got} 个，期望 {expect}")
    return html


def summary() -> str:
    shown = " ".join(f"{n}={dict(INFO_HUES)[n]}" for n in INFO_SHOWN)
    return f"设计层：+warning-soft 色块，+info 族令牌 4 个（{shown}）"
