# -*- coding: utf-8 -*-
"""渲染对比度审计：深色版的每一段文字，在它实际所在的底色上都不得比明亮版更难读。

深色层与皮肤层的断言只能在令牌层面算对比（墨对 page、状态字对 soft……）；文字实际坐在
哪种底上、底是不是半透明叠出来的、SVG 插画里的字压在什么形状上，令牌层看不见。
这道审计在真实渲染里取证：用 headless Chrome 打开产物的四页，对每个含文字的元素取
计算后的前景色（SVG 取 fill），沿 DOM 祖先链（SVG 用 elementsFromPoint 取下方图形栈）
叠出实际背景，渐变取全部色标里最坏的一个，算 APCA Lc；再把明暗两版的同一段文字按
（标签、class、文本）序列对齐逐一比较。

判据：深色 Lc ≥ min(明亮 Lc, LC_CAP) − 0.5。唯一的约定例外是品牌前景（fg-brand /
fg-brand-strong）：深色层定稿拿 Lc 换彩度，这里只要求它不低于定稿值 − 1.5（不同底色
上的读数差）。例外逐条列出，不静默放过。

运行（需要 Chrome；路径同 _verify_charm.mjs 的 CHROME 常量，换机器要改）：
    python3 _audit_contrast.py        # 审计全部存在的明暗配对，有退化则 exit 1
产物缺哪个就跳过哪组配对并注明。每组约 4 次渲染，全量约 1–2 分钟。
"""
from __future__ import annotations

import difflib
import json
import re
import subprocess
import sys
import tempfile
from collections import defaultdict
from pathlib import Path

import _theme_brand
import _theme_dark

HERE = Path(__file__).resolve().parent
CHROME = "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome"
PAGES = ("marketing", "application", "ecommerce", "components")
PAIRS = (("charm-preview-cjk-gb-zh.html", "charm-preview-cjk-gb-zh-dark.html"),
         ("charm-preview-cjk-gb-zh.html", "charm-preview-cjk-gb-zh-console.html"),
         ("charm-preview-cjk-gb-zh-sim.html", "charm-preview-cjk-gb-zh-sim-dark.html"))
LC_CAP = _theme_dark.LC_CAP
# 品牌前景的约定例外：深色值 → 定稿 Lc（珊瑚与工程蓝两套）
BRAND_FG = {}
for _src in (_theme_dark.EXPECTED, _theme_brand.EXPECTED_SIM_DARK):
    for _n, _lc in _theme_dark.BRAND_FG_LC.items():
        BRAND_FG[_src[_n]] = (_n, _lc)
BRAND_FG_SLACK = 1.5

PROBE = r"""
(function () {
  function parse(c) {
    if (!c || c === 'none' || c === 'transparent') return null;
    var m = c.match(/rgba?\(([\d.]+)[ ,]+([\d.]+)[ ,]+([\d.]+)(?:[ ,/]+([\d.]+%?))?\)/);
    if (m) { var a = m[4] === undefined ? 1 : (m[4].endsWith('%') ? parseFloat(m[4]) / 100 : parseFloat(m[4]));
      return [ +m[1], +m[2], +m[3], a ]; }
    m = c.match(/color\(srgb ([\d.e-]+) ([\d.e-]+) ([\d.e-]+)(?: \/ ([\d.]+))?\)/);
    if (m) return [ m[1] * 255, m[2] * 255, m[3] * 255, m[4] === undefined ? 1 : +m[4] ];
    return null;
  }
  function over(f, b) { var a = f[3]; return [ f[0] * a + b[0] * (1 - a), f[1] * a + b[1] * (1 - a), f[2] * a + b[2] * (1 - a), 1 ]; }
  function Y(c) { var y = .2126729 * Math.pow(c[0] / 255, 2.4) + .7151522 * Math.pow(c[1] / 255, 2.4) + .072175 * Math.pow(c[2] / 255, 2.4);
    return y < .022 ? y + Math.pow(.022 - y, 1.414) : y; }
  function apca(t, b) { var yt = Y(t), yb = Y(b), s;
    if (Math.abs(yb - yt) < .0005) return 0;
    if (yb > yt) { s = (Math.pow(yb, .56) - Math.pow(yt, .57)) * 1.14; return s < .1 ? 0 : (s - .027) * 100; }
    s = (Math.pow(yb, .65) - Math.pow(yt, .62)) * 1.14; return s > -.1 ? 0 : (s + .027) * 100; }
  function hex(c) { return '#' + c.slice(0, 3).map(function (v) { return ('0' + Math.round(v).toString(16)).slice(-2); }).join(''); }
  var PAGE = parse(getComputedStyle(document.body).backgroundColor) || [255, 255, 255, 1];
  // HTML 背景：沿祖先链叠加，渐变取全部色标（最坏情况）
  function htmlBgs(el) {
    var layers = [];
    for (var e = el; e && e.nodeType === 1; e = e.parentElement) {
      var cs = getComputedStyle(e), img = cs.backgroundImage;
      if (img && img !== 'none' && /gradient/.test(img)) {
        var stops = (img.match(/rgba?\([^)]*\)|color\(srgb[^)]*\)/g) || []).map(parse).filter(Boolean);
        if (stops.length) { layers.push({ g: stops }); if (stops.every(function (s) { return s[3] >= 1; })) break; }
      }
      var bc = parse(cs.backgroundColor);
      if (bc && bc[3] > 0) { layers.push({ c: bc }); if (bc[3] >= 1) break; }
    }
    var bases = [PAGE];
    for (var i = layers.length - 1; i >= 0; i--) {
      var L = layers[i], nb = [];
      bases.forEach(function (b) { (L.g || [L.c]).forEach(function (c) { nb.push(over(c, b)); }); });
      bases = nb;
    }
    return bases;
  }
  // SVG 文字背景：取文字中心点下方的图形栈
  function svgBgs(el) {
    var r = el.getBoundingClientRect(); if (!r.width) return null;
    var x = r.left + r.width / 2, y = r.top + r.height / 2, stack = document.elementsFromPoint(x, y), layers = [];
    for (var i = 0; i < stack.length; i++) {
      var e = stack[i];
      if (e === el || (e instanceof SVGElement && (e.tagName === 'text' || e.tagName === 'tspan' || e.tagName === 'g'))) continue;
      if (e instanceof SVGElement && e.tagName !== 'svg') {
        var cs = getComputedStyle(e), f = parse(cs.fill);
        if (f) { f[3] *= parseFloat(cs.fillOpacity || 1) * parseFloat(cs.opacity || 1); if (f[3] > 0) { layers.push(f); if (f[3] >= 1) break; } }
        continue;
      }
      var hb = htmlBgs(e); return layers.reduceRight(function (acc, c) { return acc.map(function (b) { return over(c, b); }); }, hb);
    }
    return layers.reduceRight(function (acc, c) { return acc.map(function (b) { return over(c, b); }); }, [PAGE]);
  }
  var out = [], seen = new Set(), walker = document.createTreeWalker(document.body, NodeFilter.SHOW_TEXT);
  var idx = 0;
  while (walker.nextNode()) {
    var t = walker.currentNode, el = t.parentElement;
    if (!el || !t.nodeValue.trim() || seen.has(el)) continue;
    if (/^(SCRIPT|STYLE|TITLE|PRE)$/.test(el.tagName) && !(el instanceof SVGElement)) continue;
    if (el.closest('.pv-switch, .lang-flag, [aria-hidden="true"] svg')) continue;
    var pv = el.closest('.pv'); if (!pv || pv.hidden) continue;
    seen.add(el); idx++;
    var cs = getComputedStyle(el), isSvg = el instanceof SVGElement, fg, bgs;
    if (isSvg) { fg = parse(cs.fill); if (!fg) continue; fg[3] *= parseFloat(cs.fillOpacity || 1); bgs = svgBgs(el); }
    else { fg = parse(cs.color); bgs = htmlBgs(el); }
    if (!fg || !bgs) continue;
    var worst = null;
    bgs.forEach(function (b) { var f = fg[3] < 1 ? over(fg, b) : fg, lc = Math.abs(apca(f, b)); if (!worst || lc < worst.lc) worst = { lc: lc, fg: hex(f), bg: hex(b) }; });
    out.push({ i: idx, svg: isSvg, tag: el.tagName.toLowerCase(), cls: (el.getAttribute('class') || '').slice(0, 60),
      txt: t.nodeValue.trim().slice(0, 24), fs: parseFloat(cs.fontSize), fw: cs.fontWeight, lc: Math.round(worst.lc * 10) / 10, fg: worst.fg, bg: worst.bg,
      vis: !!(el.getClientRects().length) && cs.visibility !== 'hidden' });
  }
  var pre = document.createElement('pre'); pre.id = '__audit'; pre.textContent = '@@AUDIT@@' + JSON.stringify(out) + '@@END@@';
  document.body.appendChild(pre);
})();
"""


def need(cond, msg):
    if not cond:
        sys.exit(f"[对比度审计失败] {msg}")


def sample(product: Path, page: str, work: Path) -> list:
    """渲染一页，返回每个含文字元素的 {tag, cls, txt, fg, bg, lc, svg}。"""
    probe = work / f"{product.stem}.probe.html"
    if not probe.exists():
        src = product.read_text(encoding="utf-8")
        i = src.rindex("</body>") if "</body>" in src else len(src)
        probe.write_text(src[:i] + "<script>addEventListener('load',function(){setTimeout(function(){"
                         + PROBE + "},300)})</script>" + src[i:], encoding="utf-8")
    r = subprocess.run([CHROME, "--headless=new", "--disable-gpu", "--hide-scrollbars",
                        f"--user-data-dir={work / 'profile'}", "--window-size=1440,16000",
                        "--virtual-time-budget=10000", "--dump-dom", f"file://{probe}#p={page}"],
                       capture_output=True, text=True, timeout=300)
    m = re.search(r'<pre id="__audit">@@AUDIT@@(.*?)@@END@@</pre>', r.stdout, re.S)
    need(m, f"{product.name}#p={page} 没拿到采样结果（Chrome 路径对吗？）")
    raw = m.group(1).replace("&quot;", '"').replace("&lt;", "<").replace("&gt;", ">").replace("&amp;", "&")
    return json.loads(raw)


def audit_pair(light: Path, dark: Path, work: Path):
    rows = []
    for page in PAGES:
        L, D = sample(light, page, work), sample(dark, page, work)
        key = lambda e: (e["tag"], e["cls"], e["txt"])
        sm = difflib.SequenceMatcher(a=[key(e) for e in L], b=[key(e) for e in D], autojunk=False)
        for a, b, n in sm.get_matching_blocks():
            rows += [(page, L[a + k], D[b + k]) for k in range(n)]
    bad, excused = defaultdict(list), defaultdict(list)
    for page, l, d in rows:
        want = min(l["lc"], LC_CAP)
        if d["lc"] >= want - 0.5:
            continue
        k = (page, d["svg"], d["tag"], d["cls"][:36], l["fg"], l["bg"], d["fg"], d["bg"])
        if d["fg"] in BRAND_FG and d["lc"] >= BRAND_FG[d["fg"]][1] - BRAND_FG_SLACK:
            excused[k].append((l["lc"], d["lc"], d["txt"]))
        else:
            bad[k].append((l["lc"], d["lc"], d["txt"]))
    return len(rows), bad, excused


def show(groups):
    for (page, svg, tag, cls, lfg, lbg, dfg, dbg), v in sorted(groups.items()):
        print(f"     {page:11s} {'SVG ' if svg else ''}<{tag} .{cls}> ×{len(v)}  明亮 {lfg}/{lbg} "
              f"Lc {v[0][0]:.1f} → 深色 {dfg}/{dbg} Lc {v[0][1]:.1f}  例:{[x[2] for x in v[:2]]}")


def main():
    need(Path(CHROME).exists(), f"找不到 Chrome：{CHROME}")
    failed = False
    with tempfile.TemporaryDirectory(prefix="contrast-audit-") as tmp:
        work = Path(tmp)
        for ln, dn in PAIRS:
            light, dark = HERE / ln, HERE / dn
            if not (light.exists() and dark.exists()):
                print(f"跳过 {dn}：产物不全（{ln} / {dn}）")
                continue
            n, bad, excused = audit_pair(light, dark, work)
            nb, ne = sum(map(len, bad.values())), sum(map(len, excused.values()))
            print(f"{dn}：比对 {n} 段文字，退化 {nb} 段，品牌前景约定例外 {ne} 段")
            if bad:
                failed = True
                show(bad)
    sys.exit(1 if failed else 0)


if __name__ == "__main__":
    main()
