# -*- coding: utf-8 -*-
"""生成中文字体包，供 `_build_charm.py --fonts=cjk|cjk-gb` 内嵌。

两个来源：
  正文/标题  NotoSansCJK-Woff2/*.woff2          已是 woff2
  等宽      SarasaMonoSC-TTF-1.0.36/*.ttf      TTF，本脚本转成 woff2

为什么等宽单独用更纱黑体而不是 Noto Sans SC：Noto Sans SC 的拉丁是比例字体，
拿它当等宽会让 components 页的代码示例失去列对齐。更纱黑体（Sarasa Mono）刻意
把汉字宽度做成拉丁的整两倍，中英混排也不破列。下面对每个字面都断言了这一点，
子集化之后也重新断言一次——subset 若动了 advance width，这里会立刻炸。

字重按 CSS 里实际用到的值划分区间（见下方两张表），@font-face 直接声明区间，
把匹配结果钉死，不依赖浏览器的就近回退，也不触发合成粗体。

两个包：
    python3 _make_cjk_fonts.py            # 全量 CJK → _charm_fonts_cjk.json（72 MB）
    python3 _make_cjk_fonts.py --gb2312   # GB2312 子集 → _charm_fonts_cjk_gb.json

包里的字节还可以解回独立文件，供别的项目直接引用（不必重跑转换）：
    python3 _make_cjk_fonts.py --export             # 全量 → SarasaMonoSC-Woff2/
    python3 _make_cjk_fonts.py --gb2312 --export    # 子集 → 同上目录（会覆盖同名文件）

子集包的字符集 = GB2312 全集（6763 汉字 + 682 符号）∪ 拉丁与标点区
                 ∪ 拉丁版产物里出现过的每一个字符。
最后那一项是硬要求：四页正文是英文，子集若漏掉任何一个已在用的字符，
产物就会当场退化成系统字体——所以直接从 charm-preview.html 里取全集兜底。
"""
from __future__ import annotations

import base64
import io
import json
import sys
import time
from pathlib import Path

from fontTools import subset
from fontTools.ttLib import TTFont
from fontTools.ttLib.woff2 import compress

HERE = Path(__file__).resolve().parent
DIR_NOTO = HERE / "NotoSansCJK-Woff2"
DIR_SARASA = HERE / "SarasaMonoSC-TTF-1.0.36"
OUT_FULL = HERE / "_charm_fonts_cjk.json"
OUT_GB = HERE / "_charm_fonts_cjk_gb.json"
DIR_EXPORT = HERE / "SarasaMonoSC-Woff2"   # --export 的落点，与 NotoSansCJK-Woff2/ 平行
REF_HTML = HERE / "charm-preview.html"     # 拉丁版产物，用来兜底取「已在用的字符」

# 页面 CSS 里出现过的 font-weight：100 / 400 / 500 / 600 / 700 / 800。
# Noto Sans SC 无 600、800 两档，更纱黑体无 500 档 —— 区间边界即为此而设，
# 让每个用到的字重都落进某个真实字面，不留给浏览器合成。
NOTO = [                                   # (文件, 区间)  Noto 有 100/300/350/400/500/700/900
    ("NotoSansSC-Thin.woff2",    "100 349"),
    ("NotoSansSC-Regular.woff2", "350 449"),
    ("NotoSansSC-Medium.woff2",  "450 549"),
    ("NotoSansSC-Bold.woff2",    "550 749"),   # 600 与 700 都落这里
    ("NotoSansSC-Black.woff2",   "750 900"),   # 800 落这里
]
SARASA = [                                 # 更纱黑体有 200/300/400/600/700
    ("SarasaMonoSC-Regular.ttf",  "100 549"),  # 400 与 500 都落这里
    ("SarasaMonoSC-SemiBold.ttf", "550 649"),
    ("SarasaMonoSC-Bold.ttf",     "650 900"),
]
FAM_SANS = "Noto Sans SC"
FAM_MONO = "Sarasa Mono SC"

# 子集必保的码位区：基本拉丁 + 拉丁补充 + 通用标点 + 货币 + CJK 标点 + 全角形式
KEEP_RANGES = [
    (0x0020, 0x00FF), (0x2000, 0x206F), (0x20A0, 0x20BF),
    (0x2190, 0x21FF), (0x2200, 0x22FF), (0x2460, 0x24FF), (0x25A0, 0x25FF),
    (0x3000, 0x303F), (0xFE30, 0xFE4F), (0xFF00, 0xFFEF),
]


def need(cond, msg):
    if not cond:
        sys.exit(f"[字体包构建失败] {msg}")


def human(n: int) -> str:
    return f"{n / 1048576:.1f} MB" if n >= 1048576 else f"{n / 1024:.0f} KB"


def gb2312_charset() -> set:
    """枚举 GB2312 的全部合法双字节码位，解出它收录的每一个字符。

    比手抄一份「常用字表」可靠：标准本身就是字符集的定义，
    这么取必然是 6763 汉字 + 682 符号，不多不少。
    """
    out = set()
    for hi in range(0xA1, 0xF8):
        for lo in range(0xA1, 0xFF):
            try:
                out.add(bytes([hi, lo]).decode("gb2312"))
            except UnicodeDecodeError:
                pass
    return out


def build_charset() -> set:
    gb = gb2312_charset()
    need(len(gb) == 7445, f"GB2312 解出 {len(gb)} 个字符，期望 7445（6763 汉字 + 682 符号）")
    cps = {ord(c) for c in gb}
    for lo, hi in KEEP_RANGES:
        cps.update(range(lo, hi + 1))

    need(REF_HTML.exists(), f"缺少 {REF_HTML.name}（先跑 python3 _build_charm.py）")
    used = set(REF_HTML.read_text(encoding="utf-8"))
    missing = {ord(c) for c in used} - cps
    cps |= missing
    print(f"  GB2312 {len(gb)} 字符 + 保留区 → {len(cps)} 个码位"
          f"（其中 {len(missing)} 个是产物里在用、却不在上述范围的字符）")
    return cps


def mono_metrics(font: TTFont, label: str) -> tuple:
    """返回 (拉丁 advance, 汉字 advance)，用来证明等宽与整二倍宽。"""
    cmap, hmtx = font.getBestCmap(), font["hmtx"]
    lat = {hmtx[cmap[c]][0] for c in map(ord, "iWM0.") if c in cmap}
    cjk = {hmtx[cmap[c]][0] for c in map(ord, "中永国") if c in cmap}
    need(len(lat) == 1, f"{label} 的拉丁不等宽：{lat}")
    need(len(cjk) == 1, f"{label} 的汉字不等宽：{cjk}")
    a, b = lat.pop(), cjk.pop()
    need(b == a * 2, f"{label} 汉字宽 {b} 不是拉丁 {a} 的整二倍，列对齐无法保证")
    return a, b


def to_woff2(path: Path, cps: set | None) -> bytes:
    """转 woff2；cps 非 None 时先按码位子集化。"""
    if cps is None:
        if path.suffix == ".woff2":
            return path.read_bytes()
        buf = io.BytesIO()
        compress(path.as_posix(), buf)       # brotli q=11，24 MB 的 CJK 字体要跑一会儿
        return buf.getvalue()

    opts = subset.Options()
    opts.drop_tables = []                    # 保留默认之外的表，别动垂直排版数据
    opts.ignore_missing_unicodes = True
    font = subset.load_font(path.as_posix(), opts)
    sub = subset.Subsetter(options=opts)
    sub.populate(unicodes=cps)
    sub.subset(font)
    font.flavor = "woff2"
    buf = io.BytesIO()
    font.save(buf)
    font.close()
    return buf.getvalue()


def entry(family: str, weight: str, data: bytes, src: str) -> dict:
    return {"family": family, "weight": weight, "src": src,
            "bytes": len(data), "b64": base64.b64encode(data).decode()}


def build(cps: set | None, out: Path) -> None:
    fonts = []
    kind = "GB2312 子集" if cps else "全量 CJK"
    print(f"\n== 正文/标题：{FAM_SANS}（{kind}）==")
    for name, weight in NOTO:
        p = DIR_NOTO / name
        need(p.exists(), f"缺少 {p}")
        t0 = time.time()
        data = to_woff2(p, cps)
        need(data[:4] == b"wOF2", f"{name} 结果不是 woff2")
        fonts.append(entry(FAM_SANS, weight, data, name))
        print(f"  {name:<28} {human(p.stat().st_size)} → {human(len(data)):>8}  "
              f"font-weight:{weight}  {time.time() - t0:.0f}s")

    print(f"\n== 等宽：{FAM_MONO}（{kind}）==")
    for name, weight in SARASA:
        p = DIR_SARASA / name
        need(p.exists(), f"缺少 {p}")
        src_font = TTFont(p, lazy=True)
        lat, cjk = mono_metrics(src_font, name)
        src_font.close()

        t0 = time.time()
        data = to_woff2(p, cps)
        need(data[:4] == b"wOF2", f"{name} 结果不是 woff2")
        # 子集化之后重新量一次：subset 若动了 advance width，列对齐就没了
        out_font = TTFont(io.BytesIO(data), lazy=True)
        mono_metrics(out_font, f"{name}（子集后）")
        out_font.close()

        fonts.append(entry(FAM_MONO, weight, data, name))
        print(f"  {name:<28} {human(p.stat().st_size)} → {human(len(data)):>8}  "
              f"font-weight:{weight}  拉丁{lat}/汉字{cjk}  {time.time() - t0:.0f}s")

    out.write_text(json.dumps(fonts), encoding="utf-8")
    raw = sum(f["bytes"] for f in fonts)
    b64 = sum(len(f["b64"]) for f in fonts)
    print(f"\n已写出 {out.name}：{len(fonts)} 个字面，原始 {human(raw)} → "
          f"base64 {human(b64)}（内嵌后产物约 {human(b64 + 600_000)}）")


def export_woff2(pack: Path) -> None:
    """把包里**本脚本转换出来的**字面解码成独立 .woff2，供别的项目直接用。

    只导 src 是 .ttf 的那些（更纱黑体）——思源那几个本来就是现成的 woff2 文件，
    再导一遍只是把同样的字节在磁盘上放两份。
    """
    need(pack.exists(), f"缺少字体包 {pack.name}（先跑 python3 _make_cjk_fonts.py）")
    fonts = json.loads(pack.read_text())
    made, skipped = [], []
    for f in fonts:
        if not f["src"].endswith(".ttf"):
            skipped.append(f["src"])
            continue
        data = base64.b64decode(f["b64"])
        need(len(data) == f["bytes"], f"{f['src']} 解码长度对不上")
        need(data[:4] == b"wOF2", f"{f['src']} 解码结果不是 woff2")

        dst = DIR_EXPORT / (Path(f["src"]).stem + ".woff2")
        DIR_EXPORT.mkdir(exist_ok=True)
        dst.write_bytes(data)

        # 独立文件也要能独立成立：cmap 读得出、等宽指标仍然是整二倍
        font = TTFont(io.BytesIO(data), lazy=True)
        n = len(font.getBestCmap())
        lat, cjk = mono_metrics(font, dst.name)
        font.close()
        made.append(dst)
        print(f"  {dst.name:<30} {human(len(data)):>8}  {n} 字形  拉丁{lat}/汉字{cjk}  "
              f"font-weight:{f['weight']}")

    print(f"\n已导出 {len(made)} 个到 {DIR_EXPORT.name}/（源包 {pack.name}）")
    if skipped:
        print(f"  跳过 {len(skipped)} 个非转换字面（本就是现成 woff2）：{DIR_NOTO.name}/ 里直接取")


def main(argv):
    gb = export = False
    for a in argv[1:]:
        if a == "--gb2312":
            gb = True
        elif a == "--export":
            export = True
        else:
            sys.exit(f"未知参数 {a}（可用：--gb2312 / --export）")
    if export:
        export_woff2(OUT_GB if gb else OUT_FULL)
    else:
        build(build_charset() if gb else None, OUT_GB if gb else OUT_FULL)


if __name__ == "__main__":
    main(sys.argv)
