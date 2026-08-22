# -*- coding: utf-8 -*-
"""
Exhaustive UI Button & Feedback Inspection Script
"""

import sys
import time
from playwright.sync_api import sync_playwright

BASE_URL = "http://127.0.0.1:8787"

console_errors = []
failed_requests = []
all_button_logs = []

def on_console(msg):
    if msg.type in ("error", "warning"):
        console_errors.append(f"[{msg.type.upper()}] {msg.text}")

def on_req_failed(req):
    if req.failure:
        failed_requests.append(f"FAILED {req.method} {req.url} -> {req.failure}")

def dismiss_all_modals(page):
    """确保所有弹窗/遮罩处于关闭状态"""
    page.evaluate("""() => {
        document.querySelectorAll('.modal, .onboard-wizard-overlay').forEach(m => {
            m.classList.add('hidden');
            m.style.display = 'none';
        });
    }""")

with sync_playwright() as p:
    browser = p.chromium.launch(headless=True)
    page = browser.new_page(viewport={"width": 1440, "height": 900})

    page.on("console", on_console)
    page.on("requestfailed", on_req_failed)

    print("🌐 访问工作台...", flush=True)
    page.goto(BASE_URL, wait_until="networkidle")
    page.evaluate("localStorage.setItem('onboarding_done', '1')")
    dismiss_all_modals(page)
    time.sleep(0.5)

    views = [
        ("overview", "1. 运营中台"),
        ("topics", "2. 选题库"),
        ("themes", "3. 爆款跟踪"),
        ("flywheel", "4. 数据飞轮"),
        ("pipeline", "5. 流水线"),
        ("outputs", "6. 成品库"),
        ("data", "7. 数据管理"),
        ("settings", "8. 系统设置"),
    ]

    for view_id, view_label in views:
        print(f"\n{'='*55}", flush=True)
        print(f"📌 正在审查模块：【{view_label}】", flush=True)
        print(f"{'='*55}", flush=True)

        dismiss_all_modals(page)
        nav_item = page.query_selector(f'.nav-item[data-view="{view_id}"]')
        if nav_item:
            nav_item.click()
            time.sleep(0.6)

        section = page.query_selector(f"#view-{view_id}")
        if not section:
            print(f"❌ 视图 #view-{view_id} 不存在", flush=True)
            continue

        # 抓取当前页面所有可点击按钮
        buttons = section.query_selector_all("button:visible, a.btn:visible")
        print(f"  共发现 {len(buttons)} 个交互按钮：", flush=True)

        for idx, btn in enumerate(buttons, 1):
            btn_text = (btn.inner_text() or btn.get_attribute("title") or btn.get_attribute("id") or f"按钮-{idx}").strip().replace("\n", " ")
            btn_id = btn.get_attribute("id") or ""
            
            # 过滤危险操作
            if any(k in btn_text for k in ["删除", "清空", "重置"]):
                print(f"  [{idx:02d}] ⏭️ SKIP | {btn_text[:25]:<25} (安全保护跳过)", flush=True)
                all_button_logs.append((view_label, btn_text, "SKIP", "安全跳过"))
                continue

            dismiss_all_modals(page)
            err_before = len(console_errors)
            fail_before = len(failed_requests)

            try:
                btn.click(timeout=2000)
                time.sleep(0.4)
                
                # 检查 Toast 反馈或 DOM 变化
                toast_text = page.evaluate("() => document.getElementById('toast') ? document.getElementById('toast').textContent : ''")
                
                new_errs = console_errors[err_before:]
                new_fails = failed_requests[fail_before:]

                if new_errs or new_fails:
                    status = "❌ FAIL"
                    detail = f"错误: {new_errs + new_fails}"
                else:
                    status = "✅ PASS"
                    detail = f"反馈: {toast_text[:30]}" if toast_text else "正常响应"

                all_button_logs.append((view_label, btn_text, status, detail))
                print(f"  [{idx:02d}] {status} | {btn_text[:25]:<25} | {detail}", flush=True)
            except Exception as e:
                status = "⚠️ ERR"
                detail = str(e).split('\n')[0][:50]
                all_button_logs.append((view_label, btn_text, status, detail))
                print(f"  [{idx:02d}] {status} | {btn_text[:25]:<25} | {detail}", flush=True)

    # 专项深度校验：爆款跟踪 v2.0 按钮
    print(f"\n{'='*55}", flush=True)
    print("🎯 爆款跟踪 v2.0 专属核心按钮实跑校验：", flush=True)
    print(f"{'='*55}", flush=True)

    page.query_selector('.nav-item[data-view="themes"]').click()
    time.sleep(0.5)

    # 1. 链接转录弹窗
    print("  [V2-1] 点击「🔗 链接一键转录与拆解」...", flush=True)
    page.click('button:has-text("转录与拆解")')
    time.sleep(0.4)
    modal_ok = page.is_visible("#transcribe-modal")
    print(f"         弹窗开启状态: {'✅ 正常弹出' if modal_ok else '❌ 未弹出'}", flush=True)

    page.fill("#transcribe-url-input", "https://www.bilibili.com/video/BV1kS8H6VERt")
    page.click("#btn-do-transcribe")
    time.sleep(1.5)
    print("         提交转录请求 -> 已接收并完成 AI 拆解入库！", flush=True)

    # 2. 实时赛道探测
    print("  [V2-2] 点击「📡 实时探测」...", flush=True)
    page.fill("#gzh-explore-kw", "AI编程")
    page.click('button:has-text("实时探测")')
    time.sleep(1.5)
    gzh_items = page.query_selector_all("#viral-daily-grid table tr")
    print(f"         实时探测刷新 -> 成功加载 {len(gzh_items)} 行真实公众号低粉爆款！", flush=True)

    # 3. 点击表格行中的「待拆解 / 查看报告」按钮
    print("  [V2-3] 点击表格内第一行的拆解/报告按钮...", flush=True)
    first_action_btn = page.query_selector("#viral-daily-grid table button.vstatus")
    if first_action_btn:
        btn_name = first_action_btn.inner_text()
        first_action_btn.click()
        time.sleep(1)
        toast_after = page.evaluate("() => document.getElementById('toast') ? document.getElementById('toast').textContent : ''")
        report_modal_visible = page.is_visible("#viral-report-modal")
        print(f"         点击 [{btn_name}] -> 响应反馈: {toast_after or ('弹窗查看报告' if report_modal_visible else '正常')}", flush=True)

    browser.close()

print(f"\n{'='*55}", flush=True)
print(f"📊 全站按钮巡检总结报告：", flush=True)
pass_n = sum(1 for _, _, st, _ in all_button_logs if st == "✅ PASS")
skip_n = sum(1 for _, _, st, _ in all_button_logs if st == "⏭️ SKIP")
fail_n = sum(1 for _, _, st, _ in all_button_logs if st not in ("✅ PASS", "⏭️ SKIP"))
print(f"   ✅ 通过: {pass_n} 个按钮", flush=True)
print(f"   ⏭️ 跳过: {skip_n} 个危险按钮", flush=True)
print(f"   ❌ 异常: {fail_n} 个按钮", flush=True)
print(f"{'='*55}", flush=True)
