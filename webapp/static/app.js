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
  themes: ["主题库", "6 个引流内容主题 · 一键复制出题指令"],
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
  if (name === "themes") loadThemes();
  if (name === "pipeline") loadPipeline();
  if (name === "outputs") loadOutputsView();
  if (name === "data") loadData();
}
window.switchView = switchView;

$$(".nav-item").forEach((btn) => btn.addEventListener("click", () => switchView(btn.dataset.view)));
$("#btn-refresh-topics").addEventListener("click", loadTopics);

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
  } catch (e) {
    toast("概览加载失败: " + e.message, false);
  }
}

function renderRows(records) {
  if (!records.length) return '<tr><td colspan="9" class="muted">暂无回填数据</td></tr>';
  return records.map((r) => `
    <tr>
      <td>${esc((r.collected_at || "").slice(0, 16))}</td>
      <td title="${esc(r.theme || "")}">${esc(r.job_id)}</td>
      <td>${esc(r.platform || "—")}</td>
      <td class="num">${fmtNum(r.reads)}</td>
      <td class="num">${fmtNum(r.likes)}</td>
      <td class="num">${fmtNum(r.collects)}</td>
      <td class="num">${fmtNum(r.comments)}</td>
      <td class="num">${pct(r.engagement)}</td>
      <td>${r.hit ? '<span class="badge hit">🔥 爆款</span>' : '<span class="badge">常规</span>'}</td>
    </tr>`).join("");
}

// ---------- 选题 ----------
async function loadTopics() {
  try {
    const d = await api("/api/topics");
    $("#radar-path").textContent = d.radar.path ? "(" + d.radar.path + ")" : "";
    $("#suggest-path").textContent = d.suggest.path ? "(" + d.suggest.path + ")" : "";
    $("#suggest-list").innerHTML = d.suggest.candidates.length
      ? d.suggest.candidates.map((c) => `
        <div class="topic-item">
          <div class="t">⭐${c.score ?? "?"}　${esc(c.title)}</div>
          <div class="meta">${esc(c.source || "")} · ${esc(c.view || "")}</div>
          <div class="meta">公式：${esc(c.formulas || "—")}</div>
          <div class="actions">
            <button class="btn small filled" onclick="adopt('${esc(c.title).replace(/'/g, "\\'")}')">采纳 → 建任务</button>
          </div>
        </div>`).join("")
      : '<span class="muted">暂无选题推荐（先运行“采集热点 + 推荐”）</span>';
    $("#radar-list").innerHTML = d.radar.sources.map((s) => `
      <div class="radar-src">
        <div class="src">${esc(s.source)}</div>
        <ol>${s.items.slice(0, 8).map((i) => `<li>${esc(i.title)}</li>`).join("")}</ol>
      </div>`).join("") || '<span class="muted">无热点雷达数据</span>';
  } catch (e) {
    toast("选题加载失败: " + e.message, false);
  }
}

async function adopt(title) {
  if (!confirm("采纳选题并创建任务：\n" + title)) return;
  try {
    const d = await api("/api/topics/adopt", {
      method: "POST", headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ title }),
    });
    toast("已创建任务: " + d.job_id);
    loadTopics();
  } catch (e) {
    toast("建任务失败: " + e.message, false);
  }
}
window.adopt = adopt;

// ---------- 主题库 ----------
let themesCache = [];

async function loadThemes() {
  try {
    const d = await api("/api/themes");
    themesCache = d.themes || [];
    $("#theme-cards").innerHTML = themesCache.map((t) => `
      <div class="agent-card theme-card">
        <div class="head">
          <span class="emoji">${t.emoji}</span>
          <div>
            <div class="role">${esc(t.name)}</div>
            <div class="en">${esc(t.traffic)}</div>
          </div>
        </div>
        <div class="resp">${esc(t.slogan)}</div>
        <div class="kv" style="margin:6px 0">受众：<b>${esc(t.audience)}</b></div>
        <div class="jobs" style="margin-bottom:8px">
          ${(t.hooks || []).map((h) => `<span class="badge primary">${esc(h)}</span>`).join("")}
        </div>
        <div class="samples">
          ${(t.samples || []).map((s) => `<div class="kv">• ${esc(s)}</div>`).join("")}
        </div>
        <div style="margin-top:12px">
          <button class="btn small filled" onclick="copyThemePrompt('${esc(t.id)}')">复制出题指令</button>
        </div>
      </div>`).join("");
  } catch (e) {
    toast("主题库加载失败: " + e.message, false);
  }
}

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

async function loadPipeline() {
  try {
    const [jobsRes, agentsRes] = await Promise.all([api("/api/jobs"), api("/api/agents")]);
    pipelineJobs = jobsRes.jobs;
    const sel = $("#pipeline-job-select");
    const prev = sel.value;
    sel.innerHTML = pipelineJobs.map((j) =>
      `<option value="${esc(j.job_id)}">${esc(j.job_id)} · ${esc(j.theme || "")}</option>`).join("");
    if (prev && pipelineJobs.some((j) => j.job_id === prev)) sel.value = prev;
    renderPipelineJob();
    renderAgents(agentsRes.agents);
  } catch (e) {
    toast("流水线加载失败: " + e.message, false);
  }
}

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
async function loadOutputsView() {
  try {
    const d = await api("/api/jobs");
    const sel = $("#outputs-job-select");
    const prev = sel.value;
    sel.innerHTML = d.jobs.map((j) =>
      `<option value="${esc(j.job_id)}">${esc(j.job_id)} · ${esc(j.theme || "")}</option>`).join("");
    if (prev && d.jobs.some((j) => j.job_id === prev)) sel.value = prev;
    renderOutputs();
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
    }
    if (slides) box.innerHTML += `<div class="frame-box" style="margin-top:14px"><iframe src="/assets/outputs/${encodeURIComponent(artifactState.jobId)}/${esc(slides.rel)}"></iframe></div>`;
    if (md) renderMd(md, box);
    if (!slides && !md) box.innerHTML += '<span class="muted">（无 slides HTML / 文案）</span>';
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

async function renderMd(file, box) {
  try {
    const d = await api("/api/outputs/" + encodeURIComponent(artifactState.jobId) + "/file?rel=" + encodeURIComponent(file.rel));
    const div = document.createElement("div");
    div.className = "frame-box";
    div.style.cssText = "margin-top:14px;padding:16px;max-height:480px;overflow:auto;";
    div.innerHTML = `<pre style="white-space:pre-wrap;font-size:13px;font-family:inherit;color:#3c4043">${esc(d.content || "")}</pre>`;
    box.appendChild(div);
  } catch (e) {
    box.innerHTML += '<span class="muted">文案加载失败</span>';
  }
}

async function renderArtifactSide(jobId) {
  try {
    const d = await api("/api/jobs/" + encodeURIComponent(jobId));
    const s = d.state || {};
    const vr = d.validate_report, hr = d.harsh_report, pl = d.publish_log || {};
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
    $("#artifact-publish").innerHTML = `
      <div class="kv">草稿推送：<b>${(pl.publish || []).length}</b> 次</div>
      <div class="kv">数据回填：<b>${(pl.records || []).length}</b> 条</div>
      <div class="kv">发布时间：<b>${esc(pl.published_at || "—")}</b></div>`;
  } catch (e) {
    $("#artifact-meta").innerHTML = '<span class="muted">详情加载失败</span>';
  }
}

// ---------- 数据 ----------
let statsCache = null;

function statKpis(d) {
  const items = [
    ["发布动作", d.publish_events ?? 0],
    ["人工回填", d.backfill_records ?? 0],
    ["总阅读", fmtNum(d.total_reads)],
    ["平均互动率", d.total_reads ? pct(d.avg_engagement) : "—"],
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
    <div class="kv">人工回填（阅读/赞/藏/评）：<b>${ds.manual_backfill ?? 0}</b> 条</div>
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
    block("公众号图表数", ins.gzh_viz) +
    block("小红书卡片数", ins.xhs_cards) +
    `<div class="kv muted">${esc(ins.note || "")}</div>`;
}

function renderBest(best) {
  const byReads = best && best.by_reads ? best.by_reads : [];
  const byEng = best && best.by_engagement ? best.by_engagement : [];
  if (!byReads.length && !byEng.length) return $("#best-list").innerHTML = '<span class="muted">暂无回填数据</span>';
  const row = (r) => `
    <div class="kv">${r.hit ? "🔥 " : ""}<b>${esc(r.title || r.job_id)}</b>（${esc(r.platform)}）阅读 ${fmtNum(r.reads)} ｜ 互动率 ${pct(r.engagement)}<span class="muted"> · ${esc(r.job_id)}</span></div>`;
  let html = "";
  if (byReads.length) html += `<div class="kv" style="margin-bottom:4px"><b>阅读 TOP${byReads.length}</b></div>` + byReads.map(row).join("");
  if (byEng.length) html += `<div class="kv" style="margin:10px 0 4px"><b>互动率 TOP${byEng.length}</b></div>` + byEng.map(row).join("");
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
    sel.innerHTML = jobs.jobs.map((j) =>
      `<option value="${esc(j.job_id)}">${esc(j.job_id)} · ${esc(j.theme || "")}</option>`).join("");
    if (prev && jobs.jobs.some((j) => j.job_id === prev)) sel.value = prev;
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

$("#btn-stats-refresh").addEventListener("click", async () => {
  try {
    await api("/api/stats/refresh", { method: "POST" });
    toast("统计已刷新");
    loadData();
    loadOverview();
  } catch (err) {
    toast("刷新失败: " + err.message, false);
  }
});

// ---------- 初始化 ----------
document.addEventListener("DOMContentLoaded", () => switchView("overview"));
