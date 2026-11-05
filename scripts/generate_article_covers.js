const { chromium } = require('/Users/xiaowuliao/html-video/node_modules/.pnpm/playwright@1.60.0/node_modules/playwright');
const path = require('path');
const fs = require('fs');

async function renderCovers() {
  const outputDir = '/Users/xiaowuliao/Projects/自媒体发布agent/outputs/2026-11-06_美股科技夜盘暴跌2.3万亿/公众号';
  if (!fs.existsSync(outputDir)) {
    fs.mkdirSync(outputDir, { recursive: true });
  }

  const browser = await chromium.launch({
    executablePath: '/Applications/Google Chrome.app/Contents/MacOS/Google Chrome',
    headless: true
  });

  const page = await browser.newPage();

  // Template 1: 2.35:1 Banner (2350 x 1000) - Standard WeChat Official Account Feed Card
  const html235 = `
  <!DOCTYPE html>
  <html>
  <head>
    <meta charset="UTF-8">
    <style>
      * { margin: 0; padding: 0; box-sizing: border-box; }
      body {
        width: 2350px;
        height: 1000px;
        background: radial-gradient(circle at 80% 20%, #1e1b4b 0%, #0f172a 45%, #050811 100%);
        font-family: -apple-system, BlinkMacSystemFont, "PingFang SC", "Hiragino Sans GB", "Microsoft YaHei", sans-serif;
        color: #ffffff;
        display: flex;
        flex-direction: column;
        justify-content: space-between;
        padding: 70px 90px;
        position: relative;
        overflow: hidden;
      }
      /* Subtle grid & circuit effect */
      .grid-overlay {
        position: absolute;
        inset: 0;
        background-image: 
          linear-gradient(rgba(239, 68, 68, 0.05) 1px, transparent 1px),
          linear-gradient(90deg, rgba(239, 68, 68, 0.05) 1px, transparent 1px);
        background-size: 60px 60px;
        pointer-events: none;
      }
      /* Red glow blur in corner */
      .red-glow {
        position: absolute;
        width: 700px;
        height: 700px;
        right: -100px;
        top: -100px;
        background: radial-gradient(circle, rgba(220, 38, 38, 0.28) 0%, rgba(220, 38, 38, 0) 70%);
        filter: blur(60px);
        pointer-events: none;
      }
      /* Top header */
      .top-row {
        position: relative;
        display: flex;
        align-items: center;
        justify-content: space-between;
        z-index: 2;
      }
      .badge-group {
        display: flex;
        align-items: center;
        gap: 16px;
      }
      .live-pill {
        display: inline-flex;
        align-items: center;
        gap: 10px;
        background: rgba(220, 38, 38, 0.2);
        border: 1.5px solid #ef4444;
        color: #fca5a5;
        padding: 10px 24px;
        border-radius: 40px;
        font-size: 24px;
        font-weight: 800;
        letter-spacing: 1px;
      }
      .live-dot {
        width: 12px;
        height: 12px;
        background: #ef4444;
        border-radius: 50%;
        box-shadow: 0 0 12px #ef4444;
      }
      .brand-title {
        font-size: 26px;
        color: #94a3b8;
        font-weight: 700;
        letter-spacing: 2px;
      }
      .date-tag {
        font-size: 24px;
        color: #64748b;
        font-family: ui-monospace, Menlo, Consolas, monospace;
      }

      /* Main Content Area */
      .main-body {
        position: relative;
        display: flex;
        align-items: center;
        justify-content: space-between;
        z-index: 2;
        margin: 20px 0;
      }
      .left-titles {
        max-width: 1350px;
      }
      .alert-subtitle {
        font-size: 38px;
        font-weight: 800;
        color: #f87171;
        letter-spacing: 2px;
        margin-bottom: 14px;
        display: flex;
        align-items: center;
        gap: 14px;
      }
      .title-line-1 {
        font-size: 82px;
        font-weight: 900;
        line-height: 1.15;
        letter-spacing: -1px;
        color: #ffffff;
      }
      .title-line-1 .highlight-red {
        color: #ef4444;
        background: linear-gradient(180deg, #f87171 0%, #dc2626 100%);
        -webkit-background-clip: text;
        -webkit-text-fill-color: transparent;
      }
      .title-line-2 {
        font-size: 54px;
        font-weight: 800;
        color: #cbd5e1;
        margin-top: 14px;
        letter-spacing: 0.5px;
      }

      /* Right Metric Card */
      .right-card {
        background: rgba(15, 23, 42, 0.75);
        border: 2px solid rgba(239, 68, 68, 0.4);
        border-radius: 24px;
        padding: 36px 44px;
        box-shadow: 0 20px 50px rgba(0, 0, 0, 0.5), inset 0 0 30px rgba(220, 38, 38, 0.1);
        backdrop-filter: blur(12px);
        min-width: 620px;
      }
      .metric-header {
        font-size: 22px;
        color: #94a3b8;
        letter-spacing: 1.5px;
        text-transform: uppercase;
        margin-bottom: 6px;
      }
      .metric-big {
        font-size: 78px;
        font-weight: 900;
        color: #ef4444;
        font-family: ui-monospace, Menlo, Consolas, monospace;
        line-height: 1.05;
        margin-bottom: 20px;
        text-shadow: 0 0 25px rgba(239, 68, 68, 0.4);
      }
      .ticker-chips {
        display: grid;
        grid-template-columns: 1fr 1fr;
        gap: 12px;
      }
      .ticker-chip {
        background: rgba(30, 41, 59, 0.8);
        border: 1px solid rgba(239, 68, 68, 0.3);
        padding: 10px 16px;
        border-radius: 12px;
        display: flex;
        justify-content: space-between;
        align-items: center;
      }
      .ticker-name {
        font-size: 22px;
        font-weight: 700;
        color: #e2e8f0;
      }
      .ticker-pct {
        font-size: 24px;
        font-weight: 800;
        color: #f87171;
        font-family: ui-monospace, Menlo, Consolas, monospace;
      }

      /* Bottom Footer row */
      .bottom-row {
        position: relative;
        display: flex;
        align-items: center;
        justify-content: space-between;
        border-top: 1px solid rgba(148, 163, 184, 0.2);
        padding-top: 24px;
        z-index: 2;
      }
      .bullet-points {
        display: flex;
        align-items: center;
        gap: 32px;
        font-size: 24px;
        font-weight: 700;
        color: #94a3b8;
      }
      .bullet-points span {
        color: #f87171;
        margin-right: 8px;
      }
      .watermark {
        font-size: 26px;
        font-weight: 800;
        color: #e2e8f0;
        letter-spacing: 1px;
      }
    </style>
  </head>
  <body>
    <div class="grid-overlay"></div>
    <div class="red-glow"></div>

    <div class="top-row">
      <div class="badge-group">
        <div class="live-pill">
          <div class="live-dot"></div>
          MARKET FLASH · 深度拆解
        </div>
        <div class="brand-title">小吴聊 · 科技商业与二级市场</div>
      </div>
      <div class="date-tag">2026.11.06 MIDNIGHT</div>
    </div>

    <div class="main-body">
      <div class="left-titles">
        <div class="alert-subtitle">
          <span>⚡ 中期选举“蓝潮”引爆估值大震荡</span>
        </div>
        <div class="title-line-1">
          美股科技<span class="highlight-red">夜盘彻底恐慌</span>
        </div>
        <div class="title-line-2">
          AI军备竞赛终结？还是主线全面换轨？
        </div>
      </div>

      <div class="right-card">
        <div class="metric-header">科技股市值单日蒸发</div>
        <div class="metric-big">-$2.30T</div>
        <div class="ticker-chips">
          <div class="ticker-chip">
            <span class="ticker-name">闪迪 SanDisk</span>
            <span class="ticker-pct">-20%</span>
          </div>
          <div class="ticker-chip">
            <span class="ticker-name">Lumentum</span>
            <span class="ticker-pct">-16%</span>
          </div>
          <div class="ticker-chip">
            <span class="ticker-name">高通 QCOM</span>
            <span class="ticker-pct">-14%</span>
          </div>
          <div class="ticker-chip">
            <span class="ticker-name">英伟达 NVDA</span>
            <span class="ticker-pct">-9.1%</span>
          </div>
        </div>
      </div>
    </div>

    <div class="bottom-row">
      <div class="bullet-points">
        <div><span>▶</span> 算力物理墙与政策墙</div>
        <div><span>▶</span> 华尔街转向看自由现金流</div>
        <div><span>▶</span> 中国科技追赶窗口与接棒主线</div>
      </div>
      <div class="watermark">@小吴聊原创投研</div>
    </div>
  </body>
  </html>
  `;

  // Render 2.35:1
  await page.setViewportSize({ width: 2350, height: 1000 });
  await page.setContent(html235, { waitUntil: 'load' });
  await page.waitForTimeout(600);
  const path235 = path.join(outputDir, 'cover_gzh_2.35x1.png');
  const pathDefault = path.join(outputDir, '封面.png');
  await page.screenshot({ path: path235 });
  await page.screenshot({ path: pathDefault });
  console.log('✅ Generated 2.35:1 WeChat Cover:', path235);

  // Template 2: 16:9 Banner (1920 x 1080)
  const html169 = `
  <!DOCTYPE html>
  <html>
  <head>
    <meta charset="UTF-8">
    <style>
      * { margin: 0; padding: 0; box-sizing: border-box; }
      body {
        width: 1920px;
        height: 1080px;
        background: radial-gradient(circle at 75% 25%, #1e1b4b 0%, #0f172a 45%, #050811 100%);
        font-family: -apple-system, BlinkMacSystemFont, "PingFang SC", "Hiragino Sans GB", "Microsoft YaHei", sans-serif;
        color: #ffffff;
        display: flex;
        flex-direction: column;
        justify-content: space-between;
        padding: 80px;
        position: relative;
        overflow: hidden;
      }
      .grid-overlay {
        position: absolute;
        inset: 0;
        background-image: 
          linear-gradient(rgba(239, 68, 68, 0.05) 1px, transparent 1px),
          linear-gradient(90deg, rgba(239, 68, 68, 0.05) 1px, transparent 1px);
        background-size: 50px 50px;
        pointer-events: none;
      }
      .red-glow {
        position: absolute;
        width: 600px;
        height: 600px;
        right: 0px;
        top: 0px;
        background: radial-gradient(circle, rgba(220, 38, 38, 0.3) 0%, rgba(220, 38, 38, 0) 70%);
        filter: blur(70px);
        pointer-events: none;
      }
      .top-row {
        position: relative;
        display: flex;
        align-items: center;
        justify-content: space-between;
        z-index: 2;
      }
      .badge-group {
        display: flex;
        align-items: center;
        gap: 16px;
      }
      .live-pill {
        display: inline-flex;
        align-items: center;
        gap: 10px;
        background: rgba(220, 38, 38, 0.2);
        border: 1.5px solid #ef4444;
        color: #fca5a5;
        padding: 10px 24px;
        border-radius: 40px;
        font-size: 22px;
        font-weight: 800;
      }
      .live-dot {
        width: 10px;
        height: 10px;
        background: #ef4444;
        border-radius: 50%;
        box-shadow: 0 0 10px #ef4444;
      }
      .brand-title {
        font-size: 24px;
        color: #94a3b8;
        font-weight: 700;
        letter-spacing: 2px;
      }

      .main-body {
        position: relative;
        z-index: 2;
        margin: auto 0;
      }
      .alert-subtitle {
        font-size: 32px;
        font-weight: 800;
        color: #f87171;
        letter-spacing: 2px;
        margin-bottom: 16px;
      }
      .title-line-1 {
        font-size: 78px;
        font-weight: 900;
        line-height: 1.18;
        letter-spacing: -1px;
      }
      .title-line-1 .highlight-red {
        color: #ef4444;
        background: linear-gradient(180deg, #f87171 0%, #dc2626 100%);
        -webkit-background-clip: text;
        -webkit-text-fill-color: transparent;
      }
      .title-line-2 {
        font-size: 48px;
        font-weight: 800;
        color: #cbd5e1;
        margin-top: 18px;
      }

      .metric-bar {
        margin-top: 36px;
        display: flex;
        align-items: center;
        gap: 24px;
        background: rgba(15, 23, 42, 0.75);
        border: 2px solid rgba(239, 68, 68, 0.4);
        border-radius: 20px;
        padding: 24px 32px;
        backdrop-filter: blur(12px);
      }
      .metric-col {
        border-right: 1px solid rgba(148, 163, 184, 0.2);
        padding-right: 30px;
      }
      .metric-col:last-child {
        border-right: none;
        padding-right: 0;
      }
      .metric-lbl {
        font-size: 18px;
        color: #94a3b8;
        margin-bottom: 4px;
      }
      .metric-val {
        font-size: 44px;
        font-weight: 900;
        color: #ef4444;
        font-family: ui-monospace, Menlo, Consolas, monospace;
      }

      .bottom-row {
        position: relative;
        display: flex;
        align-items: center;
        justify-content: space-between;
        border-top: 1px solid rgba(148, 163, 184, 0.2);
        padding-top: 24px;
        z-index: 2;
      }
      .bullet-points {
        display: flex;
        align-items: center;
        gap: 28px;
        font-size: 22px;
        font-weight: 700;
        color: #94a3b8;
      }
      .bullet-points span {
        color: #f87171;
        margin-right: 6px;
      }
      .watermark {
        font-size: 24px;
        font-weight: 800;
        color: #e2e8f0;
      }
    </style>
  </head>
  <body>
    <div class="grid-overlay"></div>
    <div class="red-glow"></div>

    <div class="top-row">
      <div class="badge-group">
        <div class="live-pill">
          <div class="live-dot"></div>
          MARKET FLASH · 深度研报
        </div>
        <div class="brand-title">小吴聊 · 科技商业与二级市场</div>
      </div>
      <div style="font-size: 22px; color: #64748b; font-family: ui-monospace, Menlo, monospace;">2026.11.06 MIDNIGHT</div>
    </div>

    <div class="main-body">
      <div class="alert-subtitle">⚡ 中期选举“蓝潮”掀起政策风暴 · 华尔街估值重构</div>
      <div class="title-line-1">
        美股科技<span class="highlight-red">彻底恐慌</span> · 单日狂泻2.3万亿
      </div>
      <div class="title-line-2">
        AI军备竞赛终结？还是主线全面换轨？
      </div>

      <div class="metric-bar">
        <div class="metric-col">
          <div class="metric-lbl">科技股市值蒸发</div>
          <div class="metric-val">-$2.30T</div>
        </div>
        <div class="metric-col">
          <div class="metric-lbl">费城半导体 (SOX)</div>
          <div class="metric-val">-7.2%</div>
        </div>
        <div class="metric-col">
          <div class="metric-lbl">闪迪 / Lumentum</div>
          <div class="metric-val" style="font-size: 34px;">-20% / -16%</div>
        </div>
        <div class="metric-col">
          <div class="metric-lbl">高通 / 特斯拉 / 英伟达</div>
          <div class="metric-val" style="font-size: 34px;">-14% / -10% / -9%</div>
        </div>
      </div>
    </div>

    <div class="bottom-row">
      <div class="bullet-points">
        <div><span>▶</span> 算力扩张撞上物理与政策墙</div>
        <div><span>▶</span> 华尔街转向看自由现金流(ROI)</div>
        <div><span>▶</span> 自主可控与三大接棒赛道深度透视</div>
      </div>
      <div class="watermark">@小吴聊原创投研</div>
    </div>
  </body>
  </html>
  `;

  // Render 16:9
  await page.setViewportSize({ width: 1920, height: 1080 });
  await page.setContent(html169, { waitUntil: 'load' });
  await page.waitForTimeout(600);
  const path169 = path.join(outputDir, 'cover_gzh_16x9.png');
  await page.screenshot({ path: path169 });
  console.log('✅ Generated 16:9 WeChat Cover:', path169);

  // Template 3: 1:1 Square (1080 x 1080) for WeChat secondary slot & feed square icon
  const html11 = `
  <!DOCTYPE html>
  <html>
  <head>
    <meta charset="UTF-8">
    <style>
      * { margin: 0; padding: 0; box-sizing: border-box; }
      body {
        width: 1080px;
        height: 1080px;
        background: radial-gradient(circle at 75% 25%, #1e1b4b 0%, #0f172a 45%, #050811 100%);
        font-family: -apple-system, BlinkMacSystemFont, "PingFang SC", "Hiragino Sans GB", "Microsoft YaHei", sans-serif;
        color: #ffffff;
        display: flex;
        flex-direction: column;
        justify-content: space-between;
        padding: 70px 60px;
        position: relative;
        overflow: hidden;
      }
      .grid-overlay {
        position: absolute;
        inset: 0;
        background-image: 
          linear-gradient(rgba(239, 68, 68, 0.05) 1px, transparent 1px),
          linear-gradient(90deg, rgba(239, 68, 68, 0.05) 1px, transparent 1px);
        background-size: 40px 40px;
        pointer-events: none;
      }
      .red-glow {
        position: absolute;
        width: 500px;
        height: 500px;
        right: -80px;
        top: -80px;
        background: radial-gradient(circle, rgba(220, 38, 38, 0.35) 0%, rgba(220, 38, 38, 0) 70%);
        filter: blur(60px);
        pointer-events: none;
      }
      .live-pill {
        display: inline-flex;
        align-items: center;
        gap: 8px;
        background: rgba(220, 38, 38, 0.2);
        border: 1.5px solid #ef4444;
        color: #fca5a5;
        padding: 8px 20px;
        border-radius: 40px;
        font-size: 20px;
        font-weight: 800;
        z-index: 2;
      }
      .live-dot {
        width: 10px;
        height: 10px;
        background: #ef4444;
        border-radius: 50%;
        box-shadow: 0 0 10px #ef4444;
      }
      .center-content {
        position: relative;
        z-index: 2;
        margin: auto 0;
      }
      .title-line {
        font-size: 68px;
        font-weight: 900;
        line-height: 1.2;
        color: #ffffff;
      }
      .highlight-red {
        color: #ef4444;
      }
      .sub-title {
        font-size: 36px;
        font-weight: 700;
        color: #94a3b8;
        margin-top: 14px;
      }
      .stat-box {
        margin-top: 30px;
        background: rgba(15, 23, 42, 0.85);
        border: 2px solid rgba(239, 68, 68, 0.4);
        border-radius: 18px;
        padding: 24px 28px;
      }
      .stat-num {
        font-size: 62px;
        font-weight: 900;
        color: #ef4444;
        font-family: ui-monospace, Menlo, Consolas, monospace;
        line-height: 1.1;
      }
      .stat-desc {
        font-size: 20px;
        color: #94a3b8;
        margin-top: 4px;
      }
      .bottom-info {
        position: relative;
        z-index: 2;
        display: flex;
        justify-content: space-between;
        align-items: center;
        border-top: 1px solid rgba(148, 163, 184, 0.2);
        padding-top: 20px;
        font-size: 20px;
        color: #64748b;
      }
    </style>
  </head>
  <body>
    <div class="grid-overlay"></div>
    <div class="red-glow"></div>

    <div style="position:relative; z-index:2; display:flex; justify-content:space-between; align-items:center;">
      <div class="live-pill">
        <div class="live-dot"></div>
        深夜重磅特刊
      </div>
      <div style="font-size:20px; color:#94a3b8; font-weight:700;">小吴聊 · 宏观投研</div>
    </div>

    <div class="center-content">
      <div class="title-line">
        美股科技<br/><span class="highlight-red">单日狂泻 2.3万亿</span>
      </div>
      <div class="sub-title">
        AI叙事终结还是主线切换？
      </div>

      <div class="stat-box">
        <div class="stat-num">-$2.30T</div>
        <div class="stat-desc">闪迪-20% · Lumentum-16% · 高通-14% · 特斯拉-10%</div>
      </div>
    </div>

    <div class="bottom-info">
      <div>穿透中期选举“蓝潮”与算力天花板</div>
      <div style="font-weight:800; color:#e2e8f0;">@小吴聊</div>
    </div>
  </body>
  </html>
  `;

  // Render 1:1
  await page.setViewportSize({ width: 1080, height: 1080 });
  await page.setContent(html11, { waitUntil: 'load' });
  await page.waitForTimeout(600);
  const path11 = path.join(outputDir, 'cover_gzh_1x1.png');
  await page.screenshot({ path: path11 });
  console.log('✅ Generated 1:1 WeChat Cover:', path11);

  await browser.close();
  console.log('🎉 All WeChat article covers generated successfully!');
}

renderCovers().catch(console.error);
