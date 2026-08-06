// 自媒体工作台 · 前端逻辑（原生 JS + fetch，无构建）
"use strict";

const $ = (sel) => document.querySelector(sel);
const toastEl = $("#toast");
let toastTimer = null;

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
    throw new Error(detail);
  }
  return res.json();
}

function esc(s) {
  return String(s == null ? "" : s).replace(/[&<>"']/g, (c) => (
    { "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]
  ));
}

// ---------- 视图切换 ----------
document.querySelectorAll(".tab").forEach((btn) => {
  btn.addEventListener("click", () => {
    document.querySelectorAll(".tab").forEach((b) => b.classList.remove("active"));
    btn.classList.add("active");
    document.querySelectorAll(".view").forEach((v) => v.classList.remove("active"));
    $("#view-" + btn.dataset.view).classList.add("active");
    if (btn.dataset.view === "overview") loadOverview();
    if (btn.dataset.view === "topics") loadTopics();
    if (btn.dataset.view === "jobs") loadJobs();
  });
});

// ---------- 概览 ----------
async function loadOverview() {
  try {
    const d = await api("/api/overview");
    const cards = [
      ["Job 总数", d.jobs_total], ["平均分", d.avg_score ?? "—"],
      ["待回收", d.pending_recycle], ["爆款", d.hits], ["总打回", d.reject_total],
    ];
    $("#overview-cards").innerHTML = cards.map(([lbl, num]) =>
      `<div class="card"><div class="num">${esc(num)}</div><div class="lbl">${esc(lbl)}</div></div>`).join("");
    const states = Object.entries(d.by_state);
    const total = d.jobs_total || 1;
    $("#state-bars").innerHTML = states.length
      ? states.map(([s, n]) => `
        <div class="sbar"><span class="name">${esc(s)}</span>
        <div class="track"><div class="fill" style="width:${(n / total * 100).toFixed(0)}%"></div></div>
        <span class="cnt">${n}</span></div>`).join("")
      : '<span class="muted">暂无 Job</span>';
  } catch (e) { toast("概览加载失败: " + e.message, false); }
}

// ---------- 选题 ----------
async function loadTopics() {
  try {
    const d = await api("/api/topics");
    $("#radar-path").textContent = d.radar.path ? "(" + d.radar.path + ")" : "";
    $("#suggest-list").innerHTML = d.suggest.candidates.length
      ? d.suggest.candidates.map((c) => `
        <div class="topic-item">
          <div class="t">⭐${c.score ?? "?"} ${esc(c.title)}</div>
          <div class="meta">${esc(c.source || "")} · ${esc(c.view || "")}</div>
          <div class="meta">公式：${esc(c.formulas || "—")}</div>
          <button class="btn small" onclick="adopt('${esc(c.title).replace(/'/g, "\\'")}')">采纳 → 建 Job</button>
        </div>`).join("")
      : '<span class="muted">暂无选题推荐（先运行 run_daily_pipeline.py --topics）</span>';
    $("#radar-list").innerHTML = d.radar.sources.map((s) => `
      <div class="radar-src"><div class="src">${esc(s.source)}</div>
      <ol>${s.items.slice(0, 8).map((i) => `<li>${esc(i.title)}</li>`).join("")}</ol></div>`).join("")
      || '<span class="muted">无热点雷达数据</span>';
  } catch (e) { toast("选题加载失败: " + e.message, false); }
}

async function adopt(title) {
  if (!confirm("采纳选题并创建 Job：\n" + title)) return;
  try {
    const d = await api("/api/topics/adopt", {
      method: "POST", headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ title }),
    });
    toast("已创建 Job: " + d.job_id);
    loadTopics(); loadJobs();
  } catch (e) { toast("建 Job 失败: " + e.message, false); }
}
window.adopt = adopt;

// ---------- 流水线触发 ----------
async function runPipeline(action) {
  const labels = { topics: "采集热点+选题推荐", recycle: "48h 回收检查", weekly: "质量周报" };
  if (!confirm("运行流水线动作：" + (labels[action] || action) + "？")) return;
  toast("流水线运行中（最长 180s）…", true);
  try {
    const d = await api("/api/pipeline/run", {
      method: "POST", headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ action }),
    });
    const tail = (d.stdout || "").split("\n").slice(-4).join("\n");
    toast(d.ok ? "✅ " + labels[action] + " 完成" : "⚠️ 有阻塞项，见控制台输出", d.ok);
    console.log(labels[action] + " 输出:\n" + (d.stdout || "") + (d.stderr || ""));
    if (action === "topics") loadTopics();
    if (action === "recycle" || action === "weekly") loadOverview();
  } catch (e) { toast("流水线失败: " + e.message, false); }
}
window.runPipeline = runPipeline;

// ---------- Job ----------
const STATE_ORDER = ["topic", "materials", "draft", "visual", "review", "archive", "publish", "recycle"];

async function loadJobs() {
  try {
    const d = await api("/api/jobs");
    $("#jobs-table tbody").innerHTML = d.jobs.map((j) => `
      <tr>
        <td>${esc(j.job_id)}</td>
        <td>${esc(j.theme || "—")}</td>
        <td><span class="badge ${["publish", "recycle", "reject"].includes(j.state) ? j.state : ""}">${esc(j.state)}</span></td>
        <td>${j.scores && Object.keys(j.scores).length ? esc(Object.entries(j.scores).map(([k, v]) => `${k}:${v}`).join(", ")) : "—"}</td>
        <td>${j.reject_count}</td>
        <td>${esc(j.updated_at || "")}</td>
        <td><button class="btn small" onclick="showJob('${esc(j.job_id)}')">详情</button></td>
      </tr>`).join("");
  } catch (e) { toast("Job 列表加载失败: " + e.message, false); }
}

async function showJob(jobId) {
  try {
    const d = await api("/api/jobs/" + encodeURIComponent(jobId));
    const s = d.state || {};
    const idx = STATE_ORDER.indexOf(s.state);
    const progress = STATE_ORDER.map((st, i) =>
      i < idx ? "✅" : i === idx ? "🔵" : "·").join(" ");
    const hist = (s.history || []).slice(-6).map((h) =>
      `[${esc(h.at)}] ${esc(h.state)}${h.score != null ? " score=" + h.score : ""}${h.note ? " # " + esc(h.note) : ""}`).join("\n");
    const vr = d.validate_report, hr = d.harsh_report, pl = d.publish_log;
    $("#job-detail").classList.remove("hidden");
    $("#job-detail").innerHTML = `
      <h3>📋 ${esc(jobId)} <button class="btn small" onclick="runQaFor('${esc(jobId)}')">跑质检</button>
          <button class="btn small" onclick="loadOutputs('${esc(jobId)}')">📄 产出文件</button></h3>
      <p class="muted">主题：${esc(s.theme || "—")} ｜ 打回：${s.reject_count ?? 0}</p>
      <div class="progress">${progress}</div>
      <pre class="result">${esc(hist)}</pre>
      <div id="outputs-box"></div>
      ${vr ? `<h4>契约校验: ${esc(vr.verdict)} (FAIL ${vr.fails} / WARN ${vr.warns})</h4>
        <pre class="result">${esc(vr.results.map(r => `[${r.level}] ${r.code} ${r.message}`).join("\n"))}</pre>` : ""}
      ${hr ? `<h4>Harsh Critic: ${esc(hr.score)}/100 → ${esc(hr.verdict)}</h4>` : ""}
      ${pl ? `<h4>发布日志: ${pl.records ? pl.records.length : 0} 条记录</h4>
        <pre class="result">${esc(JSON.stringify(pl, null, 2).slice(0, 1500))}</pre>` : ""}`;
  } catch (e) { toast("详情加载失败: " + e.message, false); }
}
window.showJob = showJob;

// ---------- 产出文件预览 ----------
async function loadOutputs(jobId) {
  const box = $("#outputs-box");
  box.innerHTML = '<span class="muted">加载产出文件…</span>';
  try {
    const d = await api("/api/outputs/" + encodeURIComponent(jobId));
    if (!d.files.length) { box.innerHTML = '<span class="muted">该 Job 暂无产出（outputs/ 下无文件）</span>'; return; }
    box.innerHTML = "<h4>📄 产出文件</h4><div style='margin-bottom:8px'>" +
      d.files.map((f) => {
        const icon = f.kind === "img" ? "🖼️" : f.kind === "html" ? "🌐" : f.kind === "md" ? "📝" : "📎";
        const kb = (f.size / 1024).toFixed(1);
        return `<span class="outfile" data-rel="${esc(f.rel)}" data-kind="${f.kind}" onclick="openOutput('${esc(jobId)}','${esc(f.rel)}','${f.kind}')">${icon} ${esc(f.rel)} (${kb}K)</span>`;
      }).join("") + "</div><div id='output-preview'></div>";
  } catch (e) { box.innerHTML = '<span class="muted">产出加载失败: ' + esc(e.message) + "</span>"; }
}
window.loadOutputs = loadOutputs;

async function openOutput(jobId, rel, kind) {
  const pv = $("#output-preview");
  const url = "/assets/outputs/" + jobId + "/" + rel;
  if (kind === "img") {
    pv.innerHTML = `<img src="${esc(url)}" style="max-width:100%;border-radius:8px;border:1px solid #e5e7eb">`;
  } else if (kind === "html") {
    pv.innerHTML = `<iframe src="${esc(url)}" style="width:100%;height:420px;border:1px solid #e5e7eb;border-radius:8px"></iframe>`;
  } else if (kind === "md") {
    const d = await api("/api/outputs/" + encodeURIComponent(jobId) + "/file?rel=" + encodeURIComponent(rel));
    pv.innerHTML = `<pre class="result" style="max-height:420px">${esc(d.content || "(空)")}</pre>`;
  } else {
    pv.innerHTML = `<a href="${esc(url)}" target="_blank" class="btn small">打开文件 ${esc(rel)}</a>`;
  }
}
window.openOutput = openOutput;

// ---------- 质检 ----------
async function runQa(jobId) {
  const out = jobId || $("#qa-job").value.trim();
  if (!out) return toast("请输入 job_id", false);
  $("#qa-result").classList.remove("hidden");
  $("#qa-result").textContent = "质检运行中…";
  try {
    const d = await api("/api/qa", {
      method: "POST", headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ output_dir: "outputs/" + out }),
    });
    const c = d.contract, h = d.harsh;
    $("#qa-result").textContent = [
      `契约校验: ${c ? c.verdict + " (FAIL " + c.fails + ")" : "未生成"}`,
      `Harsh Critic: ${h ? h.score + "/100 → " + h.verdict : "未生成"}`,
      "", "--- 契约明细 ---",
      c ? c.results.map(r => `[${r.level}] ${r.code} ${r.message}`).join("\n") : d.contract_run.stderr,
    ].join("\n");
  } catch (e) { $("#qa-result").textContent = "质检失败: " + e.message; }
}
function runQaFor(jobId) { runQa(jobId); }
window.runQaFor = runQaFor;
window.runQa = runQa;

// ---------- 发布 ----------
async function doPublish() {
  const title = $("#pub-title").value.trim();
  if (!title) return toast("请填写标题", false);
  if (!confirm("确认发布《" + title + "》到 NAS？\n（小红书自动发布 + 公众号草稿）")) return;
  const split = (v) => v.split(",").map(s => s.trim()).filter(Boolean);
  const payload = {
    title,
    job_id: $("#pub-job").value.trim(),
    content: $("#pub-content").value,
    gzh_html: $("#pub-gzh").value,
    images: split($("#pub-images").value),
    tags: split($("#pub-tags").value),
  };
  $("#publish-result").classList.remove("hidden");
  $("#publish-result").textContent = "发布中（NAS 直连，最长 180s）…";
  try {
    const d = await api("/api/publish", {
      method: "POST", headers: { "Content-Type": "application/json" },
      body: JSON.stringify(payload),
    });
    $("#publish-result").textContent = (d.stdout || "") + (d.stderr || "");
    toast(d.ok ? "发布请求已完成" : "发布有告警，见输出", d.ok);
  } catch (e) { $("#publish-result").textContent = "发布失败: " + e.message; }
}

// ---------- 事件绑定 ----------
document.addEventListener("DOMContentLoaded", () => {
  loadOverview();
  $("#btn-refresh-topics").addEventListener("click", loadTopics);
  $("#btn-refresh-jobs").addEventListener("click", loadJobs);
  $("#btn-qa").addEventListener("click", () => runQa(""));
  $("#btn-publish").addEventListener("click", doPublish);
});
