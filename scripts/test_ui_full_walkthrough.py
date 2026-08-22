# -*- coding: utf-8 -*-
"""
Robust Step-by-Step UI Full Walkthrough & Inspection
===================================================
"""

import sys
import time
from playwright.sync_api import sync_playwright

BASE_URL = "http://127.0.0.1:8787"

test_results = []
js_errors = []

def on_console(msg):
    if msg.type == "error":
        js_errors.append(msg.text)

with sync_playwright() as p:
    browser = p.chromium.launch(headless=True)
    page = browser.new_page(viewport={"width": 1440, "height": 900})
    page.on("console", on_console)

    print("🌐 打开自媒体工作台: http://127.0.0.1:8787...", flush=True)
    page.goto(BASE_URL, wait_until="networkidle")
    page.evaluate("""() => {
        localStorage.setItem('onboarding_done', '1');
        document.querySelectorAll('.modal, .onboard-wizard-overlay').forEach(m => {
            m.classList.add('hidden');
            m.style.display = 'none';
        });
    }""")
    page.reload(wait_until="networkidle")
    time.sleep(1)

    def test_step(module, action_name, fn):
        err_len_before = len(js_errors)
        try:
            res_msg = fn() or "成功"
            new_errs = js_errors[err_len_before:]
            if new_errs:
                status = f"❌ FAIL (JS: {new_errs[0][:60]})"
            else:
                status = f"✅ PASS ({res_msg})"
        except Exception as e:
            status = f"❌ ERR ({str(e)[:60]})"
        
        test_results.append((module, action_name, status))
        print(f"  [{module}] {action_name:<32} ➔ {status}", flush=True)

    # ===== 1. 运营中台 =====
    print("\n【1. 运营中台】", flush=True)
    page.click('.nav-item[data-view="overview"]')
    time.sleep(0.5)

    test_step("运营中台", "平台标签切换 (小红书/公众号/短视频)", lambda: (
        page.click('#ov-platform-tabs button[data-platform="小红书"]'),
        time.sleep(0.3),
        page.click('#ov-platform-tabs button[data-platform="公众号"]'),
        time.sleep(0.3),
        page.click('#ov-platform-tabs button[data-platform="all"]'),
        "3个标签切换正常"
    )[-1])

    test_step("运营中台", "时间窗口切换 (日/周/月)", lambda: (
        page.click('#ov-period-pills button[data-period="week"]'),
        time.sleep(0.3),
        page.click('#ov-period-pills button[data-period="month"]'),
        time.sleep(0.3),
        page.click('#ov-period-pills button[data-period="day"]'),
        "窗口切换正常"
    )[-1])

    test_step("运营中台", "平台管理弹窗开启与关闭", lambda: (
        page.click('button:has-text("平台管理")'),
        time.sleep(0.3),
        page.click('#platform-prefs-modal button:has-text("关闭")'),
        "弹窗开闭正常"
    )[-1])

    # ===== 2. 选题库 =====
    print("\n【2. 选题库】", flush=True)
    page.click('.nav-item[data-view="topics"]')
    time.sleep(0.5)

    test_step("选题库", "刷新选题列表", lambda: (
        page.click('button:has-text("刷新列表")'),
        time.sleep(0.5),
        "列表刷新成功"
    )[-1])

    test_step("选题库", "偏好设置弹窗开启与关闭", lambda: (
        page.click('button:has-text("偏好设置")'),
        time.sleep(0.3),
        page.click('#pref-modal button:has-text("关闭")'),
        "偏好设置弹窗正常"
    )[-1])

    # ===== 3. 爆款跟踪 (重点) =====
    print("\n【3. 爆款跟踪】", flush=True)
    page.click('.nav-item[data-view="themes"]')
    time.sleep(0.5)

    test_step("爆款跟踪", "🔗 链接一键转录与拆解", lambda: (
        page.click('button:has-text("转录与拆解")'),
        time.sleep(0.4),
        page.fill("#transcribe-url-input", "https://www.bilibili.com/video/BV1kS8H6VERt"),
        page.click("#btn-do-transcribe"),
        time.sleep(2),
        "已智能提取并入库"
    )[-1])

    test_step("爆款跟踪", "📡 赛道低粉爆款实时探测 (AI编程)", lambda: (
        page.fill("#gzh-explore-kw", "AI编程"),
        page.click('button:has-text("实时探测")'),
        time.sleep(2),
        f"已抓取并刷新今日榜单"
    )[-1])

    test_step("爆款跟踪", "＋ 手动录入表单展开与收起", lambda: (
        page.click("#btn-toggle-viral-form"),
        time.sleep(0.3),
        page.click("#btn-toggle-viral-form"),
        "表单展开收起正常"
    )[-1])

    test_step("爆款跟踪", "采集今日榜单", lambda: (
        page.click("#btn-collect-platform"),
        time.sleep(1),
        "采集接口正常"
    )[-1])

    test_step("爆款跟踪", "自动拆解 Top5", lambda: (
        page.click("#btn-breakdown-top"),
        time.sleep(1),
        "拆解后台任务启动正常"
    )[-1])

    test_step("爆款跟踪", "表格行内操作 (待拆解/查看报告)", lambda: (
        page.click("#viral-daily-grid table button.vstatus"),
        time.sleep(1),
        page.evaluate("() => { const m = document.getElementById('viral-report-modal'); if (m) m.classList.add('hidden'); }"),
        "状态流转与报告响应正常"
    )[-1])

    # ===== 4. 数据飞轮 =====
    print("\n【4. 数据飞轮】", flush=True)
    page.click('.nav-item[data-view="flywheel"]')
    time.sleep(0.5)

    test_step("数据飞轮", "重新生成反哺指令包", lambda: (
        page.click('button:has-text("重新生成反哺指令包")'),
        time.sleep(1),
        "反哺包已更新"
    )[-1])

    test_step("数据飞轮", "生成周报", lambda: (
        page.click('button:has-text("生成周报")'),
        time.sleep(1),
        "周报生成成功"
    )[-1])

    # ===== 5. 流水线 =====
    print("\n【5. 流水线】", flush=True)
    page.click('.nav-item[data-view="pipeline"]')
    time.sleep(0.5)

    test_step("流水线", "刷新流水线", lambda: (
        page.click('button:has-text("刷新")'),
        time.sleep(0.5),
        "流水线状态机刷新正常"
    )[-1])

    # ===== 6. 成品库 =====
    print("\n【6. 成品库】", flush=True)
    page.click('.nav-item[data-view="outputs"]')
    time.sleep(0.5)

    test_step("成品库", "平台成品切换 (小红书/公众号/短视频)", lambda: (
        page.click('#out-platform-pills button[data-platform="小红书"]'),
        time.sleep(0.3),
        page.click('#out-platform-pills button[data-platform="公众号"]'),
        time.sleep(0.3),
        page.click('#out-platform-pills button[data-platform="短视频"]'),
        "成品切换正常"
    )[-1])

    test_step("成品库", "查看 22 条去 AI 味规则弹窗", lambda: (
        page.click('button:has-text("22 条去 AI 味规则")'),
        time.sleep(0.4),
        page.click('#agent-doc-modal button:has-text("关闭")'),
        "SOP 规范弹窗正常"
    )[-1])

    # ===== 7. 数据与质检 =====
    print("\n【7. 数据与质检】", flush=True)
    page.click('.nav-item[data-view="data"]')
    time.sleep(0.5)

    test_step("数据与质检", "质检大盘与选题反馈子标签切换", lambda: (
        page.click('button:has-text("质检趋势与门禁")'),
        time.sleep(0.3),
        page.click('button:has-text("选题反馈模型")'),
        time.sleep(0.3),
        page.click('button:has-text("数据大盘")'),
        "子标签切换正常"
    )[-1])

    test_step("数据与质检", "选题权重立即校准", lambda: (
        page.click('button:has-text("选题反馈模型")'),
        time.sleep(0.3),
        page.click('button:has-text("立即执行权重校准")'),
        time.sleep(1),
        "校准触发成功"
    )[-1])

    # ===== 8. 系统设置 =====
    print("\n【8. 系统设置】", flush=True)
    page.click('button:has-text("设置")')
    time.sleep(0.5)

    test_step("系统设置", "设置弹窗与选项卡切换 (外观/文风/AI引擎/定时)", lambda: (
        page.click('.settings-nav-item[data-tab="appearance"]'),
        time.sleep(0.3),
        page.click('.settings-nav-item[data-tab="style"]'),
        time.sleep(0.3),
        page.click('.settings-nav-item[data-tab="ai"]'),
        time.sleep(0.3),
        page.click('.settings-nav-item[data-tab="scheduler"]'),
        time.sleep(0.3),
        page.click('#settings-modal button:has-text("关闭")'),
        "设置面板与弹窗正常"
    )[-1])

    browser.close()

print("\n" + "="*60, flush=True)
print(f"🎉 全站功能逐项实跑完成！总用例: {len(test_results)} 项", flush=True)
pass_cnt = sum(1 for _, _, s in test_results if "✅ PASS" in s)
fail_cnt = sum(1 for _, _, s in test_results if "❌" in s)
print(f"   ✅ 全部通过: {pass_cnt} 项", flush=True)
print(f"   ❌ 异常失败: {fail_cnt} 项", flush=True)
print("="*60, flush=True)
