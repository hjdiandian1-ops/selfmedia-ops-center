const { chromium } = require('playwright');
const path = require('path');
const fs = require('fs');

(async () => {
    const browser = await chromium.launch();
    const page = await browser.newPage();

    const outputDir = '/Users/xiaowuliao/Projects/自媒体发布agent/outputs/processed_images';
    if (!fs.existsSync(outputDir)) {
        fs.mkdirSync(outputDir, { recursive: true });
    }

    // Cover 1: Xiaohongshu 3:4 Dark Neon Tech Style
    const cover1Html = `
    <!DOCTYPE html>
    <html>
    <head>
        <meta charset="UTF-8">
        <style>
            * { margin: 0; padding: 0; box-sizing: border-box; font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif; }
            body {
                width: 1080px;
                height: 1440px;
                background: #090D16;
                color: #FFFFFF;
                display: flex;
                flex-direction: column;
                justify-content: space-between;
                padding: 70px 60px;
                position: relative;
                overflow: hidden;
            }
            .bg-glow1 {
                position: absolute;
                top: -150px;
                right: -150px;
                width: 600px;
                height: 600px;
                background: radial-gradient(circle, rgba(99, 102, 241, 0.35) 0%, rgba(0,0,0,0) 70%);
                border-radius: 50%;
            }
            .bg-glow2 {
                position: absolute;
                bottom: -100px;
                left: -100px;
                width: 550px;
                height: 550px;
                background: radial-gradient(circle, rgba(16, 185, 129, 0.25) 0%, rgba(0,0,0,0) 70%);
                border-radius: 50%;
            }
            .badge-top {
                display: inline-flex;
                align-items: center;
                gap: 12px;
                background: rgba(99, 102, 241, 0.15);
                border: 1px solid rgba(129, 140, 248, 0.4);
                color: #A5B4FC;
                padding: 14px 28px;
                border-radius: 40px;
                font-size: 28px;
                font-weight: 600;
                letter-spacing: 1px;
                width: fit-content;
            }
            .title-box {
                margin-top: 35px;
            }
            .main-title {
                font-size: 72px;
                font-weight: 900;
                line-height: 1.25;
                background: linear-gradient(135deg, #FFFFFF 30%, #93C5FD 100%);
                -webkit-background-clip: text;
                -webkit-text-fill-color: transparent;
            }
            .highlight-tag {
                background: linear-gradient(135deg, #F59E0B, #EF4444);
                color: #FFF;
                padding: 4px 18px;
                border-radius: 12px;
                display: inline-block;
                -webkit-text-fill-color: #FFF;
            }
            .subtitle {
                font-size: 34px;
                color: #94A3B8;
                margin-top: 20px;
                font-weight: 500;
            }
            .preview-card-container {
                position: relative;
                margin: 40px 0;
                background: rgba(30, 41, 59, 0.7);
                border: 1px solid rgba(255, 255, 255, 0.12);
                backdrop-filter: blur(20px);
                border-radius: 28px;
                padding: 30px;
                box-shadow: 0 25px 50px -12px rgba(0, 0, 0, 0.5);
            }
            .card-header {
                display: flex;
                justify-content: space-between;
                align-items: center;
                padding-bottom: 20px;
                border-bottom: 1px solid rgba(255, 255, 255, 0.1);
                margin-bottom: 25px;
            }
            .card-title {
                font-size: 32px;
                font-weight: 700;
                color: #F3F4F6;
                display: flex;
                align-items: center;
                gap: 12px;
            }
            .metrics-grid {
                display: grid;
                grid-template-columns: repeat(2, 1fr);
                gap: 20px;
            }
            .metric-box {
                background: rgba(15, 23, 42, 0.8);
                border: 1px solid rgba(255, 255, 255, 0.08);
                padding: 24px;
                border-radius: 20px;
            }
            .metric-val {
                font-size: 42px;
                font-weight: 800;
                color: #38BDF8;
            }
            .metric-lbl {
                font-size: 24px;
                color: #94A3B8;
                margin-top: 6px;
            }
            .features-list {
                display: flex;
                flex-direction: column;
                gap: 18px;
                margin-top: 25px;
            }
            .feature-item {
                display: flex;
                align-items: center;
                gap: 16px;
                font-size: 30px;
                font-weight: 600;
                color: #E2E8F0;
                background: rgba(255, 255, 255, 0.05);
                padding: 18px 24px;
                border-radius: 18px;
                border-left: 5px solid #10B981;
            }
            .footer-box {
                background: linear-gradient(135deg, rgba(239, 68, 68, 0.2), rgba(245, 158, 11, 0.2));
                border: 1px solid rgba(245, 158, 11, 0.4);
                border-radius: 24px;
                padding: 28px 40px;
                display: flex;
                justify-content: space-between;
                align-items: center;
            }
            .footer-text {
                font-size: 32px;
                font-weight: 800;
                color: #FDE68A;
            }
            .cta-btn {
                background: #F59E0B;
                color: #000;
                padding: 16px 32px;
                border-radius: 40px;
                font-size: 28px;
                font-weight: 900;
            }
        </style>
    </head>
    <body>
        <div class="bg-glow1"></div>
        <div class="bg-glow2"></div>

        <div>
            <div class="badge-top">🤫 建议默默收藏 ｜ 打破信息差</div>
            <div class="title-box">
                <div class="main-title">没事少刷短视频！<br>多看看这个<span class="highlight-tag">AI宝藏站</span></div>
                <div class="subtitle">拉开同龄人10倍认知差距的技术情报库 🔥</div>
            </div>
        </div>

        <div class="preview-card-container">
            <div class="card-header">
                <div class="card-title">🌐 全球前沿 AI 数据情报门户</div>
                <span style="color:#10B981; font-weight:700; font-size:24px;">● 实时更新</span>
            </div>
            <div class="metrics-grid">
                <div class="metric-box">
                    <div class="metric-val">193.3K</div>
                    <div class="metric-lbl">💡 AI创作灵感</div>
                </div>
                <div class="metric-box">
                    <div class="metric-val">173.2K</div>
                    <div class="metric-lbl">🔥 历史热门干货</div>
                </div>
            </div>
            <div class="features-list">
                <div class="feature-item">📦 GitHub 热门 AI 开源项目榜</div>
                <div class="feature-item">⚡️ 字节/OpenAI 最新前沿热点</div>
                <div class="feature-item">📑 顶尖学术论文结构化解读</div>
            </div>
        </div>

        <div class="footer-box">
            <div class="footer-text">👇 评论区留言【学习】自动发网址</div>
            <div class="cta-btn">免费获取</div>
        </div>
    </body>
    </html>
    `;

    await page.setViewportSize({ width: 1080, height: 1440 });
    await page.setContent(cover1Html);
    await page.screenshot({ path: path.join(outputDir, 'xhs_cover_dark_neon.png') });

    // Cover 2: High Contrast Yellow/Black Style (Xiaohongshu 3:4)
    const cover2Html = `
    <!DOCTYPE html>
    <html>
    <head>
        <meta charset="UTF-8">
        <style>
            * { margin: 0; padding: 0; box-sizing: border-box; font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif; }
            body {
                width: 1080px;
                height: 1440px;
                background: #FACC15;
                color: #000000;
                display: flex;
                flex-direction: column;
                justify-content: space-between;
                padding: 70px 60px;
            }
            .header-tag {
                background: #000;
                color: #FACC15;
                padding: 16px 32px;
                border-radius: 50px;
                font-size: 32px;
                font-weight: 900;
                display: inline-block;
                width: fit-content;
            }
            .big-title {
                font-size: 88px;
                font-weight: 1000;
                line-height: 1.15;
                margin-top: 30px;
                letter-spacing: -2px;
            }
            .highlight-bg {
                background: #000;
                color: #FFF;
                padding: 6px 20px;
                border-radius: 16px;
                display: inline-block;
            }
            .sub-desc {
                font-size: 36px;
                font-weight: 700;
                margin-top: 20px;
                color: #1F2937;
            }
            .white-card {
                background: #FFFFFF;
                border: 6px solid #000;
                border-radius: 36px;
                padding: 40px;
                box-shadow: 16px 16px 0px #000;
            }
            .card-title {
                font-size: 36px;
                font-weight: 900;
                margin-bottom: 24px;
                border-bottom: 4px solid #FACC15;
                padding-bottom: 12px;
                display: inline-block;
            }
            .list-group {
                display: flex;
                flex-direction: column;
                gap: 20px;
            }
            .list-item {
                font-size: 32px;
                font-weight: 800;
                display: flex;
                align-items: center;
                gap: 16px;
            }
            .bottom-cta {
                background: #000;
                color: #FFF;
                border-radius: 30px;
                padding: 35px;
                text-align: center;
                font-size: 40px;
                font-weight: 900;
                box-shadow: 10px 10px 0px #FFF;
            }
        </style>
    </head>
    <body>
        <div>
            <div class="header-tag">🔥 强烈推荐 ｜ 建议收藏</div>
            <div class="big-title">
                拉开差距的<br>
                <span class="highlight-bg">AI极客站点</span> 🚀
            </div>
            <div class="sub-desc">别再盲目刷贴了，真正的高手都在看这个！</div>
        </div>

        <div class="white-card">
            <div class="card-title">📌 涵盖四大超强干货板块：</div>
            <div class="list-group">
                <div class="list-item">✅ 1. 全球 AI 行业实时热点与趋势</div>
                <div class="list-item">✅ 2. GitHub 最高分 AI 开源项目榜</div>
                <div class="list-item">✅ 3. 极客级 AI 创作灵感与工具包</div>
                <div class="list-item">✅ 4. 深度 AI 学术论文结构化提取</div>
            </div>
        </div>

        <div class="bottom-cta">
            👉 私信发【站点】立即获取网址
        </div>
    </body>
    </html>
    `;

    await page.setContent(cover2Html);
    await page.screenshot({ path: path.join(outputDir, 'xhs_cover_yellow_impact.png') });

    // Cover 3: WeChat Official Account Cover (16:9 - 1080x608)
    const gzhCoverHtml = `
    <!DOCTYPE html>
    <html>
    <head>
        <meta charset="UTF-8">
        <style>
            * { margin: 0; padding: 0; box-sizing: border-box; font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif; }
            body {
                width: 1080px;
                height: 608px;
                background: linear-gradient(135deg, #0F172A 0%, #1E1B4B 100%);
                color: #FFFFFF;
                display: flex;
                align-items: center;
                justify-content: space-between;
                padding: 50px 70px;
            }
            .left-part {
                max-width: 620px;
            }
            .tag {
                background: #3B82F6;
                color: #FFF;
                padding: 8px 20px;
                border-radius: 20px;
                font-size: 22px;
                font-weight: 700;
                display: inline-block;
                margin-bottom: 20px;
            }
            .title {
                font-size: 50px;
                font-weight: 900;
                line-height: 1.3;
            }
            .sub {
                font-size: 26px;
                color: #94A3B8;
                margin-top: 15px;
            }
            .right-part {
                background: rgba(255, 255, 255, 0.08);
                border: 1px solid rgba(255, 255, 255, 0.2);
                border-radius: 24px;
                padding: 30px;
                width: 320px;
                backdrop-filter: blur(10px);
            }
            .stat-title {
                font-size: 22px;
                color: #CBD5E1;
            }
            .stat-num {
                font-size: 44px;
                font-weight: 900;
                color: #38BDF8;
                margin: 5px 0 15px 0;
            }
            .stat-lbl {
                font-size: 20px;
                color: #10B981;
                font-weight: 700;
            }
        </style>
    </head>
    <body>
        <div class="left-part">
            <div class="tag">⚡️ 前沿AI情报站推荐</div>
            <div class="title">拉开认知差距！没事多刷刷这个AI宝藏库</div>
            <div class="sub">实时追踪热点 / 热门开源项目 / 论文结构化提取</div>
        </div>
        <div class="right-part">
            <div class="stat-title">全网热度指标</div>
            <div class="stat-num">193.3K+</div>
            <div class="stat-lbl">✓ AI 灵感与技术情报</div>
        </div>
    </body>
    </html>
    `;

    await page.setViewportSize({ width: 1080, height: 608 });
    await page.setContent(gzhCoverHtml);
    await page.screenshot({ path: path.join(outputDir, 'gzh_cover_banner.png') });

    await browser.close();
    console.log('All cover images rendered successfully!');
})();
