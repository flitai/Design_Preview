# -*- coding: utf-8 -*-
"""交付打包：把工程蓝明暗两版整理成交给业务网页实现者的风格包。

输入（先跑这两条）：
    python3 _build_zh.py --sim            → charm-preview-cjk-gb-zh-sim.html
    python3 _build_zh.py --sim --dark     → charm-preview-cjk-gb-zh-sim-dark.html
运行：
    python3 _pack_sim.py                  → handoff/charm-sim-theme/ 与 handoff/charm-sim-theme.zip

包内结构：
    README.md               快速上手
    style-guide.html        风格说明（正文来自 _pack_sim_guide.html，表格由本脚本填入）
    templates/              明暗两个模版（产物原样复制）
    tokens/theme.css        明暗两套 CSS 变量
    tokens/tokens.json      同一份令牌：分组、用途、明暗取值、模版引用次数
    fonts/                  8 个 woff2 + fonts.css + LICENSE.txt

与其它层同一条规矩：**包内没有一个数值是手抄的**。令牌、字号、间距、字体文件、对比度、
组件 CSS 摘录、深色差异清单，全部从两个模版产物里读出；用途说明是人写的，但每个令牌都
必须有说明、每条说明都必须对得上一个真实令牌（双向断言）。打包是确定性的：zip 用固定
时间戳，同输入逐字节同输出。
"""
from __future__ import annotations

import base64
import difflib
import hashlib
import html as htmllib
import io
import json
import re
import shutil
import sys
import zipfile
from pathlib import Path

import _theme_brand
import _theme_dark
from _theme_dark import apca, hex_lch

HERE = Path(__file__).resolve().parent
SRC_LIGHT = HERE / "charm-preview-cjk-gb-zh-sim.html"
SRC_DARK = HERE / "charm-preview-cjk-gb-zh-sim-dark.html"
GUIDE_SRC = HERE / "_pack_sim_guide.html"
OUT = HERE / "handoff" / "charm-sim-theme"
ZIP = HERE / "handoff" / "charm-sim-theme.zip"
ZIP_TIME = (2026, 1, 1, 0, 0, 0)          # 固定时间戳：同输入逐字节同输出
NAME = "仿真蓝主题"


def need(cond, msg):
    if not cond:
        sys.exit(f"[打包失败] {msg}")


# ============================================================ 令牌的分组与用途（人写，双向断言）
# （令牌名，用途）。分组顺序即说明里的展示顺序。
COLOR_GROUPS = (
    ("品牌", (
        ("brand", "主操作色：主按钮渐变中段、选中标签页底、开关开启、图表主系列。设计指定锚点，明暗同值。"),
        ("brand-light", "主按钮渐变顶端与描边、品牌标记渐变。"),
        ("brand-medium", "主按钮渐变底端；悬停时渐变下移露出这一档。"),
        ("brand-strong", "色阶最深档，留作按下态等强调。"),
        ("brand-soft", "品牌浅底：头像底、公告条描边；明亮版焦点环的色源。"),
        ("brand-softer", "品牌最浅底：菜单激活项、侧栏徽标、信息提示条底。"),
    )),
    ("文字", (
        ("heading", "标题、强调文字、次要按钮文字。"),
        ("body", "正文。"),
        ("body-subtle", "次要文字、说明、图标、表头。"),
        ("fg-disabled", "最弱一档文字（禁用、辅助信息）。"),
        ("fg-brand", "品牌色文字：链接、激活导航。"),
        ("fg-brand-strong", "浅品牌底上的品牌文字：激活菜单、徽标、信息提示条。"),
        ("white", "品牌底上的白字、复选框勾、单选点；深色版仍为白。"),
    )),
    ("表面", (
        ("page", "页面底。"),
        ("card", "卡片、输入框、弹窗、次要按钮的面。"),
        ("card-soft", ".card 组件与若干次级面板的底。"),
        ("control-fill", "控件填充与悬停底：次要/描边/幽灵按钮悬停、输入外壳、分段控件。"),
        ("app-surface", "应用壳（侧栏 + 主区）的底。"),
        ("band", "横幅、页脚、商城导航等色带的底。"),
        ("hover-fill", "组件悬停底（标签页、分页等）。"),
    )),
    ("描边", (
        ("border-subtle", "发丝线：卡片描边、表格行线。"),
        ("border", "默认边框：输入框、次要按钮、表格外框。"),
        ("border-medium", "弹窗边框。"),
        ("border-strong", "实心小标记：开关滑块、圆点。"),
        ("border-on-band", "色带上的分隔线。"),
    )),
    ("状态", (
        ("success", "成功/完成的状态点。"),
        ("success-strong", "成功文字、徽章与提示条的字。"),
        ("success-soft", "成功浅底。"),
        ("danger", "危险操作文字（删除类菜单项）、错误状态点。"),
        ("danger-strong", "错误文字、徽章字、出错输入框描边。"),
        ("danger-soft", "错误浅底。"),
        ("danger-medium", "危险中间档。"),
        ("warning", "警告状态点。"),
        ("warning-strong", "警告强调档（深色版与 fg-warning 同值）。"),
        ("fg-warning", "浅底上的警告文字。"),
        ("warning-soft", "警告浅底。"),
        ("warning-medium", "暖色中间档。"),
        ("info", "信息/运行中。已并入品牌色阶，等于 brand。"),
        ("info-strong", "信息文字。等于 fg-brand-strong。"),
        ("info-soft", "信息浅底。等于 brand-softer。"),
        ("info-medium", "信息中间档。等于 brand-soft。"),
    )),
    ("图表与点缀", (
        ("teal", "图表第二系列。"),
        ("purple", "图表第三系列。"),
        ("indigo", "预留点缀色。与品牌蓝接近，不要和品牌色并列成系列。"),
        ("sky", "预留点缀色。与品牌蓝接近，不要和品牌色并列成系列。"),
        ("cyan", "预留点缀色。与品牌蓝、teal 都接近，慎用。"),
        ("orange", "预留点缀色。与 danger 接近，不要用于非错误的强调。"),
        ("pink", "预留点缀色。"),
    )),
    ("补充（模版里是字面值）", (
        ("series-soft", "图表对比/上期系列与图例点。深色版不能用 brand-soft（与卡片同明度，线会消失），用这一档。"),
        ("series-softer", "环形图轨道等更弱的系列。"),
        ("scrim", "弹窗、抽屉、侧栏的遮罩。"),
        ("tooltip", "工具提示气泡的底（配白字）。深色模版里就是 --tooltip；明亮模版直接用 heading 色，本包补成令牌。"),
    )),
)
OTHER_GROUPS = (
    ("圆角", (
        ("r-xs", "复选框、小标记。"), ("r-sm", "紧凑控件。"),
        ("r-md", "输入框、按钮以外的控件、徽章、提示条（.ds 组件的控件圆角）。"),
        ("r-lg", "菜单、浮层、KPI 小卡。"), ("r-xl", "卡片、面板、表格、弹窗。"),
        ("r-xxl", "大面板。"), ("r-xxxl", "最大面板。"), ("r-full", "胶囊按钮、圆点、头像、开关。"),
    )),
    ("阴影与焦点", (
        ("elevation-1", "按钮等轻抬升。深色版改为顶缘高光 + 加深投影。"),
        ("elevation-2", "菜单、浮层。深色版同上。"),
        ("elevation-3", "品牌辉光（25% 品牌色），用相对颜色语法。"),
        ("focus-ring", "键盘焦点环，4px。"),
    )),
    ("字体", (
        ("font-inter", "正文字体名（思源黑体）。"), ("font-display", "标题字体名（思源黑体）。"),
        ("font-fragment-mono", "等宽字体名（更纱黑体）。"),
        ("font-sans-stack", "正文字体栈。"), ("font-display-stack", "标题字体栈；首位为思源黑体（--font-display），其后的 Circular Std 等后备不会用到。"),
        ("font-mono-stack", "等宽字体栈：数字、代码、表格对齐。"),
    )),
    ("布局", (
        ("container", "内容最大宽度。"), ("section-y", "区块上下留白；768px 以下为 64px。"),
    )),
)
SUPPLEMENT = ("series-soft", "series-softer", "scrim", "tooltip", "hover-fill")   # 不是模版令牌，本包补的

# 对比度表：（前景，背景，场景）
CONTRAST_PAIRS = (
    ("heading", "page", "标题"), ("body", "page", "正文"), ("body-subtle", "page", "次要文字"),
    ("fg-disabled", "page", "最弱文字"), ("fg-brand", "page", "链接"),
    ("fg-brand-strong", "brand-softer", "浅品牌底上的文字"), ("white", "brand", "主按钮文字"),
    ("success-strong", "success-soft", "成功提示"), ("danger-strong", "danger-soft", "错误提示"),
    ("fg-warning", "warning-soft", "警告提示"),
)

# 组件 CSS 摘录：（组名，选择器原文）。每个选择器必须在明亮模版里恰好出现一次。
EXCERPTS = (
    ("按钮", (".btn", ".btn--primary", ".btn--primary:hover", ".btn--secondary", ".btn--outline",
              ".btn--ghost", ".btn--sm", ".btn--lg", ".btn:focus-visible")),
    ("输入框", (".ds__field", ".ds__input,.ds__select,.ds__textarea",
                ".ds__input:focus-visible,.ds__select:focus-visible,.ds__textarea:focus-visible",
                ".ds__input.is-error")),
    ("徽章", (".ds__badge", ".ds__badge--brand", ".ds__badge--success", ".ds__badge--danger",
              ".ds__badge--warning", ".ds__badge--neutral")),
    ("提示条", (".ds__alert", ".ds__alert--info", ".ds__alert--success", ".ds__alert--warning",
                ".ds__alert--danger")),
    ("标签页", (".ds__tab", ".ds__tab:hover", ".ds__tab[aria-selected=true]",
                ".ds__tabs--underline .ds__tab", ".ds__tabs--underline .ds__tab[aria-selected=true]")),
    ("开关与选择", (".ds__track", ".ds__thumb", ".ds__toggle input:checked+.ds__track",
                    ".ds__check,.ds__radioctl")),
    ("卡片与表格", (".card", ".ds__table", ".ds__table th", ".ds__table td")),
    ("菜单", (".menu", ".menu__item", ".menu__item:hover", ".menu__item--active")),
    ("浮层", (".ds__modal", ".ds__drawer", ".ds__scrim", ".ds__bubble")),
)

# 字体文件命名：（族，字重区间）→ 文件名
FONT_FILES = {
    ("Noto Sans SC", "100 349"): "NotoSansSC-Thin.woff2",
    ("Noto Sans SC", "350 449"): "NotoSansSC-Regular.woff2",
    ("Noto Sans SC", "450 549"): "NotoSansSC-Medium.woff2",
    ("Noto Sans SC", "550 749"): "NotoSansSC-Bold.woff2",
    ("Noto Sans SC", "750 900"): "NotoSansSC-Black.woff2",
    ("Sarasa Mono SC", "100 549"): "SarasaMonoSC-Regular.woff2",
    ("Sarasa Mono SC", "550 649"): "SarasaMonoSC-SemiBold.woff2",
    ("Sarasa Mono SC", "650 900"): "SarasaMonoSC-Bold.woff2",
}

# 深色差异清单里不列的规则：令牌块、.ds 别名的死回退、预览外壳
DIFF_SKIP = re.compile(r"^(:root|\.ds$|\.pv-switch)")


# ============================================================ 读产物
def _css(html):
    css = html[:html.index("</style>")]
    return css[css.index("<style>") + len("<style>"):]


def _strip_fonts(css):
    return re.sub(r"url\(data:[^)]*\)", "url()", css)


def _rules(css):
    """全部样式规则，带所在 at-rule 的上下文：[(上下文, 选择器, 声明体)]，顶层规则上下文为空串。
    逐个括号扫描而不是一条正则：@media 里的同名规则（如窄屏下的 .btn--lg）要能分开。"""
    css = re.sub(r"/\*.*?\*/", "", _strip_fonts(css), flags=re.S)
    out, ctx, pos = [], [], 0
    while True:
        j, k = css.find("{", pos), css.find("}", pos)
        if j == -1 and k == -1:
            break
        if j != -1 and (k == -1 or j < k):
            prelude = css[pos:j].strip()
            if prelude.startswith("@"):
                ctx.append(prelude)
                pos = j + 1
            else:
                end = css.find("}", j)
                out.append((" ".join(ctx), prelude, css[j + 1:end]))
                pos = end + 1
        else:
            if ctx:
                ctx.pop()
            pos = k + 1
    return out


def root_tokens(css):
    """:root 令牌（首次声明胜，与设计层 census 同一约定）与媒体查询里的覆写。"""
    base, media = {}, {}
    for m in re.finditer(r"(@media[^{]*)\{\s*:root\{([^}]*)\}|(?<![\w-]):root\{([^}]*)\}",
                         _strip_fonts(css)):
        target, body = (media.setdefault(m.group(1).strip(), {}), m.group(2)) if m.group(1) \
            else (base, m.group(3))
        for d in body.split(";"):
            if ":" in d and d.strip().startswith("--"):
                k, v = d.split(":", 1)
                target.setdefault(k.strip()[2:], v.strip())
    return base, media


def ds_fallback(css, alias):
    """.ds 别名链最末的字面回退值（模版没定义该令牌时实际渲染的就是它）。"""
    m = re.search(r"--" + re.escape(alias) + r":var\([^;]*?(#[0-9a-fA-F]{3,8})\)+[;}]", _strip_fonts(css))
    need(m, f".ds 里找不到 --{alias} 的回退值")
    return m.group(1)


def rule_body(rules, sel):
    """顶层（不在任何 at-rule 里）的那一条，必须恰好一条。"""
    hits = [b for c, s, b in rules if s == sel and not c]
    need(len(hits) == 1, f"顶层选择器 {sel} 命中 {len(hits)} 次，期望 1")
    return hits[0]


def decl(body, prop):
    m = re.search(r"(?:^|;)" + re.escape(prop) + r":([^;]+)", body)
    need(m, f"声明里找不到 {prop}")
    return m.group(1).strip()


# ============================================================ 色彩小工具
def _hex6(v):
    v = v.lower()
    return "#" + "".join(c * 2 for c in v[1:]) if re.fullmatch(r"#[0-9a-f]{3}", v) else v


def _is_color(v):
    return bool(re.fullmatch(r"#[0-9a-fA-F]{3,8}", v))


def hue_gap(a, b):
    d = abs(hex_lch(_hex6(a))[2] - hex_lch(_hex6(b))[2]) % 360
    return min(d, 360 - d)


def wcag(fg, bg):
    def lum(h):
        r, g, b = (int(h[i:i + 2], 16) / 255 for i in (1, 3, 5))
        f = lambda c: c / 12.92 if c <= 0.04045 else ((c + 0.055) / 1.055) ** 2.4
        return 0.2126 * f(r) + 0.7152 * f(g) + 0.0722 * f(b)
    a, b = sorted((lum(_hex6(fg)[:7]), lum(_hex6(bg)[:7])), reverse=True)
    return (a + 0.05) / (b + 0.05)


# ============================================================ 提取与断言
def extract():
    need(SRC_LIGHT.exists() and SRC_DARK.exists(),
         "缺少模版产物（先跑 python3 _build_zh.py --sim 与 python3 _build_zh.py --sim --dark）")
    hl, hd = SRC_LIGHT.read_text(encoding="utf-8"), SRC_DARK.read_text(encoding="utf-8")
    cl, cd = _css(hl), _css(hd)
    L, ml = root_tokens(cl)
    D, md = root_tokens(cd)
    need(ml == md, "明暗两版的媒体查询令牌不同")

    # 深色版比明亮版多 hover-fill 与 tooltip 两个令牌；明亮版补上模版实际渲染的值
    need(set(D) == set(L) | {"hover-fill", "tooltip"}, f"明暗令牌集合不符：{sorted(set(D) ^ set(L))}")
    L["hover-fill"] = ds_fallback(cl, "ds-hover")
    # 补充令牌：图表次要系列（明亮版即 brand-soft/softer，深色版取品牌层定稿）、遮罩
    SD = _theme_brand.EXPECTED_SIM_DARK
    L["series-soft"], L["series-softer"] = L["brand-soft"], L["brand-softer"]
    D["series-soft"], D["series-softer"] = SD["series-soft"], SD["series-softer"]
    rl, rd = _rules(cl), _rules(cd)
    L["scrim"] = decl(rule_body(rl, ".modal-scrim"), "background")
    D["scrim"] = decl(rule_body(rd, ".modal-scrim"), "background")
    need(SD["series-soft"] in hd and SD["series-softer"] in hd, "深色模版里找不到次要系列线的值")
    # 工具提示：明亮版即模版 .ds__bubble 的底（--ds-heading → --heading）；深色模版自带 --tooltip
    need(decl(rule_body(rl, ".ds__bubble"), "background") == "var(--ds-heading)", "明亮 .ds__bubble 的底不是 heading")
    need(decl(rule_body(rd, ".ds__bubble"), "background") == "var(--tooltip)", "深色 .ds__bubble 的底不是 --tooltip")
    need(D["tooltip"] == _theme_dark.EXPECTED["tooltip"], f"深色 --tooltip={D['tooltip']} 与深色层定稿不符")
    L["tooltip"] = L["heading"]
    need(abs(apca("#ffffff", D["tooltip"])) >= 85, "深色 tooltip 面上的白字不够亮")

    # 品牌族必须与品牌层定稿一致（包里的值就是构建管线的值）
    S = _theme_brand.EXPECTED_SIM
    for n, v in S.items():
        need(_hex6(L[n]) == v, f"明亮 --{n}={L[n]} 与品牌层定稿 {v} 不符")
    for n in ("brand-soft", "brand-softer", "fg-brand", "fg-brand-strong"):
        need(_hex6(D[n]) == SD[n], f"深色 --{n}={D[n]} 与品牌层定稿 {SD[n]} 不符")

    # 用途说明与令牌双向对齐
    described = [n for _, g in COLOR_GROUPS + OTHER_GROUPS for n, _ in g]
    need(len(described) == len(set(described)), "用途说明里有重复令牌")
    need(set(described) == set(L), "用途说明与令牌对不上："
         f"缺说明 {sorted(set(L) - set(described))}，多说明 {sorted(set(described) - set(L))}")

    # 引用次数（明亮模版，CSS + body，var(--x) 与 var(--x, …) 都算）
    refs = {n: (0 if n in SUPPLEMENT else
                len(re.findall(r"var\(--" + re.escape(n) + r"[,)]", _strip_fonts(hl))))
            for n in L}

    return dict(hl=hl, hd=hd, cl=cl, cd=cd, L=L, D=D, media=ml, rl=rl, rd=rd, refs=refs)


def fonts(cl, cd):
    faces = []
    for m in re.finditer(r"@font-face\{([^}]*)\}", cl):
        b = m.group(1)
        fam = re.search(r"font-family:'?([^';]+)'?", b).group(1)
        wt = re.search(r"font-weight:([^;]+)", b).group(1).strip()
        data = re.search(r"url\(data:font/woff2;base64,([^)]+)\)", b)
        need(data, f"{fam} {wt} 不是 woff2 data URI")
        raw = base64.b64decode(data.group(1))
        need(raw[:4] == b"wOF2", f"{fam} {wt} 解码后不是 woff2")
        need((fam, wt) in FONT_FILES, f"未登记的字面 {fam} {wt}")
        faces.append((fam, wt, FONT_FILES[(fam, wt)], raw))
    need(len(faces) == len(FONT_FILES), f"字面数 {len(faces)}，期望 {len(FONT_FILES)}")
    need(re.findall(r"@font-face\{[^}]*\}", cl) == re.findall(r"@font-face\{[^}]*\}", cd),
         "明暗两版内嵌字体不一致")
    return faces


# 许可证：子集化裁掉了 name 表的 13/14 号记录，更纱原件里本来也没有，所以许可名与上游地址
# 写在这里（依据：README「重建中文版」一节的下载表，两者均为 OFL）；版权与版本仍从字体自身读。
FONT_LICENSE = {
    "Noto Sans SC": ("SIL Open Font License 1.1", "https://github.com/notofonts/noto-cjk"),
    "Sarasa Mono SC": ("SIL Open Font License 1.1", "https://github.com/be5invis/Sarasa-Gothic"),
}


def font_license(faces):
    from fontTools.ttLib import TTFont
    out, seen = [], set()
    for fam, _, fname, raw in faces:
        if fam in seen:
            continue
        seen.add(fam)
        need(fam in FONT_LICENSE, f"{fam} 没有登记许可证，不能随包分发")
        name = TTFont(io.BytesIO(raw))["name"]
        get = lambda i: (name.getDebugName(i) or "").strip()
        need(get(0), f"{fam} 的 name 表里没有版权声明")
        lic, url = FONT_LICENSE[fam]
        out.append(f"== {fam}（{fname.split('-')[0]}-*.woff2）\n版本：{get(5)}\n版权：{get(0)}\n"
                   f"许可：{lic}\n上游：{url}\n")
    return ("本包内字体为 GB2312 子集（6763 个常用汉字 + 拉丁与标点），按 SIL Open Font License 1.1\n"
            "随包分发；许可全文见 https://openfontlicense.org 。版本与版权读自各字体文件自身的 name 表。\n\n"
            + "\n".join(out))


# ============================================================ 生成文件
def theme_css(L, D, media):
    diff = [n for n in L if D[n] != L[n]]
    order = [n for _, g in COLOR_GROUPS + OTHER_GROUPS for n, _ in g]
    group_of = {n: gname for gname, g in COLOR_GROUPS + OTHER_GROUPS for n, _ in g}

    def block(keys, src, indent):
        lines, last = [], None
        for n in keys:
            if group_of[n] != last:
                lines.append(f"{indent}/* {group_of[n]} */")
                last = group_of[n]
            lines.append(f"{indent}--{n}:{src[n]};")
        return "\n".join(lines)

    dk = [n for n in order if n in diff]
    mq = "\n".join(f"@media {q.removeprefix('@media').strip()}{{:root{{"
                   + ";".join(f"--{k}:{v}" for k, v in kv.items()) + "}}" for q, kv in media.items())
    return f"""/* {NAME} · 设计令牌（明暗两套）
   数值直接取自模版，与风格说明、模版三者一致。请勿在业务代码里改这些值；
   需要调整请反馈给主题维护方，统一修改后发布新版本。
   用法：先引入 fonts/fonts.css，再引入本文件。
         <html data-theme="light"> 固定明亮，data-theme="dark" 固定深色，不设则跟随系统。
   series-soft / series-softer / scrim 在模版里是字面值，明亮版的 hover-fill / tooltip
   在模版里没有令牌；本包都补成令牌，便于业务页统一引用。 */
:root{{
{block(order, L, "  ")}
  color-scheme:light;
}}
{mq}
:root[data-theme="dark"]{{
{block(dk, D, "  ")}
  color-scheme:dark;
}}
@media (prefers-color-scheme:dark){{
  :root:not([data-theme="light"]){{
{block(dk, D, "    ")}
    color-scheme:dark;
  }}
}}
"""


def fonts_css(cl, faces):
    out = [f"/* {NAME} · 字体（GB2312 子集，OFL）。由 _pack_sim.py 从模版产物导出。 */"]
    blocks = re.findall(r"@font-face\{([^}]*)\}", cl)
    for b, (_, _, fname, _) in zip(blocks, faces):
        b = re.sub(r"src:url\(data:[^)]*\)\s*format\([^)]*\)", f'src:url("{fname}") format("woff2")', b)
        out.append("@font-face{" + b + "}")
    return "\n".join(out) + "\n"


def tokens_json(L, D, refs, media, src_meta):
    toks = []
    for gname, g in COLOR_GROUPS + OTHER_GROUPS:
        for n, role in g:
            toks.append({"name": f"--{n}", "group": gname, "role": role,
                         "light": L[n], "dark": D[n], "templateRefs": refs[n],
                         "supplement": n in SUPPLEMENT})
    return json.dumps({"name": NAME, "source": src_meta, "media": media, "tokens": toks},
                      ensure_ascii=False, indent=2) + "\n"


# ============================================================ 说明里的生成片段
def _e(s):
    return htmllib.escape(s, quote=True)


def _swatch(v):
    if not _is_color(v):
        return f'<code class="val">{_e(v)}</code>'
    return f'<span class="sw" style="background:{v}"></span><code class="val">{_e(v)}</code>'


def color_tables(L, D, refs):
    out = []
    for gname, g in COLOR_GROUPS:
        rows = "".join(
            f'<tr><th scope="row"><code>--{n}</code></th><td class="c">{_swatch(L[n])}</td>'
            f'<td class="c">{_swatch(D[n])}</td><td>{_e(role)}</td>'
            f'<td class="num">{"补充" if n in SUPPLEMENT else refs[n]}</td></tr>'
            for n, role in g)
        out.append(f'<h3>{_e(gname)}</h3><div class="tbl"><table><thead><tr><th>令牌</th>'
                   f'<th>明亮</th><th>深色</th><th>用途</th><th class="num">引用</th></tr></thead>'
                   f'<tbody>{rows}</tbody></table></div>')
    return "".join(out)


def other_tables(L, D, refs):
    out = []
    for gname, g in OTHER_GROUPS:
        rows = "".join(
            f'<tr><th scope="row"><code>--{n}</code></th><td><code class="val wrap">{_e(L[n])}</code></td>'
            + (f'<td><code class="val wrap">{_e(D[n])}</code></td>' if D[n] != L[n] else '<td class="muted">同明亮</td>')
            + f'<td>{_e(role)}</td><td class="num">{refs[n]}</td></tr>'
            for n, role in g)
        out.append(f'<h3>{_e(gname)}</h3><div class="tbl"><table><thead><tr><th>令牌</th>'
                   f'<th>明亮</th><th>深色</th><th>用途</th><th class="num">引用</th></tr></thead>'
                   f'<tbody>{rows}</tbody></table></div>')
    return "".join(out)


def contrast_table(L, D):
    def cell(fg, bg):
        f, b = _hex6(fg), _hex6(bg)
        return (f'<td class="c"><span class="pair" style="background:{b};color:{f}">文字 Aa</span></td>'
                f'<td class="num">{abs(apca(f, b)):.1f}</td><td class="num">{wcag(f, b):.1f}:1</td>')
    rows = "".join(f'<tr><th scope="row">{_e(t)}<br><code>{fg} / {bg}</code></th>'
                   f'{cell(L[fg], L[bg])}{cell(D[fg], D[bg])}</tr>' for fg, bg, t in CONTRAST_PAIRS)
    return ('<div class="tbl"><table class="contrast"><thead><tr><th>场景</th>'
            '<th>明亮</th><th class="num">APCA Lc</th><th class="num">WCAG</th>'
            '<th>深色</th><th class="num">APCA Lc</th><th class="num">WCAG</th></tr></thead>'
            f'<tbody>{rows}</tbody></table></div>')


def scale_table(hl, title):
    i = hl.index(f'class="ds__block-title">{title}</h3>')
    seg = hl[i:hl.index('class="ds__block"', i)]
    text = re.sub(r"\s+", " ", re.sub(r"<[^>]+>", " | ", seg))
    pairs = re.findall(r"\|\s*([\w-]+)\s*\|(?:\s*\|)*\s*(\d+px)\s*\|", text)
    need(pairs, f"「{title}」里没读到梯度")
    return pairs


def type_and_space(hl):
    heads = scale_table(hl, "标题字号梯度")
    bodies = scale_table(hl, "正文字号梯度")
    spaces = scale_table(hl, "间距")
    need([h for h, _ in heads] == ["h1", "h2", "h3", "h4", "h5", "h6"], "标题梯度不是 h1–h6")
    tr = lambda pairs, demo: "".join(
        f'<tr><th scope="row"><code>{n}</code></th><td class="num">{px}</td>'
        f'<td><span style="font-size:{px};{demo}">仿真模型 1.25 s</span></td></tr>' for n, px in pairs)
    t1 = ('<div class="tbl"><table><thead><tr><th>级别</th><th class="num">字号</th><th>样张</th></tr></thead>'
          f'<tbody>{tr(heads, "font-family:var(--font-display-stack);font-weight:700;letter-spacing:-.05em;line-height:1.3;color:var(--heading)")}'
          f'{tr(bodies, "")}</tbody></table></div>')
    bars = "".join(f'<div class="sp"><code>{n}</code><span class="bar" style="width:{px}"></span>'
                   f'<span class="num">{px}</span></div>' for n, px in spaces)
    return t1, f'<div class="spaces">{bars}</div>', len(spaces)


def font_rows(faces):
    return "".join(f'<tr><td><code>{fname}</code></td><td>{_e(fam)}</td><td class="num">{wt}</td>'
                   f'<td class="num">{len(raw) / 1048576:.2f} MB</td></tr>'
                   for fam, wt, fname, raw in faces)


def alias_table(cl):
    body = rule_body(_rules(cl), ".ds")
    rows = []
    for m in re.finditer(r"--(ds-[\w-]+):var\(--([\w-]+)", body):
        rows.append(f'<tr><td><code>--{m.group(1)}</code></td><td><code>--{m.group(2)}</code></td></tr>')
    need(len(rows) >= 20, ".ds 别名少于预期")
    return ('<div class="tbl"><table><thead><tr><th>.ds 别名</th><th>取自令牌</th></tr></thead>'
            f'<tbody>{"".join(rows)}</tbody></table></div>')


def _fmt_rule(ctx, sel, body, indent=""):
    inner = "".join(f"{indent}  {d.strip()};\n" for d in body.split(";") if d.strip())
    text = f"{indent}{sel} {{\n{inner}{indent}}}"
    return f"{ctx} {{\n{_fmt_rule('', sel, body, '  ')}\n}}" if ctx else text


def excerpts(rl):
    out = []
    for gname, sels in EXCERPTS:
        parts = []
        for sel in sels:
            rule_body(rl, sel)                               # 顶层恰好一条（断言）
            parts += [_fmt_rule(c, s, b) for c, s, b in rl if s == sel]   # 媒体查询里的同名规则一并列出
        css = "\n".join(parts)
        out.append(f'<details><summary>{_e(gname)} · {len(sels)} 条规则</summary>'
                   f'<pre><code>{_e(css)}</code></pre></details>')
    return "".join(out)


def dark_diff(rl, rd):
    sm = difflib.SequenceMatcher(a=rl, b=rd, autojunk=False)
    rows = []
    for op, a1, a2, b1, b2 in sm.get_opcodes():
        if op == "equal":
            continue
        la = {(c, s): b for c, s, b in rl[a1:a2] if not DIFF_SKIP.match(s)}
        for c, s, b in rd[b1:b2]:
            if DIFF_SKIP.match(s) or c.startswith("@font-face"):
                continue
            rows.append(((c + " " if c else "") + s, la.get((c, s)), b))
    need(rows, "深色差异清单为空，比对大概坏了")
    cell = lambda b: f'<code class="wrap">{_e(b)}</code>' if b else '<span class="muted">（明亮版无此规则）</span>'
    return ('<div class="tbl"><table><thead><tr><th>规则</th><th>明亮</th><th>深色</th></tr></thead><tbody>'
            + "".join(f'<tr><th scope="row"><code>{_e(s)}</code></th><td>{cell(a)}</td><td>{cell(b)}</td></tr>'
                      for s, a, b in rows) + "</tbody></table></div>"), len(rows)


def opacity_note():
    pairs = []
    for p in _theme_dark.OPACITY_PATCHES:
        a = re.search(r'stop-opacity="([\d.]+)"', p.anchor.replace("\\", "")).group(1)
        b = re.search(r'stop-opacity="([\d.]+)"', p.payload).group(1)
        pairs.append(f"{a} → {b}")
    return "、".join(pairs)


# ============================================================ 组件样例：组件页原样搬进说明
# 不另画示意：DOM、CSS、交互脚本都从模版产物取，明暗各一份，放进声明式影子 DOM——
# 模版的全局规则（* 重置、h1–h6、button…）与说明页自己的样式互不渗透；令牌是 CSS 自定义
# 属性，会穿过影子边界从文档的 theme.css 继承，所以主题切换在样例里同样生效。
SPECIMEN_SECTIONS = ("foundations", "actions", "forms", "selection", "feedback",
                     "navigation", "surfaces", "overlays")
SPECIMEN_BLOCKS = 38          # 设计层出口断言的 ds__block 数（原 37 + 文字色板 1）
SHELL_MARK = "/* ==== 外壳补丁"


def _match_div(html, start):
    """从 start 处的 <div 起，按嵌套层数找到与之配对的 </div> 之后的位置。"""
    depth = 0
    for m in re.compile(r"<div\b|</div>").finditer(html, start):
        depth += 1 if m.group(0) == "<div" else -1
        if depth == 0:
            return m.end()
    need(False, "组件页的 .ds 容器没有闭合")


def components_dom(html):
    """组件页的 .ds 容器：八个分区与浮层，去掉头图（含来源站点署名）与分区导航。"""
    b = html[html.index("</style>"):]
    i = b.index('id="pv-components"')
    start = b.index('<div class="ds">', i)
    dom = b[start:_match_div(b, start)]
    for tag, cls in (("header", "ds__hero"), ("nav", "ds__nav")):
        pat = re.compile(r'<' + tag + r' class="' + cls + r'"[^>]*>.*?</' + tag + r'>', re.S)
        need(len(pat.findall(dom)) == 1, f"组件页的 {cls} 不是恰好一处")
        dom = pat.sub("", dom)
    secs = re.findall(r'<section class="ds__cat" id="([\w-]+)"', dom)
    need(tuple(secs) == SPECIMEN_SECTIONS, f"组件页分区不符：{secs}")
    blocks = dom.count('class="ds__block"')
    need(blocks == SPECIMEN_BLOCKS, f"组件块 {blocks} 个，期望 {SPECIMEN_BLOCKS}")
    need("<template" not in dom and "<script" not in dom, "组件页 DOM 里出现了 template/script")
    return dom


def specimen_css(html):
    """模版样式表 → 影子根样式：截掉外壳补丁及其后（外壳、深色追加段、设计层令牌），
    去掉字体声明与令牌块（文档层的 fonts.css / theme.css 提供），html/body 改挂 :host。"""
    css = _css(html)
    cut = css.find(SHELL_MARK)
    need(cut > 0, "样式表里找不到外壳补丁段")
    rest = re.sub(r"/\*.*?\*/", "", css[cut:], flags=re.S)      # 注释里提到 .ds 不算
    need(not re.search(r"\.ds(?:__|\b)", rest), "外壳补丁之后还有组件页规则，不能截断")
    css = css[:cut]
    css = re.sub(r"@font-face\{[^}]*\}", "", css)
    css = re.sub(r"@media[^{]*\{\s*:root\{[^}]*\}\s*\}", "", css)
    css = re.sub(r"(?<![\w-]):root\{[^}]*\}", "", css)
    css, n = re.subn(r"(^|\})\s*(html|body)\{", r"\1:host{", css)
    need(n == 2, f"html/body 规则改挂 :host 命中 {n} 处，期望 2")
    need(not re.search(r"(^|[},])\s*(html|body)\b", css), "还有以 html/body 开头的选择器")
    need("url(data:font" not in css and "</style" not in css, "样例样式里混进了字体或闭合标签")
    return css + ":host{display:block}.ds{min-height:0}"


def ds_script(html):
    """组件页自己的交互脚本（一段立即执行函数），原样取出。"""
    js = re.findall(r"<script\b[^>]*>(.*?)</script>", html[html.index("</style>"):], re.S)
    need(len(js) == 1, f"模版里的脚本段 {len(js)} 个，期望 1")
    js = js[0]
    a = js.index("  var root = document.querySelector('.ds');")
    st, en = js.rindex("(function () {", 0, a), js.index("})();", a) + len("})();")
    body = js[st:en]
    used = set(re.findall(r"\bdocument\.(\w+)", body))
    need(used <= {"querySelector", "getElementById", "addEventListener"},
         f"组件页脚本用到了替身没有的 document 接口：{sorted(used)}")
    return body


def specimen(html, theme):
    return (f'<div class="specimen specimen--{theme}"><template shadowrootmode="open">'
            f'<style>{specimen_css(html)}</style>{components_dom(html)}</template></div>')


# ============================================================ 主流程
README = """# {name} · 交付包

给业务网页实现者：按这两个模版统一现有网页的颜色、字体、圆角、阴影和组件样式。

**先打开 `style-guide.html`**（风格说明）。两个模版双击即可在浏览器里打开对照。

## 包里有什么

| 路径 | 内容 |
|---|---|
| `style-guide.html` | 风格说明：令牌、对比度、字体字号、组件规格、深色规则、改造步骤、验收清单 |
| `templates/template-light.html` | 明亮版模版（四页：Marketing / Application / E-commerce / Components） |
| `templates/template-dark.html` | 深色版模版（内容相同） |
| `tokens/theme.css` | 明暗两套 CSS 变量 |
| `tokens/tokens.json` | 同一份令牌的 JSON：分组、用途、明暗取值、模版引用次数 |
| `fonts/` | {nfonts} 个 woff2（思源黑体、更纱黑体 GB2312 子集）、`fonts.css`、`LICENSE.txt` |

模版底部有一个切页条，地址后加 `#p=components` 可直达组件页。切页条是预览外壳，不属于风格。

## 三步接入

```html
<link rel="stylesheet" href="fonts/fonts.css">
<link rel="stylesheet" href="tokens/theme.css">
<html data-theme="light">   <!-- 或 "dark"；不设则跟随系统 -->
```

然后把样式里的颜色、圆角、阴影换成令牌，例如 `color: var(--body); background: var(--card);
border: 1px solid var(--border); border-radius: var(--r-md);`。

## 来源

{source}

说明和 `theme.css` 里的数值都直接取自模版，三者保持一致。如果觉得某个值需要调整，
请反馈给主题维护方统一修改并发布新版本，不要在业务代码里自行覆盖。
需要 Chrome / Edge 119 及以上（模版用到 color-mix() 与相对颜色语法）。
"""


def zip_dir(src: Path, dst: Path):
    with zipfile.ZipFile(dst, "w", zipfile.ZIP_DEFLATED, compresslevel=9) as z:
        for p in sorted(src.rglob("*")):
            if p.is_file():
                info = zipfile.ZipInfo(f"{src.name}/{p.relative_to(src).as_posix()}", ZIP_TIME)
                info.compress_type = zipfile.ZIP_DEFLATED
                info.external_attr = 0o644 << 16
                z.writestr(info, p.read_bytes(), compresslevel=9)


def main():
    x = extract()
    L, D = x["L"], x["D"]
    faces = fonts(x["cl"], x["cd"])
    sha = lambda s: hashlib.sha256(s.encode()).hexdigest()[:12]
    src_meta = {"templateLight": {"file": SRC_LIGHT.name, "sha256": sha(x["hl"])},
                "templateDark": {"file": SRC_DARK.name, "sha256": sha(x["hd"])},
                "brandAnchor": _theme_brand.ANCHOR}
    source_line = (f"模版产物 `{SRC_LIGHT.name}`（sha256 {src_meta['templateLight']['sha256']}）与 "
                   f"`{SRC_DARK.name}`（sha256 {src_meta['templateDark']['sha256']}），"
                   f"品牌锚点 {_theme_brand.ANCHOR}。")

    theme = theme_css(L, D, x["media"])
    t_type, t_space, n_space = type_and_space(x["hl"])
    t_diff, n_diff = dark_diff(x["rl"], x["rd"])
    n_colors = sum(len(g) for _, g in COLOR_GROUPS)
    de = _theme_brand._de
    coral = _hex6(dict(_theme_dark.ROOT_KEEP)["brand"])          # 原品牌色，深色层恒等表里登记的
    teal, purple = _hex6(L["teal"]), _hex6(L["purple"])
    orig = (de(coral, teal), de(coral, purple), de(teal, purple))  # 原站三个图表系列两两的色差

    ds_js = ds_script(x["hl"])
    need(ds_js == ds_script(x["hd"]), "明暗两个模版的组件页脚本不一致")
    guide = GUIDE_SRC.read_text(encoding="utf-8")
    fills = {
        "/*{{THEME_CSS}}*/": theme,
        "{{SOURCE}}": _e(source_line).replace("`", ""),
        "{{COLOR_TABLES}}": color_tables(L, D, x["refs"]),
        "{{OTHER_TABLES}}": other_tables(L, D, x["refs"]),
        "{{CONTRAST_TABLE}}": contrast_table(L, D),
        "{{TYPE_TABLE}}": t_type,
        "{{SPACE_SCALE}}": t_space,
        "{{FONT_ROWS}}": font_rows(faces),
        "{{ALIAS_TABLE}}": alias_table(x["cl"]),
        "{{EXCERPTS}}": excerpts(x["rl"]),
        "{{DARK_DIFF}}": t_diff,
        "{{OPACITY}}": opacity_note(),
        "{{N_COLORS}}": str(n_colors),
        "{{N_TOKENS}}": str(len(L)),
        "{{N_DIFF}}": str(n_diff),
        "{{N_SPACE}}": str(n_space),
        "{{ANCHOR}}": _theme_brand.ANCHOR,
        "{{SCRIM_LIGHT}}": L["scrim"], "{{SCRIM_DARK}}": D["scrim"],
        "{{DANGER_GAP}}": f"{hue_gap(L['brand'], L['danger']):.0f}°",
        "{{CORAL_GAP}}": f"{hue_gap(coral, L['danger']):.0f}°",
        "{{PURPLE_DE}}": f"{de(L['brand'], L['purple']):.3f}",
        "{{ORIG_DE}}": f"{min(orig):.2f}–{max(orig):.2f}",
        "{{FG_LC}}": " / ".join(f"{v}" for v in _theme_dark.BRAND_FG_LC.values()),
        "{{SPECIMEN_LIGHT}}": specimen(x["hl"], "light"),
        "{{SPECIMEN_DARK}}": specimen(x["hd"], "dark"),
        "/*{{DS_JS}}*/": ds_js,
        "{{N_SECTIONS}}": str(len(SPECIMEN_SECTIONS)),
        "{{N_BLOCKS}}": str(SPECIMEN_BLOCKS),
    }
    for k, v in fills.items():
        need(guide.count(k) >= 1, f"说明模版里缺占位 {k}")
        guide = guide.replace(k, v)
    left = re.findall(r"\{\{[A-Z_]+\}\}", guide)
    need(not left, f"说明里还有未填的占位：{left}")

    if OUT.exists():
        shutil.rmtree(OUT)
    (OUT / "templates").mkdir(parents=True)
    (OUT / "tokens").mkdir()
    (OUT / "fonts").mkdir()
    shutil.copyfile(SRC_LIGHT, OUT / "templates" / "template-light.html")
    shutil.copyfile(SRC_DARK, OUT / "templates" / "template-dark.html")
    (OUT / "tokens" / "theme.css").write_text(theme, encoding="utf-8")
    (OUT / "tokens" / "tokens.json").write_text(tokens_json(L, D, x["refs"], x["media"], src_meta),
                                                encoding="utf-8")
    for _, _, fname, raw in faces:
        (OUT / "fonts" / fname).write_bytes(raw)
    (OUT / "fonts" / "fonts.css").write_text(fonts_css(x["cl"], faces), encoding="utf-8")
    (OUT / "fonts" / "LICENSE.txt").write_text(font_license(faces), encoding="utf-8")
    # 包里的说明是完整文档；发布成页面时用的是去掉文档外壳的同一份内容（handoff/_page/）
    head = ('<!doctype html>\n<html lang="zh-CN">\n<meta charset="utf-8">\n'
            '<meta name="viewport" content="width=device-width,initial-scale=1,viewport-fit=cover">\n')
    (OUT / "style-guide.html").write_text(head + guide, encoding="utf-8")
    (OUT / "README.md").write_text(README.format(name=NAME, nfonts=len(faces), source=source_line),
                                   encoding="utf-8")
    page = OUT.parent / "_page"
    if page.exists():
        shutil.rmtree(page)
    shutil.copytree(OUT / "fonts", page / "fonts")
    (page / "style-guide.html").write_text(guide, encoding="utf-8")

    zip_dir(OUT, ZIP)
    size = lambda p: sum(f.stat().st_size for f in p.rglob("*") if f.is_file())
    print(f"已生成 {OUT.relative_to(HERE)}/（{size(OUT) / 1048576:.1f} MB）与 "
          f"{ZIP.relative_to(HERE)}（{ZIP.stat().st_size / 1048576:.1f} MB）")
    print(f"  令牌 {len(L)} 个（颜色 {n_colors}，含补充 {len(SUPPLEMENT)}），深色改写 "
          f"{sum(1 for n in L if D[n] != L[n])} 个；字体 {len(faces)} 个；组件摘录 "
          f"{sum(len(s) for _, s in EXCERPTS)} 条；深色非令牌差异 {n_diff} 条")


if __name__ == "__main__":
    main()
