# -*- coding: utf-8 -*-
"""品牌层：把珊瑚红品牌色阶换成蓝色，只作用于 `-sim` 两个产物（明亮版与深色版）。

管线位置（_build_zh.py 编排）：

    --sim          charm-preview-cjk-gb.html
                     └─ apply → _ds_zh.apply → apply_post → _localize_zh.apply
                                               → charm-preview-cjk-gb-zh-sim.html
    --sim --dark   charm-preview-cjk-gb.html
                     └─ _theme_dark.apply → apply_dark → _ds_zh.apply
                        → _theme_dark.apply_post → apply_post(dark=True) → _localize_zh.apply
                                               → charm-preview-cjk-gb-zh-sim-dark.html

为什么换
--------
试验台要承载仿真模型界面。原站品牌色 --brand #e4544b 与 --danger #e5484d 在 OKLCH 里
色相只差 4°、明度只差 0.011——「运行」按钮与「发散/报错」同色，这在仿真界面里是硬伤。
蓝是 CAE 软件的通行配色，离 success / danger / warning 都在 110° 以上。备选的石油青
（H≈204）虽然落在状态色相环最大空档的中点，但与图表的 --teal 只差 19°，相邻系列会
分不清，故不取。

锚点：设计指定的 #1a66ff
------------------------
品牌主色是设计指定的 ANCHOR（参考按钮在 DevTools 里的计算值 rgb(26 102 255)，
即 oklch(0.57 0.24 262.24)），不是推出来的；其余七档围绕它推导。不从截图取色：
Mac 截图带显示器 ICC，直接读像素会偏（曾读成 #3264f6）。它比「等 Lc 直接转色相」
得到的蓝更饱和、更深：白字 Lc 77.7（珊瑚 brand 是 69.2），C/Cmax 1.00（珊瑚 0.73，
蓝通道 255，正在 sRGB 色域边界上）。所以推导不能再是「每档等 Lc」——那样 brand-medium
会比 brand 还浅，.btn--primary 的 light → brand → medium 渐变明暗倒挂。

明亮版的分工
------------
  · apply       主段，跑在设计层**之前**：就地改写 8 个品牌令牌与它们在 body 里的镜像。
                设计层的 token_value() 与 text_color_census() 都是「首次声明胜」，主段先行，
                文字色板的「品牌」组天然自证蓝值。
  · apply_post  后段，跑在设计层**之后**：设计层新增的 info 蓝（255°）与锚点只差 7°，
                两族并存只会是两种几乎一样的蓝。这里把 info 族并入品牌色阶
                （IBM Carbon 的做法），命中数逐条断言。

明亮版配色从哪里来
------------------
从珊瑚红色阶按每档原有的职能推导，色相统一取锚点的 OKLCH 色相：

  · 按钮面（brand / -light / -medium / -strong）：白字 |Lc| 相对珊瑚原档**整体平移**
    SHIFT = Lc(白, ANCHOR) − Lc(白, 珊瑚 brand)，档间 Lc 差原样保留（皮肤层「整体平移」
    同一思路），brand 一档因此解回锚点本身——这是自洽断言。
  · 前景（fg-brand / fg-brand-strong）：不平移，解 L 使在 --page 上的 |Lc| 等于珊瑚原档。
    前景的判据是文字可读，不跟按钮的明暗走。
  · 两类的彩度：珊瑚各档相对珊瑚 brand 的 C 比例，换算到锚点的 C，超出色域则截到 Cmax。
    不用相对彩度 C/Cmax 放大：蓝色相在深端的色域边界逼近 sRGB 蓝原色，试算锚点
    #3264f6 时 brand-strong 被推到 #0e00ee。超出色域的档截到 Cmax（本锚点下
    brand-light / -strong 落在边界上）。
  · 浅色调（brand-soft / brand-softer）：L 与绝对 C 不变，只转色相。白色附近的 Cmax
    随色相剧烈变化，保相对彩度会让浅底刺眼（试算石油青时 brand-soft 得到 #71fbfb）。

出厂值是 EXPECTED_SIM 定稿表；构建期按上述规则重算全表，断言逐通道差 ≤1/255，
理由同深色层（OKLab 逆变换在 8-bit 取整边界上可能向不同方向翻）。真正钉死的是审计：
求解过的 6 对 Lc 逐项对上目标（|Δ|≤0.5），按钮三档的明暗序不倒挂，未求解的 4 对派生
组合不退化。

深色版：深色层照旧跑，品牌族事后换
----------------------------------
深色层的品牌定稿值全是从珊瑚红推的，且断言里钉着珊瑚原值。不改深色层，而是让它按珊瑚
跑完，再由 apply_dark 把品牌族换成「深色层同一套规则作用于明亮蓝」的结果——深色层与
`--dark` 产物因此一个字节不动。apply_dark 与皮肤层同一槽位（深色层之后、设计层之前），
理由相同：设计层「首次声明胜」，色板才自证蓝值。

  · 基色四档：深色层的规则是基色恒等（按钮白字两版同值），所以与明亮蓝同值。
  · soft / softer、图表次要系列线：直接调用深色层的 dark_soft() / dark_series()，
    与珊瑚版同一条规则、同一组常数。
  · 品牌前景：深色层对珊瑚的定稿是「拿 Lc 换彩度」（Lc 53.7 / 67.2，彩度下限 .13 / .10），
    依据是 Helmholtz–Kohlrausch——蓝是该效应最强的色相，理由对蓝更成立。沿用同一组 Lc
    目标（读 _theme_dark.BRAND_FG_LC），C 取明亮版、超出色域截到 Cmax。严格等 Lc 会把
    fg-brand 的彩度从 0.226 压到 0.095（#a0c1ff 那种淡紫蓝）。fg-brand-strong 在 Lc 67.2
    处的色域上限只有 0.096，低于珊瑚的 .10 下限——这是色域边界，断言改为「不低于下限，
    或已取到色域上限」。

info 族明暗两版同一映射：info→brand、info-strong→fg-brand-strong、info-soft→brand-softer、
info-medium→brand-soft（令牌别名，不是按明度就近配对）。info-strong 并入 fg-brand-strong
而非 brand-strong：它的职能是 soft 底上的文字，深色版里 brand-strong 是恒等的按钮深蓝，
只有 fg-brand-strong 在两版都是文字色。

边界
----
「令牌 + 令牌在 body 里的镜像」，与皮肤层同一条边界：:root 的 8 个品牌令牌，加上
components 页烙进 body 的 18 处字面值（品牌色阶 6 对 chip/label、头图色条 6 块）；
深色版另有焦点环、.ds 回退链各 1 处与次要系列线 6 处。--elevation-3（rgb(from var(--brand))）
自动跟随。中性色、状态三族、点缀色一个字节不动。另外三个 zh 产物不经过本层，逐字节不变。
"""
from __future__ import annotations

import math
import re
import sys

import _ds_zh
import _theme_dark
from _ds_zh import Patch
# 色彩数学直接复用深色层的实现，不另写一份（皮肤层同一先例）
from _theme_dark import (_drift, _hex_rgb, _norm6, _oklab, apca, hex_lch, lch_cmax,
                         lch_hex)


def need(cond, msg):
    if not cond:
        sys.exit(f"[品牌层失败] {msg}")


# 设计指定的品牌主色（定稿常量），整套色阶围绕它推导
ANCHOR = "#1a66ff"
_, ANCHOR_C, HUE = hex_lch(ANCHOR)        # C≈0.238，H≈262.2

# 每档的推导角色：face=按钮面（白字 Lc 整体平移）、fg=前景（page 上等 Lc）、tint=浅色调（L、C 不变）
RAMP = (("brand", "face"), ("brand-light", "face"), ("brand-medium", "face"),
        ("brand-strong", "face"), ("brand-soft", "tint"), ("brand-softer", "tint"),
        ("fg-brand", "fg"), ("fg-brand-strong", "fg"))
# components 页品牌色阶与头图色条展示的 6 档，顺序与原站一致
SHOWN = ("brand", "brand-light", "brand-medium", "brand-strong", "brand-soft", "brand-softer")
# .btn--primary 的渐变 light → brand → medium（hover 往深端移），白字 Lc 必须严格递增
BUTTON_ORDER = ("brand-light", "brand", "brand-medium", "brand-strong")

# 出厂定稿表。verify_derivation() 按规则重算并断言逐通道差 ≤1/255。
# brand 钉的是 ANCHOR 原值（规则解出 #1966ff，差 1/255）。
EXPECTED_SIM = {
    "brand": ANCHOR, "brand-light": "#3e7eff", "brand-medium": "#0354eb",
    "brand-strong": "#0043c3", "brand-soft": "#d5e3fd", "brand-softer": "#ebf2fd",
    "fg-brand": "#2268f8", "fg-brand-strong": "#1a59d7",
}
# 深色版定稿表（基色四档恒等，不列）。verify_dark() 用深色层的规则从 EXPECTED_SIM 重算。
EXPECTED_SIM_DARK = {
    "brand-soft": "#152036", "brand-softer": "#151e2c",
    "series-soft": "#2a364e", "series-softer": "#222b3a",
    "fg-brand": "#78a7ff", "fg-brand-strong": "#9ec1ff",
}
# 深色版里要换掉的令牌：基色四档恒等（明亮珊瑚 → 明亮蓝），其余四档（深色珊瑚 → 深色蓝）
DARK_BASE = ("brand", "brand-light", "brand-medium", "brand-strong")
DARK_DERIVED = ("brand-soft", "brand-softer", "fg-brand", "fg-brand-strong")

# 未求解的派生组合：只要求不退化（≥ 珊瑚 − 0.5）
DERIVED_PAIRS = (("fg-brand", "card"), ("fg-brand-strong", "brand-soft"),
                 ("fg-brand-strong", "brand-softer"), ("brand", "card"))

# 状态三族的色相间距下限：语义不能混
STATUS_HUE_FLOOR = (("success", 90), ("danger", 90), ("warning", 90))
# 图表并列系列（New leads / Returning、Infants / Toddlers / Preschool 等）的 OKLab 色差下限。
# 用 ΔE 而不是色相角：两个低彩度色相差 45° 也分不清，两个高彩度色相差 40° 却很分明。
# OKLab 的 JND≈0.02，0.15 约 7 个 JND；原站三系列两两 0.27–0.28，锚点与 --purple 为 0.171。
SERIES_DE_FLOOR = (("teal", 0.15), ("purple", 0.15))
# 每档偏离锚点色相的容差：ab 平面上的距离 ≤ 一个 8-bit 量化步（实测单通道 ±1 位移
# 0.0011–0.0017）。不用角度：brand-softer 的 C 只有 0.018，取整就能让色相抖 4°。
HUE_AB_TOL = 0.002

# info 并入品牌色阶：（info 档，品牌档，命中数）。命中 = :root 注入 + 色板 chip/label。
# 明暗两版同一映射（令牌别名）。明亮版浅色两档的 L 恰好对应（.958 / .913），verify 时断言。
INFO_MERGE = (("info", "brand", 3), ("info-strong", "fg-brand-strong", 3),
              ("info-soft", "brand-softer", 3), ("info-medium", "brand-soft", 1))


def _hue_dist(a, b):
    d = abs(a - b) % 360
    return min(d, 360 - d)


def _ab_off(hexv):
    """与「同 L、同 C、锚点色相」的理想点在 ab 平面上的距离。"""
    _, C, H = hex_lch(hexv)
    return 2 * C * math.sin(math.radians(_hue_dist(H, HUE)) / 2)


def _de(a, b):
    return math.dist(_oklab(*_hex_rgb(a)), _oklab(*_hex_rgb(b)))


def _lc(role, hexv, page):
    return abs(apca("#ffffff", hexv)) if role == "face" else abs(apca(hexv, page))


def _derive(role, light, ctx):
    """按角色把一档珊瑚色转到锚点色相。ctx = (page, SHIFT, 珊瑚 brand 的 C)。"""
    page, shift, coral_c = ctx
    L, C, H = hex_lch(light)
    if role == "tint":
        return lch_hex(L, C, HUE)
    c = C / coral_c * ANCHOR_C
    target = _lc(role, light, page) + (shift if role == "face" else 0.0)

    def at(l):
        return lch_hex(l, min(c, lch_cmax(l, HUE)), HUE)

    lo, hi = 0.20, 0.95
    for _ in range(50):                  # L 越高，白字与前景的 |Lc| 都越低
        mid = (lo + hi) / 2
        if _lc(role, at(mid), page) > target:
            lo = mid
        else:
            hi = mid
    return at((lo + hi) / 2)


def _dark_fg(name):
    """深色品牌前景：Lc 目标沿用深色层定稿（BRAND_FG_LC），C 取明亮版、超出色域截到 Cmax，H 不变。"""
    page = _theme_dark.EXPECTED["page"]
    _, C, H = hex_lch(EXPECTED_SIM[name])
    target = _theme_dark.BRAND_FG_LC[name]

    def at(l):
        return lch_hex(l, min(C, lch_cmax(l, H)), H)

    lo, hi = hex_lch(page)[0] + 0.01, 0.999
    for _ in range(60):                  # 深底亮字：L 越高 |Lc| 越高
        mid = (lo + hi) / 2
        if abs(apca(at(mid), page)) < target:
            lo = mid
        else:
            hi = mid
    return at((lo + hi) / 2)


def _light(css):
    """珊瑚原值从产物 CSS 读，不手抄。返回（原样字面值，规范化值）两张表。"""
    raw = {n: _ds_zh.token_value(css, n) for n, _ in RAMP}
    return raw, {n: _norm6(v) for n, v in raw.items()}


def _assert_gone(text, values, what):
    """这些值（含带 alpha 的 8 位写法）必须从 text 里绝迹。"""
    for v in values:
        c = len(re.findall(re.escape(v) + r"(?:[0-9a-fA-F]{2})?(?![0-9a-fA-F])", text, re.I))
        need(c == 0, f"{what} {v} 仍残留 {c} 处")


def verify_derivation(css):
    """按规则重算全表，与 EXPECTED_SIM 逐项对照（≤1/255）；再跑 Lc 审计、明暗序与色差。"""
    _, lt = _light(css)
    S = EXPECTED_SIM
    page = _norm6(_ds_zh.token_value(css, "page"))
    card = _norm6(_ds_zh.token_value(css, "card"))
    shift = _lc("face", ANCHOR, page) - _lc("face", lt["brand"], page)
    ctx = (page, shift, hex_lch(lt["brand"])[1])

    need(S["brand"] == ANCHOR, "定稿表的 brand 必须是锚点原值")
    bad = []
    for n, role in RAMP:
        d = _derive(role, lt[n], ctx)
        if _drift(d, S[n]) > 1:
            bad.append(f"{n}: 推导 {d} vs 定稿 {S[n]}")
    need(not bad, "推导与定稿表对不上（>1/255）：\n  " + "\n  ".join(bad))

    # 求解过的 6 对：按钮面 = 珊瑚 + SHIFT，前景 = 珊瑚
    max_d = 0.0
    for n, role in RAMP:
        if role == "tint":
            continue
        want = _lc(role, lt[n], page) + (shift if role == "face" else 0.0)
        got = _lc(role, S[n], page)
        need(abs(got - want) <= 0.5, f"Lc 审计失败 {n}（{role}）：目标 {want:.1f}，实得 {got:.1f}")
        max_d = max(max_d, abs(got - want))
    lcs = [_lc("face", S[n], page) for n in BUTTON_ORDER]
    need(all(a < b for a, b in zip(lcs, lcs[1:])),
         "按钮档的明暗序倒挂：" + "，".join(f"{n} {v:.1f}" for n, v in zip(BUTTON_ORDER, lcs)))
    # 未求解的派生组合：不退化
    lt2, s2 = dict(lt, card=card), dict(S, card=card)
    for fg, bg in DERIVED_PAIRS:
        a, b = abs(apca(lt2[fg], lt2[bg])), abs(apca(s2[fg], s2[bg]))
        need(b >= a - 0.5, f"派生组合退化 {fg}/{bg}：珊瑚 {a:.1f}，新蓝 {b:.1f}")
    # 全档色相都落在锚点上
    for n, _ in RAMP:
        need(_ab_off(S[n]) <= HUE_AB_TOL,
             f"{n} 偏离锚点色相 {_hue_dist(hex_lch(S[n])[2], HUE):.1f}°（ab 距离 {_ab_off(S[n]):.4f}）")
    # 换色的理由本身也钉成断言：状态三族看色相，图表系列看色差
    for fam, floor in STATUS_HUE_FLOOR:
        h = hex_lch(_norm6(_ds_zh.token_value(css, fam)))[2]
        need(_hue_dist(h, HUE) >= floor, f"品牌色与 --{fam} 色相只差 {_hue_dist(h, HUE):.0f}°，下限 {floor}°")
    for fam, floor in SERIES_DE_FLOOR:
        de = _de(S["brand"], _norm6(_ds_zh.token_value(css, fam)))
        need(de >= floor, f"品牌色与图表系列 --{fam} 的 ΔE_OK 只有 {de:.3f}，下限 {floor}")
    # info 并入：浅色两档的 L 必须对应，否则并入就是换档而不是合并
    info = dict(_ds_zh.INFO_HUES)
    for src, dst in (("info-soft", "brand-softer"), ("info-medium", "brand-soft")):
        need(abs(hex_lch(info[src])[0] - hex_lch(S[dst])[0]) <= 0.005,
             f"{src} 与 {dst} 的明度档位对不上，不能并入")

    danger_h = hex_lch(_norm6(_ds_zh.token_value(css, "danger")))[2]
    verify_derivation.stats = {
        "max_d": max_d, "shift": shift,
        "lc_before": _lc("face", lt["brand"], page), "lc_after": _lc("face", S["brand"], page),
        "danger_before": _hue_dist(hex_lch(lt["brand"])[2], danger_h),
        "danger_after": _hue_dist(HUE, danger_h),
        "info_d": _hue_dist(HUE, hex_lch(info["info"])[2]),
    }


def verify_dark():
    """用深色层的规则从 EXPECTED_SIM 重算深色定稿（≤1/255），再审计品牌前景与次要系列线。"""
    E, S, SD = _theme_dark.EXPECTED, EXPECTED_SIM, EXPECTED_SIM_DARK
    derived = {n: _theme_dark.dark_soft(n, S[n]) for n in ("brand-soft", "brand-softer")}
    for n, (src, _) in _theme_dark.SERIES_RULE.items():
        derived[n] = _theme_dark.dark_series(n, S[src])
    for n in _theme_dark.BRAND_FG_LC:
        derived[n] = _dark_fg(n)
    need(set(derived) == set(SD), "深色定稿表的条目与推导条目对不上")
    bad = [f"{n}: 推导 {d} vs 定稿 {SD[n]}" for n, d in derived.items() if _drift(d, SD[n]) > 1]
    need(not bad, "深色推导与定稿表对不上（>1/255）：\n  " + "\n  ".join(bad))

    # 品牌前景：Lc 钉在深色层定稿值上；彩度不低于下限，或已取到色域上限
    for n, want in _theme_dark.BRAND_FG_LC.items():
        got = abs(apca(SD[n], E["page"]))
        need(abs(got - want) <= 0.2, f"深色 {n} 的 Lc={got:.1f}，定稿应为 {want}")
        L, C, H = hex_lch(SD[n])
        floor = _theme_dark.BRAND_FG_FLOOR[n]
        need(C >= floor or C >= lch_cmax(L, H) - 0.003,
             f"深色 {n} 彩度 {C:.3f} 既低于下限 {floor}，也没到色域上限 {lch_cmax(L, H):.3f}")
    # 全部落在锚点色相上；次要系列线必须比 card 亮（深色 soft 与 card 同明度，线规则存在的理由）
    for n, v in SD.items():
        need(_ab_off(v) <= HUE_AB_TOL, f"深色 {n} 偏离锚点色相（ab 距离 {_ab_off(v):.4f}）")
    for n in _theme_dark.SERIES_RULE:
        need(hex_lch(SD[n])[0] > hex_lch(E["card"])[0], f"深色 {n} 没有比 card 亮，画成线会消失")

    verify_dark.stats = {n: hex_lch(SD[n])[1] for n in _theme_dark.BRAND_FG_LC}


NOTE = """  ⚠ 本文件在设计层之前还过了一道**品牌层**（_theme_brand.py）：品牌色由珊瑚红
     换成蓝色，与明亮版 charm-preview-cjk-gb-zh.html 并排对照用。
     · 换色理由：原品牌色与 --danger 在 OKLCH 里色相只差 {before:.0f}°，「运行」按钮与
       「报错」同色；新品牌色（H={hue:.1f}）与 danger 相距 {after:.0f}°。
     · 品牌主色 {brand} 是设计指定的锚点，其余七档由珊瑚红色阶推导而非手调：按钮面
       白字 Lc 整体平移 {shift:+.1f}（按钮白字 Lc {lcb:.1f} → {lca:.1f}，渐变明暗序不变），前景保
       page 上的 Lc，浅色调保 L 与绝对彩度。求解的 6 对 |ΔLc|≤{max_d:.1f}，派生组合不退化。
       fg-brand {fg}，brand-soft {soft}。
     · 设计层新增的 info 蓝与新品牌色只差 {info_d:.0f}°，info 族并入品牌色阶（色板 info 一行即品牌值）。
       设计层说明里「.ds__alert--info 借用品牌红」一句，在本版中该变体呈蓝。
     · 中性色、状态三族、点缀色不动；只改令牌与 components 页烙进 body 的 18 处镜像。

"""

NOTE_DARK = """  ⚠ 本文件是蓝色品牌的深色版，与 charm-preview-cjk-gb-zh-sim.html 配套：深色层按
     珊瑚红跑完后，再由**品牌层深色段**（_theme_brand.apply_dark）把品牌族换成锚点
     {brand} 的蓝。深色层说明里的「珊瑚红」「品牌前景」两处指原品牌，取舍在此照搬。
     · 基色四档与明亮蓝同值（深色层的基色恒等，按钮白字两版同值）。
     · soft / softer 与图表次要系列线用深色层同一条规则从明亮蓝推出：{soft} / {softer}，
       线 {s1} / {s2}。
     · 品牌前景沿用深色层定稿的 Lc {lc1} / {lc2}（拿 Lc 换彩度）：fg-brand {fg}（C {c1:.3f}），
       fg-brand-strong {fgs}（C {c2:.3f}，已到该明度的色域上限）。
     · info 族并入品牌色阶，明暗两版同一映射。中性色与状态色同深色版，一个字节不动。

"""


def _swap_mirrors(body, lt):
    """components 页烙进 body 的品牌镜像：色阶 chip/label 按令牌名锚整个单元，头图色条整串换。
    深色层对这 12 处是恒等的（跨文件比较的锚点），所以明暗两版换法相同。"""
    S = EXPECTED_SIM
    for n in SHOWN:
        cell = '<span class="ds__chip" style="background:{v}"></span><b>' + n + '</b><span>{v}</span>'
        body = Patch(f"色阶 {n}", re.escape(cell.format(v=lt[n])), cell.format(v=S[n]),
                     mode="replace").apply(body)
    ramp = '<i style="background:{}"></i>'
    return Patch("头图色条", re.escape("".join(ramp.format(lt[n]) for n in SHOWN)),
                 "".join(ramp.format(S[n]) for n in SHOWN), mode="replace").apply(body)


def _insert_note(html, note):
    html, n = re.subn(re.escape(_ds_zh.NOTE_ANCHOR), note + _ds_zh.NOTE_ANCHOR, html, count=1)
    need(n == 1, "没找到说明块的插入锚点")
    return html


def apply(html: str) -> str:
    """明亮版主段：在设计层之前，把品牌令牌与 body 镜像换成新蓝。"""
    k = html.index("</style>")
    css, body = html[:k], html[k:]
    verify_derivation(css)
    raw, lt = _light(css)
    S = EXPECTED_SIM

    # :root 逐令牌就地改写
    for n, _ in RAMP:
        css = Patch(f"--{n}", re.escape(f"--{n}:{raw[n]}") + r"(?=[;}])",
                    f"--{n}:{S[n]}", mode="replace").apply(css)
    body = _swap_mirrors(body, lt)

    # 珊瑚色必须从全文绝迹（在插入说明块之前查）
    out = css + body
    _assert_gone(out, lt.values(), "珊瑚值")

    st = verify_derivation.stats
    return _insert_note(out, NOTE.format(
        before=st["danger_before"], after=st["danger_after"], hue=HUE, shift=st["shift"],
        lcb=st["lc_before"], lca=st["lc_after"], max_d=st["max_d"], brand=S["brand"],
        fg=S["fg-brand"], soft=S["brand-soft"], info_d=st["info_d"]))


def apply_dark(html: str, src: str) -> str:
    """深色版主段：跑在深色层之后、设计层之前，把深色珊瑚的品牌族换成深色蓝。
    src 是复刻产物原文——明亮版的推导要对着真正的明亮值复核。"""
    verify_derivation(src[:src.index("</style>")])
    verify_dark()
    E, S, SD = _theme_dark.EXPECTED, EXPECTED_SIM, EXPECTED_SIM_DARK
    _, lt = _light(src[:src.index("</style>")])
    k = html.index("</style>")
    css, body = html[:k], html[k:]

    # :root：基色四档恒等（明亮珊瑚 → 明亮蓝），派生四档（深色珊瑚 → 深色蓝）
    for n in DARK_BASE:
        css = Patch(f"--{n}", re.escape(f"--{n}:{lt[n]}") + r"(?=[;}])",
                    f"--{n}:{S[n]}", mode="replace").apply(css)
    for n in DARK_DERIVED:
        css = Patch(f"--{n}（深色）", re.escape(f"--{n}:{E[n]}") + r"(?=[;}])",
                    f"--{n}:{SD[n]}", mode="replace").apply(css)
    # 焦点环：深色层把它改成「品牌色 + 25% alpha」，取深色层自己的那条声明换品牌色，不手抄
    ring = next(dark for label, _, dark in _theme_dark.ROOT_DECL if label == "focus-ring")
    need(ring.count(lt["brand"]) == 1, "深色焦点环里应恰有一处品牌色")
    css = Patch("焦点环", re.escape(ring), ring.replace(lt["brand"], S["brand"]),
                mode="replace").apply(css)
    # .ds 回退链里深色层写进的 brand-softer 字面值
    css = Patch(".ds 链 --ds-brand-soft 回退", re.escape(f"var(--brand-soft,{E['brand-softer']})"),
                f"var(--brand-soft,{SD['brand-softer']})", mode="replace").apply(css)

    # body：镜像同明亮版；次要系列线（命中数从深色层自己的 var_patches 数出来，不手估）
    body = _swap_mirrors(body, lt)
    for n in _theme_dark.SERIES_RULE:
        cnt = sum(p.count for p in _theme_dark.var_patches() if E[n] in p.payload)
        body = Patch(f"次要系列线 {n}", re.escape(E[n]) + r"(?![0-9a-fA-F])", SD[n],
                     count=cnt, mode="replace").apply(body)

    out = css + body
    _assert_gone(out, lt.values(), "珊瑚值")
    _assert_gone(out, [E[n] for n in DARK_DERIVED + tuple(_theme_dark.SERIES_RULE)], "深色珊瑚值")

    c = verify_dark.stats
    return _insert_note(out, NOTE_DARK.format(
        brand=S["brand"], soft=SD["brand-soft"], softer=SD["brand-softer"],
        s1=SD["series-soft"], s2=SD["series-softer"],
        lc1=_theme_dark.BRAND_FG_LC["fg-brand"], lc2=_theme_dark.BRAND_FG_LC["fg-brand-strong"],
        fg=SD["fg-brand"], c1=c["fg-brand"], fgs=SD["fg-brand-strong"], c2=c["fg-brand-strong"]))


def apply_post(html: str, dark: bool = False) -> str:
    """后段：设计层刚注入的 info 族并入品牌色阶。dark=True 时接在深色层后段之后，
    此刻 info 已是深色值，并入的目标也是深色品牌值。"""
    info = dict(_ds_zh.INFO_HUES)
    if dark:
        E = _theme_dark.EXPECTED
        src = {"info": info["info"], **{n: E[n] for n in ("info-strong", "info-soft", "info-medium")}}
        tgt = dict(EXPECTED_SIM_DARK, brand=EXPECTED_SIM["brand"])
        # 深色品牌前景本就拿 Lc 换了彩度，并入后的 info 文字/底跟着这个取舍：
        # 底线是珊瑚深色版品牌的同一对，不是 info 原来那一对
        floor = abs(apca(E["fg-brand-strong"], E["brand-softer"]))
    else:
        src, tgt = info, EXPECTED_SIM
        floor = abs(apca(info["info-strong"], info["info-soft"]))
    before = abs(apca(src["info-strong"], src["info-soft"]))
    after = abs(apca(tgt["fg-brand-strong"], tgt["brand-softer"]))
    need(after >= floor - 0.5, f"并入后 info 文字/底的 Lc {after:.1f} 低于底线 {floor:.1f}")
    # 单趟逐值替换的前提：输出值不能又是后面某一条的输入
    need(not {tgt[d] for _, d, _ in INFO_MERGE} & {src[s] for s, _, _ in INFO_MERGE},
         "并入映射的输出与输入相交，逐条替换会二次映射")
    for s, d, cnt in INFO_MERGE:
        html, n = re.subn(re.escape(src[s]) + r"(?![0-9a-fA-F])", tgt[d], html)
        need(n == cnt, f"info 并入 {s} {src[s]}→{tgt[d]} 命中 {n} 处，期望 {cnt}")
    apply_post.hits = sum(c for _, _, c in INFO_MERGE)
    apply_post.lc = (before, after)
    return html


def summary(dark: bool = False) -> str:
    st = getattr(verify_derivation, "stats", {})
    post = getattr(apply_post, "hits", 0)
    before, after = getattr(apply_post, "lc", (0, 0))
    head = (f"品牌层：锚点 {ANCHOR}（H={HUE:.1f}）；与 danger 色相距 "
            f"{st.get('danger_before', 0):.0f}°→{st.get('danger_after', 0):.0f}°；")
    if dark:
        SD = EXPECTED_SIM_DARK
        return (head + f"深色段换 :root 8 条 + 焦点环 + .ds 回退 + 18 处镜像 + 6 处次要系列线；"
                f"前景 {SD['fg-brand']} / {SD['fg-brand-strong']}（Lc 沿用 "
                f"{_theme_dark.BRAND_FG_LC['fg-brand']}/{_theme_dark.BRAND_FG_LC['fg-brand-strong']}）；"
                f"info 族 {post} 处并入（文字/底 Lc {before:.1f}→{after:.1f}）")
    return (head + f"8 条品牌令牌 + 18 处 body 镜像；按钮白字 Lc "
            f"{st.get('lc_before', 0):.1f}→{st.get('lc_after', 0):.1f}"
            f"（整体平移 {st.get('shift', 0):+.1f}），6 项 |Δ|≤{st.get('max_d', 0):.1f}，"
            f"派生 {len(DERIVED_PAIRS)} 项不退化；info 族 {post} 处并入品牌色阶"
            f"（文字/底 Lc {before:.1f}→{after:.1f}）")


if __name__ == "__main__":
    sys.exit("本文件是品牌层，不单独运行。请跑：python3 _build_zh.py --sim [--dark]")
