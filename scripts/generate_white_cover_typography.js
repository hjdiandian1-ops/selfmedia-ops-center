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

    // 4K Xiaohongshu Bright White Cover (2160 x 2880) with Smiley Sans & Typography hierarchy
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
                background: #F8FAFC; /* Clean light milk white */
                color: #0F172A;
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
                background: #E0F2FE;
                border: 4px solid #38BDF8;
                color: #0369A1;
                padding: 24px 50px;
                border-radius: 80px;
                font-size: 54px;
                font-family: 'Alibaba PuHuiTi Bold', sans-serif;
                letter-spacing: 2px;
                width: fit-content;
                box-shadow: 0 10px 25px rgba(56, 189, 248, 0.15);
            }

            /* Main Title Box with Smiley Sans (得意黑) */
            .title-box {
                margin-top: 60px;
            }

            .main-title {
                font-family: 'Smiley Sans', 'PingFang SC', sans-serif;
                font-size: 135px;
                font-weight: 900;
                font-style: italic;
                line-height: 1.25;
                letter-spacing: -2px;
                color: #0F172A;
                transform: skewX(-4deg); /* Dynamic Slant */
            }

            .highlight-orange {
                color: #EA580C; /* Deep Orange */
                background: #FFF7ED;
                padding: 0px 24px;
                border-radius: 24px;
                display: inline-block;
                border: 5px solid #FDBA74;
            }

            .highlight-cyan {
                color: #0284C7; /* Cyan Blue */
                background: #F0F9FF;
                padding: 0px 24px;
                border-radius: 24px;
                display: inline-block;
                border: 5px solid #7DD3FC;
            }

            .accent-en {
                font-family: 'JetBrains Mono', monospace;
                font-style: italic;
                letter-spacing: -2px;
            }

            .subtitle {
                font-family: 'Alibaba PuHuiTi', sans-serif;
                font-size: 64px;
                color: #475569;
                margin-top: 40px;
                font-weight: 500;
            }

            .sub-highlight {
                color: #DC2626; /* Deep Red */
                font-family: 'Alibaba PuHuiTi Bold', sans-serif;
                font-weight: 700;
            }

            /* Card Section */
            .card-wrapper {
                position: relative;
                background: #FFFFFF;
                border: 6px solid #E2E8F0;
                border-radius: 60px;
                padding: 70px 70px;
                box-shadow: 0 20px 40px -15px rgba(0,0,0,0.08);
                margin: 40px 0;
            }

            .card-title {
                font-family: 'Alibaba PuHuiTi Bold', sans-serif;
                font-size: 72px;
                font-weight: 700;
                color: #0F172A;
                margin-bottom: 50px;
                padding-bottom: 20px;
                border-bottom: 6px solid #38BDF8;
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
                background: #F0FDFA;
                border: 4px solid #CCFBF1;
                border-radius: 32px;
                padding: 40px 45px;
                font-size: 60px;
                color: #0F766E;
                font-family: 'Alibaba PuHuiTi', sans-serif;
            }

            .list-item .en-tag {
                font-family: 'JetBrains Mono', monospace;
                font-weight: 800;
                font-style: italic;
                color: #0284C7;
                background: #E0F2FE;
                padding: 4px 18px;
                border-radius: 18px;
                margin: 0 12px;
            }

            /* Bottom Action CTA */
            .cta-banner {
                background: #0284C7;
                color: #FFFFFF;
                border-radius: 50px;
                padding: 55px;
                text-align: center;
                font-size: 68px;
                font-family: 'Alibaba PuHuiTi Bold', sans-serif;
                box-shadow: 0 15px 30px rgba(2, 132, 199, 0.3);
            }

            /* Watermark */
            .watermark {
                position: absolute;
                bottom: 140px;
                right: 130px;
                background: rgba(15, 23, 42, 0.8);
                border: 3px solid rgba(255, 255, 255, 0.6);
                color: #FFFFFF;
                font-size: 48px;
                font-family: 'Alibaba PuHuiTi Bold', sans-serif;
                padding: 16px 36px;
                border-radius: 40px;
                backdrop-filter: blur(10px);
                box-shadow: 0 8px 20px rgba(0,0,0,0.2);
            }
        </style>
    </head>
    <body>

        <div>
            <div class="badge-top">🔥 宝藏网站推荐 ｜ 高效学习</div>
            
            <div class="title-box">
                <div class="main-title">
                    <span class="highlight-orange">打破信息差！</span><br>
                    私藏很久的 <span class="highlight-cyan"><span class="accent-en">AI</span>前沿情报库</span> 🚀
                </div>
                <div class="subtitle">
                    拒绝信息茧房，拉开同龄人 <span class="sub-highlight">10倍效率</span> 差距！
                </div>
            </div>
        </div>

        <div class="card-wrapper">
            <div class="card-title">💡 为什么全网极客都在看？</div>
            <div class="list-group">
                <div class="list-item">
                    <span>• <span class="en-tag">193.3K+</span> <span class="en-tag">AI</span> 灵感库与案例测评</span>
                </div>
                <div class="list-item">
                    <span>• <span class="en-tag">173.2K+</span> 历史热门干货数据聚合</span>
                </div>
                <div class="list-item">
                    <span>• 字节 / <span class="en-tag">OpenAI</span> 最前沿发布第一时间追踪</span>
                </div>
                <div class="list-item">
                    <span>• <span class="en-tag">GitHub</span> 热门 <span class="en-tag">AI</span> 开源工具零门槛挖掘</span>
                </div>
            </div>
        </div>

        <div class="cta-banner">
            👉 留言区回复【站点】免费获取
        </div>

        <div class="watermark">@小吴聊AI</div>

    </body>
    </html>
    `;

    await page.setViewportSize({ width: 2160, height: 2880 });
    await page.setContent(coverHtml, { waitUntil: 'networkidle' });
    await page.waitForTimeout(1000);
    await page.screenshot({ path: path.join(outputDir, 'xhs_cover_bright_white_4k.png') });

    await browser.close();
    console.log('Milk-white 4K cover typography updated successfully!');
})();
