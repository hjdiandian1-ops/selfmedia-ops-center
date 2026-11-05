const { chromium } = require('/Users/xiaowuliao/html-video/node_modules/.pnpm/playwright@1.60.0/node_modules/playwright');
const path = require('path');

async function renderPoster() {
  const htmlPath = '/Users/xiaowuliao/Projects/自媒体发布agent/outputs/2026-11-06_美股科技夜盘暴跌2.3万亿/公众号/gzh_美股科技夜盘暴跌2.3万亿_排版_红白色系(red-white).html';
  const outDir = '/Users/xiaowuliao/Projects/自媒体发布agent/outputs/2026-11-06_美股科技夜盘暴跌2.3万亿/公众号';

  const browser = await chromium.launch({
    executablePath: '/Applications/Google Chrome.app/Contents/MacOS/Google Chrome',
    headless: true
  });

  const page = await browser.newPage({
    viewport: { width: 480, height: 960 },
    deviceScaleFactor: 2
  });

  // Load the content with clean wrapper
  await page.goto('file://' + htmlPath, { waitUntil: 'load' });
  await page.waitForTimeout(600);

  const longImgPath = path.join(outDir, '文章长图.png');
  const mobileCheckPath = path.join(outDir, 'mobile_check.png');

  await page.screenshot({ path: longImgPath, fullPage: true });
  await page.screenshot({ path: mobileCheckPath, fullPage: false });

  console.log('✅ Generated article poster:', longImgPath);
  console.log('✅ Generated mobile preview thumbnail:', mobileCheckPath);

  await browser.close();
}

renderPoster().catch(console.error);
