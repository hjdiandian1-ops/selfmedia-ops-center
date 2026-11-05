const { chromium } = require('/Users/xiaowuliao/html-video/node_modules/.pnpm/playwright@1.60.0/node_modules/playwright');
const path = require('path');
const fs = require('fs');

async function renderXhsCards() {
  const slidesHtmlPath = '/Users/xiaowuliao/Projects/自媒体发布agent/outputs/2026-11-06_美股科技夜盘暴跌2.3万亿/小红书/rednote_美股科技夜盘暴跌23万亿_slides.html';
  const outDir = '/Users/xiaowuliao/Projects/自媒体发布agent/outputs/2026-11-06_美股科技夜盘暴跌2.3万亿/小红书';

  const browser = await chromium.launch({
    executablePath: '/Applications/Google Chrome.app/Contents/MacOS/Google Chrome',
    headless: true
  });

  const page = await browser.newPage({
    viewport: { width: 1600, height: 2400 },
    deviceScaleFactor: 2
  });

  await page.goto('file://' + slidesHtmlPath, { waitUntil: 'load' });
  await page.waitForTimeout(600);

  const cards = await page.$$('.card');
  console.log(`Found ${cards.length} Xiaohongshu cards to screenshot.`);

  for (let i = 0; i < cards.length; i++) {
    const card = cards[i];
    const num = String(i + 1).padStart(2, '0');
    const outPng = path.join(outDir, `xhs-${num}.png`);
    await card.screenshot({ path: outPng });
    console.log(`✅ Saved xhs-${num}.png`);
    if (i === 0) {
      const coverPath = path.join(outDir, '封面.png');
      await card.screenshot({ path: coverPath });
      console.log(`✅ Saved cover 封面.png (xhs)`);
    }
  }

  await browser.close();
  console.log('🎉 All Xiaohongshu cards exported successfully!');
}

renderXhsCards().catch(console.error);
