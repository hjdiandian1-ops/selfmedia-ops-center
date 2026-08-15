// 自媒体运营中心 · 前端逻辑（原生 JS + fetch，零构建）
"use strict";

const $ = (sel) => document.querySelector(sel);
const $$ = (sel) => Array.from(document.querySelectorAll(sel));
const toastEl = $("#toast");
let toastTimer = null;
let artifactState = { jobId: "", files: [], tab: "xhs", imgIdx: 0 };

const STATE_LABELS = {
  topic: "选题", materials: "素材", draft: "成稿", visual: "视觉",
  review: "质检", archive: "归档", publish: "发布", recycle: "回收",
};
const STATE_ORDER = ["topic", "materials", "draft", "visual", "review", "archive", "publish", "recycle"];
const STATE_AGENTS = {
  topic: "总编", materials: "资深采编", draft: "三位主编", visual: "美术总监",
  review: "资深校对", archive: "归档发布员", publish: "归档发布员", recycle: "归档发布员",
};

function toast(msg, ok = true) {
  toastEl.textContent = msg;
  toastEl.className = "toast " + (ok ? "ok" : "err");
  clearTimeout(toastTimer);
  toastTimer = setTimeout(() => toastEl.classList.add("hidden"), 4000);
}

async function runWithSpin(btn, fn) {
  if (!btn) return fn();
  btn.classList.add("spinning");
  btn.disabled = true;
  try {
    await fn();
  } finally {
    btn.classList.remove("spinning");
    btn.disabled = false;
  }
}
window.runWithSpin = runWithSpin;

async function api(path, options) {
  const res = await fetch(path, options);
  if (!res.ok) {
    let detail = res.statusText;
    try { detail = (await res.json()).detail || detail; } catch (e) { /* ignore */ }
    throw new Error(typeof detail === "string" ? detail : JSON.stringify(detail));
  }
  return res.json();
}

function esc(s) {
  return String(s == null ? "" : s).replace(/[&<>"']/g, (c) => (
    { "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]
  ));
}

function mdInline(s) {
  s = esc(s);
  s = s.replace(/`([^`]+)`/g, "<code>$1</code>");
  s = s.replace(/\*\*([^*]+)\*\*/g, "<strong>$1</strong>");
  s = s.replace(/(^|[^*])\*([^*]+)\*(?!\*)/g, "$1<em>$2</em>");
  s = s.replace(/\[([^\]]+)\]\((https?:\/\/[^)\s]+)\)/g,
    '<a href="$2" target="_blank" rel="noopener">$1</a>');
  return s;
}

function renderMarkdown(md) {
  if (!md) return "";
  const lines = String(md).split(/\r?\n/);
  let html = "", inCode = false, codeBuf = [], inList = null;
  const closeList = () => {
    if (inList) { html += inList === "ul" ? "</ul>" : "</ol>"; inList = null; }
  };
  for (const raw of lines) {
    if (raw.trim().startsWith("```")) {
      if (inCode) {
        html += "<pre><code>" + esc(codeBuf.join("\n")) + "</code></pre>";
        codeBuf = [];
        inCode = false;
      } else {
        closeList();
        inCode = true;
      }
      continue;
    }
    if (inCode) { codeBuf.push(raw); continue; }
    const t = raw.trim();
    if (!t) { closeList(); continue; }
    const h = t.match(/^(#{1,6})\s+(.*)$/);
    if (h) {
      closeList();
      const lvl = h[1].length;
      html += `<h${lvl}>${mdInline(h[2])}</h${lvl}>`;
      continue;
    }
    const ul = t.match(/^[-*•]\s+(.*)$/);
    const ol = t.match(/^\d+[.、]\s+(.*)$/);
    if (ul || ol) {
      const type = ul ? "ul" : "ol";
      if (inList !== type) { closeList(); html += `<${type}>`; inList = type; }
      html += `<li>${mdInline((ul || ol)[1])}</li>`;
      continue;
    }
    closeList();
    html += `<p>${mdInline(t)}</p>`;
  }
  closeList();
  if (inCode) html += "<pre><code>" + esc(codeBuf.join("\n")) + "</code></pre>";
  return html;
}

function fmtNum(n) {
  n = Number(n || 0);
  if (n >= 10000) return (n / 10000).toFixed(1) + "w";
  return n.toLocaleString("zh-CN");
}

function pct(v) {
  v = Number(v || 0);
  return (v * 100).toFixed(1) + "%";
}

function stateBadge(state) {
  const cls = state === "recycle" || state === "publish" ? "success"
    : state === "reject" ? "error" : state === "review" || state === "archive" ? "primary" : "";
  return `<span class="badge ${cls}">${esc(STATE_LABELS[state] || state)}</span>`;
}

// ---------- 视图切换 ----------
const PAGE_META = {
  overview: ["运营中台", "生产 + 分析 + 学习闭环 · 平台数据一眼掌握"],
  topics: ["选题", "热点雷达 → 选题推荐 → 采纳建任务"],
  themes: ["爆款跟踪", "小红书/抖音/公众号每日爆款 · AI 拆解 + 周经验包反哺流水线"],
  flywheel: ["数据飞轮", "写稿发布 → 账户反馈 → 市场学习 → 总结经验 → 反哺 Agent"],
  pipeline: ["流水线", "Agent 角色职责与任务状态机"],
  outputs: ["成品库", "小红书 / 公众号 / 短视频成品预览"],
  data: ["数据", "自有数据统计 · 发布动作自动记录 + 人工回填"],
};

function switchView(name) {
  $$(".nav-item").forEach((b) => b.classList.toggle("active", b.dataset.view === name));
  $$(".view").forEach((v) => v.classList.remove("active"));
  $("#view-" + name).classList.add("active");
  $("#page-title").textContent = PAGE_META[name][0];
  $("#page-sub").textContent = PAGE_META[name][1];
  if (name === "overview") loadOverview();
  if (name === "topics") loadTopics();
  if (name === "themes") loadViral();
  if (name === "flywheel") loadFlywheel();
  if (name === "pipeline") loadPipeline();
  if (name === "outputs") loadOutputsView();
  if (name === "data") loadData();
}
window.switchView = switchView;

// ---------- 首启引导 ----------
function showOnboarding(force) {
  if (!force && localStorage.getItem("selfmedia_onboarded")) return;
  $("#onboard-modal").classList.remove("hidden");
}
window.showOnboarding = showOnboarding;

function dismissOnboarding() {
  localStorage.setItem("selfmedia_onboarded", "1");
  $("#onboard-modal").classList.add("hidden");
}
window.dismissOnboarding = dismissOnboarding;

function onboardGo(view) {
  if (view === "settings") openSettings();
  else switchView(view);
  dismissOnboarding();
}
window.onboardGo = onboardGo;

$$(".nav-item").forEach((btn) => btn.addEventListener("click", () => switchView(btn.dataset.view)));
$("#btn-refresh-topics").addEventListener("click", (e) => runWithSpin(e.currentTarget, loadTopics));

const TOPICS_STEPS = [
  "正在抓取今日热榜…",
  "正在抓取谷歌趋势…",
  "正在抓取 X / 推楼热点…",
  "正在清洗去重…",
  "正在计算时效/热度/质量评分…",
  "正在生成日选题与周选题…",
];

async function fetchHotTopics(btn) {
  const box = $("#topics-progress");
  const txt = $("#topics-progress-text");
  box.classList.remove("hidden");
  let i = 0;
  txt.textContent = TOPICS_STEPS[0];
  const timer = setInterval(() => {
    i = (i + 1) % TOPICS_STEPS.length;
    txt.textContent = TOPICS_STEPS[i];
    txt.classList.remove("tp-pulse");
    void txt.offsetWidth;
    txt.classList.add("tp-pulse");
  }, 1200);
  try {
    const d = await api("/api/pipeline/run", {
      method: "POST", headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ action: "topics" }),
    });
    clearInterval(timer);
    txt.classList.remove("tp-pulse");
    if (d.ok) {
      txt.textContent = "✅ 采集完成，已生成最新选题推荐";
      toast("热点采集完成，选题推荐已更新");
      loadTopics();
    } else {
      txt.textContent = "⚠️ 采集有阻塞项，见浏览器控制台";
      toast("热点采集有阻塞项", false);
      console.log((d.stdout || "") + (d.stderr || ""));
    }
  } catch (e) {
    clearInterval(timer);
    txt.classList.remove("tp-pulse");
    txt.textContent = "❌ 采集失败：" + e.message;
    toast("采集失败: " + e.message, false);
  } finally {
    if (btn) { btn.classList.remove("spinning"); btn.disabled = false; }
    setTimeout(() => box.classList.add("hidden"), 4000);
  }
}
window.fetchHotTopics = fetchHotTopics;

let prefData = { preferences: { platforms: {} }, niches: {} };

async function loadPrefData() {
  try {
    prefData = await api("/api/topics/preferences");
    loadPrefChip();
  } catch (e) { /* 偏好非必须，失败静默 */ }
}

function loadPrefChip() {
  const sel = (prefData.preferences && prefData.preferences.platforms) || {};
  const n = Object.values(sel).reduce((a, b) => a + (b ? b.length : 0), 0);
  const chip = $("#pref-chip");
  if (chip) chip.textContent = n ? `偏好：${n} 个赛道` : "";
}

function openPrefModal() {
  renderPrefNiches();
  $("#pref-modal").classList.remove("hidden");
}
window.openPrefModal = openPrefModal;

function closePrefModal() {
  $("#pref-modal").classList.add("hidden");
}
window.closePrefModal = closePrefModal;

function renderPrefNiches() {
  const pl = $("#pref-platform").value;
  const names = Object.keys((prefData.niches || {})[pl] || {});
  const saved = ((prefData.preferences || {}).platforms || {})[pl] || [];
  $("#pref-niches").innerHTML = names.length
    ? names.map((n) => `<label class="field-label"><input type="checkbox" value="${esc(n)}" ${saved.includes(n) ? "checked" : ""}> ${esc(n)}</label>`).join("")
    : '<span class="muted">该平台暂无赛道词库</span>';
}
window.renderPrefNiches = renderPrefNiches;

async function savePrefs() {
  const pl = $("#pref-platform").value;
  const names = Array.from(document.querySelectorAll("#pref-niches input:checked")).map((i) => i.value);
  const platforms = JSON.parse(JSON.stringify((prefData.preferences || {}).platforms || {}));
  platforms[pl] = names;
  try {
    const d = await api("/api/topics/preferences", {
      method: "POST", headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ platforms }),
    });
    prefData.preferences = d.preferences;
    loadPrefChip();
    toast("偏好已保存，下次热点采集按偏好过滤");
    closePrefModal();
  } catch (e) {
    toast("保存偏好失败: " + e.message, false);
  }
}
window.savePrefs = savePrefs;

async function clearPrefs() {
  try {
    const d = await api("/api/topics/preferences", {
      method: "POST", headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ platforms: {} }),
    });
    prefData.preferences = d.preferences;
    loadPrefChip();
    toast("已清除偏好，恢复默认模式");
    closePrefModal();
  } catch (e) {
    toast("清除失败: " + e.message, false);
  }
}
window.clearPrefs = clearPrefs;

// ---------- 概览 ----------
let ovCache = null;
let ovStatsCache = null;
let currentOvTab = "overview";
let lastStatsTrend = [];
let dashPeriod = "day";
let panelEditMode = false;
const ovSeriesSel = { overview: "reads", 小红书: "reads", 公众号: "reads", 短视频: "reads" };

async function loadOverview() {
  try {
    const plats = enabledPlatforms();
    const q = "platforms=" + encodeURIComponent(plats.join(","));
    const [stats, dash] = await Promise.all([
      api("/api/stats?" + q),
      api("/api/dashboard?period=" + dashPeriod + "&" + q),
    ]);
    ovCache = dash;
    ovStatsCache = stats;
    lastStatsTrend = stats.trend || [];
    $$("#ov-tabs .tab").forEach((b) => {
      const hidden = b.dataset.ov !== "overview" && !plats.includes(b.dataset.ov);
      b.classList.toggle("hidden", hidden);
    });
    if (currentOvTab !== "overview" && !plats.includes(currentOvTab)) {
      currentOvTab = "overview";
      $$("#ov-tabs .tab").forEach((b) => b.classList.toggle("active", b.dataset.ov === "overview"));
    }
    $("#topbar-meta").textContent = "更新于 " + (dash.generated_at || stats.generated_at || "");
    renderGlobalKpis(stats, dash);
    renderOverviewPane(stats, dash);
    if (currentOvTab !== "overview") renderPlatformPane(currentOvTab);
  } catch (e) {
    toast("概览加载失败: " + e.message, false);
  }
}

function enabledPlatforms() {
  try {
    const v = JSON.parse(localStorage.getItem("selfmedia_platforms") || "null");
    if (Array.isArray(v) && v.length) {
      const all = ["小红书", "公众号", "短视频"];
      const ok = v.filter((p) => all.includes(p));
      if (ok.length) return ok;
    }
  } catch (e) { /* ignore */ }
  return ["小红书", "公众号", "短视频"];
}

function setDashPeriod(p) {
  dashPeriod = p;
  $$("#period-tabs .tab").forEach((b) => b.classList.toggle("active", b.dataset.period === p));
  loadOverview();
}
window.setDashPeriod = setDashPeriod;

function openPlatformPrefs() {
  const plats = enabledPlatforms();
  $("#pfp-xhs").checked = plats.includes("小红书");
  $("#pfp-gzh").checked = plats.includes("公众号");
  $("#pfp-video").checked = plats.includes("短视频");
  $("#platform-prefs-modal").classList.remove("hidden");
}
window.openPlatformPrefs = openPlatformPrefs;

function closePlatformPrefs() {
  $("#platform-prefs-modal").classList.add("hidden");
}
window.closePlatformPrefs = closePlatformPrefs;

function savePlatformPrefs() {
  const plats = [];
  if ($("#pfp-xhs").checked) plats.push("小红书");
  if ($("#pfp-gzh").checked) plats.push("公众号");
  if ($("#pfp-video").checked) plats.push("短视频");
  localStorage.setItem("selfmedia_platforms", JSON.stringify(plats));
  closePlatformPrefs();
  toast("平台设置已保存" + (plats.length ? "" : "，至少保留一个平台更合理"));
  loadOverview();
}
window.savePlatformPrefs = savePlatformPrefs;

function renderGlobalKpis(stats, dash) {
  const isPlatform = currentOvTab !== "overview";
  let kpis;
  if (isPlatform) {
    const t = ((dash.platforms || {})[currentOvTab] || {}).totals || {};
    kpis = [
      ["任务总数", t.publish_count ?? 0],
      ["已发布任务", t.backfill_count ?? 0],
      ["爆款数", t.hits ?? 0],
      ["总阅读", fmtNum(t.total_reads ?? 0)],
      ["平均互动率", t.engagement == null ? "—" : (t.engagement * 100).toFixed(2) + "%"],
      ["粉丝数", t.followers ?? "—"],
    ];
  } else {
    kpis = [
      ["任务总数", stats.jobs_total], ["已发布任务", stats.published_jobs],
      ["爆款数", stats.hits], ["总阅读", fmtNum(stats.total_reads)],
      ["平均互动率", stats.total_reads ? pct(stats.avg_engagement) : "—"],
      ["粉丝数", stats.followers_total ?? "—"],
    ];
  }
  $("#kpi-cards").innerHTML = kpis.map(([lbl, num]) =>
    `<div class="kpi"><div class="num ${String(num).length > 5 ? "small" : ""}">${esc(num)}</div><div class="lbl">${esc(lbl)}</div></div>`).join("");
}

const OV_TITLES = {
  compare: "平台细分对比",
  focus: "本周最重要的一件事",
  summary: "生产与发布汇总（任务状态 + 发布趋势）",
  recent: "最近发布表现",
};

function overviewLayout() {
  try {
    const v = JSON.parse(localStorage.getItem("selfmedia_overview_panel") || "null");
    if (Array.isArray(v) && v.length) return v.filter((id) => OV_TITLES[id]);
  } catch (e) { /* ignore */ }
  return ["compare", "focus", "summary", "recent"];
}

function saveOverviewLayout(layout) {
  try {
    localStorage.setItem("selfmedia_overview_panel", JSON.stringify(layout));
  } catch (e) { /* ignore */ }
}

function addOverviewModule(id) {
  const layout = overviewLayout();
  if (!layout.includes(id)) {
    layout.push(id);
    saveOverviewLayout(layout);
    renderOverviewPane(ovStatsCache || {}, ovCache || {});
  }
}
window.addOverviewModule = addOverviewModule;

function removeOverviewModule(id) {
  saveOverviewLayout(overviewLayout().filter((x) => x !== id));
  renderOverviewPane(ovStatsCache || {}, ovCache || {});
}
window.removeOverviewModule = removeOverviewModule;

function renderOverviewPane(stats, d) {
  const box = $("#ov-overview");
  if (!box) return;
  const ov = d.overview || {};
  const dx = d.diagnostics || {};
  const noteParts = [];
  if (dx.generated_at) noteParts.push("诊断更新于 " + dx.generated_at.slice(5, 16));
  if (dx.previous_at) noteParts.push("上次 " + dx.previous_at.slice(5, 16));
  const layout = overviewLayout();
  const missing = Object.keys(OV_TITLES).filter((id) => !layout.includes(id));
  box.innerHTML = `
    <div class="panel-toolbar">
      <button class="btn small tonal" onclick="togglePanelEdit()">${panelEditMode ? "✓ 完成" : "编辑组件"}</button>
    </div>
    <div id="ov-modules">
      ${layout.map((id) => `
        <div class="pf-module" data-module="${esc(id)}" ${panelEditMode ? 'draggable="true"' : ""}>
          <div class="pf-module-head">
            <b>${esc(OV_TITLES[id])}</b>
            ${panelEditMode ? `
              <span class="pf-drag" title="按住拖动排序">⠿</span>
              <span class="muted">拖动排序</span>
              <button class="btn tiny tonal" onclick="removeOverviewModule('${esc(id)}')">删除</button>` : ""}
          </div>
          <div class="pf-module-body" data-body="${esc(id)}"></div>
        </div>`).join("")}
    </div>
    ${panelEditMode ? `
      <details class="card" style="padding:12px 16px">
        <summary style="cursor:pointer;font-weight:600">＋ 添加组件</summary>
        <div class="add-modules">
          ${missing.length ? missing.map((id) =>
            `<button class="btn tiny tonal" onclick="addOverviewModule('${esc(id)}')">${esc(OV_TITLES[id])}</button>`).join("")
            : '<span class="muted">全部组件都已显示</span>'}
        </div>
      </details>` : ""}`;
  layout.forEach((id) => fillOverviewModule(id, stats, d, noteParts));
  bindModuleDrag("overview", "#ov-modules");
}

function fillOverviewModule(id, stats, d, noteParts) {
  const body = $(`#ov-overview .pf-module[data-module="${id}"] .pf-module-body`);
  if (!body) return;
  const ov = d.overview || {};
  if (id === "compare") {
    body.innerHTML = `
      ${noteParts.length ? `<div class="muted" style="margin-bottom:8px">${esc(noteParts.join(" · "))}</div>` : ""}
      <div id="ov-compare" class="compare-chart"></div>
      <div id="ov-platform-cards" class="agent-grid" style="margin-top:14px"></div>`;
    renderPlatformCompareChart(d.platforms || {});
    renderPlatformCards(d.platforms || {});
  } else if (id === "focus") {
    body.innerHTML = `<div class="focus-card">${esc(ov.focus || "先回填/导入数据后开始诊断。")}</div>`;
  } else if (id === "summary") {
    const states = Object.entries(stats.by_state || {});
    const total = stats.jobs_total || 1;
    body.innerHTML = `
      <div class="grid-2">
        <div>
          <h4 class="pool-title">任务状态分布</h4>
          <div id="state-bars" class="state-bars">
            ${states.length
              ? states.map(([s, n]) => `
                <div class="sbar">
                  <span class="name">${esc(STATE_LABELS[s] || s)}</span>
                  <div class="track"><div class="fill" style="width:${(n / total * 100).toFixed(0)}%"></div></div>
                  <span class="cnt">${n}</span>
                </div>`).join("")
              : '<span class="muted">暂无任务</span>'}
          </div>
        </div>
        <div>
          <h4 class="pool-title">发布趋势</h4>
          <div id="ov-trend" class="line-chart-wrap"></div>
          <div class="series-tabs" id="ov-series"></div>
        </div>
      </div>`;
    renderOverviewTrend();
  } else if (id === "recent") {
    body.innerHTML = `
      <div class="muted" style="margin-bottom:8px">最新 10 条 · 自动快评</div>
      <div class="table-wrap">
        <table class="table">
          <thead><tr><th>时间</th><th>标题</th><th>平台</th><th>体裁</th><th class="num">曝光</th><th class="num">观看量</th><th class="num">点击率</th><th class="num">点赞</th><th class="num">评论</th><th class="num">收藏</th><th class="num">涨粉</th><th class="num">分享</th><th class="num">时长</th><th>状态</th><th>快评</th></tr></thead>
          <tbody id="recent-table"></tbody>
        </table>
      </div>`;
    renderRecentRows($("#recent-table"), ov.recent || []);
  }
}

function renderOverviewTrend() {
  const dates = new Set();
  const byDate = {};
  Object.values(ovCache.platforms || {}).forEach((p) => {
    const tr = p.trend || {};
    (tr.dates || []).forEach((dd, i) => {
      dates.add(dd);
      byDate[dd] = byDate[dd] || { publish: 0, reads: 0, followers: 0, readsEng: 0 };
      byDate[dd].publish += tr.publishes?.[i] || 0;
      byDate[dd].reads += tr.reads?.[i] || 0;
      byDate[dd].followers += tr.followers?.[i] || 0;
      if (tr.engagement?.[i] != null && tr.reads?.[i]) {
        byDate[dd].readsEng += tr.engagement[i] * tr.reads[i];
      }
    });
  });
  const sorted = Array.from(dates).sort();
  const raw = {
    dates: sorted,
    labels: sorted.map((dd) => dd.slice(5)),
    publishes: sorted.map((dd) => byDate[dd].publish),
    reads: sorted.map((dd) => byDate[dd].reads),
    engagement: sorted.map((dd) => byDate[dd].reads ? byDate[dd].readsEng / byDate[dd].reads : null),
    followers: sorted.map((dd) => byDate[dd].followers),
  };
  const bucketed = bucketTrend(raw, dashPeriod);
  const c = cumulateTrend(bucketed);
  const series = {
    publishes: { label: "累计发布", data: c.publishes },
    reads: { label: "累计阅读/播放", data: c.reads },
    followers: { label: "累计涨粉", data: c.followers },
  };
  const keys = chartSeriesFor("overview");
  $("#ov-series").innerHTML = Object.entries(series).map(([k, s]) =>
    `<button class="tab ${keys.includes(k) ? "active" : ""}" onclick="toggleChartSeries('overview','${k}')">${s.label}</button>`).join("");
  svgLineChart($("#ov-trend"), bucketed.labels, series, keys);
}

function setOverviewSeries(k) {
  ovSeriesSel.overview = k;
  renderOverviewTrend();
}
window.setOverviewSeries = setOverviewSeries;

function bucketTrend(raw, period) {
  const keys = [];
  const byKey = {};
  const engW = {};
  const labels = [];
  const seen = {};
  (raw.labels || []).forEach((lbl, i) => {
    const date = (raw.dates ? raw.dates[i] : "") || lbl;
    const key = dateKey(date, period);
    if (!(key in seen)) {
      seen[key] = true;
      keys.push(key);
      byKey[key] = { publish: 0, reads: 0, followers: 0, readsEng: 0 };
      labels.push(key);
    }
    byKey[key].publish += raw.publishes?.[i] || 0;
    byKey[key].reads += raw.reads?.[i] || 0;
    byKey[key].followers += raw.followers?.[i] || 0;
    if (raw.engagement?.[i] != null && raw.reads?.[i]) {
      byKey[key].readsEng += raw.engagement[i] * raw.reads[i];
    }
  });
  return {
    labels,
    publishes: keys.map((k) => byKey[k].publish),
    reads: keys.map((k) => byKey[k].reads),
    followers: keys.map((k) => byKey[k].followers),
    engagement: keys.map((k) => byKey[k].reads ? +(byKey[k].readsEng / byKey[k].reads * 100).toFixed(2) : null),
    _reads: keys.map((k) => byKey[k].reads),
    _readsEng: keys.map((k) => byKey[k].readsEng),
  };
}

function cumulateTrend(b) {
  let pp = 0, pr = 0, pf = 0, pw = 0, pr2 = 0;
  return {
    labels: b.labels,
    publishes: b.publishes.map((v) => (pp += v)),
    reads: b.reads.map((v) => (pr += v)),
    followers: b.followers.map((v) => (pf += v)),
    engagement: b._reads.map((r, i) => {
      pw += b._readsEng[i] || 0;
      pr2 += r || 0;
      return pr2 ? +(pw / pr2 * 100).toFixed(2) : null;
    }),
  };
}

function dateKey(date, period) {
  if (!date) return date;
  if (period === "day") return date.slice(5);
  if (period === "month") return date.slice(0, 7).replace("-", "年") + "月";
  if (period === "year") return date.slice(0, 4) + "年";
  // week：ISO 周
  const d = new Date(date + "T00:00:00");
  const day = (d.getUTCDay() + 6) % 7;
  d.setUTCDate(d.getUTCDate() - day + 3);
  const firstThu = new Date(Date.UTC(d.getUTCFullYear(), 0, 4));
  const firstDay = (firstThu.getUTCDay() + 6) % 7;
  firstThu.setUTCDate(firstThu.getUTCDate() - firstDay + 3);
  const week = 1 + Math.round((d - firstThu) / (7 * 86400000));
  return d.getUTCFullYear() + "-W" + String(week).padStart(2, "0");
}

function renderPlatformCompareChart(platforms) {
  const box = $("#ov-compare");
  if (!box) return;
  const order = ["小红书", "公众号", "短视频"].filter((p) => platforms[p]);
  if (!order.length) {
    box.innerHTML = '<span class="muted">暂无平台数据，先在「平台管理」中启用平台并回填数据。</span>';
    return;
  }
  const metrics = [
    { key: "total_reads", label: "阅读/播放", fmt: (v) => fmtNum(v) },
    { key: "followers", label: "粉丝数", fmt: (v) => fmtNum(v) },
    { key: "hits", label: "爆款数", fmt: (v) => v },
    { key: "engagement", label: "互动率", fmt: (v) => v == null ? "—" : (v * 100).toFixed(1) + "%" },
  ];
  const W = 760, H = 300, PAD_L = 12, PAD_R = 12, PAD_T = 26, PAD_B = 46;
  const innerW = W - PAD_L - PAD_R;
  const innerH = H - PAD_T - PAD_B;
  const groupW = innerW / metrics.length;
  const barW = Math.min(40, groupW * 0.24);
  const maxBy = {};
  metrics.forEach((m) => {
    let max = 0;
    order.forEach((pl) => {
      const t = (platforms[pl] || {}).totals || {};
      const v = m.key === "engagement" ? t.engagement : t[m.key] || 0;
      if (typeof v === "number" && v > max) max = v;
    });
    maxBy[m.key] = max || 1;
  });
  const bars = metrics.map((m, gi) => {
    const gx = PAD_L + gi * groupW + groupW / 2;
    return order.map((pl, pi) => {
      const t = (platforms[pl] || {}).totals || {};
      const v = m.key === "engagement" ? t.engagement : t[m.key] || 0;
      const h = (typeof v === "number" && v > 0) ? Math.max(3, v / maxBy[m.key] * innerH) : 0;
      const x = gx + (pi - (order.length - 1) / 2) * (barW + 6) - barW / 2;
      const y = PAD_T + innerH - h;
      const val = `<text x="${(x + barW / 2).toFixed(1)}" y="${(y - 4).toFixed(1)}" text-anchor="middle" class="gbar-val">${esc(m.fmt(v))}</text>`;
      return `<rect x="${x.toFixed(1)}" y="${y.toFixed(1)}" width="${barW}" height="${h.toFixed(1)}" rx="4" class="gbar ${esc(pl)}"/>${h ? val : ""}`;
    }).join("");
  }).join("");
  const metricLabels = metrics.map((m, gi) => {
    const gx = PAD_L + gi * groupW + groupW / 2;
    return `<text x="${gx.toFixed(1)}" y="${H - 14}" text-anchor="middle" class="gbar-label">${esc(m.label)}</text>`;
  }).join("");
  const legend = order.map((pl) =>
    `<span class="legend-item"><i class="legend-dot ${esc(pl)}"></i>${esc(pl)}</span>`).join("");
  box.innerHTML = `<svg viewBox="0 0 ${W} ${H}" class="compare-svg">${bars}${metricLabels}</svg><div class="legend">${legend}</div>`;
}

function renderPlatformCards(platforms) {
  const box = $("#ov-platform-cards");
  if (!box) return;
  const icons = { "公众号": "📰", "小红书": "📕", "短视频": "🎬" };
  box.innerHTML = Object.entries(platforms).map(([pl, p]) => {
    const t = p.totals || {};
    return `
      <div class="agent-card">
        <div class="head"><span class="emoji">${icons[pl] || "📊"}</span><span class="role">${esc(pl)}</span></div>
        <div class="resp">发布 <b>${t.publish_count ?? 0}</b> ｜ 回填 <b>${t.backfill_count ?? 0}</b> ｜ 爆款 <b>${t.hits ?? 0}</b></div>
        <div class="kv">阅读/播放 <b>${fmtNum(t.total_reads ?? 0)}</b> ｜ 互动率 <b>${t.engagement == null ? "—" : (t.engagement * 100).toFixed(2) + "%"}</b></div>
        <div class="kv">粉丝数 <b>${t.followers ?? "—"}</b></div>
      </div>`;
  }).join("") || '<span class="muted">暂无平台数据</span>';
}

function switchOverviewTab(name) {
  currentOvTab = name;
  $$("#ov-tabs .tab").forEach((b) => b.classList.toggle("active", b.dataset.ov === name));
  $("#ov-overview").classList.toggle("hidden", name !== "overview");
  $("#ov-platform").classList.toggle("hidden", name === "overview");
  renderGlobalKpis(ovStatsCache || {}, ovCache || {});
  if (name !== "overview") renderPlatformPane(name);
}
window.switchOverviewTab = switchOverviewTab;

function renderPlatformPane(name) {
  const p = ovCache && ovCache.platforms && ovCache.platforms[name];
  if (!p) {
    $("#ov-platform").innerHTML = '<div class="card"><span class="muted">暂无数据，先采集/回填。</span></div>';
    return;
  }
  const metricsHtml = (p.metrics || []).map((m) => `
    <div class="kpi">
      <div class="num small">${m.value == null ? "—" : esc(fmtNum(m.value)) + (m.unit ? `<small class="unit">${esc(m.unit)}</small>` : "")}</div>
      <div class="lbl">${esc(m.label)} <span class="muted">基准 ${esc(m.benchmark_text)}</span></div>
    </div>`).join("");
  const t = p.totals || {};
  const wins = (p.metrics || []).filter((m) => m.available && m.score != null && m.score >= 100);
  const winsHtml = [
    ...wins.map((m) => `<div class="kv">✅ ${esc(m.label)}：<b>${esc(m.value)}${esc(m.unit || "")}</b>（优于基准 ${esc(m.benchmark_text)}）</div>`),
    ...(t.hits ? [`<div class="kv">🔥 爆款 <b>${t.hits}</b> 篇</div>`] : []),
  ].join("") || '<span class="muted">暂无突出项，继续积累数据后自动给出。</span>';
  const layout = panelLayout(name);
  const missing = Object.keys(PANEL_TITLES).filter((id) => !layout.includes(id));
  $("#ov-platform").innerHTML = `
    <div class="panel-toolbar">
      <button class="btn small tonal" onclick="togglePanelEdit()">${panelEditMode ? "✓ 完成" : "编辑组件"}</button>
    </div>
    <div id="pf-modules">
      ${layout.map((id) => `
        <div class="pf-module" data-module="${esc(id)}" ${panelEditMode ? 'draggable="true"' : ""}>
          <div class="pf-module-head">
            <b>${esc(PANEL_TITLES[id])}</b>
            ${panelEditMode ? `
              <span class="pf-drag" title="按住拖动排序">⠿</span>
              <span class="muted">拖动排序</span>
              <button class="btn tiny tonal" onclick="removePanelModule('${esc(name)}','${esc(id)}')">删除</button>` : ""}
          </div>
          <div class="pf-module-body" data-body="${esc(id)}"></div>
        </div>`).join("")}
    </div>
    ${panelEditMode ? `
      <details class="card" style="padding:12px 16px">
        <summary style="cursor:pointer;font-weight:600">＋ 添加组件</summary>
        <div class="add-modules">
          ${missing.length ? missing.map((id) =>
            `<button class="btn tiny tonal" onclick="addPanelModule('${esc(name)}','${esc(id)}')">${esc(PANEL_TITLES[id])}</button>`).join("")
            : '<span class="muted">全部组件都已显示</span>'}
        </div>
      </details>` : ""}`;
  layout.forEach((id) => fillPanelModule(name, id, p));
  bindPanelDrag(name);
}

function togglePanelEdit() {
  panelEditMode = !panelEditMode;
  if (currentOvTab === "overview") renderOverviewPane(ovStatsCache || {}, ovCache || {});
  else renderPlatformPane(currentOvTab);
}
window.togglePanelEdit = togglePanelEdit;

const PANEL_TITLES = {
  tri: "诊断（做得好的 / 存在的问题 / 下一步）",
  kpis: "核心指标", recent: "最近发布表现", trend: "趋势",
  xhs_detail: "小红书式数据分析（导出明细）",
};

function defaultPanelLayout(platform) {
  if (platform === "小红书") return ["tri", "kpis", "recent", "xhs_detail"];
  return ["tri", "kpis", "trend", "recent"];
}

function panelLayout(platform) {
  try {
    const v = JSON.parse(localStorage.getItem("selfmedia_panel") || "{}");
    if (Array.isArray(v[platform]) && v[platform].length) {
      return v[platform].filter((id) => PANEL_TITLES[id]);
    }
  } catch (e) { /* ignore */ }
  return defaultPanelLayout(platform);
}

function savePanelLayout(platform, layout) {
  try {
    const v = JSON.parse(localStorage.getItem("selfmedia_panel") || "{}");
    v[platform] = layout;
    localStorage.setItem("selfmedia_panel", JSON.stringify(v));
  } catch (e) { /* ignore */ }
}

function addPanelModule(platform, id) {
  const layout = panelLayout(platform);
  if (!layout.includes(id)) {
    layout.push(id);
    savePanelLayout(platform, layout);
    renderPlatformPane(platform);
  }
}
window.addPanelModule = addPanelModule;

function reorderPanelModule(platform, from, to) {
  const layout = panelLayout(platform);
  const i = layout.indexOf(from);
  if (i < 0) return;
  layout.splice(i, 1);
  const j = layout.indexOf(to);
  layout.splice(j < 0 ? layout.length : j, 0, from);
  savePanelLayout(platform, layout);
  renderPlatformPane(platform);
}
window.reorderPanelModule = reorderPanelModule;

function removePanelModule(platform, id) {
  savePanelLayout(platform, panelLayout(platform).filter((x) => x !== id));
  renderPlatformPane(platform);
}
window.removePanelModule = removePanelModule;

function bindModuleDrag(platform, boxId) {
  const box = $(boxId);
  if (!box) return;
  const getLayout = platform === "overview" ? overviewLayout : () => panelLayout(platform);
  const saveLayout = platform === "overview"
    ? saveOverviewLayout
    : (l) => savePanelLayout(platform, l);
  const rerender = platform === "overview"
    ? () => renderOverviewPane(ovStatsCache || {}, ovCache || {})
    : () => renderPlatformPane(platform);
  box.addEventListener("dragstart", (e) => {
    const m = e.target.closest(".pf-module");
    if (!m) return;
    e.dataTransfer.setData("text/plain", m.dataset.module);
    m.classList.add("dragging");
  });
  box.addEventListener("dragover", (e) => {
    e.preventDefault();
    const m = e.target.closest(".pf-module");
    box.querySelectorAll(".pf-module").forEach((x) => x.classList.remove("drop-target"));
    if (m) m.classList.add("drop-target");
  });
  box.addEventListener("drop", (e) => {
    e.preventDefault();
    const from = e.dataTransfer.getData("text/plain");
    const to = e.target.closest(".pf-module");
    if (!from || !to) return;
    const layout = getLayout();
    const i = layout.indexOf(from);
    if (i < 0) return;
    layout.splice(i, 1);
    const j = layout.indexOf(to.dataset.module);
    layout.splice(j < 0 ? layout.length : j, 0, from);
    saveLayout(layout);
    rerender();
  });
  box.addEventListener("dragend", () => {
    box.querySelectorAll(".pf-module").forEach((x) => x.classList.remove("dragging", "drop-target"));
  });
}

function bindPanelDrag(platform) {
  bindModuleDrag(platform, "#pf-modules");
}

function fillPanelModule(platform, id, p) {
  const body = $(`#ov-platform .pf-module[data-module="${id}"] .pf-module-body`);
  if (!body) return;
  if (id === "tri") {
    body.innerHTML = `
      <div class="tri-grid">
        <div class="card">
          <div class="card-head"><h3>做得好的</h3></div>
          <div class="stack">${winsHtmlFor(p)}</div>
        </div>
        <div class="card">
          <div class="card-head"><h3>存在的问题</h3></div>
          <div id="pf-weak" class="stack"></div>
        </div>
        <div class="card">
          <div class="card-head"><h3>下一步要做的事情</h3></div>
          <div class="focus-card">${esc(p.focus || "—")}</div>
        </div>
      </div>`;
    renderWeakCompact($("#pf-weak"), p.weak_points || [], platform);
  } else if (id === "kpis") {
    body.innerHTML = `<div class="kpi-grid">${metricsHtmlFor(p)}</div>`;
  } else if (id === "trend") {
    body.innerHTML = '<div id="pf-trend" class="line-chart-wrap"></div><div class="series-tabs" id="pf-series"></div>';
    renderPlatformTrend(platform, p.trend);
  } else if (id === "recent") {
    body.innerHTML = `<div class="table-wrap"><table class="table">
      <thead><tr><th>时间</th><th>标题</th><th>体裁</th><th class="num">曝光</th><th class="num">观看量</th><th class="num">点击率</th><th class="num">点赞</th><th class="num">评论</th><th class="num">收藏</th><th class="num">涨粉</th><th class="num">分享</th><th class="num">时长</th><th>状态</th><th>快评</th></tr></thead>
      <tbody id="pf-recent"></tbody></table></div>`;
    renderRecentRows($("#pf-recent"), p.recent || [], false);
  } else if (id === "xhs_detail") {
    body.innerHTML = xhsDashCardHtml();
    dashState.data = ovCache;
    dashState.weakPoints = ovCache.weak_points || [];
    renderDash();
    const files = (ovCache.sources || {}).dashboard_files || {};
    $("#dash-note").textContent =
      `更新于 ${ovCache.generated_at || ""} · 看板导出 ${Object.values(files).filter(Boolean).length}/4 · 笔记明细 ${(ovCache.sources || {}).notes_in_range || 0} 条`;
  }
}

function winsHtmlFor(p) {
  const wins = (p.metrics || []).filter((m) => m.available && m.score != null && m.score >= 100);
  const t = p.totals || {};
  return [
    ...wins.map((m) => `<div class="kv">✅ ${esc(m.label)}：<b>${esc(m.value)}${esc(m.unit || "")}</b>（优于基准 ${esc(m.benchmark_text)}）</div>`),
    ...(t.hits ? [`<div class="kv">🔥 爆款 <b>${t.hits}</b> 篇</div>`] : []),
  ].join("") || '<span class="muted">暂无突出项，继续积累数据后自动给出。</span>';
}

function metricsHtmlFor(p) {
  return (p.metrics || []).map((m) => `
    <div class="kpi">
      <div class="num small">${m.value == null ? "—" : esc(fmtNum(m.value)) + (m.unit ? `<small class="unit">${esc(m.unit)}</small>` : "")}</div>
      <div class="lbl">${esc(m.label)} <span class="muted">基准 ${esc(m.benchmark_text)}</span></div>
    </div>`).join("");
}

function xhsDashCardHtml() {
  return `
    <div class="xhs-dash-head">
      <div class="tabs" id="dash-tabs" style="margin-bottom:0">
        <button class="tab active" data-dash="watch" onclick="switchDashTab('watch')">观看</button>
        <button class="tab" data-dash="interact" onclick="switchDashTab('interact')">互动</button>
        <button class="tab" data-dash="follower" onclick="switchDashTab('follower')">涨粉</button>
        <button class="tab" data-dash="publish" onclick="switchDashTab('publish')">发布</button>
      </div>
      <span class="muted" id="dash-note"></span>
    </div>
    <div class="kpi-grid" id="dash-kpis"></div>
    <div class="grid-2">
      <div id="dash-funnel" class="dash-panel"></div>
      <div id="dash-trend" class="dash-panel">
        <div class="card-head"><h3>趋势</h3></div>
        <div class="trend-chart" id="dash-trend-chart"></div>
      </div>
      <div id="dash-extra" class="grid-2" style="margin-top:18px"></div>
    </div>`;
}

function renderPlatformTrend(name, trend) {
  const bucketed = bucketTrend({
    dates: trend.dates || [],
    labels: trend.labels || [],
    publishes: trend.publishes || [],
    reads: trend.reads || [],
    engagement: trend.engagement || [],
    followers: trend.followers || [],
  }, dashPeriod);
  const c = cumulateTrend(bucketed);
  const seriesMap = {
    publishes: { label: "累计发布", data: c.publishes },
    reads: { label: "累计阅读/播放", data: c.reads },
    followers: { label: "累计涨粉", data: c.followers },
  };
  const keys = chartSeriesFor(name);
  $("#pf-series").innerHTML = Object.entries(seriesMap).map(([k, s]) =>
    `<button class="tab ${keys.includes(k) ? "active" : ""}" onclick="toggleChartSeries('${esc(name)}','${k}')">${s.label}</button>`).join("");
  svgLineChart($("#pf-trend"), bucketed.labels, seriesMap, keys);
}

function setPlatformSeries(platform, key) {
  ovSeriesSel[platform] = key;
  if (ovCache && ovCache.platforms && ovCache.platforms[platform]) {
    renderPlatformTrend(platform, ovCache.platforms[platform].trend);
  }
}
window.setPlatformSeries = setPlatformSeries;

function chartSeriesFor(scope) {
  const all = ["publishes", "reads", "followers"];
  try {
    const v = JSON.parse(localStorage.getItem("selfmedia_chart_series") || "{}");
    if (Array.isArray(v[scope]) && v[scope].length) {
      return v[scope].filter((k) => all.includes(k));
    }
  } catch (e) { /* ignore */ }
  return all;
}

function saveChartSeries(scope, keys) {
  try {
    const v = JSON.parse(localStorage.getItem("selfmedia_chart_series") || "{}");
    v[scope] = keys;
    localStorage.setItem("selfmedia_chart_series", JSON.stringify(v));
  } catch (e) { /* ignore */ }
}

function toggleChartSeries(scope, key) {
  const cur = chartSeriesFor(scope);
  const next = cur.includes(key) ? cur.filter((k) => k !== key) : [...cur, key];
  if (!next.length) return; // 至少保留一条
  saveChartSeries(scope, next);
  if (scope === "overview") renderOverviewTrend();
  else if (ovCache && ovCache.platforms && ovCache.platforms[scope]) {
    renderPlatformTrend(scope, ovCache.platforms[scope].trend);
  }
}
window.toggleChartSeries = toggleChartSeries;

function svgLineChart(el, labels, seriesMap, selectedKeys) {
  if (!el) return;
  const keys = (selectedKeys || []).filter((k) => seriesMap[k] && (seriesMap[k].data || []).some((v) => v != null && v > 0));
  if (!keys.length) {
    el.innerHTML = '<span class="muted">暂无趋势数据</span>';
    return;
  }
  const W = 600, H = 190, PAD = 34;
  const step = labels.length > 1 ? (W - PAD * 2) / (labels.length - 1) : W - PAD * 2;
  const useMulti = keys.length > 1;
  const raw = keys.map((k) => ({
    k, label: seriesMap[k].label,
    arr: seriesMap[k].data || [],
    max: Math.max(1, ...(seriesMap[k].data || []).map((v) => Number(v || 0))),
  }));
  const globalMax = Math.max(...raw.map((g) => g.max));
  const geoms = raw.map((g) => ({
    ...g,
    pts: g.arr.map((v, i) => [PAD + i * step, H - PAD - (Number(v || 0) / globalMax) * (H - PAD * 2)]),
  }));
  const activeGeom = geoms[0];
  const stepV = niceStep(globalMax / 4);
  const tickVals = [0, 1, 2, 3, 4].map((i) => i * stepV).filter((t) => t <= globalMax);
  if (tickVals[tickVals.length - 1] < globalMax - stepV / 2) tickVals.push(globalMax);
  const gridAll = tickVals.map((t) => {
    const y = H - PAD - (t / globalMax) * (H - PAD * 2);
    return `<line x1="${PAD}" y1="${y.toFixed(1)}" x2="${W - PAD}" y2="${y.toFixed(1)}" class="chart-grid"/>`;
  }).join("");
  const ticks = tickVals.map((t) => {
    const y = H - PAD - (t / globalMax) * (H - PAD * 2);
    return `<text x="${PAD - 8}" y="${(y + 4).toFixed(1)}" text-anchor="end" class="chart-axis">${esc(fmtNum(Math.round(t)))}</text>`;
  }).join("");
  const labelsHtml = labels.map((l, i) =>
    `<text x="${(PAD + i * step).toFixed(1)}" y="${H - 10}" text-anchor="middle" class="chart-axis">${esc(l)}</text>`).join("");
  const lines = useMulti
    ? geoms.map((g) => `<path d="${smoothPath(g.pts)}" class="chart-line" style="stroke:${seriesColor(g.k)}"/>`).join("")
    : `<path d="${smoothPath(activeGeom.pts)}" class="chart-line"/>`;
  const circles = useMulti ? "" : activeGeom.pts.map((p) =>
    `<circle cx="${p[0].toFixed(1)}" cy="${p[1].toFixed(1)}" r="3" class="chart-dot"/>`).join("");
  const guide = `<line id="chart-guide" x1="0" y1="8" x2="0" y2="${(H - PAD).toFixed(1)}" class="chart-guide" style="display:none"/>`;
  const hi = useMulti
    ? geoms.map((g) => `<circle data-hi="${g.k}" r="4" class="chart-hi" style="display:none;stroke:${seriesColor(g.k)}"/>`).join("")
    : `<circle id="chart-hi" r="5" class="chart-hi" style="display:none"/>`;
  const overlay = `<rect x="${PAD}" y="6" width="${(W - PAD * 2).toFixed(1)}" height="${(H - PAD * 2).toFixed(1)}" fill="transparent" class="chart-hover"/>`;
  const legend = useMulti
    ? `<div class="chart-legend">${geoms.map((g) =>
        `<span><i style="background:${seriesColor(g.k)}"></i>${esc(g.label)}</span>`).join("")}</div>`
    : "";
  const defs = `<defs>${geoms.map((g) => `
    <linearGradient id="grad-${g.k}" x1="0" y1="0" x2="0" y2="1">
      <stop offset="0%" stop-color="${seriesColor(g.k)}" stop-opacity=".28"/>
      <stop offset="100%" stop-color="${seriesColor(g.k)}" stop-opacity="0"/>
    </linearGradient>`).join("")}</defs>`;
  const areas = geoms.map((g) => {
    const d = smoothPath(g.pts);
    const last = g.pts[g.pts.length - 1];
    const first = g.pts[0];
    const base = H - PAD;
    return `<path d="${d} L ${last[0].toFixed(1)} ${base} L ${first[0].toFixed(1)} ${base} Z" fill="url(#grad-${g.k})" class="chart-area"/>`;
  }).join("");
  el.innerHTML = `<svg viewBox="0 0 ${W} ${H}" class="line-chart">${defs}${gridAll}${ticks}${guide}${hi}${areas}${lines}${circles}${labelsHtml}${overlay}</svg>${legend}<div class="chart-tip"></div>`;
  el.style.position = "relative";
  const svg = el.querySelector("svg");
  const tip = el.querySelector(".chart-tip");
  const guideEl = svg.querySelector("#chart-guide");
  const hiEls = svg.querySelectorAll(".chart-hi");
  svg.addEventListener("mousemove", (e) => {
    const r = svg.getBoundingClientRect();
    const x = (e.clientX - r.left) * (W / r.width);
    const idx = Math.max(0, Math.min(labels.length - 1, Math.round((x - PAD) / step)));
    const px = PAD + idx * step;
    guideEl.setAttribute("x1", px.toFixed(1));
    guideEl.setAttribute("x2", px.toFixed(1));
    guideEl.style.display = "";
    if (useMulti) {
      hiEls.forEach((h) => {
        const g = geoms.find((gg) => gg.k === h.dataset.hi);
        if (g) {
          h.setAttribute("cx", px.toFixed(1));
          h.setAttribute("cy", g.pts[idx][1].toFixed(1));
          h.style.display = "";
        }
      });
    } else {
      const h = hiEls[0];
      h.setAttribute("cx", px.toFixed(1));
      h.setAttribute("cy", activeGeom.pts[idx][1].toFixed(1));
      h.style.display = "";
    }
    const rows = keys.map((k) => {
      const ss = seriesMap[k];
      const v = ss.data ? ss.data[idx] : null;
      return `<div class="chart-tip-row"><i class="tip-dot" style="background:${seriesColor(k)}"></i><span>${esc(ss.label)}</span><b>${v == null ? "—" : esc(fmtNum(v))}</b></div>`;
    }).join("");
    tip.innerHTML = `<div class="chart-tip-title">${esc(labels[idx] || "")}</div>${rows}`;
    tip.style.display = "block";
    let tipX = e.clientX - r.left + 12;
    const tw = tip.offsetWidth || 150;
    if (tipX + tw > r.width) tipX = e.clientX - r.left - tw - 12;
    tip.style.left = Math.max(0, tipX) + "px";
    tip.style.top = "6px";
  });
  svg.addEventListener("mouseleave", () => {
    tip.style.display = "none";
    guideEl.style.display = "none";
    hiEls.forEach((h) => { h.style.display = "none"; });
  });
}

function smoothPath(xy) {
  if (xy.length < 2) {
    return `M ${xy.map((p) => p.join(" ")).join(" L ")}`;
  }
  let d = `M ${xy[0][0].toFixed(1)} ${xy[0][1].toFixed(1)}`;
  for (let i = 0; i < xy.length - 1; i++) {
    const [x0, y0] = xy[i], [x1, y1] = xy[i + 1];
    const c1x = x0 + (x1 - x0) / 3;
    const c2x = x0 + 2 * (x1 - x0) / 3;
    d += ` C ${c1x.toFixed(1)} ${y0.toFixed(1)}, ${c2x.toFixed(1)} ${y1.toFixed(1)}, ${x1.toFixed(1)} ${y1.toFixed(1)}`;
  }
  return d;
}

function seriesColor(k) {
  return {
    publishes: "#f59e0b", reads: "#1a73e8",
    engagement: "#0f9d58", followers: "#9c27b0",
  }[k] || "#1a73e8";
}

function niceStep(v) {
  v = Math.max(1, v);
  const p = Math.pow(10, Math.floor(Math.log10(v)));
  const r = v / p;
  const s = r <= 1 ? 1 : r <= 2 ? 2 : r <= 5 ? 5 : 10;
  return s * p;
}

function svgRadar(el, radar) {
  if (!el) return;
  const axes = (radar && radar.axes) || [];
  if (!axes.length) {
    el.innerHTML = '<span class="muted">暂无雷达数据</span>';
    return;
  }
  const N = axes.length, W = 280, H = 280, cx = W / 2, cy = H / 2, R = 92;
  const ang = (i) => -Math.PI / 2 + i * 2 * Math.PI / N;
  const xy = (i, r) => [cx + r * Math.cos(ang(i)), cy + r * Math.sin(ang(i))];
  const ring = (ratio) => axes.map((_, i) => xy(i, R * ratio).map((v) => v.toFixed(1)).join(",")).join(" ");
  const valuePts = axes.map((a, i) => {
    const v = a.available && a.value != null ? Math.min(100, a.value) / 100 : 0;
    return xy(i, R * v).map((x) => x.toFixed(1)).join(",");
  }).join(" ");
  const labels = axes.map((a, i) => {
    const [x, y] = xy(i, R + 24);
    return `<text x="${x.toFixed(1)}" y="${y.toFixed(1)}" text-anchor="middle" dominant-baseline="middle" class="radar-label">${esc(a.label)}${a.available ? "" : "（缺数据）"}</text>`;
  }).join("");
  const dots = axes.map((a, i) => {
    const r = a.available && a.value != null ? Math.min(100, a.value) / 100 : 0;
    const [x, y] = xy(i, R * r);
    return `<circle cx="${x.toFixed(1)}" cy="${y.toFixed(1)}" r="3" class="chart-dot"/>`;
  }).join("");
  el.innerHTML = `<svg viewBox="0 0 ${W} ${H}">${[0.25, 0.5, 0.75, 1].map((r) => `<polygon points="${ring(r)}" class="radar-grid"/>`).join("")}<polygon points="${valuePts}" class="radar-value"/>${dots}${labels}</svg>`;
}

function renderWeakList(box, weakList, platform) {
  if (!weakList.length) {
    return box.innerHTML = '<span class="muted">当前没有命中规则；继续回填/导入数据后自动诊断。</span>';
  }
  box.innerHTML = weakList.map((w) => `
    <div class="wp-item">
      <div class="wp-head">
        <b>${esc(w.title)}</b>
        <span class="badge error">现状 ${esc(w.current)}</span>
        <span class="muted">基准 ${esc(w.benchmark)}</span>
      </div>
      <div class="meta">${esc(w.suggestion)}</div>
      <div class="meta muted">适用：${esc(w.apply_to)}</div>
      <div class="actions">
        <button class="btn small filled" onclick="savePlatformWeakLesson('${esc(platform)}','${esc(w.id)}')">沉淀为经验</button>
      </div>
    </div>`).join("");
}

function clip(s, n) {
  s = String(s || "");
  return s.length > n ? s.slice(0, n - 1) + "…" : s;
}

function renderWeakCompact(box, weakList, platform) {
  if (!weakList.length) {
    return box.innerHTML = '<span class="muted">当前没有命中规则；继续回填/导入数据后自动诊断。</span>';
  }
  box.innerHTML = `<div class="weak-compact">
    ${weakList.map((w) => `
      <div class="weak-row" title="${esc(w.title)}｜${esc(w.suggestion)}">
        <span class="badge error">${esc(w.current)}</span>
        <span class="wt">${esc(w.title)}</span>
        <span class="wm">${esc(clip(w.suggestion, 32))}</span>
        <button class="btn tiny" onclick="savePlatformWeakLesson('${esc(platform)}','${esc(w.id)}')">沉淀</button>
      </div>`).join("")}
  </div>`;
}

async function savePlatformWeakLesson(platform, id) {
  const w = ovCache && ovCache.platforms[platform] &&
    ovCache.platforms[platform].weak_points.find((x) => x.id === id);
  if (!w) return;
  try {
    await api("/api/flywheel/lessons", {
      method: "POST", headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        title: w.title,
        conclusion: w.suggestion,
        evidence: `现状 ${w.current} vs 基准 ${w.benchmark}（${platform} 看板诊断）`,
        apply_to: w.apply_to,
        source: "dashboard",
      }),
    });
    toast("已沉淀为经验，可在数据飞轮查看并标记应用");
  } catch (e) {
    toast("沉淀失败: " + e.message, false);
  }
}
window.savePlatformWeakLesson = savePlatformWeakLesson;

function quickClass(q) {
  if (q && q.includes("爆款")) return "hit";
  if (q && q.includes("互动强")) return "success";
  if (q && q.includes("流量达标")) return "primary";
  if (q && q.includes("需优化")) return "error";
  return "";
}

function noteRow(r, withPlatform) {
  const time = fmtTime(r.first_published_at || r.collected_at);
  const ctr = r.ctr != null && Number(r.ctr) > 0
    ? (Number(r.ctr) <= 1 ? (Number(r.ctr) * 100).toFixed(1) + "%" : esc(r.ctr) + "%")
    : "—";
  return `
    <tr>
      <td>${esc(time)}</td>
      <td title="${esc(r.theme || "")}">${esc(r.title || r.job_id)}</td>
      ${withPlatform ? `<td>${esc(r.platform || "—")}</td>` : ""}
      <td>${esc(r.format || "—")}</td>
      <td class="num">${r.exposure ? fmtNum(r.exposure) : "—"}</td>
      <td class="num">${fmtNum(r.reads)}</td>
      <td class="num">${ctr}</td>
      <td class="num">${fmtNum(r.likes)}</td>
      <td class="num">${fmtNum(r.comments)}</td>
      <td class="num">${fmtNum(r.collects)}</td>
      <td class="num">${r.followers_gained ? fmtNum(r.followers_gained) : "—"}</td>
      <td class="num">${r.shares ? fmtNum(r.shares) : "—"}</td>
      <td class="num">${r.avg_watch_seconds ? esc(r.avg_watch_seconds) + "秒" : "—"}</td>
      <td>${r.hit ? '<span class="badge hit">🔥 爆款</span>' : '<span class="badge">常规</span>'}</td>
      ${r.quick ? `<td><span class="badge ${quickClass(r.quick)}">${esc(r.quick)}</span></td>` : ""}
    </tr>`;
}

function fmtTime(s) {
  if (!s) return "—";
  const pad = (n) => String(n).padStart(2, "0");
  const zh = String(s).match(/^(\d{4})年(\d{1,2})月(\d{1,2})日(\d{1,2})时(\d{1,2})分/);
  if (zh) return `${zh[1]}-${pad(zh[2])}-${pad(zh[3])} ${pad(zh[4])}:${pad(zh[5])}`;
  return String(s).replace("T", " ").slice(0, 16);
}

function renderRecentRows(box, records, withPlatform = true) {
  if (!records.length) return box.innerHTML = '<tr><td colspan="15" class="muted">暂无回填数据</td></tr>';
  box.innerHTML = records.map((r) => noteRow(r, withPlatform)).join("");
}

// ---------- 小红书式数据分析（四页签 + 薄弱点诊断） ----------
let dashState = { range: 7, tab: "watch", data: null, weakPoints: [] };

function switchDashTab(tab) {
  dashState.tab = tab;
  $$("#dash-tabs .tab").forEach((b) => b.classList.toggle("active", b.dataset.dash === tab));
  renderDash();
}
window.switchDashTab = switchDashTab;

function setDashRange(n) {
  dashState.range = n;
  $$(".range-toggle .tab").forEach((b) => b.classList.toggle("active", Number(b.dataset.range) === n));
  loadOverview();
}
window.setDashRange = setDashRange;

async function loadDashboard() {
  try {
    const d = await api("/api/dashboard?range=" + dashState.range);
    dashState.data = d;
    dashState.weakPoints = d.weak_points || [];
    renderDash();
    renderWeakPoints();
    const files = d.sources && d.sources.dashboard_files ? d.sources.dashboard_files : {};
    $("#dash-note").textContent =
      `更新于 ${d.generated_at || ""} · 看板导出 ${Object.values(files).filter(Boolean).length}/4 · 笔记明细 ${d.sources ? d.sources.notes_in_range : 0} 条`;
  } catch (e) {
    $("#dash-note").textContent = "看板数据加载失败: " + e.message;
  }
}

function renderDash() {
  const d = dashState.data;
  if (!d || !d.tabs) return;
  const tab = d.tabs[dashState.tab];
  if (!tab) return;
  renderDashKpis(tab.kpis || []);
  renderDashFunnel(tab);
  renderDashTrend(tab.trend || []);
  renderDashExtra(tab);
}

function deltaBadge(delta) {
  if (delta == null) return "";
  const cls = delta >= 0 ? "up" : "down";
  return `<span class="delta ${cls}">${delta >= 0 ? "↑" : "↓"}${Math.abs(delta)}%</span>`;
}

function renderDashKpis(kpis) {
  if (!kpis.length) return $("#dash-kpis").innerHTML = '<span class="muted">暂无数据</span>';
  $("#dash-kpis").innerHTML = kpis.map((k) => `
    <div class="kpi">
      <div class="num small">${k.value == null ? "—" : esc(fmtNum(k.value)) + (k.unit ? '<small class="unit">' + esc(k.unit) + "</small>" : "")}</div>
      <div class="lbl">${esc(k.key)} ${deltaBadge(k.delta)}</div>
    </div>`).join("");
}

function renderDashFunnel(tab) {
  const box = $("#dash-funnel");
  if (dashState.tab === "watch" && tab.funnel) {
    const f = tab.funnel;
    box.innerHTML = `
      <div class="card-head"><h3>曝光 → 观看 → 点击率</h3></div>
      <div class="funnel">
        <div class="fstep"><div class="fnum">${esc(fmtNum(f.exposure))}</div><div class="flbl">曝光</div></div>
        <div class="farrow">→</div>
        <div class="fstep"><div class="fnum">${esc(fmtNum(f.reads))}</div><div class="flbl">观看</div></div>
        <div class="farrow">→</div>
        <div class="fstep"><div class="fnum">${f.ctr == null ? "—" : esc(f.ctr) + "%"}</div><div class="flbl">封面点击率</div></div>
      </div>`;
    return;
  }
  const acc = tab.account;
  const rows = acc ? Object.entries(acc).map(([k, v]) =>
    `<div class="kv">${esc(k)}：<b>${v == null || v === "" ? "—" : esc(v)}</b></div>`).join("") : "";
  box.innerHTML = `
    <div class="card-head"><h3>${dashState.tab === "publish" ? "近30日全量参考" : dashState.tab === "follower" ? "账号快照" : "参考数据"}</h3></div>
    <div class="stack">${rows || '<span class="muted">暂无额外数据（导入对应页签导出后自动补齐）</span>'}</div>`;
}

function renderDashTrend(trend) {
  const box = $("#dash-trend-chart");
  if (!trend || !trend.length) return box.innerHTML = '<span class="muted">暂无趋势数据</span>';
  const bucketed = bucketDaily(trend, dashPeriod);
  let run = 0;
  const cum = bucketed.map((t) => ({ ...t, value: (run += Number(t.value != null ? t.value : t.total || 0)) }));
  const maxV = Math.max(1, ...cum.map((t) => Number(t.value || 0)));
  box.innerHTML = cum.map((t) => {
    const v = Number(t.value || 0);
    const extra = t.video != null ? ` 视频 ${t.video} / 图文 ${t.image}` : "";
    return `
      <div class="tcol" title="累计 ${esc(t.date + extra)}">
        <span class="val">${v ? fmtNum(v) : ""}</span>
        <div class="bar" style="height:${Math.max(4, Math.round(v / maxV * 92))}%"></div>
        <span class="day">${esc(t.label)}</span>
      </div>`;
  }).join("");
}

function bucketDaily(trend, period) {
  const map = {};
  trend.forEach((t) => {
    const k = dateKey(t.date || "", period);
    map[k] = map[k] || { label: k, value: 0, video: 0, image: 0, date: t.date || "" };
    map[k].value += Number(t.value != null ? t.value : t.total || 0);
    map[k].video += Number(t.video || 0);
    map[k].image += Number(t.image || 0);
  });
  return Object.values(map);
}

function renderDashExtra(tab) {
  const box = $("#dash-extra");
  if (dashState.tab === "watch") {
    const source = tab.source || [];
    const tod = tab.timeofday || [];
    const card = (title, rows, empty) => `
      <div class="card"><div class="card-head"><h3>${esc(title)}</h3></div>
      ${rows.length ? rows.map((r) => `
        <div class="hbar">
          <span class="hlabel">${esc(String(r.label || r[0] || ""))}</span>
          <div class="htrack"><div class="hfill" style="width:${Math.min(100, Number(r.value) || 0)}%"></div></div>
          <span class="hval">${esc(String(r.value != null ? r.value : (r[1] != null ? r[1] : "—")))}</span>
        </div>`).join("") : `<span class="muted">${esc(empty)}</span>`}
      </div>`;
    box.innerHTML = card("观看来源", source, "需导入「观看数据」导出（含来源分解）") +
                    card("观看时段", tod, "需导入「观看数据」导出（含时段分解）");
  } else {
    box.innerHTML = "";
  }
}

function renderWeakPoints() {
  const box = $("#weak-points");
  if (!box) return;
  if (!dashState.weakPoints.length) {
    return box.innerHTML = '<span class="muted">当前没有命中薄弱点规则；继续导入数据后会自动诊断。</span>';
  }
  box.innerHTML = dashState.weakPoints.map((w) => `
    <div class="wp-item">
      <div class="wp-head">
        <b>${esc(w.title)}</b>
        <span class="badge error">现状 ${esc(w.current)}</span>
        <span class="muted">基准 ${esc(w.benchmark)}</span>
      </div>
      <div class="meta">${esc(w.suggestion)}</div>
      <div class="meta muted">适用：${esc(w.apply_to)}</div>
      <div class="actions">
        <button class="btn small filled" onclick="saveWeakLesson('${esc(w.id)}')">沉淀为经验</button>
      </div>
    </div>`).join("");
}

async function saveWeakLesson(id) {
  const w = dashState.weakPoints.find((x) => x.id === id);
  if (!w) return;
  try {
    await api("/api/flywheel/lessons", {
      method: "POST", headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        title: w.title,
        conclusion: w.suggestion,
        evidence: `现状 ${w.current} vs 基准 ${w.benchmark}（薄弱点诊断）`,
        apply_to: w.apply_to,
        source: "dashboard",
      }),
    });
    toast("已沉淀为经验，可在数据飞轮查看并标记应用");
  } catch (e) {
    toast("沉淀失败: " + e.message, false);
  }
}
window.saveWeakLesson = saveWeakLesson;

function renderRows(records) {
  if (!records.length) return '<tr><td colspan="15" class="muted">暂无回填数据</td></tr>';
  return records.map((r) => noteRow(r, true)).join("");
}

// ---------- 选题 ----------
const SCORE_DIMS = [
  ["freshness", "时效"], ["heat", "热度"], ["impact", "表达"],
  ["search", "搜索"], ["durable", "持久"], ["unique", "独特"], ["cross_source", "跨源"],
];

function shortTopicMeta(c) {
  const src = (c.source || "").split("（")[0];
  const srcMap = {
    "推楼1号小时热点": "推楼1号", "今日热榜AI": "今日热榜", "谷歌趋势": "谷歌",
    "X热点": "X", "B站热门": "B站", "少数派热门": "少数派", "华尔街见闻": "见闻",
    "金十数据": "金十", "微博热搜": "微博", "知乎热榜": "知乎", "掘金趋势": "掘金",
    "36氪快讯": "36氪",
  };
  const shortSrc = srcMap[src] || (src.startsWith("hex2077") ? "hex2077"
    : src.startsWith("热点雷达") ? "雷达" : (src.slice(0, 6) || "?"));
  const formula = ((c.formulas || "").split("（")[0].split(" + ")[0] || "—")
    .replace(/\s*\[\s*|\s*\]\s*/g, "")
    .replace(/^#(\d+)(?=[^\s\d])/, "#$1 ")
    .trim();
  const meta = `${shortSrc} · ${formula}`;
  return meta.length > 20 ? meta.slice(0, 19) + "…" : meta;
}

function renderSuggestPool(tbodySel, cands, countSel, poolLabel) {
  const tbody = $(tbodySel);
  $(countSel).textContent = cands.length ? `（${cands.length} 条）` : "";
  tbody.innerHTML = cands.length
    ? cands.map((c) => {
        const titleCell = `
          <div class="t" title="${esc(c.title)}">${esc(c.title)}${c.compliance ? '<span class="badge hit">海外源</span>' : ""}</div>
          <div class="meta" title="${esc((c.source || "") + " · " + (c.view || "") + " · 公式：" + (c.formulas || "—") + (c.pool_scores ? " · " + c.pool_scores : ""))}">${esc(shortTopicMeta(c))}</div>`;
        return `
        <tr>
          <td class="title-col">${titleCell}</td>
          ${SCORE_DIMS.map(([k]) => `<td class="num">${c.breakdown_parts ? c.breakdown_parts[k] ?? "—" : "—"}</td>`).join("")}
          <td class="num score-total">${c.score ?? "?"}</td>
          <td class="actions-col">
            <button class="btn small filled" title="采纳 → 开始生产（日选题：时效×1.2+热度×1.2+质量×0.4；周选题：质量×1.2+热度×0.5+时效×0.3；IP 为准入门槛）" onclick="adopt(this,'${esc(c.title).replace(/'/g, "\\'")}')">采纳生产</button>
          </td>
        </tr>`;
      }).join("")
    : `<tr><td class="muted" colspan="${SCORE_DIMS.length + 2}">暂无${poolLabel}选题（先运行“采集热点 + 推荐”）</td></tr>`;
}

async function loadTopics() {
  loadPrefData();
  try {
    const [d, jobsRes, prodRes] = await Promise.all([
      api("/api/topics"), api("/api/jobs"), api("/api/production/status"),
    ]);
    $("#radar-path").textContent = d.radar.path ? "(" + d.radar.path + ")" : "";
    $("#suggest-path").textContent = d.suggest.path ? "(" + d.suggest.path + ")" : "";
    renderSuggestPool("#suggest-daily", d.suggest.daily || [], "#suggest-daily-count", "日");
    renderSuggestPool("#suggest-weekly", d.suggest.weekly || [], "#suggest-weekly-count", "周");
    const sources = d.radar.sources || [];
    const xSources = sources.filter((s) => /X|推楼/.test(s.source));
    const xZone = xSources.length ? `
      <div class="x-zone">
        <div class="x-zone-head">🔵 X 专区 · 推特内容（需人工复核合规）</div>
        ${xSources.flatMap((s) => s.items.slice(0, 5).map((i) => `
          <div class="x-item">
            <span class="badge primary">${esc(s.source)}</span>
            ${i.link ? `<a href="${esc(i.link)}" target="_blank" rel="noopener">${esc(i.title)}</a>` : `<span>${esc(i.title)}</span>`}
          </div>`)).join("")}
      </div>` : "";
    $("#radar-list").innerHTML = (xZone || "") + sources.map((s, idx) => `
      <details class="radar-src" ${idx === 0 || /X|推楼/.test(s.source) ? "open" : ""}>
        <summary>
          <span class="src">${esc(s.source)}</span>
          ${/X|推楼/.test(s.source) ? '<span class="badge hit">X</span>' : ""}
          <span class="badge primary">${s.items.length} 条</span>
        </summary>
        <ol>${s.items.slice(0, 12).map((i) => `<li>${i.link ? `<a href="${esc(i.link)}" target="_blank" rel="noopener">${esc(i.title)}</a>` : esc(i.title)}</li>`).join("")}</ol>
      </details>`).join("") || '<span class="muted">无热点雷达数据</span>';
    renderSources(d.sources || []);
    renderAdoptHistory((jobsRes.jobs || []), (prodRes.queue || []));
  } catch (e) {
    toast("选题加载失败: " + e.message, false);
  }
}

function renderSources(sources) {
  if (!sources.length) return $("#source-status").innerHTML = '<span class="muted">暂无信息源数据（先采集一次热点）</span>';
  $("#source-status").innerHTML = sources.map((s) => `
    <div class="src-chip">
      <span class="src-name">${esc(s.name)}</span>
      <span class="badge ${s.ok ? "success" : "error"}">${s.ok ? "成功" : "失败/未采集"}</span>
      ${s.items ? `<span class="muted">${s.items} 条</span>` : ""}
    </div>`).join("");
}

function renderAdoptHistory(jobs, queue) {
  if (!jobs.length) return $("#adopt-history").innerHTML = '<span class="muted">暂无任务，采纳选题后自动出现在这里。</span>';
  const prodMap = {};
  queue.forEach((q) => { prodMap[q.job_id] = q.status; });
  const sorted = [...jobs].sort((a, b) => String(b.updated_at || "").localeCompare(String(a.updated_at || ""))).slice(0, 8);
  $("#adopt-history").innerHTML = sorted.map((j) => {
    const pstatus = prodMap[j.job_id];
    const prodBadge = pstatus ? `<span class="badge ${pstatus === "done" ? "success" : pstatus === "failed" || pstatus === "canceled" ? "error" : "primary"}">生产 ${esc(pstatus)}</span>` : "";
    return `
      <div class="topic-item">
        <div class="t">${esc(j.theme || j.job_id)}</div>
        <div class="meta">${esc(j.job_id)} ${stateBadge(j.state)} ${prodBadge}</div>
        <div class="actions">
          <button class="btn small" onclick="goOutputs('${esc(j.job_id).replace(/'/g, "\\'")}')">查看成品/进度</button>
        </div>
      </div>`;
  }).join("");
}

async function adopt(btn, title) {
  let useTitle = String(title || "").trim();
  const chars = [...useTitle];
  if (chars.length > 60) {
    useTitle = chars.slice(0, 60).join("");
    toast("选题标题过长，已自动截断为 60 字", true);
  }
  if (!useTitle) return toast("选题标题为空，无法建任务", false);
  if (!confirm("采纳选题并开始自动生产：\n" + useTitle + "\n\n将创建任务并调用本机 Codex 后台跑完整流水线（素材→初稿→视觉→质检→归档）。")) return;
  await runWithSpin(btn, async () => {
    try {
      const d = await api("/api/topics/adopt", {
        method: "POST", headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ title: useTitle }),
      });
      toast("已创建任务并开始生产: " + d.job_id + (d.production_started ? "" : "（排队中）"));
      loadTopics();
      loadPipeline();
    } catch (e) {
      toast("建任务失败: " + e.message, false);
    }
  });
}
window.adopt = adopt;

// ---------- 主题库 ----------
let themesCache = [];

async function copyThemePrompt(id) {
  const t = themesCache.find((x) => x.id === id);
  if (!t) return;
  const prompt = [
    `请用【${t.name}】主题，按「小吴聊」IP 风格创作一期引流内容。`,
    `定位：${t.slogan}`,
    `受众：${t.audience}`,
    `钩子参考：${(t.hooks || []).join("、")}`,
    "示例选题（可选用或扩展）：",
    ...(t.samples || []).map((s, i) => `${i + 1}. ${s}`),
    "要求：硬核拆解 + 数据可视化（公众号 ≥2 个 data-viz 组件、小红书关键数字可视化），质检通过后同步公众号草稿箱，完成后汇报成品。",
  ].join("\n");
  try {
    await navigator.clipboard.writeText(prompt);
    toast("出题指令已复制，粘贴到 Codex 对话框即可");
  } catch (e) {
    const ta = document.createElement("textarea");
    ta.value = prompt;
    document.body.appendChild(ta);
    ta.select();
    document.execCommand("copy");
    ta.remove();
    toast("出题指令已复制（降级方式）");
  }
}
window.copyThemePrompt = copyThemePrompt;

// ---------- 爆款视频跟踪 ----------
let viralCache = { videos: [], ownHits: [], counts: {}, themes: [], daily: {}, sourceStatus: {}, breakdownBatch: {} };
let viralTimer = null;
let viralBusy = {};
let viralDate = "";
let showArchivedJobs = false;
let showAllLessons = false;

const VIRAL_STATUS = {
  tracked: ["待拆解", ""],
  analyzing: ["拆解中", "primary"],
  analyzed: ["已拆解", "primary"],
  applied: ["已应用", "success"],
};
const VIRAL_PLATFORMS = ["小红书", "抖音", "视频号", "B站", "快手", "X", "公众号", "其他"];

function themeName(id) {
  const t = (viralCache.themes || []).find((x) => x.id === id);
  return t ? t.name : "";
}

function fillThemeOptions() {
  const sel = $("#vf-theme");
  const prev = sel.value;
  sel.innerHTML = '<option value="">未关联</option>' +
    viralCache.themes.map((t) => `<option value="${esc(t.id)}">${esc(t.name)}</option>`).join("");
  if (prev && viralCache.themes.some((t) => t.id === prev)) sel.value = prev;
}

async function loadViral() {
  try {
    const [d, themesRes] = await Promise.all([
      api("/api/viral" + (viralDate ? "?date=" + encodeURIComponent(viralDate) : "")),
      api("/api/themes"),
    ]);
    viralCache = {
      ...d,
      themes: themesRes.themes || [],
      ownHits: d.own_hits || [],
      breakdownBatch: d.breakdown_batch || {},
      sourceStatus: d.source_status || {},
    };
    themesCache = viralCache.themes;
    $("#viral-updated-at").textContent = "更新于 " + new Date().toLocaleString("zh-CN");
    renderViralKpi(d.counts || {});
    renderViralDaily(d.daily || {});
    renderOwnHits(d.own_hits || []);
    fillThemeOptions();
    scheduleViralPoll(d.counts || {});
  } catch (e) {
    toast("爆款跟踪加载失败: " + e.message, false);
  }
}
window.loadViral = loadViral;

function setViralDate(v) {
  viralDate = v || "";
  loadViral();
}
window.setViralDate = setViralDate;

function resetViralDate() {
  viralDate = "";
  $("#viral-date").value = "";
  loadViral();
}
window.resetViralDate = resetViralDate;

function visibleJobs(jobs) {
  return showArchivedJobs ? jobs : (jobs || []).filter((j) => !j.archived);
}

function setShowArchived(show) {
  showArchivedJobs = !!show;
  if ($("#view-pipeline").classList.contains("active")) loadPipeline();
  if ($("#view-outputs").classList.contains("active")) loadOutputsView();
  if ($("#view-data").classList.contains("active")) loadData();
}
window.setShowArchived = setShowArchived;

function scheduleViralPoll(counts) {
  const analyzing = (counts.analyzing ?? 0) || (viralCache.breakdownBatch && viralCache.breakdownBatch.running ? 1 : 0);
  if (analyzing > 0 && !viralTimer) {
    viralTimer = setInterval(() => { loadViral(); }, 3000);
  } else if (analyzing === 0 && viralTimer) {
    clearInterval(viralTimer);
    viralTimer = null;
  }
}

function renderViralDaily(daily) {
  if (!Object.keys(daily).length) {
    return $("#viral-daily-grid").innerHTML = '<div class="card"><span class="muted">今日榜单为空，点「采集今日榜单」开始跟踪。</span></div>';
  }
  const order = ["小红书", "抖音", "公众号"];
  $("#viral-daily-grid").innerHTML = order.filter((p) => daily[p]).map((p) => {
    const src = (viralCache.sourceStatus || {})[p] || {};
    const rows = daily[p].map((it) => {
      const rec = viralCache.videos.find((v) => v.id === it.viral_id) || {};
      const statusBtn = statusButton(it.status, it.viral_id, rec.has_report, rec.notes || "");
      return `
        <tr>
          <td class="num">${it.rank ?? "—"}</td>
          <td class="title-col">
            ${it.link ? `<a class="t" href="${esc(it.link)}" target="_blank" rel="noopener" title="${esc(it.title)}">${esc(it.title)}</a>`
                      : `<div class="t" title="${esc(it.title)}">${esc(it.title)}</div>`}
          </td>
          <td class="num">${esc(it.heat || "—")}</td>
          <td>${statusBtn}</td>
        </tr>`;
    }).join("");
    return `
      <div class="card viral-daily-card">
        <div class="card-head">
          <h3>${esc(p)} · 今日榜单</h3>
          <span class="src-chip ${src.ok ? "" : "badge error"}">${src.ok ? `✅ ${src.items ?? 0} 条` : `❌ ${esc(src.error || "采集失败")}`}${src.mirror ? "·镜像" : ""}</span>
        </div>
        <div class="table-wrap">
          <table class="table topic-table">
            <thead><tr><th>#</th><th class="title-col">标题</th><th class="num">热度</th><th>状态</th></tr></thead>
            <tbody>${rows}</tbody>
          </table>
        </div>
      </div>`;
  }).join("");
}

function statusButton(status, vid, hasReport, note) {
  const noteTip = note ? `\n最近状态：${String(note).slice(0, 120)}` : "";
  if (status === "analyzing") {
    return '<span class="badge primary" title="拆解进行中，完成后自动更新' + esc(noteTip) + '">拆解中</span>';
  }
  const reportBtn = hasReport
    ? `<button class="btn small vstatus" title="点击查看拆解报告" onclick="viewBreakdown('${esc(vid)}')">查看报告</button>`
    : (status === "analyzed" || status === "applied")
      ? `<button class="btn small filled vstatus" title="该记录缺少报告文件，点击重新拆解${noteTip}" onclick="analyzeDailyItem('${esc(vid)}')">已拆解·重新拆</button>`
      : "";
  if (status === "applied") {
    return `<span class="badge success" title="已标记应用：该爆款已用于创作">已应用</span>${reportBtn}`;
  }
  if (status === "analyzed") {
    return `${reportBtn}<button class="btn small vstatus" title="标记该爆款已用于创作，计入已应用" onclick="setViralStatus('${esc(vid)}','applied')">标记应用</button>`;
  }
  return `<button class="btn small filled vstatus" title="点击开始 AI 拆解${noteTip}" onclick="analyzeDailyItem('${esc(vid)}')">待拆解</button>`;
}

async function analyzeDailyItem(vid) {
  const v = viralCache.videos.find((x) => x.id === vid);
  if (!v) return toast("记录不存在，请先刷新", false);
  try {
    const d = await api("/api/viral/analyze", {
      method: "POST", headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ id: vid, title: v.title, content: "", link: v.url || "", platform: v.platform || "小红书", note: "今日榜单手动拆解" }),
    });
    if (d.fallback) copyText(d.prompt || "", "codex CLI 不可用，拆解指令已复制");
    else toast("AI 拆解已启动，完成后自动入库");
    loadViral();
  } catch (e) {
    toast("拆解启动失败: " + e.message, false);
  }
}
window.analyzeDailyItem = analyzeDailyItem;

async function collectPlatformVirals() {
  try {
    toast("正在采集三平台今日榜单…");
    const d = await api("/api/viral/platform-collect", { method: "POST" });
    const parts = Object.entries(d.platforms || {}).map(([p, s]) => `${p} ${s.ok ? `✅${s.items}` : "❌"}`);
    toast(`榜单采集完成：${parts.join(" / ")}，新增 ${d.added ?? 0}`);
    loadViral();
  } catch (e) {
    toast("榜单采集失败: " + e.message, false);
  }
}
window.collectPlatformVirals = collectPlatformVirals;

async function breakdownTop() {
  try {
    const d = await api("/api/viral/breakdown-top", { method: "POST" });
    toast("已启动每平台 Top5 批量自动拆解，进度 3 秒刷新");
    loadViral();
  } catch (e) {
    toast("批量拆解启动失败: " + e.message, false);
  }
}
window.breakdownTop = breakdownTop;

async function aggregateViralWeekly() {
  if (!confirm("生成本周爆款经验包（写入经验库并自动升级 Agent SOP）？")) return;
  try {
    toast("正在聚合近 7 天拆解产物…");
    const d = await api("/api/flywheel/aggregate-viral", { method: "POST" });
    toast(`周经验包 ${d.week || ""} 已生成：${d.lessons ?? 0} 条经验，升级 ${(d.agents || []).length} 份 SOP`);
    loadViral();
    loadFlywheel();
  } catch (e) {
    toast("周经验包生成失败: " + e.message, false);
  }
}
window.aggregateViralWeekly = aggregateViralWeekly;

async function viewBreakdown(vid) {
  try {
    const d = await api("/api/viral/breakdown/" + encodeURIComponent(vid));
    const bd = d.breakdown || {};
    $("#viral-report-title").textContent = "拆解报告 · " + (bd.title || vid);
    const jsonText = Object.entries(bd).map(([k, v]) => `${k}：${v}`).join("\n");
    $("#viral-report-body").innerHTML =
      `<pre class="md-json">${esc(jsonText)}</pre>` +
      (d.report_md ? `<div class="md-divider"></div>` + renderMarkdown(d.report_md) : "");
    $("#viral-report-modal").classList.remove("hidden");
  } catch (e) {
    if (/拆解报告不存在/.test(e.message || "")) {
      toast("该记录缺少报告文件，正在转为重新拆解…", false);
      analyzeDailyItem(vid);
    } else {
      toast("读取拆解报告失败: " + e.message, false);
    }
  }
}
window.viewBreakdown = viewBreakdown;

function closeViralReport() {
  $("#viral-report-modal").classList.add("hidden");
}
window.closeViralReport = closeViralReport;

function renderViralKpi(c) {
  const items = [
    ["跟踪总数", c.total ?? 0], ["拆解中", c.analyzing ?? 0],
    ["已拆解", c.analyzed ?? 0], ["已应用", c.applied ?? 0],
  ];
  $("#viral-kpi").innerHTML = items.map(([lbl, num]) =>
    `<div class="kpi"><div class="num ${String(num).length > 5 ? "small" : ""}">${esc(num)}</div><div class="lbl">${esc(lbl)}</div></div>`).join("");
}

function renderOwnHits(hits) {
  if (!hits.length) {
    return $("#own-hits").innerHTML = '<span class="muted">暂无爆款命中记录（回填时命中 hit 会自动出现在这里）。</span>';
  }
  $("#own-hits").innerHTML = hits.map((h) => {
    const v = (viralCache.videos || []).find((x) => x.source_job === h.job_id
      || String(x.notes || "").includes(h.job_id));
    const status = v ? v.status : "tracked";
    const btn = v
      ? statusButton(status, v.id, v.has_report, v.notes || "")
      : `<button class="btn small filled" title="点击转入跟踪并启动 AI 拆解" onclick="importOwnHit('${esc(h.job_id).replace(/'/g, "\\'")}')">转入跟踪并拆解</button>`;
    return `
      <div class="topic-item">
        <div class="t">🔥 ${esc(h.title)}</div>
        <div class="meta">${esc(h.platform)} · 阅读 ${fmtNum(h.reads)} ｜ 赞 ${fmtNum(h.likes)} ｜ 互动率 ${pct(h.engagement)}<span class="muted"> · ${esc(h.job_id)}</span></div>
        <div class="actions">${btn}</div>
      </div>`;
  }).join("");
}

function toggleViralForm(hideOnly) {
  const card = $("#viral-form-card");
  const opening = card.classList.contains("hidden");
  card.classList.toggle("hidden");
  if (!opening || hideOnly) return;
  card.scrollIntoView({ behavior: "smooth", block: "start" });
  $("#vf-title").focus();
}
window.toggleViralForm = toggleViralForm;

function resetViralForm() {
  $("#vf-id").value = "";
  $("#viral-form-title").textContent = "添加爆款视频";
  ["vf-platform", "vf-theme", "vf-formula", "vf-published", "vf-title", "vf-author",
   "vf-url", "vf-content", "vf-hook", "vf-structure", "vf-why", "vf-notes"].forEach((id) => {
    const el = document.getElementById(id);
    if (el && el.tagName !== "SELECT") el.value = "";
  });
  $("#vf-platform").value = "小红书";
  $("#vf-theme").value = "";
  $("#vf-reads").value = "0";
  $("#vf-likes").value = "0";
  $("#vf-collects").value = "0";
  $("#vf-comments").value = "0";
  fillThemeOptions();
}

function editViral(id) {
  const v = viralCache.videos.find((x) => x.id === id);
  if (!v) return;
  $("#vf-id").value = v.id;
  $("#viral-form-title").textContent = "编辑爆款 · " + v.title.slice(0, 18);
  $("#vf-platform").value = VIRAL_PLATFORMS.includes(v.platform) ? v.platform : "其他";
  $("#vf-title").value = v.title || "";
  $("#vf-author").value = v.author || "";
  $("#vf-url").value = v.url || "";
  $("#vf-published").value = v.published_at || "";
  $("#vf-reads").value = v.reads || 0;
  $("#vf-likes").value = v.likes || 0;
  $("#vf-collects").value = v.collects || 0;
  $("#vf-comments").value = v.comments || 0;
  $("#vf-theme").value = v.theme || "";
  $("#vf-hook").value = v.hook || "";
  $("#vf-structure").value = v.structure || "";
  $("#vf-why").value = v.why_viral || "";
  $("#vf-formula").value = v.formula || "";
  $("#vf-notes").value = v.notes || "";
  const card = $("#viral-form-card");
  card.classList.remove("hidden");
  card.scrollIntoView({ behavior: "smooth", block: "start" });
}
window.editViral = editViral;

async function importOwnHit(jobId) {
  const h = (viralCache.ownHits || []).find((x) => x.job_id === jobId);
  if (!h) return toast("未找到该爆款记录", false);
  if (viralBusy["own:" + jobId]) return;
  viralBusy["own:" + jobId] = true;
  const platform = VIRAL_PLATFORMS.includes(h.platform) ? h.platform : "小红书";
  const note = "来自自家爆款复盘（" + jobId + "）";
  const title = String(h.title || jobId).slice(0, 120);
  try {
    const saved = await api("/api/viral", {
      method: "POST", headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        platform, title, author: "小吴聊（自家）",
        url: h.url || "", published_at: (h.collected_at || "").slice(0, 10),
        reads: h.reads || 0, likes: h.likes || 0, collects: h.collects || 0,
        comments: h.comments || 0, theme: "", hook: "", structure: "",
        why_viral: "", formula: "", status: "tracked", notes: note,
        source_job: jobId,
      }),
    });
    const vid = saved.video.id;
    const d = await api("/api/viral/analyze", {
      method: "POST", headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ id: vid, title, content: "",
                             link: h.url || "", platform, note }),
    });
    if (d.fallback) {
      copyText(d.prompt || "", "codex CLI 不可用，拆解指令已复制，粘贴到 Codex 执行");
    } else {
      toast("已转入拆解：AI 拆解后台进行中，状态会实时刷新");
    }
    loadViral();
  } catch (e) {
    toast("转入失败: " + e.message, false);
  } finally {
    delete viralBusy["own:" + jobId];
  }
}
window.importOwnHit = importOwnHit;

async function copyViralPrompt(id) {
  const v = viralCache.videos.find((x) => x.id === id);
  if (!v) return;
  const prompt = [
    "请学习这个爆款案例，用于新一期内容创作（只学方法，不照搬原文）：",
    `【平台】${v.platform}`,
    `【标题】${v.title}`,
    `【数据】播放/阅读 ${fmtNum(v.reads)} ｜ 赞 ${fmtNum(v.likes)} ｜ 藏 ${fmtNum(v.collects)} ｜ 评 ${fmtNum(v.comments)}`,
    `【关联主题】${themeName(v.theme)}`,
    `【开头钩子】${v.hook || "—"}`,
    `【内容结构】${v.structure || "—"}`,
    `【爆点归因】${v.why_viral || "—"}`,
    `【可复用公式】${v.formula || "—"}`,
    "要求：复用选题角度/结构/公式，结合本期主题重新创作，不得复制原句。",
  ].join("\n");
  copyText(prompt, "爆款拆解指令已复制，粘贴给 Codex 即可");
}
window.copyViralPrompt = copyViralPrompt;

async function setViralStatus(id, status) {
  const v = viralCache.videos.find((x) => x.id === id);
  if (!v) return;
  try {
    await api("/api/viral", {
      method: "POST", headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ ...v, status }),
    });
    toast(status === "applied" ? "已标记应用，可重新生成反哺指令包" : "已标记拆解");
    loadViral();
  } catch (e) {
    toast("更新失败: " + e.message, false);
  }
}
window.setViralStatus = setViralStatus;

async function deleteViral(id) {
  const v = viralCache.videos.find((x) => x.id === id);
  if (!v || !confirm("删除爆款记录：\n" + v.title)) return;
  try {
    await api("/api/viral/" + encodeURIComponent(id), { method: "DELETE" });
    toast("已删除");
    loadViral();
  } catch (e) {
    toast("删除失败: " + e.message, false);
  }
}
window.deleteViral = deleteViral;

async function analyzeViral() {
  const payload = {
    id: $("#vf-id").value.trim(),
    title: $("#vf-title").value.trim(),
    content: $("#vf-content").value.trim(),
    link: $("#vf-url").value.trim(),
    platform: $("#vf-platform").value,
    note: $("#vf-notes").value.trim(),
  };
  if (!payload.title) return toast("请先填写标题", false);
  if (!payload.content && !payload.id) return toast("请粘贴原文/逐字稿，或先保存一条爆款再拆解", false);
  try {
    const d = await api("/api/viral/analyze", {
      method: "POST", headers: { "Content-Type": "application/json" },
      body: JSON.stringify(payload),
    });
    if (d.fallback) {
      copyText(d.prompt || "", "codex CLI 不可用，拆解指令已复制，粘贴到 Codex 对话框执行");
    } else {
      toast("AI 拆解已启动，完成后自动入库（拆解中状态）");
    }
    toggleViralForm(true);
    loadViral();
  } catch (e) {
    toast("拆解启动失败: " + e.message, false);
  }
}
window.analyzeViral = analyzeViral;

$("#viral-form").addEventListener("submit", async (e) => {
  e.preventDefault();
  const existing = viralCache.videos.find((x) => x.id === $("#vf-id").value);
  const payload = {
    id: $("#vf-id").value.trim(),
    platform: $("#vf-platform").value,
    title: $("#vf-title").value.trim(),
    author: $("#vf-author").value.trim(),
    url: $("#vf-url").value.trim(),
    published_at: $("#vf-published").value.trim(),
    reads: parseInt($("#vf-reads").value, 10) || 0,
    likes: parseInt($("#vf-likes").value, 10) || 0,
    collects: parseInt($("#vf-collects").value, 10) || 0,
    comments: parseInt($("#vf-comments").value, 10) || 0,
    theme: $("#vf-theme").value,
    hook: $("#vf-hook").value.trim(),
    structure: $("#vf-structure").value.trim(),
    why_viral: $("#vf-why").value.trim(),
    formula: $("#vf-formula").value.trim(),
    status: existing ? existing.status : "tracked",
    notes: $("#vf-notes").value.trim(),
  };
  if (!payload.title) return toast("标题不能为空", false);
  try {
    const d = await api("/api/viral", {
      method: "POST", headers: { "Content-Type": "application/json" },
      body: JSON.stringify(payload),
    });
    toast(d.action === "updated" ? "爆款记录已更新" : "已加入爆款跟踪");
    toggleViralForm(true);
    loadViral();
  } catch (err) {
    toast("保存失败: " + err.message, false);
  }
});

// ---------- 数据飞轮 ----------
let flywheelCache = { stats: {}, lessons: [], feedback: "" };

function renderFlywheelStages(d) {
  const s = d.stats || {};
  const m = d.market || {};
  const lessons = d.lessons || [];
  const applied = lessons.filter((l) => l.applied).length;
  const radarName = m.radar && m.radar.path ? m.radar.path.split("/").pop() : "未采集";
  const stages = [
    ["1", "✍️", "写稿发布", `${s.publish_events ?? 0} 次发布动作`, "publish_log 自动记录"],
    ["2", "📈", "账户数据反馈", `${s.backfill_records ?? 0} 条回填/导入 ｜ 总阅读 ${fmtNum(s.total_reads)}`, `互动率 ${pct(s.avg_engagement)} ｜ 爆款 ${s.hits ?? 0}`],
    ["3", "🌐", "结合市场数据学习", `热点雷达 ${m.radar ? m.radar.items : 0} 条 ｜ 选题 ${m.suggest ? m.suggest.items : 0} 条`, radarName],
    ["4", "🧠", "总结经验", `${lessons.length} 条经验 ｜ 已应用 ${applied} 条`, "证据来自账户数据 + 爆款拆解"],
    ["5", "🔁", "反哺流水线 Agent", d.feedback ? "反哺指令包已就绪" : "反哺指令包未生成", d.feedback ? "复制即可喂给 Codex" : "点上方按钮生成"],
  ];
  $("#flywheel-stages").innerHTML = stages.map(([no, emoji, name, stat, sub]) => `
    <div class="fw-stage">
      <div class="fw-head">
        <span class="fw-no">${no}</span>
        <span class="fw-emoji">${emoji}</span>
        <span class="fw-name">${esc(name)}</span>
      </div>
      <div class="fw-stat">${esc(stat)}</div>
      <div class="fw-sub muted">${esc(sub)}</div>
    </div>`).join("");
}

function renderLessonList(lessons) {
  if (!lessons.length) {
    return $("#lesson-list").innerHTML = '<span class="muted">暂无经验。先在爆款跟踪里拆解案例，或在下方沉淀第一条经验。</span>';
  }
  const cutoff = new Date(Date.now() - 56 * 864e5).toISOString().slice(0, 10);
  const recent = lessons.filter((l) => String(l.updated_at || l.created_at || "").slice(0, 10) >= cutoff);
  const older = lessons.filter((l) => !recent.includes(l));
  const shown = showAllLessons ? lessons : (recent.length ? recent : lessons);
  const html = shown.map((l) => `
    <div class="lesson-item ${l.applied ? "applied" : ""}">
      <div class="head">
        <b>${esc(l.title)}</b>
        <span class="badge ${l.applied ? "success" : ""}">${l.applied ? "已应用" : "待应用"}</span>
      </div>
      <div class="meta">${esc(l.conclusion)}</div>
      <div class="meta muted">证据：${esc(l.evidence || "—")} ｜ 适用：${esc(l.apply_to || "—")}</div>
      <div class="actions">
        <button class="btn small tonal" onclick="toggleLesson('${esc(l.id)}')">${l.applied ? "取消应用" : "标记已应用"}</button>
        <button class="btn small" onclick="editLesson('${esc(l.id)}')">编辑</button>
        <button class="btn small danger" onclick="deleteLesson('${esc(l.id)}')">删除</button>
      </div>
    </div>`).join("");
  const expand = (older.length && !showAllLessons)
    ? `<button class="btn small tonal" onclick="toggleAllLessons()">展开历史经验（${older.length} 条）</button>`
    : (showAllLessons ? `<button class="btn small tonal" onclick="toggleAllLessons()">收起历史经验</button>` : "");
  $("#lesson-list").innerHTML = html + (expand ? `<div style="margin-top:8px">${expand}</div>` : "");
}

function toggleAllLessons() {
  showAllLessons = !showAllLessons;
  loadFlywheel();
}
window.toggleAllLessons = toggleAllLessons;

async function loadFlywheel() {
  try {
    const d = await api("/api/flywheel");
    flywheelCache = d;
    $("#flywheel-updated-at").textContent = "更新于 " + (d.generated_at || "");
    $("#feedback-path").textContent = d.feedback_path ? "(" + d.feedback_path + ")" : "";
    renderFlywheelStages(d);
    renderLessonList(d.lessons || []);
    $("#feedback-preview").textContent = d.feedback || "反哺指令包尚未生成，点「重新生成」从账户数据 + 经验 + 爆款公式自动组装。";
  } catch (e) {
    toast("数据飞轮加载失败: " + e.message, false);
  }
}
window.loadFlywheel = loadFlywheel;

function resetLessonForm() {
  $("#lf-id").value = "";
  $("#lf-title").value = "";
  $("#lf-conclusion").value = "";
  $("#lf-evidence").value = "";
  $("#lf-apply").value = "";
}

function editLesson(id) {
  const l = flywheelCache.lessons.find((x) => x.id === id);
  if (!l) return;
  $("#lf-id").value = l.id;
  $("#lf-title").value = l.title || "";
  $("#lf-conclusion").value = l.conclusion || "";
  $("#lf-evidence").value = l.evidence || "";
  $("#lf-apply").value = l.apply_to || "";
  document.getElementById("lesson-form").scrollIntoView({ behavior: "smooth", block: "start" });
}
window.editLesson = editLesson;

async function toggleLesson(id) {
  const l = flywheelCache.lessons.find((x) => x.id === id);
  if (!l) return;
  try {
    await api("/api/flywheel/lessons", {
      method: "POST", headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ ...l, applied: !l.applied }),
    });
    toast(l.applied ? "已取消应用标记" : "已标记应用，重新生成反哺包即可生效");
    loadFlywheel();
  } catch (e) {
    toast("更新失败: " + e.message, false);
  }
}
window.toggleLesson = toggleLesson;

async function deleteLesson(id) {
  const l = flywheelCache.lessons.find((x) => x.id === id);
  if (!l || !confirm("删除经验：\n" + l.title)) return;
  try {
    await api("/api/flywheel/lessons/" + encodeURIComponent(id), { method: "DELETE" });
    toast("已删除");
    loadFlywheel();
  } catch (e) {
    toast("删除失败: " + e.message, false);
  }
}
window.deleteLesson = deleteLesson;

$("#lesson-form").addEventListener("submit", async (e) => {
  e.preventDefault();
  const payload = {
    id: $("#lf-id").value.trim(),
    title: $("#lf-title").value.trim(),
    conclusion: $("#lf-conclusion").value.trim(),
    evidence: $("#lf-evidence").value.trim(),
    apply_to: $("#lf-apply").value.trim(),
    source: "manual",
    applied: flywheelCache.lessons.find((x) => x.id === $("#lf-id").value)?.applied || false,
  };
  if (!payload.title || !payload.conclusion) return toast("经验标题和结论不能为空", false);
  try {
    const d = await api("/api/flywheel/lessons", {
      method: "POST", headers: { "Content-Type": "application/json" },
      body: JSON.stringify(payload),
    });
    toast(d.action === "updated" ? "经验已更新" : "经验已沉淀");
    resetLessonForm();
    loadFlywheel();
  } catch (err) {
    toast("保存失败: " + err.message, false);
  }
});

function copyFeedback() {
  if (!flywheelCache.feedback) return toast("反哺指令包为空，请先重新生成", false);
  copyText(flywheelCache.feedback, "反哺指令包已复制，粘贴到 Codex 对话框即可");
}
window.copyFeedback = copyFeedback;

async function runRegenerate() {
  try {
    toast("正在重新生成反哺指令包…");
    const d = await api("/api/flywheel/regenerate", { method: "POST" });
    flywheelCache.feedback = d.feedback || "";
    $("#feedback-preview").textContent = d.feedback || "";
    $("#feedback-path").textContent = d.path ? "(" + d.path + ")" : "";
    const n = d.agents && d.agents.agents ? d.agents.agents.length : 0;
    toast(`反哺指令包已重新生成，并自动升级 ${n} 份 Agent SOP`);
    loadFlywheel();
  } catch (e) {
    toast("生成失败: " + e.message, false);
  }
}
window.runRegenerate = runRegenerate;

async function runFlywheelWeekly() {
  if (!confirm("生成质量周报（复盘数据将进入数据飞轮）？")) return;
  toast("周报生成中（最长 180s）…");
  try {
    const d = await api("/api/pipeline/run", {
      method: "POST", headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ action: "weekly" }),
    });
    toast(d.ok ? "周报已生成" : "周报生成有阻塞项，见控制台", d.ok);
    loadFlywheel();
  } catch (e) {
    toast("周报生成失败: " + e.message, false);
  }
}
window.runFlywheelWeekly = runFlywheelWeekly;

async function runPipeline(action) {
  const labels = { topics: "采集热点+选题推荐", recycle: "48h 回收检查", weekly: "质量周报" };
  if (!confirm("运行流水线动作：" + (labels[action] || action) + "？")) return;
  toast("流水线运行中（最长 180s）…");
  try {
    const d = await api("/api/pipeline/run", {
      method: "POST", headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ action }),
    });
    toast(d.ok ? labels[action] + " 完成" : "有阻塞项，见浏览器控制台", d.ok);
    console.log((d.stdout || "") + (d.stderr || ""));
    if (action === "topics") loadTopics();
    else loadOverview();
  } catch (e) {
    toast("流水线失败: " + e.message, false);
  }
}
window.runPipeline = runPipeline;

// ---------- 流水线 ----------
let pipelineJobs = [];
let prodTimer = null;

function scheduleProdPoll() {
  if (prodTimer) clearInterval(prodTimer);
  prodTimer = setInterval(() => loadPipeline(true), 3000);
}

async function loadPipeline(silent) {
  try {
    const [jobsRes, agentsRes, prodRes] = await Promise.all([
      api("/api/jobs"), api("/api/agents"), api("/api/production/status"),
    ]);
    pipelineJobs = jobsRes.jobs;
    const sel = $("#pipeline-job-select");
    const prev = sel.value;
    sel.innerHTML = visibleJobs(pipelineJobs).map((j) =>
      `<option value="${esc(j.job_id)}">${esc(j.job_id)} · ${esc(j.theme || "")}</option>`).join("");
    if (prev && visibleJobs(pipelineJobs).some((j) => j.job_id === prev)) sel.value = prev;
    renderPipelineJob();
    renderAgents(agentsRes.agents);
    renderProduction(prodRes);
    const active = (prodRes.queue || []).some((q) => ["queued", "running"].includes(q.status));
    if (active) scheduleProdPoll();
    else if (prodTimer) { clearInterval(prodTimer); prodTimer = null; }
  } catch (e) {
    if (!silent) toast("流水线加载失败: " + e.message, false);
  }
}
window.loadPipeline = loadPipeline;

function renderProduction(prod) {
  const queue = prod.queue || [];
  const running = prod.running;
  $("#prod-meta").textContent = running
    ? `正在生产：${running.job_id}（${running.started_at}）`
    : (queue.some((q) => q.status === "queued") ? "有排队任务" : "当前无生产任务");
  const statusBadge = (s) => ({
    queued: ["排队中", "primary"], running: ["生产中", ""],
    done: ["已完成", "success"], failed: ["失败", "error"], canceled: ["已取消", ""],
  }[s] || [s, ""]);
  $("#prod-queue").innerHTML = queue.length ? queue.map((q) => {
    const [label, cls] = statusBadge(q.status);
    return `
      <div class="topic-item">
        <div class="t">${esc(q.job_id)} <span class="badge ${cls}">${label}</span></div>
        <div class="meta">创建 ${esc(q.created_at || "—")}${q.started_at ? " ｜ 开始 " + esc(q.started_at) : ""}${q.finished_at ? " ｜ 结束 " + esc(q.finished_at) : ""}</div>
        ${q.error ? `<div class="meta" style="color:var(--error)">${esc(q.error)}</div>` : ""}
        <div class="actions">
          ${["queued", "running"].includes(q.status) ? `<button class="btn small danger" onclick="cancelProduction('${esc(q.job_id)}')">取消</button>` : ""}
          ${["done", "failed", "canceled"].includes(q.status) ? `<button class="btn small tonal" onclick="rerunProduction('${esc(q.job_id)}')">重新生产</button>` : ""}
        </div>
      </div>`;
  }).join("") : '<span class="muted">暂无生产任务（在选题页“采纳 → 开始生产”即可入队）</span>';
  $("#prod-log").textContent = prod.log || (running ? "日志生成中…" : "暂无日志");
}

async function cancelProduction(jobId) {
  if (!confirm("取消生产任务？\n" + jobId)) return;
  try {
    await api("/api/production/" + encodeURIComponent(jobId) + "/cancel", { method: "POST" });
    toast("已发送取消指令");
    loadPipeline();
  } catch (e) {
    toast("取消失败: " + e.message, false);
  }
}
window.cancelProduction = cancelProduction;

async function rerunProduction(jobId) {
  if (!confirm("重新生产该任务？\n" + jobId)) return;
  try {
    await api("/api/production/" + encodeURIComponent(jobId) + "/rerun", { method: "POST" });
    toast("已重新入队");
    loadPipeline();
  } catch (e) {
    toast("重跑失败: " + e.message, false);
  }
}
window.rerunProduction = rerunProduction;

function renderPipelineJob() {
  const jobId = $("#pipeline-job-select").value;
  const job = pipelineJobs.find((j) => j.job_id === jobId);
  $("#pipeline-job-meta").textContent = job ? `${esc(job.theme || "")} · 更新于 ${esc(job.updated_at || "")}` : "";
  const idx = job ? STATE_ORDER.indexOf(job.state) : -1;
  $("#state-stepper").innerHTML = STATE_ORDER.map((st, i) => {
    const cls = i < idx ? "done" : i === idx ? "current" : "";
    return `<div class="step ${cls}">
      <span class="dot">${i < idx ? "✓" : i + 1}</span>
      <span class="sname">${esc(STATE_LABELS[st])}</span>
      <span class="agent">${esc(STATE_AGENTS[st])}</span>
    </div>`;
  }).join("");
}
window.renderPipelineJob = renderPipelineJob;

function renderAgents(agents) {
  $("#agent-cards").innerHTML = agents.map((a) => `
    <div class="agent-card">
      <div class="head">
        <span class="emoji">${a.emoji}</span>
        <div>
          <div class="role">${esc(a.role)}</div>
          <div class="en">${esc(a.en)} · 活跃 ${a.active_count}</div>
        </div>
      </div>
      <div class="resp">${esc(a.responsibility)}</div>
      ${a.doc && a.doc.doc ? `<div class="kv" style="margin-bottom:8px">
          <button class="btn small tonal" onclick="viewAgentDoc('${esc(a.role)}')">📄 查看 SOP 文档</button>
          <span class="muted">v${esc(a.doc.version || "—")} · 更新 ${esc(a.doc.updated_at || "—")} · 经验 ${a.doc.patches ?? 0} 条</span>
        </div>` : ""}
      <div class="jobs">
        ${a.active_jobs.length ? a.active_jobs.map((j) => `
          <button class="chip" title="${esc(j.theme || "")}" onclick="goOutputs('${esc(j.job_id)}')">
            ${esc(j.job_id)} <span class="state">${esc(STATE_LABELS[j.state] || j.state)}</span>
          </button>`).join("") : '<span class="muted">当前无活跃任务</span>'}
      </div>
      ${a.active_jobs.flatMap((j) => j.outputs).slice(0, 3).map((o) => `
        <div class="kv" style="margin-top:6px">
          <b>${esc(o.platform)}</b> <a href="${esc(o.url)}" target="_blank">${esc(o.file)}</a>
        </div>`).join("")}
    </div>`).join("");
}

async function viewAgentDoc(role) {
  try {
    const d = await api("/api/agents/doc?role=" + encodeURIComponent(role));
    $("#agent-doc-title").textContent = d.role + " · SOP（" + d.doc + "）";
    $("#agent-doc-body").innerHTML = renderMarkdown(d.content);
    $("#agent-doc-modal").classList.remove("hidden");
  } catch (e) {
    toast("读取文档失败: " + e.message, false);
  }
}
window.viewAgentDoc = viewAgentDoc;

function closeAgentDoc() {
  $("#agent-doc-modal").classList.add("hidden");
}
window.closeAgentDoc = closeAgentDoc;

async function goOutputs(jobId) {
  try {
    const d = await api("/api/jobs");
    const sel = $("#outputs-job-select");
    sel.innerHTML = d.jobs.map((j) =>
      `<option value="${esc(j.job_id)}">${esc(j.job_id)} · ${esc(j.theme || "")}</option>`).join("");
    sel.value = jobId;
    switchView("outputs");
    renderOutputs();
  } catch (e) {
    toast("跳转失败: " + e.message, false);
  }
}
window.goOutputs = goOutputs;

// ---------- 成品库 ----------
let outputsJobsCache = [];
let outputsPubFilter = "all";
let outputsMonth = "";

function filterOutputsJobs() {
  let list = outputsJobsCache;
  if (outputsPubFilter === "published") list = list.filter((j) => j.published);
  if (outputsPubFilter === "unpublished") list = list.filter((j) => !j.published);
  if (outputsPubFilter !== "unpublished" && outputsMonth) {
    list = list.filter((j) => j.month === outputsMonth);
  }
  return list;
}

function rebuildOutputsSelect() {
  const sel = $("#outputs-job-select");
  const prev = sel.value;
  const list = visibleJobs(filterOutputsJobs());
  sel.innerHTML = list.map((j) =>
    `<option value="${esc(j.job_id)}">${esc(j.job_id)} · ${esc(j.theme || "")}</option>`).join("");
  if (prev && list.some((j) => j.job_id === prev)) {
    sel.value = prev;
  } else if (list.length) {
    sel.value = list[0].job_id;
  }
  renderOutputs();
}

function setOutputsPubFilter(pub) {
  outputsPubFilter = pub;
  $$("#outputs-pub-toggle .tab").forEach((b) => b.classList.toggle("active", b.dataset.pub === pub));
  rebuildOutputsSelect();
}
window.setOutputsPubFilter = setOutputsPubFilter;

function setOutputsMonth(month) {
  outputsMonth = month;
  rebuildOutputsSelect();
}
window.setOutputsMonth = setOutputsMonth;

async function loadOutputsView() {
  try {
    const d = await api("/api/jobs");
    outputsJobsCache = d.jobs;
    const months = [...new Set(d.jobs.filter((j) => j.month).map((j) => j.month))].sort().reverse();
    const msel = $("#outputs-month-select");
    const prevMonth = msel.value;
    msel.innerHTML = '<option value="">全部月份</option>' +
      months.map((m) => `<option value="${esc(m)}">${esc(m)}</option>`).join("");
    if (prevMonth && months.includes(prevMonth)) msel.value = prevMonth;
    else outputsMonth = "";
    rebuildOutputsSelect();
  } catch (e) {
    toast("成品库加载失败: " + e.message, false);
  }
}

async function renderOutputs() {
  const jobId = $("#outputs-job-select").value;
  artifactState = { jobId, files: [], tab: artifactState.tab || "xhs", imgIdx: 0 };
  if (!jobId) {
    $("#artifact-frame").innerHTML = '<span class="muted">请选择任务</span>';
    return;
  }
  try {
    const d = await api("/api/outputs/" + encodeURIComponent(jobId));
    artifactState.files = d.files || [];
    renderArtifactSide(jobId);
    switchArtifact(artifactState.tab);
  } catch (e) {
    $("#artifact-frame").innerHTML = '<span class="muted">加载失败: ' + esc(e.message) + "</span>";
  }
}
window.renderOutputs = renderOutputs;

function filesByPlatform(plat) {
  return artifactState.files.filter((f) => f.rel.startsWith(plat + "/"));
}

function switchArtifact(tab) {
  artifactState.tab = tab;
  artifactState.imgIdx = 0;
  $$("#artifact-tabs .tab").forEach((t) => t.classList.toggle("active", t.dataset.artifact === tab));
  const box = $("#artifact-frame");
  const carousel = $("#carousel");
  carousel.classList.add("hidden");
  if (!artifactState.files.length) {
    box.innerHTML = '<span class="muted">该任务暂无产出文件</span>';
    return;
  }
  const prefix = tab === "xhs" ? "小红书" : tab === "gzh" ? "公众号" : "短视频";
  const files = filesByPlatform(prefix);
  if (!files.length) {
    box.innerHTML = `<span class="muted">${prefix} 暂无成品</span>`;
    return;
  }

  if (tab === "xhs") {
    const imgs = files.filter((f) => f.kind === "img" && /^xhs-\d+\.(png|jpg|jpeg)$/i.test(f.rel.split("/").pop()));
    const slides = files.find((f) => f.kind === "html" && /slides/i.test(f.rel));
    const md = files.find((f) => f.kind === "md" && f.rel.endsWith("文案.md"));
    if (imgs.length) {
      carousel.classList.remove("hidden");
      renderCarousel(imgs);
      box.innerHTML = "";
    } else {
      box.innerHTML = '<span class="muted">暂无卡片截图</span>';
      // 有卡片图文时不再重复展示 slides HTML；仅无截图时用它兜底预览
      if (slides) box.innerHTML += `<div class="frame-box" style="margin-top:14px"><iframe src="/assets/outputs/${encodeURIComponent(artifactState.jobId)}/${esc(slides.rel)}"></iframe></div>`;
    }
    if (md) renderMd(md, box);
    if (!md) box.innerHTML += '<span class="muted">（无文案）</span>';
  } else if (tab === "gzh") {
    const preview = files.find((f) => f.kind === "html" && /预览/i.test(f.rel));
    const main = files.find((f) => f.kind === "html" && /排版/.test(f.rel) && !/预览/.test(f.rel));
    const md = files.find((f) => f.kind === "md" && f.rel.endsWith("文案.md"));
    const target = preview || main;
    if (target) {
      box.innerHTML = `<div class="frame-box"><iframe src="/assets/outputs/${encodeURIComponent(artifactState.jobId)}/${esc(target.rel)}"></iframe></div>`;
    } else {
      box.innerHTML = '<span class="muted">暂无公众号排版 HTML</span>';
    }
    if (md) renderMd(md, box);
  } else {
    const scripts = files.filter((f) => f.kind === "md" && /120s|分镜/i.test(f.rel));
    if (scripts.length) {
      box.innerHTML = "";
      scripts.forEach((f) => renderMd(f, box));
    } else {
      box.innerHTML = '<span class="muted">暂无短视频分镜脚本</span>';
    }
  }
}
window.switchArtifact = switchArtifact;

// ---------- 人工发布操作（标记手动发布） ----------

$("#btn-mark-publish").addEventListener("click", async () => {
  const jobId = artifactState.jobId;
  if (!jobId) return toast("请先选择任务", false);
  const platform = $("#mark-platform").value;
  try {
    const d = await api("/api/publish/manual", {
      method: "POST", headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ job_id: jobId, platform }),
    });
    toast((d.stdout || "已标记手动发布").trim().split("\n")[0]);
    loadOutputsView();
  } catch (err) {
    toast("标记失败: " + err.message, false);
  }
});

$("#btn-gzh-draft").addEventListener("click", async () => {
  const jobId = artifactState.jobId;
  if (!jobId) return toast("请先选择一个任务", false);
  if (!confirm("把当前任务推送到公众号草稿箱？\n（需已认证公众号并配置 AppID/Secret）")) return;
  toast("正在推送草稿…");
  try {
    const d = await api("/api/publish/gzh-draft", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ job_id: jobId }),
    });
    toast("草稿已推送到公众号草稿箱，请到公众平台检查后群发");
  } catch (e) {
    toast("推送失败: " + e.message, false);
  }
});

async function viewPublishGuide() {
  try {
    const d = await api("/api/docs/publish-guide");
    $("#agent-doc-title").textContent = d.title;
    $("#agent-doc-body").innerHTML = renderMarkdown(d.content);
    $("#agent-doc-modal").classList.remove("hidden");
  } catch (e) {
    toast("读取发布指引失败: " + e.message, false);
  }
}
window.viewPublishGuide = viewPublishGuide;

function renderCarousel(imgs) {
  const jobId = artifactState.jobId;
  const url = (f) => "/assets/outputs/" + encodeURIComponent(jobId) + "/" + f.rel;
  const cur = imgs[artifactState.imgIdx];
  const carousel = $("#carousel");
  carousel.innerHTML = `
    <div class="carousel-main">
      <img src="${esc(url(cur))}" alt="卡片 ${artifactState.imgIdx + 1}">
      <button class="carousel-nav prev" onclick="carouselStep(-1)">‹</button>
      <button class="carousel-nav next" onclick="carouselStep(1)">›</button>
    </div>
    <div class="carousel-thumbs">
      ${imgs.map((f, i) => `<img class="thumb ${i === artifactState.imgIdx ? "active" : ""}" src="${esc(url(f))}" onclick="carouselJump(${i})">`).join("")}
    </div>`;
  artifactState._imgs = imgs;
}

function carouselStep(delta) {
  const imgs = artifactState._imgs || [];
  if (!imgs.length) return;
  artifactState.imgIdx = (artifactState.imgIdx + delta + imgs.length) % imgs.length;
  renderCarousel(imgs);
}
function carouselJump(i) {
  const imgs = artifactState._imgs || [];
  if (i >= 0 && i < imgs.length) { artifactState.imgIdx = i; renderCarousel(imgs); }
}
window.carouselStep = carouselStep;
window.carouselJump = carouselJump;

function stripFrontmatter(content) {
  return (content || "").replace(/^---[\s\S]*?\n---\s*/, "");
}

// 把小红书文案清洗成可直贴文本：去掉旧版三选一/Markdown 符号，只留标题+正文
function cleanXhsMd(content) {
  let c = stripFrontmatter(content);
  const legacyOpt = c.match(/选项\s*1[^\n]*?[：:]\s*([^\n（(]+)/);
  c = c.replace(/^#\s*📕[^\n]*\n/, "");
  c = c.replace(/^##\s*📌\s*标题选择：[^\n]*\n[\s\S]*?\n---\s*/, "");
  c = c.replace(/^##\s*📝\s*笔记正文：[^\n]*\n/, "");
  c = c.replace(/^#{1,6}\s*/gm, "");
  c = c.replace(/\*\*/g, "");
  c = c.replace(/^---\s*$/gm, "");
  c = c.replace(/^[-*]\s+/gm, "");
  if (legacyOpt && legacyOpt[1]) c = legacyOpt[1].trim() + "\n\n" + c;
  return c.replace(/\n{3,}/g, "\n\n").trim();
}

function fallbackCopy(text) {
  const ta = document.createElement("textarea");
  ta.value = text;
  document.body.appendChild(ta);
  ta.select();
  document.execCommand("copy");
  ta.remove();
}

async function copyText(text, msg) {
  try {
    await navigator.clipboard.writeText(text);
    toast(msg);
  } catch (e) {
    fallbackCopy(text);
    toast(msg + "（降级方式）");
  }
}
window.copyText = copyText;

function copyXhs(kind) {
  const t = artifactState._xhs || {};
  const text = kind === "title" ? t.title : t.body;
  if (!text) return;
  copyText(text, kind === "title" ? "标题已复制，可直接粘贴到小红书" : "正文已复制，可直接粘贴到小红书");
}
window.copyXhs = copyXhs;

async function renderMd(file, box) {
  try {
    const d = await api("/api/outputs/" + encodeURIComponent(artifactState.jobId) + "/file?rel=" + encodeURIComponent(file.rel));
    const div = document.createElement("div");
    div.className = "frame-box";
    div.style.cssText = "margin-top:14px;padding:16px;";
    if (artifactState.tab === "xhs") {
      const clean = cleanXhsMd(d.content || "");
      const title = clean.split(/\r?\n/).find((l) => l.trim())?.trim() || "";
      const body = clean.slice(title.length).replace(/^\s*\n+/, "").trim();
      artifactState._xhs = { title, body };
      const titleLen = title ? [...title].length : 0;
      const bodyLen = body ? [...body].length : 0;
      div.innerHTML = `
        <div style="display:flex;gap:8px;flex-wrap:wrap;margin-bottom:12px">
          <button class="btn small filled" onclick="copyXhs('title')">复制标题（${titleLen}/20）</button>
          <button class="btn small tonal" onclick="copyXhs('body')">复制正文（${bodyLen}/1000）</button>
        </div>
        <div class="kv"><b>标题：</b>${esc(title)}</div>
        <pre style="white-space:pre-wrap;font-size:13px;font-family:inherit;color:var(--preview-text);max-height:420px;overflow:auto;margin-top:10px">${esc(body)}</pre>`;
    } else {
      const content = stripFrontmatter(d.content || "");
      div.style.maxHeight = "480px";
      div.style.overflow = "auto";
      div.innerHTML = `<pre style="white-space:pre-wrap;font-size:13px;font-family:inherit;color:var(--preview-text)">${esc(content)}</pre>`;
    }
    box.appendChild(div);
  } catch (e) {
    box.innerHTML += '<span class="muted">文案加载失败</span>';
  }
}

async function renderArtifactSide(jobId) {
  try {
    const d = await api("/api/jobs/" + encodeURIComponent(jobId));
    const s = d.state || {};
    const vr = d.validate_report, hr = d.harsh_report, ar = d.ai_flavor_report || {},
          cr = d.compliance_report || {}, pl = d.publish_log || {};
    $("#artifact-meta").innerHTML = `
      <div class="kv">状态：${stateBadge(s.state)}</div>
      <div class="kv">主题：<b>${esc(s.theme || "—")}</b></div>
      <div class="kv">打回：<b>${s.reject_count ?? 0}</b></div>
      <div class="kv">更新时间：<b>${esc(s.updated_at || "—")}</b></div>`;
    $("#artifact-qa").innerHTML = vr
      ? `<div class="kv">契约校验：<b>${esc(vr.verdict)}</b>（FAIL ${vr.fails ?? 0}）</div>`
      : '<div class="kv">契约校验：未运行</div>';
    $("#artifact-qa").insertAdjacentHTML("beforeend", hr
      ? `<div class="kv">Harsh Critic：<b>${esc(hr.score)}/100</b> → ${esc(hr.verdict)}</div>`
      : '<div class="kv">Harsh Critic：未运行</div>');
    const arBadge = ar.verdict
      ? `<b>${esc(ar.verdict)}</b>（high ${ar.summary ? ar.summary.high : 0} / medium ${ar.summary ? ar.summary.medium : 0}）`
      : "未运行";
    $("#artifact-qa").insertAdjacentHTML("beforeend",
      `<div class="kv">去 AI 味：${arBadge}${ar.verdict === "REJECTED" ? ' <span class="badge error">退回重写</span>' : ""}`
      + ` <button class="btn small tonal" onclick="viewAntiAiSkill()">查看规则</button></div>`);
    const crBadge = cr.verdict ? `<b>${esc(cr.verdict)}</b>（高 ${cr.summary ? cr.summary.high : 0} / 中 ${cr.summary ? cr.summary.medium : 0}）` : "未运行";
    $("#artifact-qa").insertAdjacentHTML("beforeend",
      `<div class="kv">合规审核：${crBadge}${cr.verdict === "REJECTED" ? ' <span class="badge error">禁止发布</span>' : ""}</div>`);
    $("#artifact-publish").innerHTML = `
      <div class="kv">草稿推送：<b>${(pl.publish || []).length}</b> 次</div>
      <div class="kv">数据回填：<b>${(pl.records || []).length}</b> 条</div>
      <div class="kv">发布时间：<b>${esc(pl.published_at || "—")}</b></div>`;
  } catch (e) {
    $("#artifact-meta").innerHTML = '<span class="muted">详情加载失败</span>';
  }
}

async function viewAntiAiSkill() {
  try {
    const d = await api("/api/skills/anti-ai-flavor");
    $("#agent-doc-title").textContent = "去 AI 味规范 · " + d.name;
    $("#agent-doc-body").innerHTML = renderMarkdown(d.content);
    $("#agent-doc-modal").classList.remove("hidden");
  } catch (e) {
    toast("读取规则失败: " + e.message, false);
  }
}
window.viewAntiAiSkill = viewAntiAiSkill;

// ---------- 数据 ----------
let statsCache = null;

function statKpis(d) {
  const items = [
    ["发布动作", d.publish_events ?? 0],
    ["回填/导入", d.backfill_records ?? 0],
    ["总阅读", fmtNum(d.total_reads)],
    ["平均互动率", d.total_reads ? pct(d.avg_engagement) : "—"],
    ["累计涨粉", d.xhs_followers_gained ?? 0],
    ["涨粉率", d.xhs_reads ? pct(d.xhs_follower_rate) : "—"],
    ["爆款数", d.hits],
    ["待回收", d.pending_recycle],
  ];
  $("#stats-kpi").innerHTML = items.map(([lbl, num]) =>
    `<div class="kpi"><div class="num ${String(num).length > 5 ? "small" : ""}">${esc(num)}</div><div class="lbl">${esc(lbl)}</div></div>`).join("");
}

function renderPlatformCompare(rows) {
  const icons = { "公众号": "📰", "小红书": "📕", "短视频": "🎬" };
  $("#platform-compare").innerHTML = rows.map((p) => `
    <div class="agent-card">
      <div class="head"><span class="emoji">${icons[p.platform] || "📊"}</span><span class="role">${esc(p.platform)}</span></div>
      <div class="resp">发布 <b>${p.publish_events}</b> 次 ｜ 回填 <b>${p.backfills}</b> 条 ｜ 发文 <b>${p.posts}</b> 篇</div>
      <div class="kv">总阅读 <b>${fmtNum(p.reads)}</b> ｜ 互动率 <b>${p.reads ? pct(p.engagement) : "—"}</b> ｜ 爆款 <b>${p.hits}</b></div>
    </div>`).join("") || '<span class="muted">暂无平台数据</span>';
}

function renderDataStatus(ds, stats) {
  const untracked = (ds.untracked_list || []).map((u) =>
    `<div class="kv">· ${esc(u.job_id)}<span class="muted">（${esc(u.title || "")}）</span></div>`).join("")
    || '<div class="muted">无</div>';
  $("#data-status").innerHTML = `
    <div class="kv">自动记录（发布/草稿推送）：<b>${ds.auto_tracked ?? 0}</b> 次</div>
    <div class="kv">回填/导入（阅读/赞/藏/评/涨粉）：<b>${ds.manual_backfill ?? 0}</b> 条</div>
    <div class="kv">已发布但未回填：<b>${ds.untracked_posts ?? 0}</b> 篇</div>
    <div class="kv">待回收检查：<b>${ds.pending_recycle ?? 0}</b> 篇</div>
    <div class="kv muted" style="margin-top:8px">${esc(ds.external_note || "")}</div>
    <div class="kv muted">引擎：<code>scripts/data_stats.py</code> · 聚合落盘 <code>data/stats/</code> · 回填源 <code>jobs/*/publish_log.json</code></div>
    <div class="kv" style="margin-top:8px"><b>待回填任务：</b></div>
    ${untracked}`;
}

function renderThemeTable(rows) {
  if (!rows.length) return $("#theme-table").innerHTML = '<tr><td colspan="6" class="muted">暂无回填数据</td></tr>';
  $("#theme-table").innerHTML = rows.map((t) => `
    <tr>
      <td>${esc(t.theme)}</td>
      <td class="num">${t.posts}</td>
      <td class="num">${t.backfills}</td>
      <td class="num">${fmtNum(t.reads)}</td>
      <td class="num">${t.reads ? pct(t.engagement) : "—"}</td>
      <td>${t.hits ? `<span class="badge hit">🔥 ${t.hits}</span>` : t.hits}</td>
    </tr>`).join("");
}

function renderContentInsights(ins) {
  if (!ins || !ins.title_number || !ins.title_number.length) {
    return $("#content-insights").innerHTML = '<span class="muted">暂无回填数据，完成人工回填后这里会对比标题/图表/卡片的表现。</span>';
  }
  const block = (title, rows) => `
    <div>
      <div class="kv" style="margin-bottom:6px"><b>${esc(title)}</b></div>
      ${rows.map((r) => `
        <div class="kv">${esc(r.bucket)}：样本 <b>${r.n}</b> ｜ 均阅读 <b>${fmtNum(r.avg_reads)}</b> ｜ 均互动 <b>${pct(r.avg_engagement)}</b> ｜ 爆款 <b>${r.hits}</b></div>`).join("")}
    </div>`;
  $("#content-insights").innerHTML =
    block("标题数字", ins.title_number) +
    block("体裁", ins.format) +
    block("公众号图表数", ins.gzh_viz) +
    block("小红书卡片数", ins.xhs_cards) +
    `<div class="kv muted">${esc(ins.note || "")}</div>`;
}

function renderBest(best) {
  const byReads = best && best.by_reads ? best.by_reads : [];
  const byEng = best && best.by_engagement ? best.by_engagement : [];
  const byFollowers = best && best.by_followers ? best.by_followers : [];
  if (!byReads.length && !byEng.length && !byFollowers.length) {
    return $("#best-list").innerHTML = '<span class="muted">暂无回填数据</span>';
  }
  const row = (r) => `
    <div class="kv">${r.hit ? "🔥 " : ""}<b>${esc(r.title || r.job_id)}</b>（${esc(r.platform)}）阅读 ${fmtNum(r.reads)} ｜ 互动率 ${pct(r.engagement)}<span class="muted"> · ${esc(r.job_id)}</span></div>`;
  let html = "";
  if (byReads.length) html += `<div class="kv" style="margin-bottom:4px"><b>阅读 TOP${byReads.length}</b></div>` + byReads.map(row).join("");
  if (byEng.length) html += `<div class="kv" style="margin:10px 0 4px"><b>互动率 TOP${byEng.length}</b></div>` + byEng.map(row).join("");
  if (byFollowers.length) html += `<div class="kv" style="margin:10px 0 4px"><b>涨粉 TOP${byFollowers.length}</b></div>` + byFollowers.map((r) => `
    <div class="kv"><b>${esc(r.title || r.job_id)}</b> 阅读 ${fmtNum(r.reads)} ｜ 涨粉 ${fmtNum(r.followers_gained)}<span class="muted"> · ${esc(r.job_id)}</span></div>`).join("");
  $("#best-list").innerHTML = html;
}

async function loadData() {
  try {
    const [stats, jobs] = await Promise.all([api("/api/stats"), api("/api/jobs")]);
    statsCache = stats;
    const acc = stats.xhs_account || {};
    if ($("#snap-followers")) $("#snap-followers").value = acc.followers ?? 0;
    if ($("#snap-following")) $("#snap-following").value = acc.following ?? 0;
    if ($("#snap-likes-collects")) $("#snap-likes-collects").value = acc.likes_collects ?? 0;
    if ($("#snap-note")) {
      $("#snap-note").textContent = acc.updated_at
        ? `上次更新：${acc.updated_at}${acc.period ? "（" + acc.period + "）" : ""}`
        : "尚未保存过快照";
    }
    $("#stats-updated-at").textContent = "更新于 " + (stats.generated_at || "");
    statKpis(stats);
    renderDataStatus(stats.data_status || {}, stats);
    renderThemeTable(stats.by_theme || []);
    renderContentInsights(stats.content_insights || {});
    renderBest(stats.best || {});
    $("#perf-table").innerHTML = renderRows(stats.recent);
    const sel = $("#bf-job");
    const prev = sel.value;
    const bfJobs = visibleJobs(jobs.jobs);
    sel.innerHTML = bfJobs.map((j) =>
      `<option value="${esc(j.job_id)}">${esc(j.job_id)} · ${esc(j.theme || "")}</option>`).join("");
    if (prev && bfJobs.some((j) => j.job_id === prev)) sel.value = prev;
  } catch (e) {
    toast("数据加载失败: " + e.message, false);
  }
}

async function saveAccountSnapshot() {
  const body = {
    followers: Number($("#snap-followers").value) || 0,
    following: Number($("#snap-following").value) || 0,
    likes_collects: Number($("#snap-likes-collects").value) || 0,
  };
  try {
    await api("/api/stats/account-snapshot", {
      method: "POST", headers: { "Content-Type": "application/json" },
      body: JSON.stringify(body),
    });
    toast("账号快照已保存，粉丝数将以该数据为准");
    loadData();
    loadOverview();
  } catch (e) {
    toast("保存失败: " + e.message, false);
  }
}
window.saveAccountSnapshot = saveAccountSnapshot;

$("#backfill-form").addEventListener("submit", async (e) => {
  e.preventDefault();
  const payload = {
    job_id: $("#bf-job").value,
    platform: $("#bf-platform").value,
    reads: parseInt($("#bf-reads").value, 10) || 0,
    likes: parseInt($("#bf-likes").value, 10) || 0,
    collects: parseInt($("#bf-collects").value, 10) || 0,
    comments: parseInt($("#bf-comments").value, 10) || 0,
    url: $("#bf-url").value.trim(),
  };
  if (!payload.job_id) return toast("请选择任务", false);
  try {
    const d = await api("/api/stats/backfill", {
      method: "POST", headers: { "Content-Type": "application/json" },
      body: JSON.stringify(payload),
    });
    toast((d.stdout || "已保存回填").trim().split("\n")[0]);
    loadData();
    loadOverview();
  } catch (err) {
    toast("回填失败: " + err.message, false);
  }
});

$("#btn-stats-refresh").addEventListener("click", (e) => runWithSpin(e.currentTarget, async () => {
  await api("/api/stats/refresh", { method: "POST" });
  toast("统计已刷新");
  loadData();
  loadOverview();
}));

$("#btn-dash-import").addEventListener("click", () => $("#dash-import-file").click());
$("#dash-import-file").addEventListener("change", async (e) => {
  const files = Array.from(e.target.files || []);
  if (!files.length) return;
  try {
    const ok = [], fail = [];
    for (const file of files) {
      try {
        // 笔记明细（列表明细）走笔记导入器，其余按看板四页签自动识别
        const isNotes = /笔记|明细/.test(file.name);
        const path = isNotes ? "/api/stats/import-xhs" : "/api/stats/import-dashboard";
        const d = await api(`${path}?filename=${encodeURIComponent(file.name)}`, {
          method: "POST", body: file,
        });
        ok.push(isNotes ? "笔记明细" : (d.kind || file.name));
      } catch (err) {
        fail.push(`${file.name}（${err.message}）`);
      }
    }
    if (ok.length) toast(`已导入看板 ${ok.length}/${files.length}：${ok.join("、")}`);
    if (fail.length) toast(`导入失败 ${fail.length} 项：${fail.join("；")}`, false);
    loadData();
    loadOverview();
  } catch (err) {
    toast("导入失败: " + err.message, false);
  }
  e.target.value = "";
});

// ---------- 初始化 ----------
document.addEventListener("DOMContentLoaded", () => {
  switchView("overview");
  loadLicenseStatus();
  applyProfile();
  setTimeout(() => showOnboarding(false), 500);
});

async function loadLicenseStatus() {
  try {
    const d = await api("/api/license/status");
    const tierTxt = {
      owner: "Pro · 卖家模式",
      pro: "Pro 已激活" + (d.exp ? " · 到期 " + d.exp : ""),
      free: "免费版 · 升级 Pro",
    }[d.tier] || d.tier;
    const eng = { codex: "引擎 Codex", api: "引擎 API", none: "引擎未配置" }[d.engine.mode] || "引擎未知";
    const el = $("#license-badge");
    el.innerHTML = d.tier === "free"
      ? `<a href="${esc(d.upgrade_url || "#")}" target="_blank" rel="noopener">${tierTxt}</a> · ${eng}`
      : `${tierTxt} · ${eng}`;
  } catch (e) {
    $("#license-badge").textContent = "授权状态加载失败";
  }
}
window.loadLicenseStatus = loadLicenseStatus;

function applyProfile() {
  let prof = {};
  try { prof = JSON.parse(localStorage.getItem("selfmedia_profile") || "{}"); } catch (e) { /* ignore */ }
  const av = $("#brand-avatar");
  if (av) {
    if (prof.avatar) {
      av.style.backgroundImage = 'url("' + String(prof.avatar).replace(/["\\]/g, "") + '")';
      av.style.backgroundSize = "cover";
      av.style.backgroundPosition = "center";
      av.textContent = "";
    } else {
      av.style.backgroundImage = "";
      av.textContent = (prof.nickname || "小吴聊").slice(0, 1);
    }
  }
  const nk = $("#brand-nickname");
  if (nk) nk.textContent = (prof.nickname || "小吴聊") + " · 运营工作台";
}
window.applyProfile = applyProfile;

function readFileAsDataUrl(file) {
  return new Promise((resolve, reject) => {
    const reader = new FileReader();
    reader.onload = () => resolve(reader.result);
    reader.onerror = () => reject(new Error("读取文件失败"));
    reader.readAsDataURL(file);
  });
}

const cropState = { imgX: 0, imgY: 0, zoom: 1, stage: 340, cropSize: 220, naturalW: 1, naturalH: 1 };
const cropFramePos = { x: 0, y: 0 };
let cropDrag = null;

function cropBaseScale() {
  return Math.max(cropState.stage / cropState.naturalW, cropState.stage / cropState.naturalH);
}

function renderCrop() {
  const img = $("#crop-img");
  if (!img) return;
  const base = cropBaseScale();
  const w = cropState.naturalW * base * cropState.zoom;
  const h = cropState.naturalH * base * cropState.zoom;
  img.style.width = w + "px";
  img.style.height = h + "px";
  img.style.left = cropState.imgX + "px";
  img.style.top = cropState.imgY + "px";
  const frame = $("#crop-frame");
  if (frame) {
    frame.style.left = cropFramePos.x + "px";
    frame.style.top = cropFramePos.y + "px";
  }
}

function centerImage() {
  const base = cropBaseScale();
  cropState.imgX = (cropState.stage - cropState.naturalW * base * cropState.zoom) / 2;
  cropState.imgY = (cropState.stage - cropState.naturalH * base * cropState.zoom) / 2;
}

function openCropModal(dataUrl) {
  const img = $("#crop-img");
  img.onload = () => {
    cropState.naturalW = img.naturalWidth || 1;
    cropState.naturalH = img.naturalHeight || 1;
    const cover = cropBaseScale();
    cropState.zoom = cover;
    const zoom = $("#crop-zoom");
    if (zoom) {
      zoom.min = cover.toFixed(2);
      zoom.max = Math.max(4, (cover * 3).toFixed(2));
      zoom.value = cropState.zoom.toFixed(2);
    }
    centerImage();
    cropFramePos.x = (cropState.stage - cropState.cropSize) / 2;
    cropFramePos.y = (cropState.stage - cropState.cropSize) / 2;
    renderCrop();
    $("#crop-modal").classList.remove("hidden");
  };
  img.src = dataUrl;
}

function closeCrop() {
  $("#crop-modal").classList.add("hidden");
  const img = $("#crop-img");
  img.removeAttribute("src");
  const fv = $("#set-avatar-file");
  if (fv) fv.value = "";
}
window.closeCrop = closeCrop;

function confirmCrop() {
  const img = $("#crop-img");
  const w = parseFloat(img.style.width);
  const h = parseFloat(img.style.height);
  if (!w || !h) return;
  const scale = w / cropState.naturalW;
  const cropPx = cropState.cropSize / scale;
  const cx = cropFramePos.x + cropState.cropSize / 2;
  const cy = cropFramePos.y + cropState.cropSize / 2;
  const sx = Math.max(0, Math.min(cropState.naturalW - cropPx, (cx - cropState.imgX) / scale));
  const sy = Math.max(0, Math.min(cropState.naturalH - cropPx, (cy - cropState.imgY) / scale));
  const cv = document.createElement("canvas");
  cv.width = 256;
  cv.height = 256;
  cv.getContext("2d").drawImage(img, sx, sy, cropPx, cropPx, 0, 0, 256, 256);
  const dataUrl = cv.toDataURL("image/jpeg", 0.9);
  const inp = $("#set-avatar");
  if (inp) inp.value = dataUrl;
  const pv = $("#set-avatar-preview");
  if (pv) {
    pv.src = dataUrl;
    pv.classList.remove("hidden");
  }
  closeCrop();
  toast("头像已裁剪，点「保存配置」生效");
}
window.confirmCrop = confirmCrop;

async function handleAvatarUpload(input) {
  const file = input && input.files && input.files[0];
  if (!file) return;
  if (!file.type.startsWith("image/")) {
    toast("请选择图片文件", false);
    input.value = "";
    return;
  }
  if (file.size > 2 * 1024 * 1024) {
    toast("图片过大（≤2MB）", false);
    input.value = "";
    return;
  }
  try {
    const dataUrl = await readFileAsDataUrl(file);
    openCropModal(dataUrl);
  } catch (e) {
    toast("头像上传失败: " + e.message, false);
    input.value = "";
  }
}
window.handleAvatarUpload = handleAvatarUpload;

const cropStage = $("#crop-stage");
const cropFrame = $("#crop-frame");
if (cropStage && cropFrame) {
  cropFrame.addEventListener("pointerdown", (e) => {
    cropDrag = { sx: e.clientX, sy: e.clientY, x: cropFramePos.x, y: cropFramePos.y };
    cropFrame.setPointerCapture(e.pointerId);
    cropFrame.classList.add("dragging");
  });
  cropFrame.addEventListener("pointermove", (e) => {
    if (!cropDrag) return;
    cropFramePos.x = Math.max(0, Math.min(cropState.stage - cropState.cropSize, cropDrag.x + (e.clientX - cropDrag.sx)));
    cropFramePos.y = Math.max(0, Math.min(cropState.stage - cropState.cropSize, cropDrag.y + (e.clientY - cropDrag.sy)));
    renderCrop();
  });
  const endCropDrag = () => {
    cropDrag = null;
    cropFrame.classList.remove("dragging");
  };
  cropFrame.addEventListener("pointerup", endCropDrag);
  cropFrame.addEventListener("pointercancel", endCropDrag);
  const zoom = $("#crop-zoom");
  if (zoom) {
    zoom.addEventListener("input", (e) => {
      const img = $("#crop-img");
      const oldW = parseFloat(img.style.width) || cropState.stage;
      const oldH = parseFloat(img.style.height) || cropState.stage;
      const cx = cropFramePos.x + cropState.cropSize / 2;
      const cy = cropFramePos.y + cropState.cropSize / 2;
      const fx = (cx - cropState.imgX) / oldW;
      const fy = (cy - cropState.imgY) / oldH;
      cropState.zoom = parseFloat(e.target.value) || cropState.zoom;
      renderCrop();
      const nw = parseFloat(img.style.width) || oldW;
      const nh = parseFloat(img.style.height) || oldH;
      cropState.imgX = cx - fx * nw;
      cropState.imgY = cy - fy * nh;
      renderCrop();
    });
  }
}

function switchSettingsPanel(name) {
  $$("#settings-menu .set-menu-item").forEach((b) => b.classList.toggle("active", b.dataset.panel === name));
  $$("#settings-modal .set-panel").forEach((p) => p.classList.toggle("active", p.id === "panel-" + name));
}
window.switchSettingsPanel = switchSettingsPanel;

let tplData = { categories: [] };
let tplSel = {};
let tplActiveCat = "";
let styleDocs = [];

async function loadTemplates() {
  try {
    const [td, prefs] = await Promise.all([
      api("/api/templates"),
      api("/api/user-preferences"),
    ]);
    tplData = td;
    tplSel = (prefs.templates || {});
    tplActiveCat = (td.categories[0] || {}).id || "";
    renderTplCats();
    renderTplGrid();
  } catch (e) { /* 模板非必须 */ }
}

function renderTplCats() {
  const box = $("#tpl-cats");
  if (!box) return;
  box.innerHTML = (tplData.categories || []).map((c) =>
    `<button class="tab ${c.id === tplActiveCat ? "active" : ""}" onclick="tplActiveCat='${esc(c.id)}';renderTplCats();renderTplGrid()">${esc(c.name)}</button>`).join("");
}

function tplMockHtml(catId, name, colors) {
  const [bg, ink, accent] = colors;
  const base = `background:${bg};color:${ink};border-color:${accent}`;
  const titleBar = `<div class="tpl-mock-title" style="background:${accent}"></div>`;
  const lines = `<div class="tpl-mock-line"></div><div class="tpl-mock-line short"></div><div class="tpl-mock-line"></div>`;
  if (catId === "xhs_card") {
    return `<div class="tpl-mock tpl-mock-card" style="${base}">
      ${titleBar}
      <div class="tpl-mock-media" style="background:${ink}"></div>
      ${lines}
      <span class="tpl-mock-tag" style="color:${accent}">${esc(name)}</span>
    </div>`;
  }
  if (catId === "gzh_layout") {
    return `<div class="tpl-mock tpl-mock-article" style="${base}">
      ${titleBar}
      <div class="tpl-mock-title wide" style="background:${ink}"></div>
      <div class="tpl-mock-meta" style="color:${accent}">标题 · 作者 · 摘要</div>
      ${lines}${lines}
    </div>`;
  }
  return `<div class="tpl-mock tpl-mock-cover" style="${base}">
    <span class="tpl-mock-tag" style="color:${ink}">${esc(name)}</span>
    <div class="tpl-mock-title wide" style="background:${accent}"></div>
    ${lines}
  </div>`;
}

function renderTplGrid() {
  const box = $("#tpl-grid");
  if (!box) return;
  const cat = (tplData.categories || []).find((c) => c.id === tplActiveCat);
  if (!cat) return box.innerHTML = '<span class="muted">暂无模板</span>';
  box.innerHTML = cat.items.map((it) => {
    const sel = tplSel[cat.id] === it.id;
    return `
      <div class="tpl-item ${sel ? "selected" : ""}" onclick="selectTemplate('${esc(cat.id)}','${esc(it.id)}')">
        <div class="tpl-preview">${tplMockHtml(cat.id, it.name, it.colors)}</div>
        <div class="tpl-name">${esc(it.name)}</div>
        <div class="tpl-desc">${esc(it.desc)}</div>
      </div>`;
  }).join("");
}

function selectTemplate(catId, itemId) {
  tplSel[catId] = itemId;
  renderTplGrid();
}
window.selectTemplate = selectTemplate;

async function saveTemplates() {
  try {
    await api("/api/user-preferences", {
      method: "POST", headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ templates: tplSel }),
    });
    const st = $("#tpl-save-status");
    if (st) st.textContent = "已保存 " + new Date().toLocaleTimeString();
    toast("模板选择已保存，后续生成将按此模板初始化");
  } catch (e) {
    toast("保存模板失败: " + e.message, false);
  }
}
window.saveTemplates = saveTemplates;

async function loadStyleDocs() {
  try {
    const d = await api("/api/style-docs");
    styleDocs = d.docs || [];
    const sel = $("#style-doc-select");
    if (!sel) return;
    sel.innerHTML = styleDocs.map((doc) => `<option value="${esc(doc.path)}">${esc(doc.name)}</option>`).join("");
    loadStyleDoc();
  } catch (e) { /* 忽略 */ }
}

async function loadStyleDoc() {
  const sel = $("#style-doc-select");
  const ta = $("#style-doc-text");
  if (!sel || !ta || !sel.value) return;
  try {
    const d = await api("/api/style-doc?path=" + encodeURIComponent(sel.value));
    ta.value = d.content || "";
    $("#style-doc-status").textContent = "已加载 " + sel.value;
  } catch (e) {
    $("#style-doc-status").textContent = "加载失败: " + e.message;
  }
}
window.loadStyleDoc = loadStyleDoc;

async function saveStyleDoc() {
  const sel = $("#style-doc-select");
  const ta = $("#style-doc-text");
  if (!sel || !sel.value) return;
  try {
    await api("/api/style-doc", {
      method: "POST", headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ path: sel.value, content: ta.value }),
    });
    $("#style-doc-status").textContent = "已保存 " + sel.value;
    toast("文风文档已保存");
  } catch (e) {
    toast("保存失败: " + e.message, false);
  }
}
window.saveStyleDoc = saveStyleDoc;

// ---------- 配置（API Key / 公众号凭据） ----------
function openSettings() {
  loadSettings();
  loadRetention();
  loadTemplates();
  loadStyleDocs();
  $("#settings-modal").classList.remove("hidden");
}
window.openSettings = openSettings;

function closeSettings() {
  $("#settings-modal").classList.add("hidden");
}
window.closeSettings = closeSettings;

async function loadSettings() {
  const st = $("#settings-status");
  try {
    const d = await api("/api/settings");
    let prof = {};
    try { prof = JSON.parse(localStorage.getItem("selfmedia_profile") || "{}"); } catch (e) { /* ignore */ }
    if ($("#set-nickname")) $("#set-nickname").value = prof.nickname || "";
    if ($("#set-avatar")) $("#set-avatar").value = prof.avatar || "";
    const pv = $("#set-avatar-preview");
    if (pv) {
      if (prof.avatar) {
        pv.src = prof.avatar;
        pv.classList.remove("hidden");
      } else {
        pv.classList.add("hidden");
        pv.removeAttribute("src");
      }
    }
    const fv = $("#set-avatar-file");
    if (fv) fv.value = "";
    const th = document.documentElement.dataset.theme || "default";
    const themeSel = $("#set-theme");
    if (themeSel) themeSel.value = THEME_NAMES[th] ? th : "default";
    $("#set-llm-key").value = "";
    $("#set-llm-base").value = d.llm.base_url || "";
    $("#set-llm-model").value = d.llm.model || "";
    $("#set-gzh-id").value = "";
    $("#set-gzh-secret").value = "";
    $("#set-key-mask").textContent = d.llm.configured
      ? "当前已配置：" + d.llm.api_key_masked
      : "未配置（免费功能不需要 AI Key）";
    const gzhTxt = d.gzh.configured ? "公众号已配置：" + d.gzh.app_id_masked : "公众号未配置（手动发布也能用）";
    st.textContent = (d.llm.status_ok ? "AI 引擎就绪（" + d.engine.mode + "）" : "AI 引擎：" + d.llm.status_reason) + " · " + gzhTxt;
  } catch (e) {
    st.textContent = "读取配置失败: " + e.message;
  }
}
window.loadSettings = loadSettings;

const THEME_NAMES = {
  default: "蓝白默认", "brand-red": "红白小吴聊", midnight: "深空暗黑",
  pink: "粉漾少女", doraemon: "哆啦A梦（蓝胖）",
};

function applyTheme(name) {
  name = THEME_NAMES[name] ? name : "default";
  document.documentElement.dataset.theme = name;
  localStorage.setItem("selfmedia_theme", name);
  const sel = $("#set-theme");
  if (sel) sel.value = name;
  toast("已切换主题：" + THEME_NAMES[name]);
}
window.applyTheme = applyTheme;

const RETENTION_LABELS = {
  candidates: "过期候选", logs: "过期日志", platform_days: "过期榜单快照",
  stale_videos: "长期未拆解跟踪", jobs_to_archive: "可归档旧任务",
  media_files: "过期大文件", dashboard_files: "超出保留份数导入文件",
};

async function loadRetention() {
  const el = $("#retention-summary");
  el.textContent = "正在扫描存储…";
  try {
    const d = await api("/api/retention/status");
    const plan = d.plan || {};
    const parts = Object.entries(plan)
      .filter(([, n]) => n > 0)
      .map(([k, n]) => `${RETENTION_LABELS[k] || k} ${n} 项`);
    el.innerHTML = `当前占用 <b>${(d.space.scanned_mb || 0).toFixed(1)}MB</b>，可释放 <b>${(d.space.reclaimable_mb || 0).toFixed(1)}MB</b>` +
      (parts.length ? "：" + parts.join("、") : "，无需清理");
    $("#retention-last").textContent = d.last_run
      ? `上次清理：${d.last_run.ran_at}（释放 ${(d.last_run.reclaimable_mb || 0).toFixed(1)}MB）`
      : "尚未执行过清理";
  } catch (e) {
    el.textContent = "扫描失败: " + e.message;
  }
}
window.loadRetention = loadRetention;

async function applyRetention() {
  if (!confirm("将删除过期日志/榜单快照/候选与未出爆款任务的旧图片（文案与拆解报告保留），确认执行？")) return;
  const el = $("#retention-summary");
  el.textContent = "正在清理…";
  try {
    const d = await api("/api/retention/apply", { method: "POST" });
    const total = Object.values(d.applied || {}).reduce((a, b) => a + b, 0);
    el.innerHTML = `清理完成：释放 <b>${(d.space.reclaimable_mb || 0).toFixed(1)}MB</b>（${total} 项）`;
    $("#retention-last").textContent = "上次清理：" + (d.ran_at || "");
    toast("数据清理完成");
  } catch (e) {
    el.textContent = "清理失败: " + e.message;
  }
}
window.applyRetention = applyRetention;

async function saveSettings(silent) {
  const st = $("#settings-status");
  const body = {};
  const val = (id) => $(id).value.trim();
  if (val("#set-llm-key")) body.llm_api_key = val("#set-llm-key");
  if (val("#set-llm-base")) body.llm_base_url = val("#set-llm-base");
  if (val("#set-llm-model")) body.llm_model = val("#set-llm-model");
  if (val("#set-gzh-id")) body.gzh_app_id = val("#set-gzh-id");
  if (val("#set-gzh-secret")) body.gzh_app_secret = val("#set-gzh-secret");
  try {
    const d = await api("/api/settings", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(body),
    });
    try {
      localStorage.setItem("selfmedia_profile", JSON.stringify({
        nickname: $("#set-nickname") ? $("#set-nickname").value.trim() : "",
        avatar: $("#set-avatar") ? $("#set-avatar").value.trim() : "",
      }));
    } catch (e) { /* ignore */ }
    applyProfile();
    $("#set-llm-key").value = "";
    $("#set-gzh-secret").value = "";
    $("#set-key-mask").textContent = d.llm.configured ? "当前已配置：" + d.llm.api_key_masked : "未配置";
    if (!silent) {
      st.textContent = "已保存。" + (d.llm.status_ok ? " AI 引擎就绪（" + d.engine.mode + "）" : " " + d.llm.status_reason);
    }
    loadLicenseStatus();
    return d;
  } catch (e) {
    if (!silent) st.textContent = "保存失败: " + e.message;
    throw e;
  }
}
window.saveSettings = saveSettings;

async function testLlm() {
  const st = $("#settings-status");
  st.textContent = "正在保存并测试连接…";
  try {
    await saveSettings(true);
    const d = await api("/api/settings/llm-test", { method: "POST" });
    st.textContent = d.ok ? "✅ " + d.message : "❌ " + d.message;
  } catch (e) {
    st.textContent = "测试失败: " + e.message;
  }
}
window.testLlm = testLlm;

async function refreshLicense() {
  const st = $("#settings-status");
  st.textContent = "正在刷新授权状态…";
  try {
    await loadLicenseStatus();
    const d = await api("/api/license/status");
    const tierTxt = {
      owner: "Pro · 卖家模式",
      pro: "Pro 已激活" + (d.exp ? " · 到期 " + d.exp : ""),
      free: "免费版",
    }[d.tier] || d.tier;
    const eng = d.engine.mode === "codex" ? "引擎 Codex" : d.engine.mode === "api" ? "引擎 API" : "引擎未配置";
    st.textContent = "授权状态已刷新：" + tierTxt + " · " + eng;
  } catch (e) {
    st.textContent = "刷新失败: " + e.message;
  }
}
window.refreshLicense = refreshLicense;

async function activateLicense() {
  const st = $("#settings-status");
  const token = $("#set-license-token").value.trim();
  if (!token) return toast("请先粘贴授权 token", false);
  st.textContent = "正在激活授权…";
  try {
    const d = await api("/api/license/activate", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ token }),
    });
    $("#set-license-token").value = "";
    st.textContent = "✅ " + d.message;
    loadLicenseStatus();
    toast("授权激活成功，已是 Pro 会员");
  } catch (e) {
    st.textContent = "激活失败: " + e.message;
    toast("激活失败: " + e.message, false);
  }
}
window.activateLicense = activateLicense;
