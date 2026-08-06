import os
import time
import re
import html as html_lib
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
            print("小红书发布页 URL:", page.url)

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

            # 新版入口页：先点“上传图文”进入图文编辑器
            try:
                clicked = await page.evaluate("""() => {
                    const els = [...document.querySelectorAll('*')].filter(e =>
                        e.children.length === 0 &&
                        (e.textContent || '').trim() === '上传图文');
                    if (!els.length) return false;
                    els[0].click();
                    return true;
                }""")
                if clicked:
                    await page.wait_for_timeout(6000)
                    print("已点击(JS)：上传图文；URL:", page.url)
                else:
                    print("未找到『上传图文』文本元素")
            except Exception as e:
                print("上传图文点击提示:", e)

            # 定位图片上传 file input
            all_inputs = await page.query_selector_all('input[type="file"]')
            image_input = None
            # 优先多图输入框（正文配图）；封面等单图输入框一次只能传 1 张
            for inp in all_inputs:
                has_mult = (await inp.get_attribute("multiple")) is not None
                if has_mult:
                    image_input = inp
                    break
            if not image_input:
                for inp in all_inputs:
                    acc = (await inp.get_attribute("accept")) or ""
                    if "image" in acc or ".png" in acc:
                        image_input = inp
                        break
            if not image_input and all_inputs:
                image_input = all_inputs[-1]

            if image_input:
                has_mult = (await image_input.get_attribute("multiple")) is not None
                if has_mult or len(valid_images) == 1:
                    await image_input.set_input_files(valid_images)
                else:
                    # 兜底：单图输入框一次只能传 1 张，先传第一张
                    await image_input.set_input_files(valid_images[:1])
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
                try:
                    await page.screenshot(path="/data/shared/xhs_debug_title.png", full_page=True)
                    body_snip = (await page.inner_text("body"))[:200].replace("\n", " | ")
                    print("已截图: xhs_debug_title；body:", body_snip)
                except Exception as se:
                    print("截图失败:", se)

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
                try:
                    await page.screenshot(path="/data/shared/xhs_debug_content.png", full_page=True)
                    print("已截图: xhs_debug_content")
                except Exception as se:
                    print("截图失败:", se)

            await page.wait_for_timeout(3000)

            # 点击发布按钮并二次断言成功(不再 sleep 5s 谎报成功)
            published, evidence = False, ""
            try:
                await page.evaluate("window.scrollTo(0, document.body.scrollHeight)")
                await page.wait_for_timeout(1000)
                try:
                    cands = await page.evaluate("""() => {
                        const out = [];
                        [...document.querySelectorAll('button, a, div, span')].forEach(e => {
                            const t = (e.innerText || '').trim();
                            const r = e.getBoundingClientRect();
                            if ((t === '发布' || t === '发布笔记' || t === '下一步' || t === '完成')
                                    && r.width > 0 && r.height > 0) {
                                out.push({
                                    tag: e.tagName,
                                    cls: (e.className || '').toString().slice(0, 60),
                                    text: t.slice(0, 20),
                                    x: Math.round(r.x), y: Math.round(r.y),
                                    w: Math.round(r.width), h: Math.round(r.height),
                                });
                            }
                        });
                        return out.slice(0, 40);
                    }""")
                    print("发布按钮候选:", cands)
                except Exception as ce:
                    print("发布按钮诊断失败:", ce)

                pub_clicked = False
                # Playwright 定位器（可穿透 open shadow DOM）
                try:
                    pub_locs = page.locator("text=发布")
                    pub_n = await pub_locs.count()
                    print("发布 locator 数量:", pub_n)
                    for i in range(pub_n):
                        el = pub_locs.nth(i)
                        box = await el.bounding_box()
                        if box and box["x"] > 300 and box["y"] > 500 and box["width"] > 40:
                            await el.click()
                            pub_clicked = True
                            break
                except Exception as le:
                    print("发布 locator 点击提示:", le)
                if not pub_clicked:
                    pub_clicked = await page.evaluate("""() => {
                        const els = [...document.querySelectorAll('*')].filter(e => {
                            const t = (e.innerText || '').trim();
                            const r = e.getBoundingClientRect();
                            return t === '发布' &&
                                r.width > 30 && r.width < 300 &&
                                r.height > 20 && r.height < 90 &&
                                r.x > 300;
                        });
                        if (!els.length) return false;
                        els[els.length - 1].click();
                        return true;
                    }""")
                print("发布按钮 JS 点击:", pub_clicked)
                if pub_clicked:
                    published, evidence = await wait_for_success(
                        page, ["发布成功", "发布完成", "已发布"], timeout_ms=30000)
                    try:
                        await page.screenshot(path="/data/shared/xhs_debug_after_publish.png",
                                              full_page=True)
                        print("发布后 URL:", page.url)
                        tail_txt = (await page.inner_text("body"))[-300:].replace("\n", " | ")
                        print("发布后 body:", tail_txt)
                    except Exception as se:
                        print("发布后诊断失败:", se)
                else:
                    publish_btn = await page.query_selector('button:has-text("发布"), .publishBtn')
                    if publish_btn:
                        await publish_btn.click()
                        published, evidence = await wait_for_success(
                            page, ["发布成功", "发布完成", "已发布"], timeout_ms=30000)
                        try:
                            await page.screenshot(path="/data/shared/xhs_debug_after_publish.png",
                                                  full_page=True)
                            print("发布后 URL:", page.url)
                            tail_txt = (await page.inner_text("body"))[-300:].replace("\n", " | ")
                            print("发布后 body:", tail_txt)
                        except Exception as se:
                            print("发布后诊断失败:", se)
                    else:
                        evidence = "未找到发布按钮"
                        try:
                            await page.screenshot(path="/data/shared/xhs_debug_publish.png",
                                                  full_page=True)
                            body_snip = (await page.inner_text("body"))[:200].replace("\n", " | ")
                            print("已截图: xhs_debug_publish；body:", body_snip)
                        except Exception as se:
                            print("截图失败:", se)
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
            console_msgs = []
            save_reqs = []
            page.on("console", lambda m: console_msgs.append(f"[{m.type}] {m.text[:200]}"))
            page.on("pageerror", lambda e: console_msgs.append(f"[pageerror] {str(e)[:300]}"))

            async def _on_response(r):
                if "operate_appmsg" in r.url or "cgi-bin" in r.url:
                    try:
                        body = await r.text()
                        save_reqs.append(f"RESP {r.status} {r.url} :: {body[:300]}")
                    except Exception:
                        save_reqs.append(f"RESP {r.status} {r.url}")

            page.on("request", lambda r: save_reqs.append(
                f"REQ {r.method} {r.url}") if "operate_appmsg" in r.url else None)
            page.on("response", lambda r: asyncio.ensure_future(_on_response(r)))

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

            # 填写标题：优先在可见 ProseMirror 标题框内键入（触发编辑器真实事件）
            title_set = False
            try:
                title_box = page.locator(".ProseMirror:visible").first
                if await title_box.count():
                    await title_box.click()
                    await page.keyboard.insert_text(payload.title)
                    await page.wait_for_timeout(800)
                    title_set = True
                    print("公众号标题: 键入 ProseMirror")
            except Exception as e:
                print("公众号标题键入提示:", e)
            # 回退 1：可见占位元素 DOM 填充
            if not title_set:
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
            # 回退 2：JS 定位占位符元素
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
            else:
                print("公众号标题填充: OK")

            # 诊断：列出所有标题占位元素（含可见性/尺寸），用于定位新版编辑器真实标题框
            try:
                candidates = await page.evaluate("""() => {
                    const out = [];
                    document.querySelectorAll(
                        'input, textarea, div, span, [contenteditable="true"]').forEach(e => {
                        const ph = e.getAttribute ? (e.getAttribute('placeholder') ||
                            e.getAttribute('data-placeholder') || '') : '';
                        if (ph.includes('标题')) {
                            const r = e.getBoundingClientRect();
                            out.push({
                                tag: e.tagName, id: e.id || '', cls: (e.className || '').toString().slice(0, 40),
                                vis: e.offsetParent !== null, w: Math.round(r.width), h: Math.round(r.height),
                                text: (e.innerText || e.value || '').slice(0, 30), ph: ph.slice(0, 20),
                            });
                        }
                    });
                    return out;
                }""")
                print("公众号标题候选:", candidates)
            except Exception as e:
                print("公众号标题诊断提示:", e)

            # 强制回写隐藏的 #title（新版编辑器的真实数据模型）
            try:
                await page.evaluate("""(t) => {
                    const el = document.querySelector('#title');
                    if (el) {
                        const setter = Object.getOwnPropertyDescriptor(
                            HTMLTextAreaElement.prototype, 'value').set;
                        setter.call(el, t);
                        el.dispatchEvent(new Event('input', {bubbles:true}));
                        el.dispatchEvent(new Event('change', {bubbles:true}));
                    }
                    return el ? el.value.length : -1;
                }""", payload.title)
                title_len = await page.evaluate(
                    "() => document.querySelector('#title') ? document.querySelector('#title').value.length : -1")
                print("公众号隐藏标题 #title 长度:", title_len)
            except Exception as e:
                print("公众号隐藏标题同步提示:", e)

            # 填写正文：优先键盘键入（触发 ProseMirror/ueditor 事务，保证字数登记）
            content_set = False
            plain_content = html_lib.unescape(re.sub(r"<[^>]+>", "", payload.content))
            plain_content = re.sub(r"[ \t\u00a0]+", " ", plain_content)
            plain_content = re.sub(r"\n{3,}", "\n\n", plain_content).strip()

            # 1) iframe 编辑器 body 键入
            for f in page.frames:
                try:
                    body = f.locator('body[contenteditable="true"]:visible, '
                                     '[contenteditable="true"]:visible').first
                    if await body.count():
                        await body.click()
                        await page.keyboard.insert_text(plain_content)
                        await page.wait_for_timeout(800)
                        content_set = True
                        print("公众号正文: 键入 iframe body")
                        break
                except Exception as e:
                    print("公众号 frame 键入提示:", e)
            # 2) 主页面可见 contenteditable 键入
            if not content_set:
                for sel in ['div[contenteditable="true"]:visible', ".ql-editor:visible"]:
                    try:
                        el = page.locator(sel).first
                        if await el.count() and await el.is_visible():
                            await el.click()
                            await page.keyboard.insert_text(plain_content)
                            await page.wait_for_timeout(800)
                            content_set = True
                            print("公众号正文: 键入 selector:", sel)
                            break
                    except Exception as e:
                        print("公众号正文键入提示:", e)
            # 3) innerHTML 注入兜底（仅当键入失败）
            if not content_set:
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
                            print("公众号正文填充: iframe:", f.url or f.name)
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
                            print("公众号正文填充: selector:", sel)
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
            else:
                print("公众号正文填充: OK")

            # 用编辑器官方 Vue API 把内容登记进模型（DOM/键入都不触发字数统计）
            try:
                api_result = await page.evaluate("""(arg) => {
                    const out = {};
                    try {
                        const t = window.__mpTitleEditor;
                        if (t && typeof t.setContent === 'function') {
                            t.focus && t.focus();
                            t.setContent(arg.title);
                            out.title = 'ok:' + t.getContentLength();
                        } else {
                            out.title = 'no-api';
                        }
                    } catch (e) {
                        out.title = 'ERR:' + e.message;
                    }
                    try {
                        const pms = [...document.querySelectorAll('div.ProseMirror')];
                        const pm = pms.find(e => e.offsetParent !== null &&
                            (e.innerText || '').length > 50);
                        if (pm && pm.__vue__ && typeof pm.__vue__.setContent === 'function') {
                            pm.__vue__.setContent(arg.body);
                            out.body = 'ok:' + (pm.__vue__.getContentLength ?
                                pm.__vue__.getContentLength() : '?');
                        } else {
                            out.body = 'no-api pm=' + !!pm + ' vue=' + !!(pm && pm.__vue__);
                        }
                    } catch (e) {
                        out.body = 'ERR:' + e.message;
                    }
                    return out;
                }""", {"title": payload.title, "body": payload.content})
                print("编辑器 Vue API:", api_result)
            except Exception as e:
                print("编辑器 Vue API 失败:", e)

            # 验证编辑器是否真的登记了内容（正文字数）
            await page.wait_for_timeout(1500)
            try:
                wc = await page.evaluate(
                    "() => { const m = document.body.innerText.match(/正文字数\\s*(\\d+)/); "
                    "return m ? m[1] : '?'; }")
                print("公众号正文字数:", wc)
            except Exception as e:
                print("公众号字数读取提示:", e)

            # 诊断：编辑器全局对象与 iframe 结构（定位真实编辑器实例）
            try:
                globs = await page.evaluate("""() => {
                    const keys = Object.keys(window).filter(
                        k => /editor|appmsg|prose|ue|ueditor|wx/i.test(k)).slice(0, 50);
                    const frames = [];
                    document.querySelectorAll('iframe').forEach(f => {
                        frames.push({id: f.id, name: f.name, src: (f.src || '').slice(0, 80)});
                    });
                    return {
                        keys: keys,
                        frames: frames,
                        hasUE: typeof window.UE !== 'undefined',
                        hasEditor: typeof window.editor !== 'undefined',
                        hasProse: typeof window.ProseMirror !== 'undefined',
                    };
                }""")
                print("编辑器全局:", globs)
            except Exception as e:
                print("编辑器全局诊断失败:", e)
            try:
                api_info = await page.evaluate("""() => {
                    const out = {};
                    for (const name of ['__MP_Editor_JSAPI__', '__MpEditor',
                                        '__mpTitleEditor', 'editorVarGlobal', 'UE']) {
                        const o = window[name];
                        if (!o) { out[name] = null; continue; }
                        out[name] = {
                            type: typeof o,
                            keys: Object.keys(o).slice(0, 60),
                        };
                    }
                    return out;
                }""")
                print("编辑器 API:", api_info)
            except Exception as e:
                print("编辑器 API 诊断失败:", e)
            for f in page.frames:
                try:
                    info = await f.evaluate("""() => {
                        const els = [...document.querySelectorAll(
                            '[contenteditable="true"], .ProseMirror, body')];
                        return els.map(e => ({
                            tag: e.tagName,
                            cls: (e.className || '').toString().slice(0, 30),
                            ce: e.getAttribute('contenteditable'),
                            vis: e.offsetParent !== null,
                            len: (e.innerText || '').length,
                        })).slice(0, 10);
                    }""")
                    print("frame 可编辑:", (f.url[:60] or f.name), info)
                except Exception as e:
                    print("frame 诊断失败:", e)

            # 保存草稿并二次断言(不点群发)
            saved, evidence = False, ""
            try:
                async def dump_ui(tag):
                    try:
                        ui_text = await page.evaluate("""() => {
                            const sels = '[class*="dialog"],[class*="toast"],[class*="tips"],' +
                                        '[class*="modal"],[role="dialog"]';
                            const out = [];
                            document.querySelectorAll(sels).forEach(e => {
                                const t = (e.innerText || '').trim();
                                const r = e.getBoundingClientRect();
                                if (t && r.width > 0 && e.offsetParent !== null) {
                                    out.push(t.slice(0, 200));
                                }
                            });
                            return out;
                        }""")
                        print(f"UI 弹层文本[{tag}]:", ui_text)
                    except Exception as e:
                        print(f"UI 读取失败[{tag}]:", e)

                # 方案 1：Ctrl+S 原生保存草稿快捷键
                await page.keyboard.press("Control+s")
                await page.wait_for_timeout(3000)
                print("Ctrl+S 已按下")
                await dump_ui("ctrl_s")
                saved, evidence = await wait_for_success(
                    page, ["保存成功", "已保存", "保存草稿成功"], timeout_ms=5000)

                # 方案 2：JS 点击“保存为草稿”按钮
                if not saved:
                    js_clicked = await page.evaluate("""() => {
                        const btns = [...document.querySelectorAll('button, a, span')];
                        const el = btns.find(e =>
                            (e.innerText || '').trim().includes('保存为草稿') &&
                            e.offsetParent !== null);
                        if (!el) return false;
                        el.click();
                        return true;
                    }""")
                    print("保存按钮 JS 点击:", js_clicked)
                    await page.wait_for_timeout(3000)
                    await dump_ui("js_click")
                    saved2, evidence2 = await wait_for_success(
                        page, ["保存成功", "已保存", "保存草稿成功"], timeout_ms=8000)
                    if saved2:
                        saved, evidence = True, evidence2
                    else:
                        evidence = f"Ctrl+S 与按钮点击均未确认；{evidence2}"

                try:
                    await page.screenshot(path="/data/shared/gzh_debug_after_save.png",
                                          full_page=True)
                    print("已截图: /data/shared/gzh_debug_after_save.png")
                except Exception as se:
                    print("截图失败:", se)
                print("保存后 URL:", page.url)
                try:
                    body_txt = (await page.inner_text("body"))[:200].replace("\n", " | ")
                    print("保存后 body:", body_txt)
                except Exception as be:
                    print("body 读取失败:", be)
                print("console:", console_msgs[-8:])
                print("save_reqs:", save_reqs[-20:])
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
