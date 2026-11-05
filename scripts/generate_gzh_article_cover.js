const { chromium } = require('/Users/xiaowuliao/html-video/node_modules/.pnpm/playwright@1.60.0/node_modules/playwright');
const path = require('path');
const fs = require('fs');

(async () => {
    const browser = await chromium.launch({
        executablePath: '/Applications/Google Chrome.app/Contents/MacOS/Google Chrome',
        headless: true,
        args: ['--no-sandbox', '--disable-setuid-sandbox']
    });

    const page = await browser.newPage();

    const outputDir = '/Users/xiaowuliao/Projects/自媒体发布agent/outputs/2026-11-06_美股科技夜盘暴跌2.3万亿/公众号';
    if (!fs.existsSync(outputDir)) {
        fs.mkdirSync(outputDir, { recursive: true });
    }

    // ==========================================
    // 1. 微信公众号首条主推荐大图标准比例 2.35 : 1 (2350 x 1000)
    // ==========================================
    const coverHtml235 = `
    <!DOCTYPE html>
    <html lang="zh-CN">
    <head>
        <meta charset="UTF-8">
        <style>
            * { margin: 0; padding: 0; box-sizing: border-box; }
            body {
                width: 2350px;
                height: 1000px;
                background: radial-gradient(circle at 18% 28%, #1E1B4B 0%, #0F172A 45%, #050811 100%);
                color: #FFFFFF;
                font-family: -apple-system, BlinkMacSystemFont, "PingFang SC", "Hiragino Sans GB", "Microsoft YaHei", sans-serif;
                position: relative;
                overflow: hidden;
                display: flex;
                flex-direction: column;
                justify-content: space-between;
                padding: 70px 100px;
            }

            /* 背景科技网格与微弱光效 */
            .bg-grid {
                position: absolute;
                inset: 0;
                background-image: 
                    linear-gradient(rgba(255, 255, 255, 0.03) 1px, transparent 1px),
                    linear-gradient(90deg, rgba(255, 255, 255, 0.03) 1px, transparent 1px);
                background-size: 80px 80px;
                pointer-events: none;
            }

            /* 红色危机警示光晕 */
            .glow-red {
                position: absolute;
                top: -150px;
                left: 15%;
                width: 750px;
                height: 750px;
                background: radial-gradient(circle, rgba(239, 68, 68, 0.28) 0%, rgba(220, 38, 38, 0.05) 55%, transparent 75%);
                filter: blur(60px);
                pointer-events: none;
            }

            /* 绿色转机生机光晕 */
            .glow-green {
                position: absolute;
                bottom: -150px;
                right: 8%;
                width: 650px;
                height: 650px;
                background: radial-gradient(circle, rgba(16, 185, 129, 0.22) 0%, rgba(5, 150, 105, 0.04) 55%, transparent 75%);
                filter: blur(50px);
                pointer-events: none;
            }

            /* 顶部栏目条 */
            .top-bar {
                display: flex;
                align-items: center;
                justify-content: space-between;
                z-index: 2;
            }

            .badge-wrapper {
                display: inline-flex;
                align-items: center;
                gap: 16px;
            }

            .badge-pulse {
                display: flex;
                align-items: center;
                gap: 10px;
                background: rgba(239, 68, 68, 0.18);
                border: 2px solid rgba(239, 68, 68, 0.5);
                padding: 10px 24px;
                border-radius: 40px;
                font-size: 26px;
                font-weight: 800;
                color: #FCA5A5;
                letter-spacing: 1px;
            }

            .badge-dot {
                width: 14px;
                height: 14px;
                background: #EF4444;
                border-radius: 50%;
                box-shadow: 0 0 16px #EF4444;
            }

            .brand-tag {
                font-size: 26px;
                color: #94A3B8;
                letter-spacing: 2px;
                font-weight: 600;
            }

            /* 中间主视觉核心内容 */
            .center-content {
                z-index: 2;
                display: flex;
                justify-content: space-between;
                align-items: flex-end;
                gap: 60px;
            }

            .title-area {
                flex: 1;
            }

            .hook-sub {
                display: flex;
                align-items: center;
                gap: 16px;
                margin-bottom: 20px;
            }

            .hook-tag {
                background: #FEE2E2;
                color: #991B1B;
                font-size: 28px;
                font-weight: 900;
                padding: 6px 18px;
                border-radius: 8px;
            }

            .hook-text {
                font-size: 32px;
                color: #F87171;
                font-weight: 700;
                letter-spacing: 1px;
            }

            .main-title {
                font-size: 88px;
                font-weight: 900;
                line-height: 1.18;
                letter-spacing: -1.5px;
                color: #FFFFFF;
                text-shadow: 0 6px 30px rgba(0, 0, 0, 0.6);
            }

            .highlight-red {
                color: #EF4444;
                text-shadow: 0 0 50px rgba(239, 68, 68, 0.65);
                font-family: -apple-system, BlinkMacSystemFont, "PingFang SC", sans-serif;
            }

            .highlight-gold {
                color: #FBBF24;
                text-shadow: 0 0 40px rgba(251, 191, 36, 0.5);
            }

            .sub-desc {
                margin-top: 24px;
                font-size: 30px;
                color: #CBD5E1;
                font-weight: 500;
                line-height: 1.5;
                letter-spacing: 0.5px;
            }

            /* 右侧核心行情与异动面板 */
            .data-board {
                width: 720px;
                background: rgba(15, 23, 42, 0.85);
                backdrop-filter: blur(20px);
                border: 2px solid rgba(255, 255, 255, 0.12);
                border-radius: 24px;
                padding: 34px 38px;
                box-shadow: 0 25px 60px rgba(0, 0, 0, 0.5), inset 0 1px 0 rgba(255, 255, 255, 0.15);
            }

            .board-header {
                display: flex;
                justify-content: space-between;
                align-items: center;
                border-bottom: 2px solid rgba(255, 255, 255, 0.08);
                padding-bottom: 18px;
                margin-bottom: 22px;
            }

            .board-title {
                font-size: 26px;
                font-weight: 800;
                color: #E2E8F0;
                display: flex;
                align-items: center;
                gap: 12px;
            }

            .board-source {
                font-size: 22px;
                color: #64748B;
                font-family: ui-monospace, Menlo, Consolas, monospace;
            }

            .stock-grid {
                display: grid;
                grid-template-columns: repeat(3, 1fr);
                gap: 16px;
                margin-bottom: 22px;
            }

            .stock-item {
                background: rgba(239, 68, 68, 0.12);
                border: 1px solid rgba(239, 68, 68, 0.3);
                border-radius: 14px;
                padding: 14px 16px;
                text-align: center;
            }

            .stock-name {
                font-size: 20px;
                color: #CBD5E1;
                font-weight: 600;
                margin-bottom: 4px;
            }

            .stock-val {
                font-size: 32px;
                font-weight: 900;
                color: #F87171;
                font-family: ui-monospace, Menlo, Consolas, monospace;
            }

            .bottom-thesis {
                background: rgba(16, 185, 129, 0.12);
                border: 1px solid rgba(16, 185, 129, 0.35);
                border-radius: 14px;
                padding: 16px 20px;
                display: flex;
                align-items: center;
                justify-content: space-between;
            }

            .thesis-lbl {
                font-size: 22px;
                color: #6EE7B7;
                font-weight: 800;
            }

            .thesis-text {
                font-size: 22px;
                color: #ECFDF5;
                font-weight: 700;
            }

            /* 底部署名与水印 */
            .bottom-bar {
                z-index: 2;
                display: flex;
                justify-content: space-between;
                align-items: center;
                border-top: 1px dashed rgba(255, 255, 255, 0.15);
                padding-top: 20px;
                font-size: 22px;
                color: #94A3B8;
            }

            .bottom-pills {
                display: flex;
                gap: 16px;
            }

            .bottom-pill {
                background: rgba(255, 255, 255, 0.08);
                border: 1px solid rgba(255, 255, 255, 0.12);
                padding: 6px 16px;
                border-radius: 20px;
                color: #E2E8F0;
                font-size: 20px;
                font-weight: 600;
            }
        </style>
    </head>
    <body>
        <div class="bg-grid"></div>
        <div class="glow-red"></div>
        <div class="glow-green"></div>

        <!-- 顶部信息 -->
        <div class="top-bar">
            <div class="badge-wrapper">
                <div class="badge-pulse">
                    <span class="badge-dot"></span>
                    <span>BREAKING · 深夜特刊</span>
                </div>
                <div style="font-size:26px; color:#FCA5A5; font-weight:700;">
                    美国中期选举引发科技股海啸
                </div>
            </div>
            <div class="brand-tag">小吴聊 · 科技商业深度拆解</div>
        </div>

        <!-- 核心内容区 -->
        <div class="center-content">
            <div class="title-area">
                <div class="hook-sub">
                    <span class="hook-tag">单日市值蒸发</span>
                    <span class="hook-text" style="font-size:42px; font-weight:900; font-family:ui-monospace,Menlo,Consolas,monospace;">-$2,300,000,000,000</span>
                </div>
                <div class="main-title">
                    美股科技彻底恐慌：<br>
                    <span class="highlight-red">AI军备竞赛终结？</span> 还是 <span class="highlight-gold">主线换轨？</span>
                </div>
                <div class="sub-desc">
                    撞上“物理墙”与“政策墙” ｜ 华尔街转向自由现金流ROI ｜ 四大接棒主线研判
                </div>
            </div>

            <!-- 右侧数据看板 -->
            <div class="data-board">
                <div class="board-header">
                    <span class="board-title">🚨 芯片与核心硬件惨烈盘面</span>
                    <span class="board-source">SOX -7.2%</span>
                </div>
                <div class="stock-grid">
                    <div class="stock-item">
                        <div class="stock-name">闪迪 SanDisk</div>
                        <div class="stock-val">-20%</div>
                    </div>
                    <div class="stock-item">
                        <div class="stock-name">Lumentum</div>
                        <div class="stock-val">-16%</div>
                    </div>
                    <div class="stock-item">
                        <div class="stock-name">高通 QCOM</div>
                        <div class="stock-val">-14%</div>
                    </div>
                    <div class="stock-item">
                        <div class="stock-name">特斯拉 TSLA</div>
                        <div class="stock-val">-10%</div>
                    </div>
                    <div class="stock-item">
                        <div class="stock-name">英伟达 NVDA</div>
                        <div class="stock-val">-9.1%</div>
                    </div>
                    <div class="stock-item">
                        <div class="stock-name">博通 AVGO</div>
                        <div class="stock-val">-8.4%</div>
                    </div>
                </div>
                <div class="bottom-thesis">
                    <span class="thesis-lbl">🛡️ 接棒机会</span>
                    <span class="thesis-text">AI Agent应用 · 绿电大储 · 端侧AI</span>
                </div>
            </div>
        </div>

        <!-- 底部条 -->
        <div class="bottom-bar">
            <div class="bottom-pills">
                <span class="bottom-pill"># 华尔街宏观复盘</span>
                <span class="bottom-pill"># 北美算力降速</span>
                <span class="bottom-pill"># 国产替代卡位</span>
                <span class="bottom-pill"># 纳指定投策略</span>
            </div>
            <div>微信公众号首发 · @小吴聊团队原创出品</div>
        </div>
    </body>
    </html>
    `;

    // 渲染 2.35:1 微信推荐大图 (2350 x 1000)
    await page.setViewportSize({ width: 2350, height: 1000 });
    await page.setContent(coverHtml235, { waitUntil: 'load' });
    await page.waitForTimeout(500);

    const path235 = path.join(outputDir, '封面_2.35x1.png');
    const pathDefault = path.join(outputDir, '封面.png');
    await page.screenshot({ path: path235 });
    await page.screenshot({ path: pathDefault });
    console.log('✅ 2.35:1 微信主卡片封面已生成:', path235);

    // ==========================================
    // 2. 微信朋友圈与历史列表标准 16:9 比例 (1920 x 1080)
    // ==========================================
    const coverHtml169 = coverHtml235
        .replace('width: 2350px;', 'width: 1920px;')
        .replace('height: 1000px;', 'height: 1080px;')
        .replace('padding: 70px 100px;', 'padding: 80px 80px;')
        .replace('width: 720px;', 'width: 600px;')
        .replace('font-size: 88px;', 'font-size: 76px;');

    await page.setViewportSize({ width: 1920, height: 1080 });
    await page.setContent(coverHtml169, { waitUntil: 'load' });
    await page.waitForTimeout(500);

    const path169 = path.join(outputDir, '封面_16x9.png');
    await page.screenshot({ path: path169 });
    console.log('✅ 16:9 微信标准封面已生成:', path169);

    await browser.close();
    console.log('🎉 全部规格封面图片生成完毕！');
})();
