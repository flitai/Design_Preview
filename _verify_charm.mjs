/* Charm 四页合集单文件复刻版的验证脚本。
 *
 * 用法：
 *   NODE_PATH=<装了 puppeteer-core 的 node_modules> node "_verify_charm.mjs"
 *   node "_verify_charm.mjs" --no-visual        # 跳过像素回归（不需要单页产物）
 *
 * 分六层：
 *   0 静态检查（不开浏览器）        3 每页结构
 *   1 加载与资源                    4 交互矩阵
 *   2 切换与页间隔离                5 像素回归（合并版 vs 单页版）
 */
import fs from "fs";
import path from "path";
import { fileURLToPath } from "url";
import { createRequire } from "module";
// 用 createRequire 而非 import：它认 NODE_PATH，于是 puppeteer-core 可以装在本目录之外
// （本目录是自包含的可分发单元，不该出现 node_modules）。
const puppeteer = createRequire(import.meta.url)("puppeteer-core");

const HERE = path.dirname(fileURLToPath(import.meta.url));
const FILE = path.join(HERE, "charm-preview.html");
const CHROME = "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome";
const SLUGS = ["marketing", "application", "ecommerce", "components"];
// 默认页从产物里读，而不是在这儿写死——改 _build_charm.py 的 DEFAULT_SLUG 时
// 不必同步改验证脚本，但断言依然盯着「产物确实按它声明的默认页打开」。
const DEFAULT = /data-default="(\w+)"/.exec(fs.readFileSync(path.join(HERE, "charm-preview.html"), "utf8"))?.[1];
const SINGLE = { components: "charm-components.html" };   // 其余是 charm-single-<slug>.html
const singlePath = (s) => path.join(HERE, SINGLE[s] || `charm-single-${s}.html`);
const DO_VISUAL = !process.argv.includes("--no-visual");

let pass = 0, fail = 0;
const ok = (c, m, extra = "") => { c ? (pass++, console.log(`  ✓ ${m}`)) : (fail++, console.log(`  ✗ ${m}  ${extra}`)); };
const eq = (a, b, m) => ok(JSON.stringify(a) === JSON.stringify(b), m, `实际=${JSON.stringify(a)} 期望=${JSON.stringify(b)}`);
const t = async (name, fn) => { try { ok(await fn(), name); } catch (e) { ok(false, name, e.message); } };

// ================================================================= Phase 0
console.log("\n[Phase 0] 静态检查");
const src = fs.readFileSync(FILE, "utf8");
const noComments = src.replace(/<!--[\s\S]*?-->/g, "");
ok(!/\ssrc\s*=\s*["'](?!data:)/.test(noComments), "无外部 src=");
ok(!/<link\b/.test(noComments), "无 <link>");
ok(!/url\(\s*(?!["']?data:)(?!#)/.test(noComments), "CSS 中无非 data:／非页内的 url()");
ok(!/href\s*=\s*["'](?!#)/.test(noComments), "无非页内锚点 href");
ok(!/module__|__variable/.test(noComments), "无遗留的 CSS-module 哈希类");
ok(!/vercel\.app/.test(noComments), "无 vercel 外链残留");
{
  const ids = [...noComments.matchAll(/(?<![-\w])id="([^"]*)"/g)].map(m => m[1]);
  const dup = [...new Set(ids.filter((x, i) => ids.indexOf(x) !== i))];
  ok(dup.length === 0, `全文档 ${ids.length} 个 id 无重复`, dup.slice(0, 6).join(","));
  const refs = [...new Set([...noComments.matchAll(/url\(#([^)]*)\)/g)].map(m => m[1]))];
  ok(refs.length > 0 && refs.every(r => /^(co|ma|ap|ec)\d+_/.test(r)), "svg 内引用全部带页前缀",
    refs.filter(r => !/^(co|ma|ap|ec)\d+_/.test(r)).slice(0, 5).join(","));
}
{
  const kb = Buffer.byteLength(src) / 1024;
  ok(kb > 620 && kb < 820, `体积 ${kb.toFixed(0)} KB 在预期区间`);
}

// ================================================================= Phase 1
const browser = await puppeteer.launch({ executablePath: CHROME, headless: "new", args: ["--disable-gpu"] });
const page = await browser.newPage();
await page.setViewport({ width: 1440, height: 1000, deviceScaleFactor: 1 });

const requests = [], consoleMsgs = [], pageErrors = [];
page.on("request", r => requests.push(r.url()));
page.on("console", m => { if (m.type() === "error" || m.type() === "warning") consoleMsgs.push(m.text()); });
page.on("pageerror", e => pageErrors.push(e.message));

await page.goto("file://" + FILE, { waitUntil: "networkidle0" });
await new Promise(r => setTimeout(r, 600));

console.log("\n[Phase 1] 加载与资源");
{
  const external = requests.filter(u => !u.startsWith("file://") && !u.startsWith("data:"));
  ok(external.length === 0, "零外部网络请求", external.slice(0, 3).join(", "));
}
ok(pageErrors.length === 0, "无 JS 运行时错误", pageErrors.join(" | "));
ok(consoleMsgs.length === 0, "无 console 报错/警告", consoleMsgs.slice(0, 2).join(" | "));

const env = await page.evaluate(() => ({
  brand: getComputedStyle(document.documentElement).getPropertyValue("--brand").trim(),
  rxl: getComputedStyle(document.documentElement).getPropertyValue("--r-xl").trim(),
  rfull: getComputedStyle(document.documentElement).getPropertyValue("--r-full").trim(),
  alertBorder: getComputedStyle(document.querySelector(".ds__alert--danger")).borderColor,
  fontsInter: document.fonts.check("16px Inter"),
  fontsDM: document.fonts.check('700 16px "DM Sans"'),
  fontsMono: document.fonts.check('12px "Fragment Mono"'),
  barPos: getComputedStyle(document.querySelector(".pv-switch")).position,
  barZ: getComputedStyle(document.querySelector(".pv-switch")).zIndex,
  pvFull: document.querySelector(".pv:not([hidden])").clientHeight === window.innerHeight,
}));
eq(env.brand, "#e4544b", "设计令牌 --brand 可解析");
eq(env.rxl, "24px", "设计令牌 --r-xl 可解析");
eq(env.rfull, "9999px", "设计令牌 --r-full 可解析");
ok(!/rgba\(0,\s*0,\s*0,\s*0\)/.test(env.alertBorder), "color-mix() 生效（alert 边框非透明）", env.alertBorder);
ok(env.fontsInter, "Inter 字体已加载");
ok(env.fontsDM, "DM Sans 字体已加载");
ok(env.fontsMono, "Fragment Mono 字体已加载");
eq(env.barPos, "fixed", "切换器是悬浮层");
ok(env.pvFull, "切换器不占布局：.pv 高度等于整个视口");
eq(env.barZ, "500", "切换器的 z-index 高于所有原页面浮层");

// ================================================================= Phase 2
console.log("\n[Phase 2] 切换与页间隔离");
const goto = async (slug) => {
  await page.evaluate(s => {
    [...document.querySelectorAll(".pv-switch [role=tab]")].find(b => b.dataset.goto === s).click();
  }, slug);
  await new Promise(r => setTimeout(r, 120));
};

eq(await page.evaluate(() => [...document.querySelectorAll(".pv")].filter(p => p.offsetParent !== null).map(p => p.dataset.page)),
  [DEFAULT], `初始恰好一页可见，且是默认的 ${DEFAULT}`);
eq(await page.evaluate(() => [...document.querySelectorAll(".pv-switch [role=tab]")].map(b => b.textContent)),
  ["Marketing", "Application", "E-commerce", "Components"], "tab 顺序与原站一致");

for (const slug of SLUGS) {
  await goto(slug);
  await t(`切到 ${slug}：仅此页可见，其余三页 offsetParent 为 null`, () => page.evaluate(s => {
    const ps = [...document.querySelectorAll(".pv")];
    return ps.filter(p => p.offsetParent !== null).map(p => p.dataset.page).join() === s
      && ps.filter(p => p.dataset.page !== s).every(p => p.offsetParent === null);
  }, slug));
  await t(`切到 ${slug}：tab 的 aria-selected 唯一`, () => page.evaluate(s => {
    const on = [...document.querySelectorAll(".pv-switch [role=tab]")].filter(b => b.getAttribute("aria-selected") === "true");
    return on.length === 1 && on[0].dataset.goto === s && on[0].classList.contains("is-active");
  }, slug));
}

// 切换器贴底而不贴顶，图的就是不压住各页的常驻导航——必须有断言看着，
// 否则哪天有人把它挪回顶部，只会在截图里悄悄少半条导航。
for (const slug of SLUGS) {
  await goto(slug);
  await t(`${slug}：切换器不与该页顶部导航相交`, () => page.evaluate(() => {
    const pill = document.querySelector(".pv-switch").getBoundingClientRect();
    const nav = document.querySelector(".pv:not([hidden]) header, .pv:not([hidden]) .appnav, .pv:not([hidden]) .ds__nav");
    if (!nav) return false;
    const n = nav.getBoundingClientRect();
    return pill.top >= n.bottom || pill.bottom <= n.top || pill.left >= n.right || pill.right <= n.left;
  }));
}

await t("隐藏页里的 position:fixed 浮层不可见", () => page.evaluate(() => {
  // 先把所有页的浮层都打开，再切页，检查隐藏页的浮层确实没渲染
  document.querySelectorAll(".pv .pdrawer, .pv .appsidebar").forEach(e => e.classList.add("is-open"));
  document.querySelectorAll(".pv .modal-scrim, .pv .pdrawer-scrim, .pv .appsidebar-scrim, .pv .ds__scrim").forEach(e => (e.hidden = false));
  const bad = [...document.querySelectorAll(".pv[hidden] .pdrawer, .pv[hidden] .appsidebar, .pv[hidden] .modal-scrim, .pv[hidden] .pdrawer-scrim, .pv[hidden] .appsidebar-scrim, .pv[hidden] .ds__scrim")]
    .filter(e => e.getClientRects().length > 0);
  document.querySelectorAll(".pv .pdrawer, .pv .appsidebar").forEach(e => e.classList.remove("is-open"));
  document.querySelectorAll(".pv .modal-scrim, .pv .pdrawer-scrim, .pv .appsidebar-scrim, .pv .ds__scrim").forEach(e => (e.hidden = true));
  return bad.length === 0;
}));

await t("隐藏页里的元素不可 Tab 聚焦", () => page.evaluate(() => {
  const el = document.querySelector('.pv[hidden] a, .pv[hidden] button, .pv[hidden] input');
  el.focus();
  return document.activeElement !== el;
}));

for (const w of [1440, 1024, 768]) {
  await page.setViewport({ width: w, height: 1000, deviceScaleFactor: 1 });
  await new Promise(r => setTimeout(r, 250));
  for (const slug of SLUGS) {
    await goto(slug);
    await t(`${slug} @${w} 无横向溢出`, () => page.evaluate(() =>
      document.documentElement.scrollWidth <= document.documentElement.clientWidth
      && document.body.scrollWidth <= document.body.clientWidth));
  }
}
await page.setViewport({ width: 1440, height: 1000, deviceScaleFactor: 1 });
await new Promise(r => setTimeout(r, 250));

await t("body 不滚动，.pv 才是滚动容器", () => page.evaluate(() =>
  document.body.scrollHeight <= window.innerHeight && getComputedStyle(document.body).overflow === "hidden"));

await t("三个文档型页面各自以 .pv 为滚动容器（application 是 appshell，内部自滚）", async () => {
  for (const slug of ["marketing", "ecommerce", "components"]) {
    await goto(slug);
    const okk = await page.evaluate(() => {
      const pv = document.querySelector(".pv:not([hidden])");
      return pv.scrollHeight > pv.clientHeight + 10;
    });
    if (!okk) return false;
  }
  await goto("application");
  return page.evaluate(() => {
    const pv = document.querySelector(".pv:not([hidden])");
    return pv.scrollHeight <= pv.clientHeight + 2 && document.querySelector(".appmain").scrollHeight > 1000;
  });
});

await t("切走再切回，滚动位置保留", async () => {
  await goto("ecommerce");
  await page.evaluate(() => { document.querySelector(".pv:not([hidden])").scrollTop = 1234; });
  await goto("marketing");
  await goto("ecommerce");
  return page.evaluate(() => document.querySelector(".pv:not([hidden])").scrollTop === 1234);
});

await t("深链 #p=ecommerce 直接打开对应页", async () => {
  await page.goto("file://" + FILE + "#p=ecommerce", { waitUntil: "networkidle0" });
  await new Promise(r => setTimeout(r, 400));
  return page.evaluate(() => [...document.querySelectorAll(".pv")].filter(p => p.offsetParent !== null)
    .map(p => p.dataset.page).join() === "ecommerce");
});

await t("未知 hash 不改变当前 tab（交给浏览器做页内跳转）", async () => {
  // 此时停在 ecommerce。application 侧栏等处有 13 个形如 #components 的页内死锚点，
  // 它们绝不能被误当成 tab slug。
  await page.evaluate(() => { location.hash = "#pricing"; });
  await new Promise(r => setTimeout(r, 200));
  return page.evaluate(() => [...document.querySelectorAll(".pv")].filter(p => p.offsetParent !== null)
    .map(p => p.dataset.page).join() === "ecommerce");
});

await t(`未知 hash 冷启动回落到默认页（${DEFAULT}）`, async () => {
  // 特意用 #components：它既是 application 侧栏的页内死锚点，也与某个 slug 同名，
  // 路由必须只认 #p= 而不能被它骗过去。
  await page.goto("about:blank");
  await page.goto("file://" + FILE + "#components", { waitUntil: "networkidle0" });
  await new Promise(r => setTimeout(r, 400));
  return page.evaluate(d => [...document.querySelectorAll(".pv")].filter(p => p.offsetParent !== null)
    .map(p => p.dataset.page).join() === d, DEFAULT);
});

await t("点 tab 会把 hash 写成 #p=xxx 且不新增历史条目", async () => {
  const before = await page.evaluate(() => history.length);
  await goto("marketing");
  return page.evaluate(h => location.hash === "#p=marketing" && history.length === h, before);
});

await t("跨页链接：marketing 里指向 application 的链接能跳过去", async () => {
  await goto("marketing");
  return page.evaluate(() => {
    const a = document.querySelector('.pv[data-page="marketing"] a[href="#p=application"]');
    if (!a) return false;
    a.click();
    return [...document.querySelectorAll(".pv")].filter(p => p.offsetParent !== null)
      .map(p => p.dataset.page).join() === "application";
  });
});

await t("方向键在 tab 之间移动", async () => {
  await goto("marketing");
  await page.evaluate(() => document.querySelector('.pv-switch [data-goto="marketing"]').focus());
  await page.keyboard.press("ArrowRight");
  return page.evaluate(() => document.activeElement.dataset.goto === "application"
    && !document.querySelector('.pv[data-page="application"]').hidden);
});

// ================================================================= Phase 3
console.log("\n[Phase 3] 每页结构");
const count = (sel) => page.evaluate(s => document.querySelectorAll(s).length, sel);

await goto("components");
eq(await page.evaluate(() => [...document.querySelectorAll("section.ds__cat")].map(s => s.id)),
  ["foundations", "actions", "forms", "selection", "feedback", "navigation", "surfaces", "overlays"], "components：8 个 section 顺序正确");
eq(await count(".ds__block"), 37, "components：37 个组件块");
eq(await page.evaluate(() => [...document.querySelectorAll("section.ds__cat")].map(s => s.querySelectorAll(".ds__block").length)),
  [7, 7, 9, 3, 3, 3, 3, 2], "components：各 section 组件块数");

await goto("marketing");
eq(await count('.pv[data-page="marketing"] .faq__cat'), 4, "marketing：4 个 FAQ 分类");
eq(await count('.pv[data-page="marketing"] .faq__panel'), 4, "marketing：4 个 FAQ 面板（三个 hidden）");
eq(await count('.pv[data-page="marketing"] .faq__item'), 40, "marketing：40 条问答全部在 DOM 里");
eq(await page.evaluate(() => document.querySelectorAll('.pv[data-page="marketing"] .faq__panel:not([hidden])').length), 1,
  "marketing：同时只显示一个面板");
eq(await count('.pv[data-page="marketing"] img'), 11, "marketing：11 个 <img>");
await t("marketing：11 个 <img> 全部加载成功（data: URI）", () => page.evaluate(() =>
  [...document.querySelectorAll('.pv[data-page="marketing"] img')].every(i => i.naturalWidth > 0 && i.src.startsWith("data:"))));
eq(await count('.pv[data-page="marketing"] .offer .segmented__btn'), 3, "marketing：3 档计费周期");
eq(await count('.pv[data-page="marketing"] .fshow__seg-btn'), 4, "marketing：4 个功能分段按钮");
await t("marketing：hero 纹理层保留但没有 background-image", () => page.evaluate(() => {
  const el = document.querySelector(".hero-pattern");
  const st = getComputedStyle(el);
  return el && st.backgroundImage === "none" && st.opacity === "0.35" && st.maskImage !== "none";
}));

await goto("application");
eq(await count('.pv[data-page="application"] .menu'), 21, "application：21 份下拉面板");
eq(await count('.pv[data-page="application"] .recharts-surface'), 8, "application：8 张 recharts 图");
eq(await count('.pv[data-page="application"] .dtable tbody tr'), 10, "application：表格 10 行");
eq(await count('.pv[data-page="application"] .appsidebar__children'), 2, "application：侧栏两个可折叠分组");
eq(await count('.pv[data-page="application"] .modal-scrim'), 1, "application：Revenue details 弹窗已还原");
eq(await count('.pv[data-page="application"] .appsidebar-scrim'), 1, "application：侧栏遮罩已还原");
await t("application：8 张图表都被容器撑开（不是 0×0）", () => page.evaluate(() =>
  [...document.querySelectorAll(".recharts-surface")].every(s => {
    const r = s.getBoundingClientRect();
    return r.width > 100 && r.height > 50;
  })));
await t("application：图表宽度跟随容器（不是快照里的固定 px）", () => page.evaluate(() =>
  [...document.querySelectorAll(".recharts-wrapper")].every(w => /100%/.test(w.style.width))));

await goto("ecommerce");
eq(await count('.pv[data-page="ecommerce"] .pcell'), 16, "ecommerce：16 个商品卡");
eq(await count('.pv[data-page="ecommerce"] .topcat-tile'), 16, "ecommerce：16 个品类瓷砖");
eq(await count('.pv[data-page="ecommerce"] .pdrawer-scrim'), 1, "ecommerce：筛选抽屉遮罩已还原");
eq(await count('.pv[data-page="ecommerce"] .menu'), 2, "ecommerce：语言 / Sort 两份下拉");
eq(await count('.pv[data-page="ecommerce"] .mobile-menu'), 1, "ecommerce：移动端菜单已还原");

await t("所有 fill=\"url(#x)\" 的目标都存在且是渐变/图案", () => page.evaluate(() => {
  const bad = [...document.querySelectorAll('[fill^="url(#"]')].filter(e => {
    const id = e.getAttribute("fill").slice(5, -1);
    const t = document.getElementById(id);
    return !t || !["linearGradient", "pattern", "radialGradient"].includes(t.tagName);
  });
  return bad.length === 0;
}));
await t("16 个商品图各自用不同的渐变 id（原页面有两处重复定义）", () => page.evaluate(() => {
  const ids = [...document.querySelectorAll('.pv[data-page="ecommerce"] .pcell__img [id]')].map(e => e.id);
  return ids.length > 0 && new Set(ids).size === ids.length;
}));

// ================================================================= Phase 4
console.log("\n[Phase 4] 交互矩阵");

// ---- components（沿用原来的 11 项） ----
await goto("components");
await t("components ① 导航初始高亮 Foundations", () => page.evaluate(() => {
  const on = [...document.querySelectorAll('.ds__nav-link[aria-current="true"]')];
  return on.length === 1 && on[0].textContent.trim() === "Foundations";
}));
await t("components ② tabs 切到 Billing 换文案", () => page.evaluate(() => {
  const tabs = [...document.querySelectorAll('.ds__tabs[aria-label="Filled tabs"] .ds__tab')];
  const billing = tabs.find(b => b.textContent.trim() === "Billing");
  billing.click();
  const panel = billing.parentNode.parentNode.querySelector(".ds__panel");
  return billing.getAttribute("aria-selected") === "true"
    && tabs.filter(b => b.getAttribute("aria-selected") === "true").length === 1
    && panel.textContent === "Invoices, payment methods and the current plan.";
}));
await t("components ③ 按钮组切到 Day", () => page.evaluate(() => {
  const segs = [...document.querySelectorAll('.ds__group[aria-label="Timeframe"] .ds__seg')];
  const day = segs.find(s => s.textContent.trim() === "Day");
  day.click();
  return day.getAttribute("aria-pressed") === "true"
    && segs.filter(s => s.getAttribute("aria-pressed") === "true").length === 1;
}));
await t("components ④ 手风琴单开 + 再点收起", () => page.evaluate(() => {
  const items = [...document.querySelectorAll(".ds__acc-item")];
  items[1].querySelector(".ds__acc-trigger").click();
  const openedRight = items[1].classList.contains("is-open")
    && !items[1].querySelector(".ds__acc-panel").hidden
    && items[1].querySelector(".ds__acc-panel").textContent.includes("split across payers")
    && !items[0].classList.contains("is-open")
    && items[0].querySelector(".ds__acc-panel").hidden;
  items[1].querySelector(".ds__acc-trigger").click();
  return openedRight && items.every(i => !i.classList.contains("is-open"));
}));
for (const [id, label, title] of [["ds-modal", "Open modal", "Remove this account?"], ["ds-drawer", "Open drawer", "Settings"]]) {
  await t(`components ⑤ ${label}：打开 + 三种关法`, async () => {
    const open = () => page.evaluate(l => [...document.querySelectorAll("button")].find(b => b.textContent.trim() === l).click(), label);
    const state = () => page.evaluate(i => {
      const p = document.getElementById(i);
      return { hidden: p.hidden, title: p.querySelector(".ds__overlay-title").textContent };
    }, id);
    await open();
    const s1 = await state();
    if (s1.hidden || s1.title !== title) return false;
    await page.keyboard.press("Escape");
    if (!(await state()).hidden) return false;
    await open();
    await page.evaluate(i => document.querySelector(`.ds__scrim[data-close="${i}"]`).click(), id);
    if (!(await state()).hidden) return false;
    await open();
    await page.evaluate(i => document.querySelector(`#${i} .ds__x`).click(), id);
    return (await state()).hidden;
  });
}
await t("components ⑥ Drawer 内容正确（Northwind + 开关默认开）", async () => {
  await page.evaluate(() => [...document.querySelectorAll("button")].find(b => b.textContent.trim() === "Open drawer").click());
  const r = await page.evaluate(() => ({
    v: document.getElementById("ds-drawer-name").value,
    on: document.querySelector("#ds-drawer .ds__toggle input").checked,
  }));
  await page.keyboard.press("Escape");
  return r.v === "Northwind" && r.on === true;
});
await t("components ⑦ stepper 加减且下限截断到 0", () => page.evaluate(() => {
  const st = document.querySelector(".ds__stepper");
  const inp = st.querySelector("input"), btns = st.querySelectorAll("button");
  const start = inp.value;
  btns[1].click(); btns[1].click();
  const up = inp.value;
  for (let i = 0; i < 9; i++) btns[0].click();
  return start === "3" && up === "5" && inp.value === "0";
}));
await t("components ⑧ range 三处联动", () => page.evaluate(() => {
  const r = document.querySelector(".ds__range");
  r.value = 75; r.dispatchEvent(new Event("input", { bubbles: true }));
  return r.value === "75" && document.getElementById("ds-range-out").textContent === "75"
    && r.style.getPropertyValue("--fill") === "75%";
}));
await t("components ⑨ 下拉菜单：开 → 3 项 + 1 分隔线 → 点外面关", () => page.evaluate(() => {
  const dd = document.querySelector(".ds__dd");
  const trigger = dd.querySelector('button[aria-haspopup="menu"]');
  trigger.click();
  const items = [...dd.querySelectorAll(".ds__menu-item")].map(i => i.textContent.trim());
  const opened = trigger.getAttribute("aria-expanded") === "true" && !dd.querySelector(".ds__dd-panel").hidden;
  const right = items.length === 3 && items[0] === "Profile" && items[2] === "Sign out"
    && dd.querySelectorAll(".ds__menu-divider").length === 1;
  dd.querySelector(".ds__dd-scrim").click();
  return opened && right && dd.querySelector(".ds__dd-panel").hidden;
}));
await t("components ⑩ alert 逐条关闭 → 复位按钮 → 全部恢复", () => page.evaluate(() => {
  const stage = document.querySelector(".ds__alert").parentNode;
  const alerts = [...stage.querySelectorAll(".ds__alert")];
  const restore = stage.querySelector("[data-alerts-restore]");
  if (alerts.length !== 4 || !restore.hidden) return false;
  alerts.forEach(a => a.querySelector('button[aria-label^="Dismiss "]').click());
  const allGone = alerts.every(a => a.hidden) && !restore.hidden;
  restore.click();
  return allGone && alerts.every(a => !a.hidden) && restore.hidden;
}));
await t("components ⑪ 滚动后导航高亮跟随（观察根是 .pv）", async () => {
  await page.evaluate(() => document.getElementById("forms").scrollIntoView());
  await new Promise(r => setTimeout(r, 600));
  return page.evaluate(() => {
    const on = document.querySelector('.ds__nav-link[aria-current="true"]');
    return on && on.textContent.trim() === "Forms";
  });
});

// ---- 共享下拉的定位算法 ----
await goto("application");
await t("Dropdown 定位 ① 面板顶边 = 触发器底边 + 8", () => page.evaluate(() => {
  const trig = document.querySelector('[aria-label="Account menu"]');
  trig.click();
  const m = trig.nextElementSibling;
  return Math.round(m.getBoundingClientRect().top) === Math.round(trig.getBoundingClientRect().bottom + 8);
}));
await t("Dropdown 定位 ② align=end 右对齐且不越界", () => page.evaluate(() => {
  const trig = document.querySelector('[aria-label="Account menu"]');
  const m = trig.nextElementSibling, r = m.getBoundingClientRect();
  const okAlign = Math.round(r.right) === Math.round(trig.getBoundingClientRect().right);
  document.body.click();
  return okAlign && r.right <= window.innerWidth - 8 + 0.5 && r.left >= 7.5;
}));
await t("Dropdown 定位 ③ 贴近视口底部时翻到触发器上方", () => page.evaluate(() => {
  const trig = [...document.querySelectorAll('[aria-label^="Actions for"]')].pop();
  trig.scrollIntoView({ block: "end" });
  trig.click();
  const m = trig.nextElementSibling, r = m.getBoundingClientRect(), tr = trig.getBoundingClientRect();
  const flipped = Math.round(r.bottom) === Math.round(tr.top - 8);
  const belowFits = tr.bottom + 8 + r.height <= window.innerHeight - 8;
  document.body.click();
  return flipped || belowFits;      // 只在装不下时才翻
}));
await t("Dropdown 定位 ④ 滚动时跟随（滚动源是 .pv/.appmain，需捕获阶段）", async () => {
  await page.evaluate(() => {
    document.querySelector(".appmain").scrollTop = 0;
    document.querySelector('[aria-label="Widget options"]').click();
  });
  const before = await page.evaluate(() => document.querySelector(".menu:not([hidden])").getBoundingClientRect().top);
  await page.evaluate(() => { document.querySelector(".appmain").scrollTop += 200; });
  await new Promise(r => setTimeout(r, 120));
  const after = await page.evaluate(() => {
    const v = document.querySelector(".menu:not([hidden])").getBoundingClientRect().top;
    document.body.click();
    return v;
  });
  return Math.abs(before - after - 200) < 3;
});

// ---- application ----
await t("application ① 账户菜单四项 + 一条分隔线", () => page.evaluate(() => {
  const trig = document.querySelector('[aria-label="Account menu"]');
  trig.click();
  const m = trig.nextElementSibling;
  const items = [...m.querySelectorAll(".menu__item")].map(i => i.textContent.trim());
  const r = items.join("|") === "Profile|Settings|Billing|Sign out"
    && m.querySelectorAll(".menu__divider").length === 1
    && m.querySelector(".menu__item--danger").textContent.trim() === "Sign out"
    && m.style.width === "244px";
  document.body.click();
  return r;
}));
await t("application ② 行操作菜单三项（10 行同构）", () => page.evaluate(() => {
  const trigs = [...document.querySelectorAll('[aria-label^="Actions for"]')];
  if (trigs.length !== 10) return false;
  return trigs.every(tr => {
    const items = [...tr.nextElementSibling.querySelectorAll(".menu__item")].map(i => i.textContent.trim());
    return items.join("|") === "Archive staff|Edit staff|Delete staff";
  });
}));
await t("application ③ Actions / 每页行数 / 时间范围三份文案正确", () => page.evaluate(() => {
  const byText = (s) => [...document.querySelectorAll('.pv[data-page="application"] [aria-haspopup="menu"]')]
    .find(b => b.textContent.trim() === s);
  const list = (b) => [...b.nextElementSibling.querySelectorAll(".menu__label")].map(i => i.textContent).join("|");
  return list(byText("Actions")) === "Export selection|Send message|Archive selected"
    && list(byText("10")) === "10|25|50|100"
    && list(byText("Last 12 months")) === "Last 7 days|Last 30 days|Last 90 days|Custom period";
}));
await t("application ④ Filters 菜单勾选后不关闭（closeOnSelect:false）", () => page.evaluate(() => {
  const trig = [...document.querySelectorAll('[aria-haspopup="menu"]')].find(b => b.textContent.trim() === "Filters");
  trig.click();
  const m = trig.nextElementSibling;
  const cb = m.querySelector('input[type="checkbox"]');
  cb.click();
  const r = !m.hidden && cb.checked && m.querySelectorAll(".menu__item--check").length === 5;
  document.body.click();
  return r && m.hidden;
}));
await t("application ⑤ 表格选择：逐行 → .is-picked + 计数条", () => page.evaluate(() => {
  const rows = [...document.querySelectorAll(".dtable tbody tr")];
  rows[0].querySelector(".dtable__pick input").click();
  rows[2].querySelector(".dtable__pick input").click();
  const tag = document.querySelector(".dtx__selected");
  return document.querySelectorAll(".dtable tbody tr.is-picked").length === 2
    && !tag.hidden && tag.textContent.trim() === "2 selected";
}));
await t("application ⑥ 表格全选 / 全不选", () => page.evaluate(() => {
  const all = document.querySelector(".dtable thead .dtable__pick input");
  all.click();
  const on = document.querySelectorAll(".dtable tbody tr.is-picked").length === 10
    && document.querySelector(".dtx__selected").textContent.trim() === "10 selected";
  all.click();
  return on && document.querySelectorAll(".dtable tbody tr.is-picked").length === 0
    && document.querySelector(".dtx__selected").hidden;
}));
await t("application ⑦ promote 开关纯 CSS 驱动（初始 5 开）", () => page.evaluate(() =>
  [...document.querySelectorAll(".dtable tbody .toggle input")].filter(i => i.checked).length === 5));
await t("application ⑧ Revenue details 弹窗：打开 / 六行数据 / 三种关法", async () => {
  const open = () => page.evaluate(() =>
    [...document.querySelectorAll(".ovw__actions .btn")].find(b => /Details/.test(b.textContent)).click());
  const shown = () => page.evaluate(() => !document.querySelector(".modal-scrim").hidden);
  await open();
  const info = await page.evaluate(() => {
    const s = document.querySelector(".modal-scrim");
    return {
      title: s.querySelector(".modal__title").textContent,
      rows: [...s.querySelectorAll("tbody tr")].map(r => [...r.querySelectorAll("td")].map(c => c.textContent.trim()).join(" ")),
      top: Math.round(s.getBoundingClientRect().top),
    };
  });
  if (!(await shown())) return false;
  if (info.title !== "Revenue details" || info.rows.length !== 6) return false;
  if (info.rows[0] !== "Dec $171k $138k +24%") return false;
  if (info.top !== 0) return false;                    // 浮层回到原本的整视口定位
  await page.keyboard.press("Escape");
  if (await shown()) return false;
  await open();
  await page.evaluate(() => document.querySelector(".modal__close").click());
  if (await shown()) return false;
  await open();
  await page.evaluate(() => document.querySelector(".modal-scrim").click());
  return !(await shown());
});
await t("application ⑧b 弹窗遮罩之上切换器仍是命中目标（z 500 > 300）", async () => {
  await page.evaluate(() =>
    [...document.querySelectorAll(".ovw__actions .btn")].find(b => /Details/.test(b.textContent)).click());
  const hit = await page.evaluate(() => {
    const p = document.querySelector(".pv-switch").getBoundingClientRect();
    const el = document.elementFromPoint(p.left + p.width / 2, p.top + p.height / 2);
    return !!(el && el.closest(".pv-switch"));
  });
  await page.keyboard.press("Escape");
  return hit;
});
await t("application ⑨ 侧栏两个分组都能开合", () => page.evaluate(() => {
  const btns = [...document.querySelectorAll(".appsidebar__item[aria-expanded]")];
  if (btns.length !== 2) return false;
  return btns.every(b => {
    const kids = b.nextElementSibling, was = b.getAttribute("aria-expanded") === "true";
    b.click();
    const flipped = b.getAttribute("aria-expanded") === String(!was) && kids.hidden === was
      && b.querySelector(".chev").classList.contains("is-open") === !was;
    b.click();
    return flipped && kids.hidden === !was;
  });
}));
await t("application ⑩ 窄屏侧栏：汉堡开、遮罩关，且都让出 bar 高", async () => {
  await page.setViewport({ width: 900, height: 1000, deviceScaleFactor: 1 });
  await new Promise(r => setTimeout(r, 300));
  const r = await page.evaluate(() => {
    document.querySelector('[aria-label="Open sidebar"]').click();
    const sb = document.querySelector(".appsidebar"), sc = document.querySelector(".appsidebar-scrim");
    const o = { open: sb.classList.contains("is-open"), scrim: !sc.hidden, sbTop: Math.round(sb.getBoundingClientRect().top), scTop: Math.round(sc.getBoundingClientRect().top) };
    sc.click();
    return { ...o, closed: !sb.classList.contains("is-open") };
  });
  await page.setViewport({ width: 1440, height: 1000, deviceScaleFactor: 1 });
  await new Promise(r => setTimeout(r, 300));
  return r.open && r.scrim && r.closed && r.sbTop === 0 && r.scTop === 0;
});

// ---- ecommerce ----
await goto("ecommerce");
await t("ecommerce ① 语言下拉四项 + 选中回写触发器标签", () => page.evaluate(() => {
  const trig = document.querySelector(".lang-trigger");
  trig.click();
  const m = trig.nextElementSibling;
  const items = [...m.querySelectorAll(".menu__label")].map(i => i.textContent);
  if (items.join("|") !== "English (US)|Deutsch|Français|Español") return false;
  m.querySelectorAll(".menu__item")[1].click();
  const r = trig.textContent.trim() === "Deutsch" && m.hidden
    && m.querySelectorAll('[aria-checked="true"]').length === 1
    && m.querySelectorAll(".menu__item--active")[0].textContent.trim() === "Deutsch";
  m.querySelectorAll(".menu__item")[0].click();     // 复原
  return r;
}));
await t("ecommerce ② Sort 下拉五项 + 右对齐 + 点外面关", () => page.evaluate(() => {
  const trig = document.querySelector(".psort");
  trig.click();
  const m = trig.nextElementSibling;
  const r = [...m.querySelectorAll(".menu__label")].map(i => i.textContent).join("|")
    === "Most popular|Price: low to high|Price: high to low|Top rated|Newest"
    && Math.round(m.getBoundingClientRect().right) === Math.round(trig.getBoundingClientRect().right)
    && m.style.width === "160px";
  document.body.click();
  return r && m.hidden;
}));
await t("ecommerce ③ 筛选抽屉：开 / 遮罩关 / ✕ 关，且让出 bar 高", () => page.evaluate(() => {
  const open = document.querySelector('[data-pdrawer="open"]');
  const d = document.querySelector(".pdrawer"), s = document.querySelector(".pdrawer-scrim");
  open.click();
  const o1 = d.classList.contains("is-open") && !s.hidden
    && Math.round(d.getBoundingClientRect().top) === 0 && Math.round(s.getBoundingClientRect().top) === 0
    && open.getAttribute("aria-expanded") === "true";
  s.click();
  const o2 = !d.classList.contains("is-open") && s.hidden;
  open.click();
  d.querySelector('.iconbtn[data-pdrawer="close"]').click();
  return o1 && o2 && !d.classList.contains("is-open");
}));
await t("ecommerce ④ 价格滑块与数字输入双向联动 + --fill", () => page.evaluate(() => {
  document.querySelector('[data-pdrawer="open"]').click();
  const rg = document.querySelector(".pdrawer input[type=range].range");
  const to = document.querySelector('input[aria-label="Price to"]');
  rg.value = 1000; rg.dispatchEvent(new Event("input", { bubbles: true }));
  const a = to.value === "1000" && rg.style.getPropertyValue("--fill") === "25%";
  to.value = 2000; to.dispatchEvent(new Event("input", { bubbles: true }));
  const b = rg.value === "2000" && rg.style.getPropertyValue("--fill") === "50%";
  document.querySelector('.pdrawer .iconbtn[data-pdrawer="close"]').click();
  return a && b;
}));
await t("ecommerce ⑤ Condition 分段控件三选一", () => page.evaluate(() => {
  document.querySelector('[data-pdrawer="open"]').click();
  const segs = [...document.querySelectorAll('.pdrawer .segmented[aria-label="Condition"] .segmented__btn')];
  segs[2].click();
  const r = segs.filter(s => s.classList.contains("is-active")).length === 1
    && segs[2].getAttribute("aria-selected") === "true";
  segs[0].click();
  document.querySelector('.pdrawer .iconbtn[data-pdrawer="close"]').click();
  return r;
}));
await t("ecommerce ⑥ 窄屏汉堡菜单六项", async () => {
  await page.setViewport({ width: 768, height: 1000, deviceScaleFactor: 1 });
  await new Promise(r => setTimeout(r, 300));
  const r = await page.evaluate(() => {
    const mt = document.querySelector('.pv[data-page="ecommerce"] .menu-toggle');
    mt.click();
    const nav = document.querySelector('.pv[data-page="ecommerce"] .mobile-menu');
    const o = !nav.hidden && [...nav.querySelectorAll("a")].map(a => a.textContent).join("|")
      === "Home|Marketplace|Features|Products|Team|Contact";
    mt.click();
    return o && nav.hidden;
  });
  await page.setViewport({ width: 1440, height: 1000, deviceScaleFactor: 1 });
  await new Promise(r => setTimeout(r, 300));
  return r;
});

// ---- marketing ----
await goto("marketing");
await t("marketing ① FAQ 分类切换：面板与高亮同步", () => page.evaluate(() => {
  const cats = [...document.querySelectorAll('.pv[data-page="marketing"] .faq__cat')];
  const panels = [...document.querySelectorAll('.pv[data-page="marketing"] .faq__panel')];
  return cats.every((c, i) => {
    c.click();
    return c.classList.contains("is-active")
      && cats.filter(x => x.classList.contains("is-active")).length === 1
      && panels.filter(p => !p.hidden).length === 1 && !panels[i].hidden
      && panels[i].querySelectorAll(".faq__item").length === 10;
  });
}));
await t("marketing ② 四个分类的首题文案正确", () => page.evaluate(() => {
  const cats = [...document.querySelectorAll('.pv[data-page="marketing"] .faq__cat')].map(c => c.textContent.trim());
  const firsts = [...document.querySelectorAll('.pv[data-page="marketing"] .faq__panel')]
    .map(p => p.querySelector(".faq__q-text").textContent);
  return cats.join("|") === "Getting started|Billing & plans|Families & staff|Security & privacy"
    && firsts[0] === "How long does it take to set up Charm?"
    && firsts[3] === "Is our data secure?";
}));
await t("marketing ③ FAQ 手风琴单开 + 再点收起", () => page.evaluate(() => {
  document.querySelectorAll('.pv[data-page="marketing"] .faq__cat')[0].click();
  const items = [...document.querySelectorAll('.pv[data-page="marketing"] .faq__panel:not([hidden]) .faq__item')];
  items[3].querySelector(".faq__q").click();
  const one = items.filter(i => i.classList.contains("is-open")).length === 1 && items[3].classList.contains("is-open")
    && items[3].querySelector(".faq__q").getAttribute("aria-expanded") === "true";
  items[3].querySelector(".faq__q").click();
  return one && items.every(i => !i.classList.contains("is-open"));
}));
await t("marketing ④ 三档计费周期切换价格与小字", () => page.evaluate(() => {
  const segs = [...document.querySelectorAll('.pv[data-page="marketing"] .offer .segmented__btn')];
  const want = [["$149", "Billed monthly. Cancel anytime."],
  ["$119", "Billed $1,428 yearly, a 20% saving."],
  ["$99", "Billed $2,376 up front, a 34% saving."]];
  return segs.every((s, i) => {
    s.click();
    return document.querySelector(".offer__price strong").textContent === want[i][0]
      && document.querySelector(".offer__fine").textContent === want[i][1]
      && segs.filter(x => x.classList.contains("is-active")).length === 1;
  });
}));
await t("marketing ⑤ 功能分段控件四选一", () => page.evaluate(() => {
  const segs = [...document.querySelectorAll(".fshow__seg-btn")];
  segs[2].click();
  return segs.filter(s => s.classList.contains("is-active")).length === 1
    && segs[2].getAttribute("aria-selected") === "true";
}));
await t("marketing ⑥ 窄屏汉堡菜单四项", async () => {
  await page.setViewport({ width: 768, height: 1000, deviceScaleFactor: 1 });
  await new Promise(r => setTimeout(r, 300));
  const r = await page.evaluate(() => {
    const mt = document.querySelector('.pv[data-page="marketing"] .menu-toggle');
    mt.click();
    const nav = document.querySelector('.pv[data-page="marketing"] .mobile-menu');
    const o = !nav.hidden && [...nav.querySelectorAll("a")].map(a => a.textContent).join("|") === "Home|Products|Blog|Contact";
    mt.click();
    return o && nav.hidden;
  });
  await page.setViewport({ width: 1440, height: 1000, deviceScaleFactor: 1 });
  await new Promise(r => setTimeout(r, 300));
  return r;
});

// ================================================================= Phase 5
console.log("\n[Phase 5] 像素回归（合并版逐页 vs 单页版）");
if (!DO_VISUAL) {
  console.log("  （--no-visual，已跳过）");
} else {
  const H = 900, W = 1440;
  const missing = SLUGS.filter(s => !fs.existsSync(singlePath(s)));
  if (missing.length) {
    ok(false, "单页版产物齐全", `缺 ${missing.join(", ")}；先跑 python3 _build_charm.py --all`);
  } else {
    // 切换器是 position:fixed，隐藏它不影响任何布局，因此合并版与单页版的
    // 视口、clip 完全相同，可以要求逐像素相等——不需要任何掩码或容差。
    // （ecommerce 那 2 处 id 修复、缺失的 hero 纹理在两版里本来就一致。）
    const shoot = async (url, hidePill) => {
      const pg = await browser.newPage();
      await pg.setViewport({ width: W, height: H, deviceScaleFactor: 1 });
      await pg.goto(url, { waitUntil: "networkidle0" });
      if (hidePill) await pg.evaluate(() => { document.querySelector(".pv-switch").style.display = "none"; });
      await new Promise(r => setTimeout(r, 700));
      const buf = await pg.screenshot({ clip: { x: 0, y: 0, width: W, height: H }, encoding: "base64" });
      await pg.close();
      return buf;
    };
    // 在浏览器里做逐像素比对，免掉 pixelmatch/pngjs 依赖
    const differ = await browser.newPage();
    const diff = (a, b) => differ.evaluate(async (a, b) => {
      const load = (d) => new Promise(res => { const i = new Image(); i.onload = () => res(i); i.src = "data:image/png;base64," + d; });
      const [ia, ib] = await Promise.all([load(a), load(b)]);
      if (ia.width !== ib.width || ia.height !== ib.height) return { size: [ia.width, ia.height, ib.width, ib.height] };
      const px = (im) => { const c = new OffscreenCanvas(im.width, im.height); const x = c.getContext("2d"); x.drawImage(im, 0, 0); return x.getImageData(0, 0, im.width, im.height).data; };
      const [pa, pb] = [px(ia), px(ib)];
      let n = 0, max = 0;
      for (let i = 0; i < pa.length; i += 4) {
        const d = Math.abs(pa[i] - pb[i]) + Math.abs(pa[i + 1] - pb[i + 1]) + Math.abs(pa[i + 2] - pb[i + 2]);
        if (d > 6) { n++; if (d > max) max = d; }
      }
      return { diff: n, max, total: pa.length / 4 };
    }, a, b);

    for (const slug of SLUGS) {
      const merged = await shoot("file://" + FILE + "#p=" + slug, true);
      const single = await shoot("file://" + singlePath(slug), false);
      const r = await diff(merged, single);
      if (r.size) { ok(false, `${slug} 首屏与单页版逐像素一致`, `尺寸不同 ${r.size}`); continue; }
      const good = r.diff === 0;
      ok(good, `${slug} 首屏与单页版逐像素一致`, `${r.diff}/${r.total} 像素不同，最大色差 ${r.max}`);
      if (!good) {
        fs.writeFileSync(path.join(HERE, `_diff_${slug}_merged.png`), Buffer.from(merged, "base64"));
        fs.writeFileSync(path.join(HERE, `_diff_${slug}_single.png`), Buffer.from(single, "base64"));
        console.log(`      已导出 _diff_${slug}_{merged,single}.png 供人工比对`);
      }
    }
    await differ.close();
  }
}

// ================================================================= 截图
console.log("\n[Phase 6] 截图");
for (const slug of SLUGS) {
  // 同文档只改 hash 不会重载，前面用例留下的滚动位置会残留；
  // 逐个滚动容器归零，截图才是「这一页打开时长什么样」。
  await page.goto("about:blank");
  await page.goto("file://" + FILE + "#p=" + slug, { waitUntil: "networkidle0" });
  await page.evaluate(() => document.querySelectorAll(".pv:not([hidden]), .appmain, .sbscroll")
    .forEach(e => { e.scrollTop = 0; }));
  await new Promise(r => setTimeout(r, 500));
  await page.setViewport({ width: 1440, height: 1000, deviceScaleFactor: 2 });
  await new Promise(r => setTimeout(r, 400));
  await page.screenshot({ path: path.join(HERE, `_shot_${slug}.png`) });
  console.log(`  已保存 _shot_${slug}.png`);
  await page.setViewport({ width: 1440, height: 1000, deviceScaleFactor: 1 });
}

await browser.close();
console.log(`\n结果：${pass} 通过 / ${fail} 失败`);
process.exit(fail ? 1 : 0);
