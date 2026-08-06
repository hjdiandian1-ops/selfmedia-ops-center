const { chromium } = require('/Users/xiaowuliao/html-video/node_modules/.pnpm/playwright@1.60.0/node_modules/playwright');
const path = require('path');
const fs = require('fs');

(async () => {
    const browser = await chromium.launch();
    const page = await browser.newPage();

    const outputDir = '/Users/xiaowuliao/Projects/自媒体发布agent/outputs/processed_images_4k_watermarked';
    if (!fs.existsSync(outputDir)) {
        fs.mkdirSync(outputDir, { recursive: true });
    }

    // 4K Xiaohongshu Cover (2160 x 2880) with Smiley Sans & Typography hierarchy
    const coverHtml = `
    <!DOCTYPE html>
    <html>
    <head>
        <meta charset="UTF-8">
        <style>
            @font-face {
                font-family: 'Smiley Sans';
                src: url('https://cdn.jsdelivr.net/npm/smiley-sans@1.1.1/SmileySans-Oblique.otf') format('opentype');
                font-style: oblique;
                font-weight: 900;
            }
            @font-face {
                font-family: 'Alibaba PuHuiTi';
                src: url('https://cdn.jsdelivr.net/npm/@fontsource/noto-sans-sc@4.5.12/files/noto-sans-sc-chinese-simplified-400-normal.woff2') format('woff2');
                font-weight: 400;
            }
            @font-face {
                font-family: 'Alibaba PuHuiTi Bold';
                src: url('https://cdn.jsdelivr.net/npm/@fontsource/noto-sans-sc@4.5.12/files/noto-sans-sc-chinese-simplified-700-normal.woff2') format('woff2');
                font-weight: 700;
            }
            @font-face {
                font-family: 'JetBrains Mono';
                src: url('https://cdn.jsdelivr.net/npm/@fontsource/jetbrains-mono@5.0.18/files/jetbrains-mono-latin-800-italic.woff2') format('woff2');
                font-weight: 800;
                font-style: italic;
            }

            * { margin: 0; padding: 0; box-sizing: border-box; }
            
            body {
                width: 2160px;
                height: 2880px;
                background: #FEF08A; /* Warm bright sunshine yellow */
                color: #111827;
                display: flex;
                flex-direction: column;
                justify-content: space-between;
                padding: 120px 110px;
                position: relative;
                font-family: 'Alibaba PuHuiTi', -apple-system, BlinkMacSystemFont, "PingFang SC", sans-serif;
            }

            /* Badge Top */
            .badge-top {
                display: inline-flex;
                align-items: center;
                gap: 20px;
                background: #111827;
                color: #FEF08A;
                padding: 24px 50px;
                border-radius: 80px;
                font-size: 54px;
                font-family: 'Alibaba PuHuiTi Bold', sans-serif;
                letter-spacing: 2px;
                width: fit-content;
                box-shadow: 0 10px 25px rgba(0,0,0,0.15);
            }

            /* Main Title Box with Smiley Sans (得意黑) */
            .title-box {
                margin-top: 60px;
            }

            .main-title {
                font-family: 'Smiley Sans', 'PingFang SC', sans-serif;
                font-size: 140px;
                font-weight: 900;
                font-style: italic;
                line-height: 1.25;
                letter-spacing: -2px;
                color: #0F172A;
                transform: skewX(-4deg); /* Dynamic Slant */
            }

            .highlight-red {
                color: #DC2626; /* Deep Red */
                background: #FFFFFF;
                padding: 0px 24px;
                border-radius: 24px;
                box-shadow: 6px 6px 0px #0F172A;
                display: inline-block;
                border: 5px solid #0F172A;
            }

            .accent-en {
                font-family: 'JetBrains Mono', monospace;
                font-style: italic;
                letter-spacing: -2px;
            }

            .subtitle {
                font-family: 'Alibaba PuHuiTi', sans-serif;
                font-size: 64px;
                color: #374151;
                margin-top: 40px;
                font-weight: 500;
            }

            .sub-highlight {
                color: #EA580C; /* Deep Orange */
                font-family: 'Alibaba PuHuiTi Bold', sans-serif;
                font-weight: 700;
            }

            /* Card Section */
            .card-wrapper {
                position: relative;
                background: #FFFFFF;
                border: 8px solid #111827;
                border-radius: 60px;
                padding: 70px 70px;
                box-shadow: 20px 20px 0px #111827;
                margin: 40px 0;
            }

            .card-title {
                font-family: 'Alibaba PuHuiTi Bold', sans-serif;
                font-size: 72px;
                font-weight: 700;
                color: #111827;
                margin-bottom: 50px;
                padding-bottom: 20px;
                border-bottom: 6px solid #FEF08A;
                display: inline-block;
            }

            .list-group {
                display: flex;
                flex-direction: column;
                gap: 40px;
            }

            .list-item {
                display: flex;
                align-items: center;
                background: #F9FAFB;
                border: 4px solid #E5E7EB;
                border-radius: 32px;
                padding: 40px 45px;
                font-size: 62px;
                color: #1F2937;
                font-family: 'Alibaba PuHuiTi', sans-serif;
            }

            .list-item .en-tag {
                font-family: 'JetBrains Mono', monospace;
                font-weight: 800;
                font-style: italic;
                color: #2563EB;
                background: #EFF6FF;
                padding: 4px 18px;
                border-radius: 18px;
                margin: 0 12px;
            }

            /* Bottom Action CTA */
            .cta-banner {
                background: #111827;
                color: #FEF08A;
                border-radius: 50px;
                padding: 55px;
                text-align: center;
                font-size: 68px;
                font-family: 'Alibaba PuHuiTi Bold', sans-serif;
                box-shadow: 12px 12px 0px rgba(0,0,0,0.2);
            }

            /* Watermark */
            .watermark {
                position: absolute;
                bottom: 140px;
                right: 130px;
                background: rgba(0, 0, 0, 0.75);
                border: 3px solid rgba(255, 255, 255, 0.6);
                color: #FFFFFF;
                font-size: 48px;
                font-family: 'Alibaba PuHuiTi Bold', sans-serif;
                padding: 16px 36px;
                border-radius: 40px;
                backdrop-filter: blur(10px);
                box-shadow: 0 8px 20px rgba(0,0,0,0.3);
            }
        </style>
    </head>
    <body>

        <div>
            <div class="badge-top">🤫 建议默默收藏 ｜ 打破信息差</div>
            
            <div class="title-box">
                <div class="main-title">
                    没事少刷短视频！<br>
                    多看看这个 <span class="highlight-red"><span class="accent-en">AI</span>宝藏站</span>
                </div>
                <div class="subtitle">
                    拉开同龄人 <span class="sub-highlight">10倍效率</span> 差距的技术情报库 🔥
                </div>
            </div>
        </div>

        <div class="card-wrapper">
            <div class="card-title">📌 涵盖四大超强干货板块：</div>
            <div class="list-group">
                <div class="list-item">
                    <span>⚡️ 1. 实时追踪全球 <span class="en-tag">AI</span> 热点与爆帖动态</span>
                </div>
                <div class="list-item">
                    <span>📦 2. <span class="en-tag">GitHub</span> 最高分 <span class="en-tag">AI</span> 开源项目榜单</span>
                </div>
                <div class="list-item">
                    <span>💡 3. 极客级 <span class="en-tag">AI</span> 创作灵感与实用工具包</span>
                </div>
                <div class="list-item">
                    <span>📑 4. 顶尖 <span class="en-tag">AI</span> 学术论文结构化摘要</span>
                </div>
            </div>
        </div>

        <div class="cta-banner">
            👉 评论区发送【学习】或私信取网址
        </div>

        <div class="watermark">@小吴聊AI</div>

    </body>
    </html>
    `;

    await page.setViewportSize({ width: 2160, height: 2880 });
    await page.setContent(coverHtml, { waitUntil: 'networkidle' });
    // Wait slightly for fonts to load
    await page.waitForTimeout(1000);
    await page.screenshot({ path: path.join(outputDir, 'xhs_cover_bright_yellow_4k.png') });

    // Also render WeChat Banner (3840 x 1632)
    const gzhHtml = `
    <!DOCTYPE html>
    <html>
    <head>
        <meta charset="UTF-8">
        <style>
            @font-face {
                font-family: 'Smiley Sans';
                src: url('https://cdn.jsdelivr.net/npm/smiley-sans@1.1.1/SmileySans-Oblique.otf') format('opentype');
                font-style: oblique;
                font-weight: 900;
            }
            @font-face {
                font-family: 'Alibaba PuHuiTi Bold';
                src: url('https://cdn.jsdelivr.net/npm/@fontsource/noto-sans-sc@4.5.12/files/noto-sans-sc-chinese-simplified-700-normal.woff2') format('woff2');
                font-weight: 700;
            }
            @font-face {
                font-family: 'JetBrains Mono';
                src: url('https://cdn.jsdelivr.net/npm/@fontsource/jetbrains-mono@5.0.18/files/jetbrains-mono-latin-800-italic.woff2') format('woff2');
                font-weight: 800;
                font-style: italic;
            }
            * { margin: 0; padding: 0; box-sizing: border-box; }
            body {
                width: 3840px;
                height: 1632px;
                background: #FEF08A;
                color: #111827;
                display: flex;
                align-items: center;
                justify-content: space-between;
                padding: 140px 180px;
                position: relative;
                font-family: 'Alibaba PuHuiTi Bold', sans-serif;
            }
            .left-part {
                max-width: 2100px;
            }
            .tag {
                background: #111827;
                color: #FEF08A;
                padding: 24px 60px;
                border-radius: 60px;
                font-size: 80px;
                display: inline-block;
                margin-bottom: 50px;
            }
            .title {
                font-family: 'Smiley Sans', sans-serif;
                font-size: 160px;
                font-weight: 900;
                line-height: 1.25;
                transform: skewX(-4deg);
            }
            .highlight-orange {
                color: #EA580C;
            }
            .highlight-red {
                color: #DC2626;
            }
            .sub {
                font-size: 90px;
                color: #4B5563;
                margin-top: 40px;
            }
            .right-card {
                background: #FFFFFF;
                border: 12px solid #111827;
                border-radius: 80px;
                padding: 100px;
                width: 1200px;
                box-shadow: 24px 24px 0px #111827;
            }
            .stat-val {
                font-family: 'JetBrains Mono', monospace;
                font-size: 170px;
                font-weight: 900;
                color: #DC2626;
            }
            .stat-lbl {
                font-size: 95px;
                color: #111827;
                margin-top: 20px;
            }
            .watermark {
                position: absolute;
                bottom: 120px;
                right: 180px;
                background: rgba(0, 0, 0, 0.75);
                border: 3px solid rgba(255, 255, 255, 0.6);
                color: #FFFFFF;
                font-size: 48px;
                padding: 16px 36px;
                border-radius: 40px;
            }
        </style>
    </head>
    <body>
        <div class="left-part">
            <div class="tag">💡 宝藏 <span style="font-family:'JetBrains Mono';">AI</span> 情报站推荐</div>
            <div class="title">
                拉开<span class="highlight-orange">10倍效率</span>差距！<br>
                没事多刷刷这个 <span class="highlight-red"><span style="font-family:'JetBrains Mono';">AI</span> 宝藏库</span> 🔥
            </div>
            <div class="sub">实时热点追踪 / <span style="font-family:'JetBrains Mono'; font-weight:800;">GitHub</span> 开源榜 / 论文摘要</div>
        </div>

        <div class="right-card">
            <div style="font-size: 80px; color: #6B7280;">全网情报指标</div>
            <div class="stat-val">193.3K+</div>
            <div class="stat-lbl">✓ AI 创作灵感</div>
            <div class="stat-lbl">✓ 开源项目榜单</div>
        </div>

        <div class="watermark">@小吴聊AI</div>
    </body>
    </html>
    `;

    await page.setViewportSize({ width: 3840, height: 1632 });
    await page.setContent(gzhHtml, { waitUntil: 'networkidle' });
    await page.waitForTimeout(1000);
    await page.screenshot({ path: path.join(outputDir, 'gzh_banner_bright_4k.png') });

    await browser.close();
    console.log('Typography-optimized 4K covers generated successfully!');
})();
