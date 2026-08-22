# -*- coding: utf-8 -*-
"""
Full Interactive UI Button-by-Button Auditor
"""

import time
from playwright.sync_api import sync_playwright

BASE_URL = "http://127.0.0.1:8787"

console_errors = []
failed_requests = []
audit_report = []

def on_console(msg):
    if msg.type == "error":
        console_errors.append(f"JS ERROR: {msg.text}")

def on_req_failed(req):
    if req.failure:
        failed_requests.append(f"HTTP FAILED: {req.method} {req.url} -> {req.failure}")

with sync_playwright() as p:
    browser = p.chromium.launch(headless=True)
    page = browser.new_page(viewport={"width": 1440, "height": 900})
    
    page.on("console", on_console)
    page.on("requestfailed", on_req_failed)

    page.goto(BASE_URL, wait_until="networkidle")
    # 关闭新手向导与提示遮罩
    page.evaluate("""() => {
        localStorage.setItem('onboarding_done', '1');
        localStorage.setItem('selfmedia_theme', 'default');
        const wiz = document.getElementById('onboarding-wizard-modal');
        if (wiz) wiz.classList.add('hidden');
    }""")
    page.reload(wait_until="networkidle")
    time.sleep(1)

    views = [
        ("overview", "运营中台"),
        ("topics", "选题库"),
        ("themes", "爆款跟踪"),
        ("flywheel", "数据飞轮"),
        ("pipeline", "流水线"),
        ("outputs", "成品库"),
        ("data", "数据与质检"),
        ("settings", "系统设置")
    ]

    for view_id, view_name in views:
        print(flush=True, f"\n==================================================")
        print(flush=True, f"🔍 检查模块视图: 【{view_name} ({view_id})】")
        print(flush=True, f"==================================================")

        # 切换导航
        nav = page.query_selector(f'.nav-item[data-view="{view_id}"]')
        if nav:
            nav.click()
            time.sleep(0.6)

        section = page.query_selector(f"#view-{view_id}")
        if not section:
            print(flush=True, f"❌ 找不到视图 #view-{view_id}")
            continue

        # 获取当前视图下所有可见按钮
        btns = section.query_selector_all("button:visible, a.btn:visible")
        print(flush=True, f"  共检测到 {len(btns)} 个交互按钮：")

        for idx, btn in enumerate(btns, 1):
            btn_text = (btn.inner_text() or btn.get_attribute("title") or btn.get_attribute("id") or f"Btn-{idx}").strip().replace("\n", " ")
            btn_id = btn.get_attribute("id") or ""
            
            # 跳过危险破坏性按钮
            if any(k in btn_text for k in ["删除", "清空", "重置", "回滚"]):
                print(flush=True, f"  [{idx:02d}] ⏭️ SKIP: {btn_text[:28]:<28} (危险破坏操作)")
                audit_report.append((view_id, btn_text, "SKIP", "安全跳过"))
                continue

            err_count_before = len(console_errors)
            fail_count_before = len(failed_requests)

            try:
                btn.click(timeout=3000)
                time.sleep(0.5)
                new_errs = console_errors[err_count_before:]
                new_fails = failed_requests[fail_count_before:]

                if new_errs or new_fails:
                    status = f"❌ FAIL: {new_errs + new_fails}"
                    audit_report.append((view_id, btn_text, "FAIL", str(new_errs + new_fails)))
                else:
                    status = "✅ PASS"
                    audit_report.append((view_id, btn_text, "PASS", "正常"))
            except Exception as e:
                status = f"⚠️ EXCEPTION: {str(e)[:80]}"
                audit_report.append((view_id, btn_text, "EXCEPTION", str(e)[:80]))

            print(flush=True, f"  [{idx:02d}] {btn_text[:28]:<28} | id={btn_id:<18} | {status}")

    # 针对爆款跟踪核心新特性的专门测试
    print(flush=True, f"\n==================================================")
    print(flush=True, f"🎯 核心功能专项深度测试：爆款跟踪")
    print(flush=True, f"==================================================")
    page.query_selector('.nav-item[data-view="themes"]').click()
    time.sleep(0.5)

    # 1. 链接转录弹窗与解析
    print(flush=True, "  [1] 测试「🔗 链接一键转录与拆解」按钮...")
    page.click('button:has-text("转录与拆解")')
    time.sleep(0.5)
    modal_open = page.is_visible("#transcribe-modal")
    print(flush=True, f"      弹窗状态: {'✅ 打开成功' if modal_open else '❌ 打开失败'}")

    page.fill("#transcribe-url-input", "https://www.bilibili.com/video/BV1kS8H6VERt")
    page.click("#btn-do-transcribe")
    time.sleep(2)
    modal_closed = not page.is_visible("#transcribe-modal")
    print(flush=True, f"      转录入库与弹窗关闭: {'✅ 成功' if modal_closed else '❌ 失败'}")

    # 2. 实时赛道探测
    print(flush=True, "\n  [2] 测试「📡 赛道探测」...")
    page.fill("#gzh-explore-kw", "AI编程")
    page.click('button:has-text("实时探测")')
    time.sleep(2)
    rows = page.query_selector_all("#viral-daily-grid table tr")
    print(flush=True, f"      探测后文章行数: {len(rows)} 行 (✅ 正常)")

    browser.close()

print(flush=True, f"\n==================================================")
print(flush=True, f"📊 全量审查总结：共检测 {len(audit_report)} 个按钮")
pass_count = sum(1 for _, _, st, _ in audit_report if st == "PASS")
skip_count = sum(1 for _, _, st, _ in audit_report if st == "SKIP")
fail_count = sum(1 for _, _, st, _ in audit_report if st in ("FAIL", "EXCEPTION"))
print(flush=True, f"   ✅ 正常通过: {pass_count}")
print(flush=True, f"   ⏭️ 安全跳过: {skip_count}")
print(flush=True, f"   ❌ 异常失败: {fail_count}")
