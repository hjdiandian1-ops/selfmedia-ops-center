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
  overview: ["概览", "数据大盘 · 结果优先"],
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

$$(".nav-item").forEach((btn) => btn.addEventListener("click", () => switchView(btn.dataset.view)));
$("#btn-refresh-topics").addEventListener("click", (e) => runWithSpin(e.currentTarget, loadTopics));

// ---------- 概览 ----------
async function loadOverview() {
  try {
    const d = await api("/api/stats");
    $("#topbar-meta").textContent = "更新于 " + (d.generated_at || "");
    const kpis = [
      ["任务总数", d.jobs_total], ["已发布任务", d.published_jobs],
      ["爆款数", d.hits], ["总阅读", fmtNum(d.total_reads)],
      ["平均互动率", d.total_reads ? pct(d.avg_engagement) : "—"],
      ["待回收", d.pending_recycle],
    ];
    $("#kpi-cards").innerHTML = kpis.map(([lbl, num]) =>
      `<div class="kpi"><div class="num ${String(num).length > 5 ? "small" : ""}">${esc(num)}</div><div class="lbl">${esc(lbl)}</div></div>`).join("");

    const states = Object.entries(d.by_state);
    const total = d.jobs_total || 1;
    $("#state-bars").innerHTML = states.length
      ? states.map(([s, n]) => `
        <div class="sbar">
          <span class="name">${esc(STATE_LABELS[s] || s)}</span>
          <div class="track"><div class="fill" style="width:${(n / total * 100).toFixed(0)}%"></div></div>
          <span class="cnt">${n}</span>
        </div>`).join("")
      : '<span class="muted">暂无任务</span>';

    const maxPubs = Math.max(1, ...d.trend.map((t) => t.publish_count || 0));
    $("#trend-chart").innerHTML = d.trend.map((t) => `
      <div class="tcol" title="${t.reads ? `阅读 ${fmtNum(t.reads)}` : "暂无回填阅读"}">
        <span class="val">${t.publish_count ? t.publish_count + " 篇" : ""}</span>
        <div class="bar" style="height:${Math.max(4, Math.round((t.publish_count || 0) / maxPubs * 92))}%">
          ${t.hits ? '<span class="hits" title="爆款"></span>' : ""}
        </div>
        <span class="day">${esc(t.label)}</span>
      </div>`).join("");

    $("#recent-table").innerHTML = renderRows(d.recent);
    loadDashboard();
  } catch (e) {
    toast("概览加载失败: " + e.message, false);
  }
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
  loadDashboard();
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
  const maxV = Math.max(1, ...trend.map((t) => Number(t.value || t.total || 0)));
  box.innerHTML = trend.map((t) => {
    const v = Number(t.value != null ? t.value : t.total || 0);
    const extra = t.video != null ? ` 视频 ${t.video} / 图文 ${t.image}` : "";
    return `
      <div class="tcol" title="${esc(t.date + extra)}">
        <span class="val">${v ? fmtNum(v) : ""}</span>
        <div class="bar" style="height:${Math.max(4, Math.round(v / maxV * 92))}%"></div>
        <span class="day">${esc(t.label)}</span>
      </div>`;
  }).join("");
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
  if (!records.length) return '<tr><td colspan="10" class="muted">暂无回填数据</td></tr>';
  return records.map((r) => `
    <tr>
      <td>${esc((r.collected_at || "").slice(0, 16))}</td>
      <td title="${esc(r.theme || "")}">${esc(r.job_id)}</td>
      <td>${esc(r.platform || "—")}</td>
      <td class="num">${fmtNum(r.reads)}</td>
      <td class="num">${fmtNum(r.likes)}</td>
      <td class="num">${fmtNum(r.collects)}</td>
      <td class="num">${fmtNum(r.comments)}</td>
      <td class="num">${r.followers_gained ? fmtNum(r.followers_gained) : "—"}</td>
      <td class="num">${pct(r.engagement)}</td>
      <td>${r.hit ? '<span class="badge hit">🔥 爆款</span>' : '<span class="badge">常规</span>'}</td>
    </tr>`).join("");
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
            <button class="btn small filled" title="采纳 → 开始生产（日选题：时效×1.2+热度×1.2+质量×0.4；周选题：质量×1.2+热度×0.5+时效×0.3；IP 为准入门槛）" onclick="adopt('${esc(c.title).replace(/'/g, "\\'")}')">采纳生产</button>
          </td>
        </tr>`;
      }).join("")
    : `<tr><td class="muted" colspan="${SCORE_DIMS.length + 2}">暂无${poolLabel}选题（先运行“采集热点 + 推荐”）</td></tr>`;
}

async function loadTopics() {
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

async function adopt(title) {
  if (!confirm("采纳选题并开始自动生产：\n" + title + "\n\n将创建任务并调用本机 Codex 后台跑完整流水线（素材→初稿→视觉→质检→归档）。")) return;
  try {
    const d = await api("/api/topics/adopt", {
      method: "POST", headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ title }),
    });
    toast("已创建任务并开始生产: " + d.job_id + (d.production_started ? "" : "（排队中）"));
    loadTopics();
    loadPipeline();
  } catch (e) {
    toast("建任务失败: " + e.message, false);
  }
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
      const statusBtn = statusButton(it.status, it.viral_id, rec.has_report);
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

function statusButton(status, vid, hasReport) {
  if (status === "analyzing") {
    return '<span class="badge primary" title="拆解进行中，完成后自动更新">拆解中</span>';
  }
  if (status === "analyzed" || status === "applied") {
    if (hasReport) {
      return `<button class="btn small vstatus" title="点击查看拆解报告" onclick="viewBreakdown('${esc(vid)}')">已拆解</button>`;
    }
    return `<button class="btn small filled vstatus" title="该记录缺少报告文件，点击重新拆解" onclick="analyzeDailyItem('${esc(vid)}')">已拆解·重新拆</button>`;
  }
  return `<button class="btn small filled vstatus" title="点击开始 AI 拆解" onclick="analyzeDailyItem('${esc(vid)}')">待拆解</button>`;
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
      ? statusButton(status, v.id, v.has_report)
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
        <pre style="white-space:pre-wrap;font-size:13px;font-family:inherit;color:#3c4043;max-height:420px;overflow:auto;margin-top:10px">${esc(body)}</pre>`;
    } else {
      const content = stripFrontmatter(d.content || "");
      div.style.maxHeight = "480px";
      div.style.overflow = "auto";
      div.innerHTML = `<pre style="white-space:pre-wrap;font-size:13px;font-family:inherit;color:#3c4043">${esc(content)}</pre>`;
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
    $("#stats-updated-at").textContent = "更新于 " + (stats.generated_at || "");
    statKpis(stats);
    renderPlatformCompare(stats.by_platform || []);
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

$("#btn-xhs-import").addEventListener("click", () => $("#xhs-import-file").click());
$("#xhs-import-file").addEventListener("change", async (e) => {
  const file = e.target.files && e.target.files[0];
  if (!file) return;
  try {
    const d = await api(`/api/stats/import-xhs?filename=${encodeURIComponent(file.name)}`, {
      method: "POST",
      body: file,
    });
    toast(`导入完成：新增 ${d.new_notes ?? 0} / 更新 ${d.updated_notes ?? 0}，匹配 Job ${d.matched_jobs ?? 0} 条`);
    loadData();
    loadOverview();
  } catch (err) {
    toast("导入失败: " + err.message, false);
  }
  e.target.value = "";
});

$("#btn-dash-import").addEventListener("click", () => $("#dash-import-file").click());
$("#dash-import-file").addEventListener("change", async (e) => {
  const file = e.target.files && e.target.files[0];
  if (!file) return;
  try {
    const d = await api(`/api/stats/import-dashboard?filename=${encodeURIComponent(file.name)}`, {
      method: "POST",
      body: file,
    });
    const series = Object.entries(d.series || {}).map(([k, v]) => `${k} ${v}条`).join("、");
    toast(`已导入「${d.kind}」看板：指标 ${(d.account_keys || []).length} 个${series ? "，" + series : ""}`);
    loadData();
    loadDashboard();
  } catch (err) {
    toast("导入失败: " + err.message, false);
  }
  e.target.value = "";
});

// ---------- 初始化 ----------
document.addEventListener("DOMContentLoaded", () => {
  switchView("overview");
  loadLicenseStatus();
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

// ---------- 配置（API Key / 公众号凭据） ----------
function openSettings() {
  loadSettings();
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
