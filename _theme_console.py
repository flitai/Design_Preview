# -*- coding: utf-8 -*-
"""控制台皮肤层：把深色版的暖炭壳换成近黑冷中性 + 方角 + 扁平，
只作用于 `charm-preview-cjk-gb-zh-console.html`。

管线位置（_build_zh.py --console 编排）：

    charm-preview-cjk-gb.html
      └─ _theme_dark.apply → **_theme_console.apply** → _ds_zh.apply
         → _theme_console.check_after_ds → _theme_dark.apply_post → _localize_zh.apply
                                              → charm-preview-cjk-gb-zh-console.html

为什么夹在深色层与设计层之间
----------------------------
设计层的 `token_value()` 与 `text_color_census()` 都是「首次声明胜」：本层先行，
设计层随后生成的三块色板（状态色、文字色、以及它读的表面色）天然自证冷值。
若放到设计层之后，色板显示的是刚被覆盖掉的旧值——色板对自己撒谎。
深色层的全部断言在本层之前已执行完毕，`apply_post` 的 info 计数由设计层在本层
之后注入，两头都不受影响；`--dark` 与明亮路径一行不碰。

这一层做什么、不做什么
----------------------
**只换令牌皮肤**：中性族 16 条声明、圆角 8 条、阴影/焦点环 3 条。排版、字样、
DOM 结构、文案一律不动；**品牌珊瑚红与四族状态色一个字节不改**（恒等断言在场）
——换的是壳，不是牌子。

例外只有一处，且是必须的：components 页把 8 个中性色块与 7 个圆角块**烙进了
body**（chip 的内联 style + hex 标签成对、演示块的 `border-radius:` + px 标签）。
那是令牌在 body 里的字面镜像。令牌改而镜像不改 = 色板对自己撒谎，违反「色板自证、
无手抄副本」这条硬性不变量（深色层的 CHIP_MAP 成对改并断言 chip==label 是先例）。
除这 15 处镜像外，body 一律不碰。

配色从哪里来
------------
同样不是手调，是从**深色版**再锚定一次。深色层已经把明亮版按 OKLCH + APCA 推成
一套审计过的关系（面的 ΔL、线的方向翻转、墨的等 Lc）；本层保留那套关系，只做两件事：

  · 面 / 线 / 抬升：把深色版的 L **整体平移**到新锚点 —— page 从 #1c1917 移到
    #0e0e0e（ΔL = −0.0524，对齐参考图的近黑），彩度一律归零（C=0 纯中性，与暖炭
    的 56° 色相带彻底脱钩）。整体平移意味着深色层审计过的全部 ΔL 关系原样保留。
  · 墨：**不平移**，按深色层同一条多座面规则在冷面上重解——冷 page 上按明亮版的 Lc
    目标等 Lc，再对 card 等所坐的面兜底（不低于明亮版同一面）。平移会把对比度一起
    平移掉；墨的判据从来是感知对比，不是明度差。

品牌与状态四族的值完全不动。实测冷底上它们的 Lc 只升不降（fg-brand 53.7 → 54.7，
fg-brand-strong 67.2 → 68.1），四族 soft 由「与 card 几乎等明度」变成明确浮在 card
之上——底更冷更暗，珊瑚红反而更立得住。verify_derivation() 把这两条当断言钉住。

方角与扁平
----------
圆角令牌 8 条各 ×1 声明、40 处 var 引用穿透（`.ds` 层经别名自动传导）：
4/6/8px → 2px，12px → 3px，24px → 4px。`--r-full:9999px` **不动**——40 处引用是
圆点、头像、开关滑块，必须保圆；代价是药丸按钮仍圆（见「已知差异」）。
阴影换成发丝线：`--elevation-1/2` 从投影改成 1px 内描边（深色 UI 里让面浮起来的
本就是边缘高光不是黑影），`--focus-ring` 加一圈实心 1px 品牌线，扁平但焦点仍可见。

就地改写，绝不追加
------------------
全部 Patch 用 `mode="replace"`。若在 `</style>` 前追加覆盖块，浏览器认后者、
census 认前者，渲染与色板会静默分家——深色层已经把这条写成规矩。
"""
from __future__ import annotations

import re
import sys

import _ds_zh
import _theme_dark
from _ds_zh import Patch
# 色彩数学直接复用深色层的实现（零依赖、已在那边核过锚点），不另写一份：
# 两处各写一份 OKLab/APCA 迟早会漂。
from _theme_dark import (INK_SEATS, LC_CAP, LIGHT_HOVER, STRONG_SEATS, _drift, _norm6, apca,
                         audit_seated, hex_lch, lch_hex, seat_pairs, seated)


def need(cond, msg):
    if not cond:
        sys.exit(f"[皮肤层失败] {msg}")


E = _theme_dark.EXPECTED                                  # 深色层定稿表（本层的输入）
LIGHT = {n: _norm6(l) for n, l, _ in _theme_dark.ROOT_MAP}  # 明亮值：深色层已逐条在产物里断言过

# ============================================================ 推导常数与定稿表
PAGE = "#0e0e0e"      # 新锚点：参考图的近黑冷中性底（L=0.1638，C=0）
CHROMA = 0.0          # 中性族一律纯中性
COLD_C = 0.002        # 「冷」断言阈值：输出彩度必须低于此值

SHIFTED = ("band", "control-fill", "page", "card-soft", "card",
           "border-subtle", "border", "border-on-band", "border-medium",
           "border-strong", "hover-fill", "tooltip")
INKS = ("fg-disabled", "body-subtle", "body", "heading")
SURF_ORDER = ("band", "control-fill", "page", "card-soft", "card")

# 出厂定稿表：下面 _derive() 用两条规则重算并断言逐通道差 ≤1/255。
# 没有「设计定稿常量」——本层每一个值都从规则推得出来。
EXPECTED_CONSOLE = {
    # 面（平移 ΔL=−0.0524，C=0）
    "band": "#090909", "control-fill": "#0b0b0b", "page": "#0e0e0e",
    "card-soft": "#111111", "card": "#151515",
    # 线（同一平移，深色层的方向翻转原样保留）
    "border-on-band": "#101010", "border-subtle": "#232323", "border": "#262626",
    "border-medium": "#343434", "border-strong": "#5d5d5d",
    # 抬升面与反色药丸（tooltip 与 border 同值：平移后的巧合，两者角色不同，各锚各的）
    "hover-fill": "#1b1b1b", "tooltip": "#262626",
    # 墨（冷 page 上等 Lc，再按所坐的面兜底；前三个由 card 约束提亮，不平移）
    "fg-disabled": "#9f9f9f", "body-subtle": "#c9c9c9", "body": "#dfdfdf",
    "heading": "#f3f3f3",
}
C = EXPECTED_CONSOLE

# 品牌与四族状态色：本层一个字节不改，逐条断言在场（值取自深色层定稿表）
KEEP_DERIVED = ("brand-soft", "brand-softer", "fg-brand", "fg-brand-strong",
                "success-strong", "success-soft", "danger-strong", "danger-soft",
                "danger-medium", "warning-strong", "warning-soft", "warning-medium",
                "fg-warning")
SOFTS = ("brand-soft", "success-soft", "danger-soft", "warning-soft")


def _derive() -> dict:
    """两条规则重算全表：面/线/抬升整体平移到冷锚点，墨按多座面规则在冷面上重解。"""
    shift = hex_lch(PAGE)[0] - hex_lch(E["page"])[0]
    out = {n: lch_hex(hex_lch(E[n])[0] + shift, CHROMA, 0.0) for n in SHIFTED}
    for n in INKS:
        out[n], _ = seated(LIGHT[n], CHROMA, 0.0, seat_pairs(LIGHT, INK_SEATS, out))
    return out


def verify_derivation() -> None:
    """重算全表并与定稿对照（≤1/255），再跑冷度、等 Lc 审计、序关系与保留族交叉审计。

    **不复用 `_theme_dark.verify_derivation`**：那一套的锚是暖 INK（#1c1917），
    整个推导围绕它展开；本层的锚是冷 page，必须自己写自己的判据。
    """
    ink_l, _, ink_h = hex_lch(_theme_dark.INK)
    need(abs(ink_l - 0.2161) < 5e-4 and abs(ink_h - 56.0) < 0.5,
         f"OKLab 实现漂了：#1c1917 算出 L={ink_l:.4f} H={ink_h:.1f}，应为 0.2161/56°")
    need(abs(apca(_theme_dark.INK, LIGHT["page"]) - 99.5) < 0.1
         and abs(apca("#ffffff", _theme_dark.INK) + 106.6) < 0.1,
         "APCA 实现漂了：锚点 Lc 不等于 99.5 / -106.6")
    need(LIGHT["heading"] == _theme_dark.INK,
         "明亮锚点不对：深色层的 --heading 明亮值不再是 #1c1917")

    derived = _derive()
    need(set(derived) == set(C), f"推导表与定稿表键不一致：{set(derived) ^ set(C)}")
    bad = [f"{n}: 推导 {derived[n]} vs 定稿 {C[n]}（漂移 {_drift(derived[n], C[n])}）"
           for n in sorted(C) if _drift(derived[n], C[n]) > 1]
    need(not bad, "推导与定稿表对不上（>1/255）：\n  " + "\n  ".join(bad))
    need(derived["page"] == PAGE, f"page 应恰好落在锚点 {PAGE}，得 {derived['page']}")

    # 冷：全部输出必须是纯中性，与暖炭的 56° 色相带彻底脱钩
    warm = [f"{n}={C[n]} C={hex_lch(C[n])[1]:.4f}" for n in C if hex_lch(C[n])[1] >= COLD_C]
    need(not warm, "这些输出不是纯中性：" + "，".join(warm))

    # 墨：多座面审计——冷面上处处不低于明亮版同一面，且至少一面取等
    for n in INKS:
        audit_seated(n, LIGHT[n], C[n], INK_SEATS, LIGHT, dark=C)
    # 继承的状态字：soft 恒等、page/card 换冷面，只许更清楚（不要求取等：值是深色层定的）
    for n, seats in STRONG_SEATS.items():
        if n == "info-strong":                # info 族由设计层注入，不在本层的明亮表里
            continue
        for s in seats:
            want = min(abs(apca(LIGHT[n], LIGHT[s])), LC_CAP)
            got = abs(apca(E[n], E[s] if s.endswith("soft") else C[s]))
            need(got >= want - 0.5, f"状态字 {n}/{s} 在冷面上退化：明亮 Lc={want:.1f} 控制台 Lc={got:.1f}")
    # 反色药丸平移后白字仍足够亮、仍浮得出面板
    need(abs(apca("#ffffff", C["tooltip"])) >= 85, "tooltip 药丸上的白字不够亮")
    need(hex_lch(C["tooltip"])[0] - hex_lch(C["card-soft"])[0] >= 0.08, "tooltip 药丸浮不出面板")
    ink_order = sorted(INKS, key=lambda n: hex_lch(LIGHT[n])[0])
    need(ink_order == sorted(INKS, key=lambda n: -hex_lch(C[n])[0]),
         "墨族的明度序没有整体翻转")

    # 面的层级不倒挂；线全部亮于 page；hover-fill 仍夹在 card 与 border-subtle 之间
    need(list(SURF_ORDER) == sorted(SURF_ORDER, key=lambda n: hex_lch(C[n])[0]),
         "面的层级顺序被打乱（卡片应仍比页面亮）")
    for n in ("border-subtle", "border", "border-medium", "border-strong", "border-on-band"):
        need(hex_lch(C[n])[0] > hex_lch(C["page"])[0],
             f"{n} 没有比 page 亮（线的方向必须翻转）")
    need(hex_lch(C["card"])[0] < hex_lch(C["hover-fill"])[0] < hex_lch(C["border-subtle"])[0],
         "hover-fill 应落在 card 与 border-subtle 之间")

    # 保留族交叉审计：底换冷了，品牌前景与状态徽章底必须只变好、不变差
    for n, floor in (("fg-brand", 53.7), ("fg-brand-strong", 67.2)):
        got = abs(apca(E[n], PAGE))
        need(got >= floor, f"{n} 在冷 page 上的 Lc={got:.1f}，低于深色版的 {floor}")
    for n in SOFTS:
        need(hex_lch(E[n])[0] > hex_lch(C["card"])[0] > hex_lch(C["page"])[0],
             f"{n} 没有浮在 card 之上（徽章底会糊进卡片）")

    # 输出值不相交：撞上任何一版的值域，都会让别层「按值计数」的断言错位、或让旧值复活
    mine = set(C.values())
    others = ({_norm6(v) for v in E.values()}
              | {_norm6(v) for v in LIGHT.values()}
              | {_norm6(v) for _, v in _theme_dark.ROOT_KEEP}
              | {_norm6(v) for _, v in _ds_zh.INFO_HUES})
    need(not (mine & others), f"控制台输出值与既有值域相交：{sorted(mine & others)}")


# ============================================================ 第 1 级：:root 令牌
# 锚点一律用「--令牌:深色值」**完整键值对** + (?=[;}])：裸 `--card:` 会误中选择器
# `.section--card:before`，裸 hex 会误伤外壳的字面值。实测每条恰 1 处。
ROOT_MAP = (
    ("band", E["band"], C["band"]),
    ("control-fill", E["control-fill"], C["control-fill"]),
    # app-surface 与 control-fill 同值异键：深色层的 EXPECTED 表没有它的条目，
    # 照表列清单会漏掉一条声明，必须各锚各的。
    ("app-surface", E["control-fill"], C["control-fill"]),
    ("page", E["page"], C["page"]),
    ("card-soft", E["card-soft"], C["card-soft"]),
    ("card", E["card"], C["card"]),
    ("border-on-band", E["border-on-band"], C["border-on-band"]),
    ("border-subtle", E["border-subtle"], C["border-subtle"]),
    ("border", E["border"], C["border"]),
    ("border-medium", E["border-medium"], C["border-medium"]),
    ("border-strong", E["border-strong"], C["border-strong"]),
    ("fg-disabled", E["fg-disabled"], C["fg-disabled"]),
    ("body-subtle", E["body-subtle"], C["body-subtle"]),
    ("body", E["body"], C["body"]),
    ("heading", E["heading"], C["heading"]),
    # hover-fill 的声明在第 4 个 :root 块（深色层追加段）里。#2b2724 全 CSS 共 3 处，
    # 另两处是 ds 链的死回退与外壳的 is-active:hover——按边界与外壳不变量都不动，
    # 完整键值对锚点天然只命中声明这一处。
    ("hover-fill", E["hover-fill"], C["hover-fill"]),
    # tooltip 同在深色层追加段的 :root 里（组件页 tooltip 气泡的底）
    ("tooltip", E["tooltip"], C["tooltip"]),
)

# ============================================================ 第 2 级：圆角与阴影
# 8 条声明各 ×1；40 处 var 引用穿透到改后的令牌，另 40 处指向保圆的 --r-full。
RADIUS_MAP = (("r-xs", "4px", "2px"), ("r-sm", "6px", "2px"), ("r-md", "8px", "2px"),
              ("r-lg", "12px", "3px"), ("r-xl", "24px", "4px"),
              ("r-xxl", "24px", "4px"), ("r-xxxl", "24px", "4px"))
RADIUS_KEEP = ("r-full", "9999px")      # 40 处圆点/头像/开关滑块，必须保圆
RADIUS_REFS = {"r-xs": 2, "r-sm": 1, "r-md": 16, "r-lg": 7, "r-xl": 11,
               "r-xxl": 3, "r-xxxl": 0, "r-full": 40}

# 阴影：锚点直接取深色层 ROOT_DECL 写进 CSS 的那一串原文，锚与源同出一处，不会各自漂。
_DARK_DECL = {name: dark for name, _, dark in _theme_dark.ROOT_DECL}
SHADOW_MAP = (
    # 深色 UI 里让面浮起来的是边缘高光；参考图更进一步，连高光都收成一圈发丝线。
    ("elevation-1", "--elevation-1:0 0 0 1px #ffffff12"),
    ("elevation-2", "--elevation-2:0 0 0 1px #ffffff14, 0 12px 32px #000000b3"),
    # 焦点环：扁平壳里 4px 柔光认不出来，加一圈 1px 实心品牌线兜底。
    ("focus-ring", "--focus-ring:0 0 0 1px #e4544b, 0 0 0 4px #e4544b33"),
)
# elevation-3 是品牌辉光 rgb(from var(--brand))，brand 恒等，自动跟随，不动。

# ============================================================ 第 3 级：body 里的令牌镜像
# components 页把 8 个中性令牌与 7 个圆角令牌**烙成了 body 字面值**。令牌改而镜像
# 不改 = 色板对自己撒谎。除这 15 处外 body 一律不碰。
CHIP_MIRROR = ("page", "card", "card-soft", "control-fill", "app-surface",
               "band", "border", "border-subtle")
CHIP_DARK = {"app-surface": E["control-fill"], **{n: E[n] for n in CHIP_MIRROR
                                                  if n != "app-surface"}}
CHIP_TMPL = ('<span class="ds__chip" style="background:{v}"></span>'
             '<b>{n}</b><span>{v}</span>')
# 圆角演示块**按令牌名锚整个单元**，绝不按值多趟替换：r-xs 的旧值 4px 恰是 r-xl 的
# 新值，值键碰撞会把刚写好的 2px 再当输入二次映射（深色层「输出值同时是输入键」同一课）。
RADIUS_TMPL = ('<span class="ds__radius-box" style="border-radius:{v}"></span>'
               '<b>{n}</b><span>{v}</span>')

# ============================================================ 收窄版 gone 扫描
# 只在**两个令牌 :root 块**内断言暖炭值绝迹。全 CSS 扫描必然假阳：外壳 EXTRA_CSS 的
# 亮玻璃与 .ds 链的死回退里，暖值是合法在场的（前者是站点 chrome、后者不可达）。
GONE = tuple(dict.fromkeys([dark for _, dark, _ in ROOT_MAP]))

# ============================================================ 设计层之后的 census 钉死
# 本层把令牌变冷、而 body 的插画/图表字面值仍是深色层的暖炭（令牌级不可达面），
# 于是文字色板必然分裂出更多「无令牌」条目。这不是设计债，是分层的忠实呈现——
# 但必须钉死，否则它就成了静默退化。数字照实际构建数出来，不估。
# 23 / 12 的来由（相对上一版 25 / 9）：深色层把「基色当文字」改成前景档后，品牌与危险
# 两个基色从文字色板消失（−2）；插画头像缩写改为推导出的专用色，不再碰巧等于点缀令牌
# 值（无令牌 +3）。
CENSUS_TOTAL, CENSUS_ADHOC = 23, 12

NOTE_TEXT = """  ⚠ 本文件在深色层与设计层之间还过了一道**控制台皮肤层**(_theme_console.py)：
     把深色版的暖炭壳换成近黑冷中性 + 方角 + 扁平，取自任务控制台一类界面的观感。
     只换令牌皮肤：中性族 16 条声明、圆角 8 条、阴影/焦点环 3 条；排版、字样、
     DOM、文案一律不动。
     · 配色不是手调，是从深色版再锚定一次：面/线/抬升整体平移 ΔL={dl}
       （page 从 {darkpage} 移到 {page}），彩度归零，深色层审计过的全部 ΔL 关系
       原样保留；墨不平移，按深色层的多座面规则在冷面上重解：冷 page 上等 Lc，
       card 等所坐的面不低于明亮版（fg-disabled/body-subtle/body/heading = {ink}）。
     · 品牌珊瑚红与四族状态色一个字节不改。冷底上它们只变好：fg-brand 的 Lc
       53.7 → {lc1}，fg-brand-strong 67.2 → {lc2}，四族 soft 由「与卡片几乎等明度」
       变成明确浮在卡片之上。
     · 方角：圆角令牌 4/6/8px → 2px、12px → 3px、24px → 4px，40 处 var 引用穿透。
       --r-full:9999px 不动——另 40 处引用是圆点、头像、开关滑块，必须保圆，
       代价是药丸按钮与胶囊 chip 仍圆。
     · 扁平：--elevation-1/2 从投影改成 1px 发丝内描边；--focus-ring 加一圈 1px
       实心品牌线，扁了但焦点仍可见。
     · 色板自证：components 页把 8 个中性色块与 7 个圆角块烙成了 body 字面值，
       它们与令牌成对改并断言一致——色板里显示的就是令牌的真值。
     · 已知差异：插画与图表里的字面色仍是深色层的暖炭（纸面、网格线、图表提示
       药丸、次要系列线），那是令牌级不可达的面，在冷黑 UI 里呈极轻微暖调；
       文字色板因此为 {total} 条，其中「无令牌」{adhoc} 条——body 字面值属于
       深色层，不再溯源到（已变冷的）令牌。组件页 tooltip 的底是令牌，已随壳变冷。
     · 底部切换器保持深色层的亮玻璃与暖色字面：它是站点外壳不是被预览的组件，
       「一眼可辨」的不变量优先。

"""


def _root_blocks(css: str) -> str:
    """取出两个承载令牌的 :root 块（第一块是四页共享的令牌表，第四块是深色层追加段）。"""
    segs = []
    for m in re.finditer(r":root\{", css):
        j = css.index("}", m.end())
        seg = css[m.start():j + 1]
        if "--heading:" in seg or "color-scheme:dark" in seg:
            segs.append(seg)
    need(len(segs) == 2, f"承载令牌的 :root 块有 {len(segs)} 个，期望 2")
    return "".join(segs)


def apply(html: str) -> str:
    """把控制台皮肤应用到一份**已经过深色层、尚未过设计层**的产物上。"""
    verify_derivation()

    k = html.index("</style>")
    css, body = html[:k], html[k:]

    # 第 1 级：:root 令牌就地改写
    for name, dark, cold in ROOT_MAP:
        css = Patch(f"--{name}", re.escape(f"--{name}:{dark}") + r"(?=[;}])",
                    f"--{name}:{cold}", mode="replace").apply(css)
    # 品牌与四族状态色：恒等断言在场（换的是壳，不是牌子）
    for name in KEEP_DERIVED:
        pat = re.escape(f"--{name}:{E[name]}") + r"(?=[;}])"
        got = len(re.findall(pat, css))
        need(got == 1, f"恒等令牌 --{name}:{E[name]} 命中 {got} 处，期望 1")
    for name, val in _theme_dark.ROOT_KEEP:
        need(re.search(re.escape(f"--{name}:{val}") + r"(?=[;}])", css),
             f"恒等令牌 --{name}:{val} 不在场")

    # 第 2 级：圆角与阴影
    for name, old, new in RADIUS_MAP:
        css = Patch(f"--{name}", re.escape(f"--{name}:{old}") + r"(?=[;}])",
                    f"--{name}:{new}", mode="replace").apply(css)
    need(re.search(re.escape("--{}:{}".format(*RADIUS_KEEP)) + r"(?=[;}])", css),
         "--r-full:9999px 必须保持——40 处圆点/头像/开关滑块靠它")
    for name, cnt in RADIUS_REFS.items():
        got = len(re.findall(r"var\(--" + name + r"[,)]", css))
        need(got == cnt, f"var(--{name}) 引用 {got} 处，期望 {cnt}")
    for name, cold in SHADOW_MAP:
        css = Patch(f"--{name}", re.escape(_DARK_DECL[name]), cold, mode="replace").apply(css)

    # 收窄版 gone 扫描：暖炭值只在两个令牌 :root 块内断言绝迹
    seg = _root_blocks(css)
    for h in GONE:
        n = len(re.findall(re.escape(h) + r"(?![0-9a-fA-F])", seg))
        need(n == 0, f":root 里仍残留暖炭值 {h} ×{n}")

    # 第 3 级：body 里的 15 处令牌镜像（色块对 8 + 圆角演示 7）
    for name in CHIP_MIRROR:
        cold = C["control-fill"] if name == "app-surface" else C[name]
        body = Patch(f"色块 {name}",
                     re.escape(CHIP_TMPL.format(n=name, v=CHIP_DARK[name])),
                     CHIP_TMPL.format(n=name, v=cold), mode="replace").apply(body)
    for name, old, new in RADIUS_MAP:
        if name == "r-xxxl":                 # 0 处 var 引用，色板也没给它演示块
            continue
        body = Patch(f"圆角演示 {name}", re.escape(RADIUS_TMPL.format(n=name, v=old)),
                     RADIUS_TMPL.format(n=name, v=new), mode="replace").apply(body)
    need(body.count(RADIUS_TMPL.format(n=RADIUS_KEEP[0], v=RADIUS_KEEP[1])) == 1,
         "r-full 的圆角演示块必须原样在场")

    out = css + body
    out, n = re.subn(re.escape(_ds_zh.NOTE_ANCHOR), _note() + _ds_zh.NOTE_ANCHOR, out, count=1)
    need(n == 1, "没找到说明块的插入锚点")

    apply.stats = {"root": len(ROOT_MAP), "radius": len(RADIUS_MAP),
                   "shadow": len(SHADOW_MAP),
                   # 8 个色块对 + 7 个圆角演示块（r-full 那块是恒等断言，不改写）
                   "mirror": len(CHIP_MIRROR) + len(RADIUS_MAP)}
    return out


def _note() -> str:
    """说明块。注意：文本里不得出现 info 族的明亮 hex——深色层 apply_post 在本层
    之后按全文档计数映射它们，多一处字样就会把命中数撞歪。"""
    txt = NOTE_TEXT.format(
        page=PAGE, darkpage=E["page"], ink="/".join(C[n] for n in INKS),
        dl=f"{hex_lch(PAGE)[0] - hex_lch(E['page'])[0]:+.4f}",
        lc1=f"{abs(apca(E['fg-brand'], PAGE)):.1f}",
        lc2=f"{abs(apca(E['fg-brand-strong'], PAGE)):.1f}",
        total=CENSUS_TOTAL, adhoc=CENSUS_ADHOC)
    for h, _, _ in _theme_dark.INFO_MAP:
        need(h not in txt, f"说明块里不得出现 info 族明亮值 {h}（会撞 apply_post 计数）")
    return txt


def check_after_ds() -> None:
    """钉死设计层的文字色板普查结果。

    在编排里、`_ds_zh.apply` 之后调用。读的是设计层自己挂在函数属性上的那份 census
    ——色板就是按它生成的，不另算一遍。本层令牌变冷而 body 的插画字面值仍是暖炭，
    普查条目必然增加；不钉死的话，这个「已知差异」会退化成一次静默漂移。
    """
    census = getattr(_ds_zh.apply, "census", None)
    need(census, "拿不到设计层的 census（check_after_ds 必须在 _ds_zh.apply 之后调用）")
    adhoc = sum(1 for _, names, _ in census if not names)
    need((len(census), adhoc) == (CENSUS_TOTAL, CENSUS_ADHOC),
         f"文字色板普查漂了：得 {len(census)} 条 / {adhoc} 条无令牌，"
         f"钉死值为 {CENSUS_TOTAL} / {CENSUS_ADHOC}")


def summary() -> str:
    st = getattr(apply, "stats", {})
    return (f"皮肤层：{st.get('root', 0)} 条中性令牌再锚定（page {E['page']}→{PAGE}，"
            f"ΔL={hex_lch(PAGE)[0] - hex_lch(E['page'])[0]:+.4f}，C=0），"
            f"{st.get('radius', 0)} 条圆角改写 + r-full 保圆，{st.get('shadow', 0)} 条阴影，"
            f"{st.get('mirror', 0)} 处 body 令牌镜像；品牌与四族状态色恒等，"
            f"冷底上 fg-brand Lc {abs(apca(E['fg-brand'], PAGE)):.1f}")


if __name__ == "__main__":
    sys.exit("本文件是控制台皮肤层，不单独运行。请跑：python3 _build_zh.py --console")
