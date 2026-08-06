import os
import time
import re
os.environ["PLAYWRIGHT_BROWSERS_PATH"] = "/data/shared/ms-playwright"
os.environ["PLAYWRIGHT_DOWNLOAD_HOST"] = "https://npmmirror.com/mirrors/playwright"
import asyncio
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
from typing import List, Optional
from playwright.async_api import async_playwright

app = FastAPI(title="Selfmedia Publishing Service for n8n")

# ---------- 数据模型 ----------
class PublishPayload(BaseModel):
    title: str
    content: str
    images: List[str] = []  # 共享目录下的图片路径，如 ["/data/shared/slide1.png"]
    tags: Optional[List[str]] = []
    cookies_json_path: Optional[str] = ""  # 平台 cookie 文件；空则按平台取默认
    platform: Optional[str] = ""  # 兼容旧调用方；未指定时按路由定
    auto_publish: Optional[bool] = False  # 公众号：True=存草稿后继续群发；False(默认)=存草稿待人工确认


# ---------- 共用辅助（多平台复用） ----------
DEFAULT_COOKIES = {
    "xhs": "/data/shared/xhs_cookies.json",
    "gzh": "/data/shared/gzh_cookies.json",
}


def resolve_cookies(platform, payload_path):
    if payload_path:
        return payload_path
    return DEFAULT_COOKIES.get(platform, DEFAULT_COOKIES["xhs"])


def ensure_cookies(path, platform):
    if not os.path.exists(path):
        raise HTTPException(
            status_code=400,
            detail=f"Cookies 文件不存在: {path}。请先用扫码脚本保存 {platform} 登录态。",
        )


def ensure_images(images):
    valid = []
    for img_path in images:
        if os.path.exists(img_path):
            valid.append(os.path.abspath(img_path))
        else:
            print(f"警告: 图片文件不存在 - {img_path}")
    if not valid:
        raise HTTPException(status_code=400, detail="没有有效的待上传图片文件")
    return valid


async def wait_for_success(page, keywords, timeout_ms=30000):
    """发布/保存后的二次断言：轮询检测页面 URL 变化或成功提示文本，
    替代"sleep N 秒即报成功"的假成功。返回 (ok, evidence)。
    """
    start_url = page.url
    deadline = time.monotonic() + timeout_ms / 1000.0
    while True:
        try:
            if page.url != start_url:
                return True, f"URL 变化: {page.url}"
            body = await page.inner_text("body")
            for kw in keywords:
                if kw in body:
                    return True, f"命中成功信号: {kw}"
        except Exception:
            pass
        if time.monotonic() >= deadline:
            return False, f"超时 {timeout_ms}ms 未检测到成功信号"
        await page.wait_for_timeout(2000)


async def launch_context(p, storage_state):
    """共用浏览器启动逻辑：多平台复用同一套 Chromium 启动参数。"""
    args = ["--headless=new", "--no-sandbox", "--disable-setuid-sandbox", "--disable-dev-shm-usage"]
    try:
        browser = await p.chromium.launch(headless=False, args=args)
    except Exception as launch_err:
        print(f"⚠️ 浏览器准备启动，安装/补齐二进制中: {launch_err}")
        os.system("playwright install chromium")
        browser = await p.chromium.launch(headless=False, args=args)
    context = await browser.new_context(viewport={"width": 1280, "height": 800}, storage_state=storage_state)
    return browser, context


# ---------- 根路由 ----------
@app.get("/")
def read_root():
    return {"status": "ok", "service": "Selfmedia Publisher API", "endpoints": ["/publish", "/publish/gzh"]}


@app.get("/healthz")
def healthz():
    """容器健康检查：供 docker restart 策略与外部探活使用（治 502）。"""
    ok_xhs = os.path.exists(DEFAULT_COOKIES["xhs"])
    ok_gzh = os.path.exists(DEFAULT_COOKIES["gzh"])
    return {"status": "ok", "service": "Selfmedia Publisher API",
            "cookies": {"xhs": ok_xhs, "gzh": ok_gzh}}


def stale_cookie_warning(path, days=7):
    """cookie 文件超过 N 天未刷新则告警（不阻断，提示重新扫码）。"""
    if not os.path.exists(path):
        return f"cookie 文件不存在: {path}"
    age = time.time() - os.path.getmtime(path)
    if age > days * 86400:
        return f"cookie 文件已 {int(age // 86400)} 天未刷新，建议重新扫码"
    return ""


# ---------- 小红书发布（原 /publish 保留，向后兼容） ----------
@app.post("/publish")
async def publish_note(payload: PublishPayload):
    """
    通过 Playwright 自动化上传发布小红书图文笔记。
    """
    cookies = resolve_cookies("xhs", payload.cookies_json_path)
    ensure_cookies(cookies, "小红书")
    warn = stale_cookie_warning(cookies)
    if warn:
        print(f"⚠️ {warn}")
    valid_images = ensure_images(payload.images)

    try:
        async with async_playwright() as p:
            browser, context = await launch_context(p, cookies)
            page = await context.new_page()

            # 打开小红书创作服务平台
            await page.goto("https://creator.xiaohongshu.com/publish/publish?source=official")
            await page.wait_for_timeout(4000)

            # 登录态哨兵：未登录会跳转 login 或出现扫码登录
            body_probe = ""
            try:
                body_probe = await page.inner_text("body")
            except Exception:
                pass
            if "login" in page.url.lower() or "扫码登录" in body_probe:
                await context.storage_state(path=cookies)
                await browser.close()
                raise HTTPException(
                    status_code=401,
                    detail="小红书登录态失效，请重新扫码登录（python3 init_xiaohongshu_login.py 或本地扫码脚本）",
                )

            # 定位图片上传 file input
            all_inputs = await page.query_selector_all('input[type="file"]')
            image_input = None
            for inp in all_inputs:
                acc = (await inp.get_attribute("accept")) or ""
                has_mult = (await inp.get_attribute("multiple")) is not None
                if "image" in acc or has_mult or ".png" in acc:
                    image_input = inp
                    break
            if not image_input and all_inputs:
                image_input = all_inputs[-1]

            if image_input:
                await image_input.set_input_files(valid_images)
            else:
                await page.set_input_files('input[type="file"]', valid_images)
            await page.wait_for_timeout(5000)

            # 填写标题
            try:
                title_input = await page.wait_for_selector('input[placeholder*="标题"]', timeout=10000)
                if title_input:
                    await title_input.fill(payload.title)
            except Exception as e:
                print("填写标题提示:", e)

            # 填写正文与标签
            try:
                full_content = payload.content
                if payload.tags:
                    full_content += "\n\n" + " ".join([f"#{t}" for t in payload.tags])
                content_input = await page.wait_for_selector(
                    'div[contenteditable="true"], .post-content #post-textarea', timeout=10000)
                if content_input:
                    await content_input.fill(full_content)
            except Exception as e:
                print("填写正文提示:", e)

            await page.wait_for_timeout(3000)

            # 点击发布按钮并二次断言成功(不再 sleep 5s 谎报成功)
            published, evidence = False, ""
            try:
                publish_btn = await page.query_selector('button:has-text("发布"), .publishBtn')
                if publish_btn:
                    await publish_btn.click()
                    published, evidence = await wait_for_success(
                        page, ["发布成功", "发布完成", "已发布"], timeout_ms=30000)
                else:
                    evidence = "未找到发布按钮"
            except Exception as e:
                evidence = f"点击发布异常: {e}"

            # 刷新保存最新 Session Cookies
            await context.storage_state(path=cookies)
            await browser.close()
            if published:
                return {"status": "success", "message": "小红书笔记发布成功",
                        "title": payload.title, "evidence": evidence}
            return {"status": "pending",
                    "message": "发布请求已提交但未确认成功，请人工到创作者中心核对",
                    "title": payload.title, "evidence": evidence}

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"自动化发布异常: {str(e)}")


# ---------- 公众号草稿发布（mp.weixin.qq.com · 存草稿模式，人工确认发布） ----------
@app.post("/publish/gzh")
async def publish_gzh_draft(payload: PublishPayload):
    """
    公众号草稿模式：登录 mp.weixin.qq.com → 新建图文 → 填标题与正文 → 保存草稿（不群发）。
    草稿进后台后由用户在手机/电脑端确认发布（官方容忍度高，反封号风险最低）。
    content 支持 Markdown 基础转换与富文本 HTML（注入编辑器 innerHTML）。
    """
    cookies = resolve_cookies("gzh", payload.cookies_json_path)
    ensure_cookies(cookies, "公众号")

    try:
        async with async_playwright() as p:
            browser, context = await launch_context(p, cookies)
            page = await context.new_page()

            await page.goto("https://mp.weixin.qq.com/", wait_until="domcontentloaded")
            await page.wait_for_timeout(3000)

            # 登录态哨兵：跳转登录页即判定失效
            if "login" in page.url or await page.query_selector("#header a[href*='login']"):
                await context.storage_state(path=cookies)
                await browser.close()
                raise HTTPException(status_code=401,
                                    detail="公众号登录态失效，请重新扫码登录（写入 gzh_cookies.json）")

            # 提取真实会话 token（用 0 打不开编辑器）
            token = ""
            m = re.search(r"[?&]token=(\d+)", page.url)
            if m:
                token = m.group(1)
            if not token:
                try:
                    await page.wait_for_url(re.compile(r"token=\d+"), timeout=10000)
                    m = re.search(r"[?&]token=(\d+)", page.url)
                    if m:
                        token = m.group(1)
                except Exception:
                    pass
            try:
                window_token = await page.evaluate("window.token || ''")
                if window_token:
                    token = str(window_token)
            except Exception:
                pass
            if not token:
                html = await page.content()
                m = re.search(r"token[=:]['\"]?(\d+)", html)
                if m:
                    token = m.group(1)
            if not token:
                link = await page.query_selector("a[href*='token=']")
                if link:
                    href = await link.get_attribute("href") or ""
                    m = re.search(r"token=(\d+)", href)
                    if m:
                        token = m.group(1)
            print("公众号 token:", token or "（未取到，回退 0）")

            # 进入新建图文草稿页（携带真实 token）
            await page.goto(
                "https://mp.weixin.qq.com/cgi-bin/appmsg?t=media/appmsg_edit_v2&action=edit"
                f"&isNew=1&type=10&token={token}&lang=zh_CN",
                wait_until="domcontentloaded",
            )
            await page.wait_for_timeout(6000)
            print("公众号编辑页 URL:", page.url)

            # 填写标题：按可见元素/占位符定位（新版编辑器 #title 是隐藏的）
            title_set = False
            for sel in ['input[placeholder*="标题"]:visible',
                        'textarea[placeholder*="标题"]:visible',
                        'div[placeholder*="标题"]:visible',
                        'div[data-placeholder*="标题"]:visible',
                        '#title:visible']:
                try:
                    el = page.locator(sel).first
                    if await el.count():
                        await el.click()
                        tag = (await el.evaluate("e => e.tagName")).upper()
                        if tag in ("DIV", "SPAN") or await el.get_attribute("contenteditable") == "true":
                            await el.evaluate(
                                "(e, t) => { e.textContent = t; "
                                "e.dispatchEvent(new Event('input', {bubbles:true})); }",
                                payload.title)
                        else:
                            await el.fill(payload.title)
                        title_set = True
                        break
                except Exception as e:
                    print("公众号标题提示:", e)
            if not title_set:
                try:
                    tag = await page.evaluate("""(arg) => {
                        const all = [...document.querySelectorAll(
                            'input, textarea, div, span, [contenteditable="true"]')];
                        const el = all.find(e => {
                          const ph = e.getAttribute ? (e.getAttribute('placeholder') ||
                            e.getAttribute('data-placeholder') || '') : '';
                          return ph.includes('标题') && e.offsetParent !== null;
                        });
                        if (!el) return '';
                        el.focus();
                        if (el.isContentEditable) {
                          el.textContent = arg;
                          el.dispatchEvent(new Event('input', {bubbles:true}));
                        } else {
                          const setter = Object.getOwnPropertyDescriptor(
                            HTMLInputElement.prototype, 'value').set ||
                            Object.getOwnPropertyDescriptor(HTMLTextAreaElement.prototype, 'value').set;
                          setter.call(el, arg);
                          el.dispatchEvent(new Event('input', {bubbles:true}));
                        }
                        return el.tagName;
                    }""", payload.title)
                    title_set = bool(tag)
                    print("公众号标题 JS 填充:", tag or "未找到")
                except Exception as e:
                    print("公众号标题 JS 提示:", e)
            if not title_set:
                print("公众号标题: 未找到可见输入框")
                try:
                    await page.screenshot(path="/data/shared/gzh_debug_title.png", full_page=True)
                    print("已截图: /data/shared/gzh_debug_title.png")
                except Exception as se:
                    print("截图失败:", se)

            # 填写正文：遍历所有 frame + 可见 contenteditable（新版编辑器兼容）
            content_set = False
            for f in page.frames:
                try:
                    body = f.locator('body[contenteditable="true"]:visible, '
                                     '[contenteditable="true"]:visible').first
                    if await body.count():
                        await body.click()
                        await body.evaluate(
                            "(el, html) => { el.innerHTML = html; "
                            "el.dispatchEvent(new Event('input', {bubbles:true})); }",
                            payload.content)
                        content_set = True
                        break
                except Exception as e:
                    print("公众号 frame 正文提示:", e)
            if not content_set:
                for sel in ['div[contenteditable="true"]:visible',
                            ".ProseMirror:visible",
                            ".ql-editor:visible"]:
                    try:
                        el = page.locator(sel).first
                        if await el.count() and await el.is_visible():
                            await el.click()
                            await el.evaluate(
                                "(el, html) => { el.innerHTML = html; "
                                "el.dispatchEvent(new Event('input', {bubbles:true})); }",
                                payload.content)
                            content_set = True
                            break
                    except Exception as e:
                        print("公众号正文提示:", e)
            if not content_set:
                try:
                    done = await page.evaluate("""(arg) => {
                        const all = [...document.querySelectorAll(
                            '[contenteditable="true"], div[data-placeholder], div[placeholder]')];
                        const el = all.find(e => e.offsetParent !== null);
                        if (!el) return false;
                        el.focus();
                        el.innerHTML = arg;
                        el.dispatchEvent(new Event('input', {bubbles:true}));
                        return true;
                    }""", payload.content)
                    content_set = bool(done)
                    print("公众号正文 JS 填充:", "OK" if done else "未找到")
                except Exception as e:
                    print("公众号正文 JS 提示:", e)
            if not content_set:
                print("公众号正文提示: 未找到可编辑区域")
                try:
                    await page.screenshot(path="/data/shared/gzh_debug_content.png", full_page=True)
                    print("已截图: /data/shared/gzh_debug_content.png")
                except Exception as se:
                    print("截图失败:", se)

            # 保存草稿并二次断言(不点群发)
            saved, evidence = False, ""
            try:
                draft_btn = await page.query_selector(
                    'button:has-text("保存为草稿"), a:has-text("保存为草稿"), '
                    'button:has-text("存草稿"), #js_save, '
                    'a:has-text("存草稿"), button:has-text("保存草稿")')
                if draft_btn:
                    await draft_btn.click()
                    saved, evidence = await wait_for_success(
                        page, ["保存成功", "已保存"], timeout_ms=15000)
                else:
                    evidence = "未找到存草稿按钮"
            except Exception as e:
                evidence = f"存草稿异常: {e}"

            # 发布模式：auto_publish=True 时存草稿后继续群发（全自动模式）
            published = False
            if payload.auto_publish and saved:
                try:
                    send_btn = await page.query_selector('button:has-text("群发"), button:has-text("发表")')
                    if send_btn:
                        await send_btn.click()
                        await page.wait_for_timeout(1500)
                        # 群发确认弹窗
                        try:
                            confirm = await page.query_selector(
                                'button:has-text("确认"), .weui-desktop-btn_primary:has-text("确认"), button:has-text("确定")')
                            if confirm:
                                await confirm.click()
                        except Exception:
                            pass
                        published, ev2 = await wait_for_success(
                            page, ["群发成功", "发送成功"], timeout_ms=30000)
                        evidence += f"；群发: {ev2}"
                    else:
                        evidence += "；未找到群发按钮"
                except Exception as e:
                    evidence += f"；群发异常: {e}"

            await context.storage_state(path=cookies)
            await browser.close()
            if published:
                return {"status": "success", "message": "公众号已群发（全自动模式）",
                        "title": payload.title, "draft": False, "evidence": evidence}
            if saved:
                return {"status": "success", "message": "公众号草稿已保存（待人工确认发布）",
                        "title": payload.title, "draft": True, "evidence": evidence}
            return {"status": "pending",
                    "message": "草稿保存请求已提交但未确认成功，请人工到公众号后台核对",
                    "title": payload.title, "draft": True, "evidence": evidence}

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"公众号草稿自动化异常: {str(e)}")


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
