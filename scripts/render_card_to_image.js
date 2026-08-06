const { chromium } = require('playwright');
const path = require('path');
const fs = require('fs');

/**
 * 通用 3:4 HTML 社交卡片 ➔ 高清 PNG 截图渲染脚本
 * 用法: node scripts/render_card_to_image.js <inputHtmlPath> <outputPngPath>
 */

(async () => {
    const args = process.argv.slice(2);
    if (args.length < 2) {
        console.error('用法: node scripts/render_card_to_image.js <inputHtmlPath> <outputPngPath>');
        process.exit(1);
    }

    const inputHtmlPath = path.resolve(args[0]);
    const outputPngPath = path.resolve(args[1]);

    if (!fs.existsSync(inputHtmlPath)) {
        console.error(`错误: 输入 HTML 文件不存在: ${inputHtmlPath}`);
        process.exit(1);
    }

    // 确保输出目录存在
    const outputDir = path.dirname(outputPngPath);
    if (!fs.existsSync(outputDir)) {
        fs.mkdirSync(outputDir, { recursive: true });
    }

    console.log(`🚀 启动 Playwright 渲染卡片: ${inputHtmlPath}`);
    const browser = await chromium.launch({ headless: true });
    const page = await browser.newPage({
        viewport: { width: 1080, height: 1440 },
        deviceScaleFactor: 2 // 2x 采样高清晰度
    });

    const fileUrl = `file://${inputHtmlPath}`;
    await page.goto(fileUrl, { waitUntil: 'networkidle' });

    await page.screenshot({
        path: outputPngPath,
        type: 'png',
        fullPage: true
    });

    await browser.close();
    console.log(`✅ 成功渲染高清晰度图片: ${outputPngPath}`);
})();
