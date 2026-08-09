# -*- coding: utf-8 -*-
"""深色层：把复刻产物翻成深色，只作用于 `charm-preview-cjk-gb-zh-dark.html`。

管线位置（_build_zh.py --dark 编排）：

    charm-preview-cjk-gb.html
      └─ _theme_dark.apply → _ds_zh.apply → _theme_dark.apply_post → _localize_zh.apply
                                                → charm-preview-cjk-gb-zh-dark.html

两段的分工
----------
  · apply       主段，跑在设计层**之前**:就地改写 :root 令牌与全部字面色。
                设计层的 token_value() 与 text_color_census() 都是「首次声明胜」，
                主段先行，设计层读到的天然是深色值——状态色板与文字色板自动自证深色。
  · apply_post  后段，跑在设计层**之后**:设计层注入的 info 族来自其模块内硬编码的
                明亮常量（INFO_HUES），这里把那几个刚落地的值映射到深色，命中数逐条断言。

配色从哪里来
------------
不是手调，是从明亮版**算**出来的。空间用 OKLCH（感知均匀、hue-linear），
对比度用 APCA（W3C 草案 0.1.9,对深底浅字唯一给出可信读数的模型）；两组转换
内置本文件、零依赖。三条推导规则：

  · 面：保留相对 --page 的 ΔL,×1.30 暗环绕补偿（CIECAM16 暗环绕下感知对比约降
    24%），锚点从明亮版 --page 移到明亮版 --heading #1c1917——深色版的纸就是
    明亮版的墨。
  · 线：明亮版边框比所坐的面暗，深色版必须比面亮（中性族唯一的方向翻转）；
    ΔL 锚在各自坐的面上等量搬运（×1.00:暗环绕 ×1.30 与光渗 ×0.77 相抵）。
  · 墨：等 Lc 移植——解出深色 L,使 |Lc（深字，深底）| == |Lc（明字，明底）|。

外加两条修正：中性色彩度 ×1.615（Hunt 效应：同一彩度在暗底上显得更灰）；
C<0.010 的色相角是 8-bit 量化噪声，归到 ink 的 56°（#1c1917 的 H）。
状态族：soft/medium 是有色深底，H 不变、C 锁 0.045/0.062、L=page+0.030/+0.055
（0.045 是上界：再高 warning 就顶到 sRGB 色域边界）；strong 由等 Lc 在各自深色
soft 底上解出，C、H 不变，越界通道直接裁剪。

出厂值与复算断言
----------------
出厂值是 EXPECTED 定稿表（评审过的预演结果）。构建期用上述规则**重算全表**,
断言逐通道差 ≤1/255:OKLab 逆变换在 8-bit 取整边界上，不同实现会向不同方向翻，
钉「≤1 量化步」才是可复现的；真正逐字节钉死的是 APCA 审计（verify_derivation）：
八对组合的深色 Lc 与明亮版逐项差 ≤0.5。五个值是设计定稿、不走规则复算，
各有性质断言：

  · fg-brand #f4897f / fg-brand-strong #ffaa9a:严格等 Lc 会把彩度掉到 0.104,
    珊瑚红退成鲭鱼粉；设彩度下限 C≥0.13 / ≥0.10,拿 Lc 换彩度（53.7 / 67.2）。
    依据 Helmholtz–Kohlrausch:高彩度前景的视觉明度高于其亮度，APCA 不建模此项。
  · warning-medium #382605:C=0.062 在暗黄区顶出色域，上提 L 保住蓝通道不带状。
  · --hover-fill #2b2724:补 --ds-hover 落到冷灰 #e9e9ec 的漏洞，新增令牌。
  · tooltip 反色药丸 #38322e:跟墨表翻转是白底白字，恒等则消失在深面板里；
    取抬高两档的反色面，白字 Lc 102。

映射为什么是三级
----------------
「角色×上下文」三级，不是一张纯值表——同值异角必须分开：#fff 同时是 --card
（变深）与 --white（保白）；#a8a29e 同时是 --border-strong（线）与 --fg-disabled
（墨）；#1c1917 在色板 chip 上是 heading(→ #faf3ee)、在商品颜色选择器上是
「Black」这个商品色（恒等）；#ffe9c1 在 :root 是 warning-medium（变深）、在
ecommerce 插画里是暖光（恒等——插画只暗化纸与结构，不动彩色内容）。

  1. :root 内逐令牌名；
  2. CSS 字面值按声明定位（.ds 回退链、遮罩、mini-chip、hero mock）；
  3. body 按 （标签×属性）分表，单趟合并正则——映射的输出值（如 #1c1917）同时
     也是输入键，多趟会把输出再当输入二次映射。

外壳（SHELL_PATCH_CSS）与美国国旗 SVG 整段挖出保护、映射完原样放回；外壳另
追加亮玻璃覆写：外壳与被预览页面永远反相，「一眼可辨」的不变量在深色页上
因此仍然成立。
"""
from __future__ import annotations

import math
import re
import sys

import _ds_zh
from _ds_zh import Patch


def need(cond, msg):
    if not cond:
        sys.exit(f"[深色层失败] {msg}")


# ============================================================ 色彩数学（零依赖）
# sRGB↔OKLab 用 Ottosson 2020 的原始矩阵，APCA 用 W3C 草案 0.1.9 的常数。
# 两组转换都以评审时的锚点核过：#1c1917 的 OKLab L=0.2161,heading/page 的
# Lc=99.5,#ffffff on #1c1917 = 106.6（verify_derivation 里逐条断言）。

def _lin(c):
    return c / 12.92 if c <= 0.04045 else ((c + 0.055) / 1.055) ** 2.4


def _unlin(c):
    c = max(0.0, min(1.0, c))
    return c * 12.92 if c <= 0.0031308 else 1.055 * c ** (1 / 2.4) - 0.055


def _hex_rgb(h):
    h = h.lstrip("#")
    if len(h) == 3:
        h = "".join(c * 2 for c in h)
    return tuple(int(h[i:i + 2], 16) / 255 for i in (0, 2, 4))


def _rgb_hex(rgb):
    return "#%02x%02x%02x" % tuple(round(x * 255) for x in rgb)


def _oklab(r, g, b):
    r, g, b = _lin(r), _lin(g), _lin(b)
    l = 0.4122214708 * r + 0.5363325363 * g + 0.0514459929 * b
    m = 0.2119034982 * r + 0.6806995451 * g + 0.1073969566 * b
    s = 0.0883024619 * r + 0.2817188376 * g + 0.6299787005 * b
    l, m, s = l ** (1 / 3), m ** (1 / 3), s ** (1 / 3)
    return (0.2104542553 * l + 0.7936177850 * m - 0.0040720468 * s,
            1.9779984951 * l - 2.4285922050 * m + 0.4505937099 * s,
            0.0259040371 * l + 0.7827717662 * m - 0.8086757660 * s)


def hex_lch(h):
    L, a, b = _oklab(*_hex_rgb(h))
    return L, math.hypot(a, b), math.degrees(math.atan2(b, a)) % 360


def _lch_rgb(L, C, H):
    """OKLCH → sRGB 浮点；越出色域的通道直接裁剪（naive clip）。"""
    a = C * math.cos(math.radians(H))
    b = C * math.sin(math.radians(H))
    l = (L + 0.3963377774 * a + 0.2158037573 * b) ** 3
    m = (L - 0.1055613458 * a - 0.0638541728 * b) ** 3
    s = (L - 0.0894841775 * a - 1.2914855480 * b) ** 3
    return tuple(_unlin(max(0.0, min(1.0, x))) for x in (
        +4.0767416621 * l - 3.3077115913 * m + 0.2309699292 * s,
        -1.2684380046 * l + 2.6097574011 * m - 0.3413193965 * s,
        -0.0041960863 * l - 0.7034186147 * m + 1.7076147010 * s))


def lch_hex(L, C, H):
    return _rgb_hex(_lch_rgb(L, C, H))


def _apca_y(rgb):
    y = 0.2126729 * rgb[0] ** 2.4 + 0.7151522 * rgb[1] ** 2.4 + 0.0721750 * rgb[2] ** 2.4
    return y + (0.022 - y) ** 1.414 if y < 0.022 else y


def _apca(fg_rgb, bg_rgb):
    yt, yb = _apca_y(fg_rgb), _apca_y(bg_rgb)
    if abs(yb - yt) < 0.0005:
        return 0.0
    if yb > yt:
        s = (yb ** 0.56 - yt ** 0.57) * 1.14
        return 0.0 if s < 0.1 else (s - 0.027) * 100
    s = (yb ** 0.65 - yt ** 0.62) * 1.14
    return 0.0 if s > -0.1 else (s + 0.027) * 100


def apca(fg_hex, bg_hex):
    return _apca(_hex_rgb(fg_hex), _hex_rgb(bg_hex))


def _drift(a, b):
    ra, rb = _hex_rgb(a), _hex_rgb(b)
    return max(abs(round(x * 255) - round(y * 255)) for x, y in zip(ra, rb))


# ============================================================ 推导常数与定稿表
GAIN = 1.615          # 中性色彩度增益（Hunt 效应补偿）
NOISE_C = 0.010       # 彩度低于此值的色相角视为 8-bit 量化噪声
SURROUND = 1.30       # 暗环绕补偿（面的 ΔL 增益）
INK = "#1c1917"       # 明亮版 --heading:深色版全部推导的锚点

# 出厂定稿表：评审过的预演结果。verify_derivation() 用三条规则重算并断言
# 逐通道差 ≤1/255;带 * 的五个是设计定稿常量，只验性质，不走规则复算。
EXPECTED = {
    # 中性 · 暖炭 —— 面（ΔL×1.30,锚点 #1c1917）
    "band": "#15150d", "control-fill": "#1a1614", "page": "#1c1917",
    "card-soft": "#1f1c1a", "card": "#24201e",
    "efedeb": "#14110f",            # 插画纸面 #efedeb（非令牌），同面规则
    # 中性 —— 线（ΔL 锚在所坐的面，方向翻转，×1.00）
    "border-subtle": "#332f2c", "border": "#363230", "border-medium": "#45413f",
    "border-strong": "#736a64", "border-on-band": "#1b1d10",
    "gridline": "#2c2826",          # marketing 图表网格线 stroke #f5f4f1（非令牌），同线规则
    # 中性 —— 墨（等 Lc 移植）
    "fg-disabled": "#9e958e", "body-subtle": "#cebfb5", "body": "#e1d7cf",
    "heading": "#faf3ee",
    # 品牌 · 珊瑚红（基色不动；前景是设计定稿，拿 Lc 换彩度）
    "brand-soft": "#331716", "brand-softer": "#2a1817",
    "fg-brand": "#f4897f",          # * C=0.132≥0.13,Lc 53.7
    "fg-brand-strong": "#ffaa9a",   # * C=0.104≥0.10,Lc 67.2
    # 状态 · 四族（soft: L=page+.030 C=.045;medium: L=page+.055 C=.062;strong: 等 Lc）
    "success-strong": "#51c77b", "success-soft": "#092719",
    "danger-strong": "#ffa59b", "danger-soft": "#331719", "danger-medium": "#40181b",
    "warning-strong": "#f8aa5a", "warning-soft": "#291f04",
    "warning-medium": "#382605",    # * C=0.062 在暗黄区顶出色域，上提 L 保蓝通道
    "fg-warning": "#f8aa5a",        # 与 warning-strong 同值：两者由同一 Lc 目标解出
    "info-strong": "#81ccff", "info-soft": "#0f2235", "info-medium": "#0d2844",
    # 次要系列线：brand-soft/-softer 被图表当**线**用（次要系列、圆环轨道、图例点）。
    # 深色的 soft 令牌是为「徽章底」设计的面，与 card 的 ΔL≈0.002,线一画就消失；
    # 按线规则单独推导（ΔL 锚在 card、方向翻转），C 沿用深色 soft 族的 0.045/0.030。
    "series-soft": "#4b2d2b", "series-softer": "#392524",
    # 设计定稿
    "hover-fill": "#2b2724",        # * 新增令牌，card 与 border-subtle 之间的抬升面
    "tooltip": "#38322e",           # * 反色药丸：抬高两档的反色面
}

# 明亮版各族的非令牌字面值（令牌值 verify 时从产物 CSS 读，这两个只在插画/图表里）
LIGHT_EFEDEB, LIGHT_GRIDLINE = "#efedeb", "#f5f4f1"

# APCA 审计表：深色版感知对比必须是明亮版的逐项复刻（|Δ|≤0.5），
# 品牌前景两项除外——那是拿 Lc 换彩度的定稿，钉死绝对值。
AUDIT_PAIRS = (
    ("heading", "page"), ("body", "page"), ("body-subtle", "page"),
    ("fg-disabled", "page"), ("success-strong", "success-soft"),
    ("danger-strong", "danger-soft"), ("fg-warning", "warning-soft"),
    ("info-strong", "info-soft"),
)
BRAND_FG_LC = {"fg-brand": 53.7, "fg-brand-strong": 67.2}


def _norm6(h):
    h = h.lower()
    return "#" + "".join(c * 2 for c in h[1:]) if len(h) == 4 else h


def _neutral_ch(C, H, ink_c, ink_h):
    """中性色的 C/H:彩度 ×GAIN 且不低于 ink 的 C;噪声级彩度的色相归到 ink 的 H。"""
    return max(C * GAIN, ink_c), (H if C >= NOISE_C else ink_h)


def _solve_ink_L(target_lc, C, H, bg_hex):
    """解出深底上的墨的 L,使 |Lc| 达到 target（反极性，亮字深底）。"""
    bg = _hex_rgb(bg_hex)
    lo, hi = hex_lch(bg_hex)[0] + 0.01, 0.999
    for _ in range(60):
        mid = (lo + hi) / 2
        if abs(_apca(_lch_rgb(mid, C, H), bg)) < target_lc:
            lo = mid
        else:
            hi = mid
    return (lo + hi) / 2


def verify_derivation(css):
    """用三条规则从产物自己的明亮值重算全表，与 EXPECTED 逐项对照（≤1/255）；
    再跑 APCA 审计、序关系与定稿常量的性质断言。明亮值由 token_value() 读出，不手抄。"""
    lt = {n: _norm6(_ds_zh.token_value(css, n)) for n in (
        "heading", "body", "body-subtle", "fg-disabled", "page", "card", "card-soft",
        "control-fill", "band", "border", "border-subtle", "border-medium",
        "border-strong", "border-on-band", "brand", "brand-soft", "brand-softer",
        "fg-brand", "fg-brand-strong", "success-strong", "success-soft",
        "danger-strong", "danger-soft", "danger-medium", "warning-strong",
        "warning-soft", "warning-medium", "fg-warning", "white")}
    need(lt["heading"] == INK and lt["white"] == "#ffffff",
         "明亮版锚点不对：--heading/--white 与预期不符，保存件可能变了")
    # info 族此刻还不在产物里（设计层注入），明亮值取 _ds_zh 的模块常量
    lt["info-strong"], lt["info-soft"] = dict(_ds_zh.INFO_HUES)["info-strong"], \
        dict(_ds_zh.INFO_HUES)["info-soft"]

    ink_l, ink_c, ink_h = hex_lch(INK)
    need(abs(ink_l - 0.2161) < 5e-4 and abs(ink_h - 56.0) < 0.5,
         f"OKLab 实现漂了：#1c1917 算出 L={ink_l:.4f} H={ink_h:.1f},应为 0.2161/56°")
    need(abs(apca(INK, lt["page"]) - 99.5) < 0.1 and abs(apca("#ffffff", INK) + 106.6) < 0.1,
         "APCA 实现漂了：锚点 Lc 不等于 99.5 / -106.6")

    page_l = hex_lch(lt["page"])[0]
    bad = []

    def check(name, derived):
        d = _drift(derived, EXPECTED[name])
        if d > 1:
            bad.append(f"{name}: 推导 {derived} vs 定稿 {EXPECTED[name]}(漂移 {d})")

    # 面
    for n, light in (("band", lt["band"]), ("control-fill", lt["control-fill"]),
                     ("card-soft", lt["card-soft"]), ("card", lt["card"]),
                     ("efedeb", LIGHT_EFEDEB)):
        L, C, H = hex_lch(light)
        C2, H2 = _neutral_ch(C, H, ink_c, ink_h)
        check(n, lch_hex(ink_l + (L - page_l) * SURROUND, C2, H2))
    # 线（border 族坐在 card 上，border-on-band 坐在 band 上，gridline 坐在 card 上）
    for n, light, seat_l, seat_d in (
            ("border-subtle", lt["border-subtle"], lt["card"], EXPECTED["card"]),
            ("border", lt["border"], lt["card"], EXPECTED["card"]),
            ("border-medium", lt["border-medium"], lt["card"], EXPECTED["card"]),
            ("border-strong", lt["border-strong"], lt["card"], EXPECTED["card"]),
            ("border-on-band", lt["border-on-band"], lt["band"], EXPECTED["band"]),
            ("gridline", LIGHT_GRIDLINE, lt["card"], EXPECTED["card"])):
        L, C, H = hex_lch(light)
        C2, H2 = _neutral_ch(C, H, ink_c, ink_h)
        check(n, lch_hex(hex_lch(seat_d)[0] + (hex_lch(seat_l)[0] - L), C2, H2))
    # 次要系列线（线规则，C 用深色 soft 族的常数，H 不变）
    for n, light, cv in (("series-soft", lt["brand-soft"], .045),
                         ("series-softer", lt["brand-softer"], .030)):
        L, _, H = hex_lch(light)
        check(n, lch_hex(hex_lch(EXPECTED["card"])[0] + (1.0 - L), cv, H))
    # 墨
    for n in ("fg-disabled", "body-subtle", "body", "heading"):
        L, C, H = hex_lch(lt[n])
        C2 = C * GAIN
        H2 = H if C >= NOISE_C else ink_h
        check(n, lch_hex(_solve_ink_L(abs(apca(lt[n], lt["page"])), C2, H2, INK), C2, H2))
    # soft / medium（brand-softer 的常数不同：L=page+.016,C=.030）
    for n, dl, cv in (("brand-soft", .030, .045), ("brand-softer", .016, .030),
                      ("success-soft", .030, .045), ("danger-soft", .030, .045),
                      ("warning-soft", .030, .045), ("danger-medium", .055, .062)):
        check(n, lch_hex(ink_l + dl, cv, hex_lch(lt[n])[2]))
    # strong:等 Lc 在深色 soft 上解，C/H 保持
    for n, soft in (("success-strong", "success-soft"), ("danger-strong", "danger-soft")):
        _, C, H = hex_lch(lt[n])
        t = abs(apca(lt[n], lt[soft]))
        check(n, lch_hex(_solve_ink_L(t, C, H, EXPECTED[soft]), C, H))
    # fg-warning 与 warning-strong 同值，由 fg-warning 的 Lc 目标解出
    _, C, H = hex_lch(lt["fg-warning"])
    t = abs(apca(lt["fg-warning"], lt["warning-soft"]))
    check("fg-warning", lch_hex(_solve_ink_L(t, C, H, EXPECTED["warning-soft"]), C, H))
    need(EXPECTED["warning-strong"] == EXPECTED["fg-warning"],
         "warning-strong 与 fg-warning 应同值（同一 Lc 目标）")
    need(not bad, "推导与定稿表对不上（>1/255）：\n  " + "\n  ".join(bad))
    # 品牌底白字两版同值：--brand 恒等（ROOT_KEEP）+ 白字保白（TEXT_FILL），无需另行审计

    # APCA 审计：深色版是明亮版感知对比的逐项复刻
    for fg, bg in AUDIT_PAIRS:
        lcl = abs(apca(lt[fg], lt[bg]))
        lcd = abs(apca(EXPECTED[fg], EXPECTED[bg]))
        need(abs(lcd - lcl) <= 0.5,
             f"审计失败 {fg}/{bg}:light Lc={lcl:.1f} dark Lc={lcd:.1f}")
    for n, want in BRAND_FG_LC.items():
        got = abs(apca(EXPECTED[n], EXPECTED["page"]))
        need(abs(got - want) <= 0.2, f"{n} 的 Lc={got:.1f},定稿应为 {want}")
        floor = 0.13 if n == "fg-brand" else 0.10
        need(hex_lch(EXPECTED[n])[1] >= floor, f"{n} 彩度跌破下限 {floor}")
        need(abs(hex_lch(EXPECTED[n])[2] - hex_lch(lt[n])[2]) % 360 <= 5,
             f"{n} 色相偏离明亮版超过 5°")

    # 序关系：墨族明亮版越暗、深色版必须越亮；面的浮起方向不翻转；线全部比 page 亮
    inks = ("heading", "body", "body-subtle", "fg-disabled")
    light_order = sorted(inks, key=lambda n: hex_lch(lt[n])[0])
    dark_order = sorted(inks, key=lambda n: -hex_lch(EXPECTED[n])[0])
    need(light_order == dark_order, "墨族的明度序没有整体翻转")
    surf = ("band", "control-fill", "page", "card-soft", "card")
    need([s for s in surf] == sorted(surf, key=lambda n: hex_lch(EXPECTED[n])[0]),
         "面的层级顺序被打乱（卡片应仍比页面亮）")
    for n in ("border-subtle", "border", "border-medium", "border-strong", "border-on-band"):
        need(hex_lch(EXPECTED[n])[0] > hex_lch(EXPECTED["page"])[0],
             f"{n} 没有比 page 亮（线的方向必须翻转）")
    # 定稿常量的性质
    need(hex_lch(EXPECTED["card"])[0] < hex_lch(EXPECTED["hover-fill"])[0]
         < hex_lch(EXPECTED["border-subtle"])[0], "hover-fill 应落在 card 与 border-subtle 之间")
    need(abs(apca("#ffffff", EXPECTED["tooltip"])) >= 85, "tooltip 药丸上的白字不够亮")
    need(hex_lch(EXPECTED["tooltip"])[0] - hex_lch(EXPECTED["card-soft"])[0] >= 0.08,
         "tooltip 药丸浮不出面板")
    # 四族 soft 两两色相拉开 ≥25°,不然深底上退成一团灰
    softs = ("success-soft", "danger-soft", "warning-soft", "info-soft")
    hs = [hex_lch(EXPECTED[n])[2] for n in softs]
    for i in range(len(hs)):
        for j in range(i + 1, len(hs)):
            d = abs(hs[i] - hs[j]) % 360
            need(min(d, 360 - d) >= 25, f"{softs[i]} 与 {softs[j]} 色相距离不足")


# ============================================================ 第 1 级：：root 逐令牌
E = EXPECTED
ROOT_MAP = (  # （令牌名，明亮值，深色值）——明亮值一并断言；同值异角全靠这一级分开
    ("heading", "#1c1917", E["heading"]), ("body", "#57534e", E["body"]),
    ("body-subtle", "#79716b", E["body-subtle"]),
    ("fg-brand", "#c9443a", E["fg-brand"]),
    ("fg-brand-strong", "#ae382f", E["fg-brand-strong"]),
    ("fg-disabled", "#a8a29e", E["fg-disabled"]),
    ("page", "#f7f7f5", E["page"]), ("card", "#fff", E["card"]),
    ("card-soft", "#fbfaf9", E["card-soft"]),
    ("control-fill", "#f5f4f1", E["control-fill"]),
    ("app-surface", "#f5f4f1", E["control-fill"]),
    ("band", "#f1f2ea", E["band"]),
    ("brand-soft", "#fbd9d6", E["brand-soft"]),
    ("brand-softer", "#fdedec", E["brand-softer"]),
    ("success-strong", "#179c53", E["success-strong"]),
    ("success-soft", "#eafbf1", E["success-soft"]),
    ("danger-strong", "#c73737", E["danger-strong"]),
    ("danger-soft", "#fbebeb", E["danger-soft"]),
    ("danger-medium", "#f5dbdb", E["danger-medium"]),
    ("warning-soft", "#fff6df", E["warning-soft"]),
    ("warning-medium", "#ffe9c1", E["warning-medium"]),
    ("warning-strong", "#d98200", E["warning-strong"]),
    ("fg-warning", "#b36a00", E["fg-warning"]),
    ("border", "#e7e6e5", E["border"]), ("border-subtle", "#ebebe7", E["border-subtle"]),
    ("border-medium", "#d6d3d1", E["border-medium"]),
    ("border-strong", "#a8a29e", E["border-strong"]),
    ("border-on-band", "#e6e8dd", E["border-on-band"]),
)
ROOT_KEEP = (  # 恒等令牌：品牌与状态基色、点缀色、--white。存在与取值都要断言。
    ("brand", "#e4544b"), ("brand-light", "#ec6f66"), ("brand-medium", "#d24439"),
    ("brand-strong", "#b8362e"), ("success", "#1ebd66"), ("danger", "#e5484d"),
    ("warning", "#ffa211"), ("purple", "#8e40cc"), ("indigo", "#473dfe"),
    ("orange", "#fc5f35"), ("sky", "#09f"), ("teal", "#0d9488"),
    ("cyan", "#0891b2"), ("pink", "#e60076"), ("white", "#fff"),
)
# 阴影与焦点环也在 :root 一级就地改写（不追加，避免 census 首见歧义）。
# 深色 UI 里让卡片浮起来的是顶缘高光（inset）而非黑影——黑影叠黑底等于没有，
# 但仍加深保底；焦点环不能用品牌浅色调（brand-soft 已变深），用品牌色本身加透明度。
ROOT_DECL = (
    ("elevation-1",
     "--elevation-1:0 1px 2px 0 #0000000d",
     "--elevation-1:inset 0 1px 0 #ffffff0f, 0 1px 2px 0 #00000040"),
    ("elevation-2",
     "--elevation-2:0px 0px 0px 1px #0000000a, 0px 1px 1px .5px #0000000a, "
     "0px 3px 3px 1.5px #0000000a, 0px 6px 6px -3px #0000000a, "
     "0px 12px 12px -6px #0000000a, 0px 24px 24px -12px #0000000a",
     "--elevation-2:inset 0 1px 0 #ffffff0f, 0px 0px 0px 1px #00000026, "
     "0px 1px 1px .5px #00000026, 0px 3px 3px 1.5px #00000026, "
     "0px 6px 6px -3px #00000026, 0px 12px 12px -6px #00000026, "
     "0px 24px 24px -12px #00000026"),
    # elevation-3 是品牌辉光 rgb(from var(--brand)),brand 恒等，自动成立，不动
    ("focus-ring",
     "--focus-ring:0 0 0 4px var(--brand-soft)",
     "--focus-ring:0 0 0 4px #e4544b40"),
)


# ============================================================ 第 2 级：CSS 字面值按声明定位
def css_patches():
    """zinc 系冷灰按明度归到暖石灰对应档，四个遮罩统一 #000000b3,
    hero mock 的暖褐 alpha 改叠白（深底上叠光不叠影），mini-chip 跟状态族。"""
    ds = (  # （链名，整条明亮声明，深色回退值）
        ("--ds-heading:var(--heading,var(--color-heading,#18181b))", E["heading"]),
        ("--ds-body:var(--body,var(--color-body,#52525b))", E["body"]),
        ("--ds-subtle:var(--body-subtle,var(--color-body-subtle,#71717a))", E["body-subtle"]),
        ("--ds-card:var(--card,var(--color-neutral-primary-soft,var(--neutral-primary-soft,#fff)))", E["card"]),
        ("--ds-control:var(--card,var(--color-neutral-primary,#fff))", E["card"]),
        ("--ds-hover:var(--hover-fill,var(--color-neutral-secondary-medium,var(--neutral-tertiary-medium,#e9e9ec)))", E["hover-fill"]),
        ("--ds-border:var(--border,var(--color-border-default,var(--border-default,#e4e4e7)))", E["border"]),
        ("--ds-brand:var(--brand,var(--color-brand,#18181b))", E["heading"]),
        ("--ds-brand-soft:var(--brand-softer,var(--color-brand-softer,var(--brand-soft,#f0f0f0)))", E["brand-softer"]),
        ("--ds-success-soft:var(--success-soft,var(--color-success-soft,#f0fdf4))", E["success-soft"]),
        ("--ds-success-fg:var(--success-strong,var(--color-fg-success-strong,var(--color-fg-success,var(--fg-success,#15803d))))", E["success-strong"]),
        ("--ds-danger-soft:var(--danger-soft,var(--color-danger-soft,#fef2f2))", E["danger-soft"]),
        ("--ds-danger-fg:var(--danger-strong,var(--color-fg-danger-strong,var(--color-fg-danger,var(--fg-danger,#b91c1c))))", E["danger-strong"]),
        ("--ds-warning-soft:var(--warning-soft,var(--color-warning-soft,#fffbeb))", E["warning-soft"]),
        ("--ds-warning-fg:var(--fg-warning,var(--color-fg-warning,var(--warning-strong,#b45309)))", E["fg-warning"]),
    )
    out = []
    for decl, dark in ds:
        i = decl.rindex("#")
        j = decl.index(")", i)
        out.append(Patch("ds 链 " + decl[:decl.index(":")],
                         re.escape(decl), decl[:i] + dark + decl[j:], mode="replace"))
    out += [
        Patch("modal 遮罩", re.escape("background:#00000080"), "background:#000000b3", mode="replace"),
        Patch("pdrawer 遮罩", re.escape("background:#1c191766"), "background:#000000b3", mode="replace"),
        Patch("appsidebar 遮罩", re.escape("background:#0006") + r"(?![0-9a-fA-F])",
              "background:#000000b3", mode="replace"),
        Patch("ds 遮罩", re.escape("background:#00000073"), "background:#000000b3", mode="replace"),
        Patch("hero mock 面", re.escape("#4419060a"), "#ffffff0a", mode="replace"),
        Patch("hero mock 边", re.escape("#4419060d"), "#ffffff12", mode="replace"),
        Patch("hero mock 内边", re.escape("#44190624"), "#ffffff1f", mode="replace"),
        Patch("mini-chip 底", re.escape("background:#eafbf1"), "background:" + E["success-soft"], mode="replace"),
        Patch("mini-chip 字", re.escape("color:#179c53"), "color:" + E["success-strong"], mode="replace"),
    ]
    return tuple(out)


# CSS 里刻意不动、但必须在场的字面值（恒等断言）：金星、白开关滑块、白箭头
CSS_KEEP = (("pstar 金星", r"#ffb020(?![0-9a-fA-F])", 2),
            ("mini-toggle 滑块", r"background:#fff(?=[;}])", 1),
            ("mini__send 白箭头", re.escape("2px solid #fff"), 2))


# ============================================================ 第 3 级：body 按 （标签×属性）分表
# 键一律小写——全文档大写 hex 只在美国国旗段（挖出保护），表天然不会命中它。
_ID = None   # 恒等（仍然计数、仍然要求在表内，保证「每个颜色位置都有映射」）

TEXT_FILL = {  # <text> 的 fill=:墨
    "#1c1917": E["heading"], "#79716b": E["body-subtle"], "#a8a29e": E["fg-disabled"],
    "#b36a00": E["fg-warning"], "#179c53": E["success-strong"],
    "#c73737": E["danger-strong"],
    "#ffffff": _ID,             # 品牌红底上的白字，保白
    "#1ebd66": _ID, "#8e40cc": _ID, "#fc5f35": _ID,     # 基色/点缀直标的文字
}
SHAPE_FILL = {  # 形状的 fill=:面（插画只暗化纸与结构，不动彩色内容）
    "#ffffff": E["card"],       # 插画里的卡片面
    "#fbfaf9": E["card-soft"], "#f5f4f1": E["control-fill"], "#efedeb": E["efedeb"],
    "#e7e6e5": E["border"],     # 108×8 的骨架条：以 fill 画的线，走线的值
    "#eafbf1": E["success-soft"], "#fbebeb": E["danger-soft"], "#fff6df": E["warning-soft"],
    "#1c1917": E["tooltip"],    # marketing 图表的反色药丸（全文档唯一一处形状 fill 用墨）
    "#ffe9c1": _ID, "#ffce30": _ID, "#bff0d4": _ID,     # 插画的暖光与彩色内容
    "#1ebd66": _ID, "#e5484d": _ID, "#8e40cc": _ID, "#fc5f35": _ID, "#ffa211": _ID,
}
STROKE = {  # stroke=:线（编织纹理是墨，深底上翻亮——叠光不叠影）
    "#1c1917": E["heading"],    # stroke-opacity=0.03 的编织纹理
    "#e7e6e5": E["border"], "#ebebe7": E["border-subtle"], "#a8a29e": E["border-strong"],
    "#f5f4f1": E["gridline"],   # marketing 图表网格线
    "#fff": E["card"], "#ffffff": E["card"],    # 饼图分片描边/红点白圈：底色的角色
    "#79716b": E["body-subtle"], "#ffa211": _ID,
}
STOP_COLOR = {"#f5f4f1": E["control-fill"], "#fbfaf9": E["card-soft"]}  # 插画纸面渐变
STYLE_ATTR = {  # 非色块的内联 style:全是内容色，恒等——
    # ecommerce 商品颜色选择器（Silver/Space grey/Black 是商品的颜色，不是 UI 令牌）
    "#d6d3d1": _ID, "#57534e": _ID, "#1c1917": _ID, "#1f5cf7": _ID,
    "#1ebd66": _ID, "#ffce6a": _ID,
    # components 头图的 brand ramp 装饰条（品牌资产）
    "#e4544b": _ID, "#ec6f66": _ID, "#d24439": _ID, "#b8362e": _ID,
    "#fbd9d6": _ID, "#fdedec": _ID,
}
CHIP_MAP = {  # 色板 chip+label 成对映射；brand ramp 六块恒等（跨文件比较的锚点）
    "#e4544b": _ID, "#ec6f66": _ID, "#d24439": _ID, "#b8362e": _ID,
    "#fbd9d6": _ID, "#fdedec": _ID,
    "#f7f7f5": E["page"], "#ffffff": E["card"], "#fbfaf9": E["card-soft"],
    "#f5f4f1": E["control-fill"], "#f1f2ea": E["band"],
    "#e7e6e5": E["border"], "#ebebe7": E["border-subtle"],
    "#1ebd66": _ID, "#179c53": E["success-strong"], "#eafbf1": E["success-soft"],
    "#e5484d": _ID, "#c73737": E["danger-strong"], "#fbebeb": E["danger-soft"],
    "#ffa211": _ID, "#d98200": E["warning-strong"],
}

# body 命中数，照产物数出来（census:22 对色块 + 各属性位置）。变一处就报错。
EXPECTED_BODY = {
    ("chip", "#e4544b"): 1, ("chip", "#ec6f66"): 1, ("chip", "#d24439"): 1,
    ("chip", "#b8362e"): 1, ("chip", "#fbd9d6"): 1, ("chip", "#fdedec"): 1,
    ("chip", "#f7f7f5"): 1, ("chip", "#ffffff"): 1, ("chip", "#fbfaf9"): 1,
    ("chip", "#f5f4f1"): 2, ("chip", "#f1f2ea"): 1, ("chip", "#e7e6e5"): 1,
    ("chip", "#ebebe7"): 1, ("chip", "#1ebd66"): 1, ("chip", "#179c53"): 1,
    ("chip", "#eafbf1"): 1, ("chip", "#e5484d"): 1, ("chip", "#c73737"): 1,
    ("chip", "#fbebeb"): 1, ("chip", "#ffa211"): 1, ("chip", "#d98200"): 1,
    ("text-fill", "#1c1917"): 13, ("text-fill", "#79716b"): 46,
    ("text-fill", "#a8a29e"): 14, ("text-fill", "#ffffff"): 6,
    ("text-fill", "#b36a00"): 1, ("text-fill", "#179c53"): 3,
    ("text-fill", "#c73737"): 1, ("text-fill", "#1ebd66"): 1,
    ("text-fill", "#8e40cc"): 1, ("text-fill", "#fc5f35"): 1,
    ("shape-fill", "#ffffff"): 29, ("shape-fill", "#fbfaf9"): 1,
    ("shape-fill", "#f5f4f1"): 22, ("shape-fill", "#efedeb"): 20,
    ("shape-fill", "#e7e6e5"): 20, ("shape-fill", "#eafbf1"): 3,
    ("shape-fill", "#fbebeb"): 1, ("shape-fill", "#fff6df"): 1,
    ("shape-fill", "#1c1917"): 1, ("shape-fill", "#ffe9c1"): 28,
    ("shape-fill", "#ffce30"): 20, ("shape-fill", "#bff0d4"): 6,
    ("shape-fill", "#1ebd66"): 1, ("shape-fill", "#e5484d"): 1,
    ("shape-fill", "#8e40cc"): 1, ("shape-fill", "#fc5f35"): 1,
    ("shape-fill", "#ffa211"): 1,
    ("stroke", "#1c1917"): 20, ("stroke", "#e7e6e5"): 20, ("stroke", "#ebebe7"): 9,
    ("stroke", "#a8a29e"): 7, ("stroke", "#f5f4f1"): 5, ("stroke", "#fff"): 3,
    ("stroke", "#ffffff"): 1, ("stroke", "#ffa211"): 1, ("stroke", "#79716b"): 1,
    ("stop-color", "#f5f4f1"): 20, ("stop-color", "#fbfaf9"): 20,
    ("style", "#d6d3d1"): 1, ("style", "#57534e"): 1, ("style", "#1c1917"): 1,
    ("style", "#1f5cf7"): 1, ("style", "#1ebd66"): 1, ("style", "#ffce6a"): 1,
    ("style", "#e4544b"): 1, ("style", "#ec6f66"): 1, ("style", "#d24439"): 1,
    ("style", "#b8362e"): 1, ("style", "#fbd9d6"): 1, ("style", "#fdedec"): 1,
}

_CHIP_RE = (r'<span class="ds__chip" style="background:(#[0-9a-f]{3,8})"></span>'
            r'<b>([-\w]+)</b><span>(#[0-9a-f]{3,8})</span>')
_TAG_RE = r'<([a-zA-Z][\w-]*)((?:"[^"]*"|[^>"])*)>'
_MASTER = re.compile(_CHIP_RE + "|" + _TAG_RE)
_ATTR = re.compile(r'(?<=\s)(fill|stroke|stop-color|style)="([^"]*)"')
_HEX = re.compile(r"#[0-9a-f]{3,8}\b")


def _map_body(body, counts, errors):
    """单趟合并正则：色块对优先（chip 与 label 同表同映射），其余按 （标签×属性）查表。"""
    def hex_sub(kind, tag):
        def sub(hm):
            v = hm.group(0)
            table = {"text-fill": TEXT_FILL, "shape-fill": SHAPE_FILL, "stroke": STROKE,
                     "stop-color": STOP_COLOR, "style": STYLE_ATTR}[kind]
            if v not in table:
                errors.append(f"{kind} <{tag}> 出现未映射的 {v}")
                return v
            counts[(kind, v)] = counts.get((kind, v), 0) + 1
            return table[v] or v
        return sub

    def attr_sub(tag):
        def sub(am):
            attr, val = am.group(1), am.group(2)
            if "#" not in val:
                return am.group(0)
            kind = ("text-fill" if attr == "fill" and tag in ("text", "tspan")
                    else "shape-fill" if attr == "fill" else attr)
            return f'{attr}="{_HEX.sub(hex_sub(kind, tag), val)}"'
        return sub

    def master_sub(m):
        if m.group(1):                       # 色块对：chip 与 label 必须同值、同映射
            chip, name, label = m.group(1), m.group(2), m.group(3)
            if chip != label:
                errors.append(f"色块 {name} 的 chip({chip}) 与 label({label}) 不一致")
            if chip not in CHIP_MAP:
                errors.append(f"色块 {name} 出现未映射的 {chip}")
                return m.group(0)
            counts[("chip", chip)] = counts.get(("chip", chip), 0) + 1
            v = CHIP_MAP[chip] or chip
            return (f'<span class="ds__chip" style="background:{v}"></span>'
                    f"<b>{name}</b><span>{v}</span>")
        tag, attrs = m.group(4), m.group(5)
        if "#" not in attrs:
            return m.group(0)
        return "<" + tag + _ATTR.sub(attr_sub(tag), attrs) + ">"

    return _MASTER.sub(master_sub, body)


# 次要系列线与其图例点：var(--brand-soft/-softer) 在**线/标记**上下文改指专用深色线值。
# 这是三级映射的 var() 延伸：同一令牌，面上下文（徽章、相框）保持 var 自动跟随，
# 线上下文（次要系列、圆环轨道、12px 图例点）一画就消失，必须换成 series-* 字面值。
# gauge 的 Desktop 弧走 var(--control-fill),明暗两版都与图例点异色，是原站自己的怪癖，不修。
def var_patches():
    return (
        Patch("marketing 教职工图例点",
              re.escape('<circle cx="522" cy="29" r="4" fill="var(--brand-soft)"></circle>'),
              f'<circle cx="522" cy="29" r="4" fill="{E["series-soft"]}"></circle>',
              mode="replace"),
        Patch("次要系列线 stroke", re.escape('stroke="var(--brand-soft)"'),
              f'stroke="{E["series-soft"]}"', count=2, mode="replace"),
        Patch("图例点 chart-tip__dot", re.escape('style="background:var(--brand-soft)"'),
              f'style="background:{E["series-soft"]}"', count=2, mode="replace"),
        Patch("Plan mix 圆环轨道", re.escape('stroke="var(--brand-softer)"'),
              f'stroke="{E["series-softer"]}"', mode="replace"),
    )


# 面积渐变的顶部 stop:同一 alpha 在暗环绕下感知更弱，统一 ×4/3 补偿（是补偿不是加戏）
OPACITY_PATCHES = (
    Patch("渐变补偿 .24", re.escape('stop-opacity="0.24"'), 'stop-opacity="0.32"', mode="replace"),
    Patch("渐变补偿 .22", re.escape('stop-opacity="0.22"'), 'stop-opacity="0.29"', count=3, mode="replace"),
    Patch("渐变补偿 .20", re.escape('stop-opacity="0.20"'), 'stop-opacity="0.27"', mode="replace"),
)

# ============================================================ 保护段与追加段
SHELL_MARK = "/* ==== 外壳补丁"
FLAG_RE = re.compile(r'<span class="lang-flag"[^>]*>.*?</span>', re.S)
FLAG_HEX = (("#FFFFFF", 51), ("#B22234", 7), ("#3C3B6E", 1))   # 国旗的 59 个大写 hex

EXTRA_CSS = """
/* ==== 深色层补丁（_theme_dark.py）：外壳翻亮玻璃 + 深色杂项 ====
   外壳与被预览页面永远反相——浅色页配深玻璃、深色页配亮玻璃，
   「一眼可辨这是外壳」的不变量因此在深色页上仍然成立。
   覆写必须盖全全部态：漏掉 is-active:hover 会残留明亮版的 #f4f4f5 亮斑。*/
:root{color-scheme:dark;--hover-fill:#2b2724}
.pv-switch{border:1px solid #0000001f;background:#f5f2efd9}
.pv-switch__btn{color:#1c1917cc}
.pv-switch__btn:hover{background:#00000014;color:#1c1917}
.pv-switch__btn:focus-visible{outline:2px solid #1c1917}
.pv-switch__btn.is-active{background:#1c1917;color:#f5f2ef}
.pv-switch__btn.is-active:hover{background:#2b2724}
/* 明亮位图在深底上像发光的贴纸：非破坏性压暗（Material/Apple 深色规范的通行做法），
   滤镜可逆，像素资产分毫未动。*/
#pv-marketing img{filter:brightness(.92) saturate(.96)}
"""

NOTE = """  ⚠ 本文件在设计层之前还过了一道**深色层**(_theme_dark.py):同一份内容的
     深色配色版，与明亮版 charm-preview-cjk-gb-zh.html 并排对照用。
     · 配色由明亮版推导而非手调：OKLCH 空间 + APCA 对比度。面保相对 page 的
       ΔL（×1.30 暗环绕补偿），线翻转方向、ΔL 锚在所坐的面上等量搬运，
       墨走等 Lc 移植；深色版的纸（#1c1917）就是明亮版的墨。
     · APCA 审计：八对组合的感知对比与明亮版逐项差 ≤0.5;品牌前景两项例外，
       拿 Lc 换彩度（Helmholtz–Kohlrausch 依据），Lc 53.7 / 67.2。
     · 品牌与状态基色、点缀色、插画暖光、商品颜色不动；明亮位图只加
       非破坏性压暗滤镜（brightness .92 saturate .96），像素资产未动。
     · 图表次要系列线（brand-soft 作 stroke 与图例点）换用按线规则推导的
       专用值——深色 soft 是徽章底的面，与卡片同明度，画成线会消失。
     · 底部切换器翻成亮玻璃：外壳与被预览页面永远反相，「一眼可辨」仍成立。

"""


# ============================================================ 两段入口
def apply(html: str) -> str:
    """主段：在设计层之前，把复刻产物整体翻成深色。"""
    k = html.index("</style>")
    css, body = html[:k], html[k:]

    # 推导复算 + 审计（明亮值从产物自己读）
    verify_derivation(css)

    # 挖出保护段：外壳（值与页面共用，#00000080/#f4f4f5 都会被误伤）与美国国旗
    i = css.find(SHELL_MARK)
    need(i >= 0, "找不到外壳补丁段")
    css, shell = css[:i], css[i:]
    flags = list(FLAG_RE.finditer(body))
    need(len(flags) == 1, f"lang-flag 段命中 {len(flags)} 处，期望 1")
    flag = flags[0].group(0)
    for h, n in FLAG_HEX:
        need(flag.count(h) == n, f"国旗段 {h} 有 {flag.count(h)} 个，期望 {n}")
    body = body[:flags[0].start()] + "\x00FLAG\x00" + body[flags[0].end():]

    # 第 1 级：：root 逐令牌就地改写；恒等令牌断言在场
    for name, light, dark in ROOT_MAP:
        css = Patch(f"--{name}", re.escape(f"--{name}:{light}") + r"(?=[;}])",
                    f"--{name}:{dark}", mode="replace").apply(css)
    for name, val in ROOT_KEEP:
        need(re.search(re.escape(f"--{name}:{val}") + r"(?=[;}])", css),
             f"恒等令牌 --{name}:{val} 不在场")
    for label, light, dark in ROOT_DECL:
        css = Patch(label, re.escape(light), dark, mode="replace").apply(css)

    # 第 2 级：CSS 字面值按声明定位；刻意保留的字面值断言在场
    for p in css_patches():
        css = p.apply(css)
    for label, pat, cnt in CSS_KEEP:
        got = len(re.findall(pat, css))
        need(got == cnt, f"[{label}] 恒等断言：命中 {got} 处，期望 {cnt}")

    # 第 3 级：body 单趟合并正则（色块对 + 标签×属性）
    counts, errors = {}, []
    body = _map_body(body, counts, errors)
    need(not errors, "body 映射失败：\n  " + "\n  ".join(errors[:12]))
    miss = {k for k in EXPECTED_BODY if counts.get(k, 0) != EXPECTED_BODY[k]}
    extra = {k for k in counts if k not in EXPECTED_BODY}
    need(not miss and not extra,
         "body 命中数与普查不符：\n  " +
         "\n  ".join(f"{k}: 得 {counts.get(k, 0)},期望 {EXPECTED_BODY.get(k, '（不在表内）')}"
                     for k in sorted(miss | extra)))
    for p in OPACITY_PATCHES:
        body = p.apply(body)
    for p in var_patches():
        body = p.apply(body)

    # 明亮版的中性值必须已从颜色位置上绝迹（在放回保护段之前查）
    gone = ("#f7f7f5", "#fbfaf9", "#f5f4f1", "#f1f2ea", "#e7e6e5", "#ebebe7",
            "#efedeb", "#a8a29e", "#79716b", "#c9443a", "#ae382f", "#e6e8dd",
            "#eafbf1", "#fbebeb", "#fff6df", "#f5dbdb", "#d98200", "#b36a00",
            "#e9e9ec", "#18181b", "#52525b", "#71717a", "#e4e4e7", "#f0f0f0",
            "#f0fdf4", "#15803d", "#fef2f2", "#b91c1c", "#fffbeb", "#b45309")
    for h in gone:
        pat = re.escape(h) + r"(?![0-9a-fA-F])"
        n = len(re.findall(pat, css))
        need(n == 0, f"CSS 里仍残留明亮值 {h} ×{n}")
    # body 里 #d6d3d1/#57534e/#1c1917/#ffe9c1 等是内容色，允许在场；只查纯 UI 中性值
    for h in ("#f7f7f5", "#fbfaf9", "#efedeb", "#ebebe7", "#e6e8dd", "#eafbf1",
              "#fbebeb", "#fff6df", "#d98200", "#b36a00"):
        pat = re.escape(h) + r"(?![0-9a-fA-F])"
        n = len(re.findall(pat, body))
        need(n == 0, f"body 里仍残留明亮值 {h} ×{n}")

    # 放回保护段，追加深色补丁段（令牌与覆写都落在 </style> 之前）
    body = body.replace("\x00FLAG\x00", flag, 1)
    out = css + shell + EXTRA_CSS + body
    for h, n in FLAG_HEX:
        need(out.count(h) == n, f"国旗放回后 {h} 计数不对")
    need(len(re.findall(r"#2041\b", out)) == 3, "正文 Invoice #2041 应有 3 处且不被触碰")

    # 说明块（最终顺序：深色层 → 设计层 → 内容层 → 锚点）。
    # 本层注入的中文全在注释里（<!-- --> 说明块与 CSS 注释），不进渲染树，
    # 不受子集字体覆盖约束——与 _ds_zh/_localize_zh 的说明块同一先例
    # （它们的 ⚠ 同样不在 GB2312 子集内）；会渲染的 DOM 本层一个字都没加。
    out, n = re.subn(re.escape(_ds_zh.NOTE_ANCHOR), NOTE + _ds_zh.NOTE_ANCHOR, out, count=1)
    need(n == 1, "没找到说明块的插入锚点")

    apply.stats = {"root": len(ROOT_MAP) + len(ROOT_DECL), "body": sum(counts.values()),
                   "css": len(css_patches()), "series": sum(p.count for p in var_patches())}
    return out


# 设计层 INFO_HUES 落地的明亮值 → 深色（base 恒等）。命中 = :root 注入 + 色板 chip/label。
INFO_MAP = (("#1a68c1", "#81ccff", 3), ("#eaf2fb", "#0f2235", 3), ("#d4e4f7", "#0d2844", 1))


def apply_post(html: str) -> str:
    """后段：设计层刚注入的 info 族由明亮常量而来，在此映射到深色。"""
    # 深色值也复算一遍：strong 等 Lc 在深色 soft 上解，soft/medium 与其它三族同公式
    _, C, H = hex_lch("#1a68c1")
    t = abs(apca("#1a68c1", "#eaf2fb"))
    ink_l = hex_lch(INK)[0]
    for name, derived in (("info-strong", lch_hex(_solve_ink_L(t, C, H, E["info-soft"]), C, H)),
                          ("info-soft", lch_hex(ink_l + .030, .045, hex_lch("#eaf2fb")[2])),
                          ("info-medium", lch_hex(ink_l + .055, .062, hex_lch("#d4e4f7")[2]))):
        need(_drift(derived, E[name]) <= 1,
             f"info 推导与定稿不符：{name} {derived} vs {E[name]}")

    need(html.count("#287ee2") == 3, "info 基色 #287ee2 应恰有 3 处（：root+chip+label）且恒等")
    for light, dark, cnt in INFO_MAP:
        html, n = re.subn(re.escape(light) + r"(?![0-9a-fA-F])", dark, html)
        need(n == cnt, f"info 映射 {light}→{dark} 命中 {n} 处，期望 {cnt}")
    apply_post.hits = sum(c for _, _, c in INFO_MAP)
    return html


def summary() -> str:
    st = getattr(apply, "stats", {})
    post = getattr(apply_post, "hits", 0)
    return (f"深色层：{st.get('root', 0)} 条 :root 令牌就地改写，{st.get('css', 0)} 处 CSS "
            f"字面值，{st.get('body', 0)} 处 body 属性，{st.get('series', 0)} 处次要系列线，"
            f"后段 info 族 {post} 处；APCA 审计 8 项 |Δ|≤0.5，"
            f"品牌前景 Lc 53.7/67.2（拿 Lc 换彩度）")


if __name__ == "__main__":
    sys.exit("本文件是深色层，不单独运行。请跑：python3 _build_zh.py --dark")
