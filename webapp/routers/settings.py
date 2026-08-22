# -*- coding: utf-8 -*-
"""
授权与设置 Router (/api/license/*, /api/settings, /api/templates, /api/style-docs, /api/user-preferences)
"""
import json
import os
import re
import urllib.request
from typing import Optional

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

import core

router = APIRouter(tags=["授权与设置"])


class SettingsRequest(BaseModel):
    llm_api_key: Optional[str] = None
    llm_base_url: Optional[str] = None
    llm_model: Optional[str] = None
    llm_engine_mode: Optional[str] = None
    gzh_app_id: Optional[str] = None
    gzh_app_secret: Optional[str] = None
    proxy_url: Optional[str] = None


class ProxyTestRequest(BaseModel):
    proxy_url: str = ""


class LicenseActivateRequest(BaseModel):
    token: str


class StyleDocPayload(BaseModel):
    path: str
    content: str = ""


class StyleDocResetPayload(BaseModel):
    path: str


class StyleGuidePayload(BaseModel):
    audience: str = ""
    platforms: str = ""
    tone: str = ""
    avoid: str = ""
    keywords: str = ""
    redlines: str = ""


class UserPrefsPayload(BaseModel):
    templates: dict = {}


@router.get("/api/license/status")
def api_license_status():
    """授权与引擎状态：免费/Pro/owner、到期时间、可用引擎（codex/api）。"""
    lic = core.LG._read_license()
    mode = (lic or {}).get("mode", "none")
    token = (lic or {}).get("token", "")
    payload = core.LG.LL.verify_token(token) if token else None
    tier = "owner" if mode == "owner" else (payload.get("tier") if payload else "free")
    return {
        "mode": mode,
        "tier": tier,
        "exp": payload.get("exp", "") if payload else "",
        "features": payload.get("features", []) if payload else [],
        "engine": core._engine_status(),
        "upgrade_url": core.LG.UPGRADE_URL,
        "quota_left": {
            "viral_breakdown": core.LG.quota_left("viral_breakdown", core.LG.QUOTA_FEATURES.get("viral_breakdown", 3)),
        },
        "fingerprint": core.LG.LL.device_fingerprint(),
    }


@router.get("/api/templates")
def api_templates():
    data = core.read_json(core.TEMPLATES_FILE) or {"categories": []}
    return data


@router.get("/api/style-presets")
def api_style_presets():
    out = []
    for sp in core.STYLE_PRESETS:
        full = os.path.join(core.ROOT, sp["file"])
        content = core.read_text(full) if os.path.exists(full) else ""
        out.append({"id": sp["id"], "name": sp["name"], "content": content})
    return {"presets": out}


@router.get("/api/style-docs")
def api_style_docs():
    out = []
    for rel, name in core.STYLE_DOCS:
        core._ensure_style_default(rel)
        p = os.path.join(core.ROOT, rel)
        out.append({
            "path": rel, "name": name,
            "chars": os.path.getsize(p) if os.path.exists(p) else 0,
            "is_default": core._style_is_default(rel),
        })
    return {"docs": out}


@router.get("/api/style-doc")
def api_style_doc(path: str = ""):
    p = core._safe_style_path(path)
    core._ensure_style_default(path)
    if not os.path.exists(p):
        raise HTTPException(status_code=404, detail=f"文档不存在: {path}")
    return {"path": path, "content": core.read_text(p), "is_default": core._style_is_default(path)}


@router.post("/api/style-doc/reset")
def api_style_doc_reset(payload: StyleDocResetPayload):
    p = core._safe_style_path(payload.path)
    content = core._default_style_content(payload.path)
    if not content:
        raise HTTPException(status_code=404, detail=f"该文档没有默认模板: {payload.path}")
    core._backup_style_doc(p)
    with open(p, "w", encoding="utf-8") as f:
        f.write(content)
    return {"ok": True, "path": payload.path, "is_default": True}


@router.post("/api/style-doc/guide")
def api_style_doc_guide(payload: StyleGuidePayload):
    """文风初始化引导：LLM 可用则 AI 生成，否则返回可填空模板骨架。"""
    default = core._default_style_content("skills/personal-style-guide.md")
    prompt = (
        "根据下面的回答生成一份《个人文风指南》Markdown。"
        "必须包含分节：人设定位/目标读者/主要平台/说话口吻/要避免的表达/常用术语/开头与结构/硬红线/参考示例。"
        "语气自然、可直接用于自媒体生产，不要出现解释性文字，只输出 Markdown 正文。\n\n"
        f"目标读者：{payload.audience or '（未填）'}\n"
        f"主要平台：{payload.platforms or '（未填）'}\n"
        f"说话风格：{payload.tone or '（未填）'}\n"
        f"要避免的表达：{payload.avoid or '（未填）'}\n"
        f"常用术语/黑话：{payload.keywords or '（未填）'}\n"
        f"硬红线：{payload.redlines or '（未填）'}\n\n"
        f"默认模板结构参考：\n{default[:1800]}"
    )
    try:
        out = core.llm_engine.chat_json(
            [
                {"role": "system", "content": "你是资深自媒体文风顾问，擅长把用户零散回答整理成可执行的内容风格指南。"},
                {"role": "user", "content": prompt},
            ],
            max_tokens=3000,
        )
        content = ((out or {}).get("content") or "").strip()
        if content:
            return {"ok": True, "mode": "ai", "content": content}
    except Exception as e:
        core.logger.warning("AI 文风生成失败，降级为模板模式: %s", e)
    content = (
        "# 个人文风指南（引导生成草稿）\n\n"
        f"- 目标读者：{payload.audience or '（待补充）'}\n"
        f"- 主要平台：{payload.platforms or '（待补充）'}\n"
        f"- 说话风格：{payload.tone or '（待补充）'}\n"
        f"- 要避免的表达：{payload.avoid or '（待补充）'}\n"
        f"- 常用术语/黑话：{payload.keywords or '（待补充）'}\n"
        f"- 硬红线：{payload.redlines or '（待补充）'}\n\n"
        "> 这是填空草稿，请补充具体例子后保存；配置 LLM Key 后可一键 AI 生成更完整的版本。"
    )
    return {"ok": True, "mode": "template", "content": content}


@router.post("/api/style-doc")
def api_style_doc_save(payload: StyleDocPayload):
    p = core._safe_style_path(payload.path)
    if len(payload.content) > 200_000:
        raise HTTPException(status_code=400, detail="内容过大（≤200KB）")
    os.makedirs(os.path.dirname(p), exist_ok=True)
    core._backup_style_doc(p)
    with open(p, "w", encoding="utf-8") as f:
        f.write(payload.content)
    return {"ok": True, "path": payload.path}


@router.post("/api/user-preferences")
def api_user_preferences_save(payload: UserPrefsPayload):
    """保存用户偏好（模板选择等），供初始化与流水线读取。"""
    templates = payload.templates or {}
    valid_ids = set()
    td = core.read_json(core.TEMPLATES_FILE) or {"categories": []}
    for cat in td.get("categories", []):
        for it in cat.get("items", []):
            valid_ids.add(it.get("id", ""))
    cleaned = {k: v for k, v in templates.items() if v in valid_ids}
    data = {"templates": cleaned, "updated_at": core._now_str()}
    os.makedirs(os.path.dirname(core.USER_PREFS_FILE), exist_ok=True)
    with open(core.USER_PREFS_FILE, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
    return {"ok": True, "preferences": data}


@router.get("/api/user-preferences")
def api_user_preferences():
    return core.read_json(core.USER_PREFS_FILE) or {"templates": {}}


@router.get("/api/settings")
def api_settings():
    """读取配置状态（密钥只显示掩码，不返回明文）。"""
    env = core._read_env()
    api_ok, api_reason, _ = core.llm_engine.engine_status()
    proxy_val = env.get("SELFMEDIA_PROXY", env.get("HTTP_PROXY", "")).strip()
    usage = core.llm_engine.get_usage()
    return {
        "llm": {
            "configured": bool(env.get("LLM_API_KEY", "").strip()),
            "api_key_masked": core._mask(env.get("LLM_API_KEY", "")),
            "base_url": env.get("LLM_BASE_URL", core.llm_engine.DEFAULT_BASE_URL),
            "model": env.get("LLM_MODEL", core.llm_engine.DEFAULT_MODEL),
            "engine_mode": core.llm_engine.engine_mode(),
            "status_ok": api_ok,
            "status_reason": api_reason,
        },
        "gzh": {
            "configured": bool(env.get("GZH_APP_ID", "").strip() and env.get("GZH_APP_SECRET", "").strip()),
            "app_id_masked": core._mask(env.get("GZH_APP_ID", "")),
            "secret_masked": core._mask(env.get("GZH_APP_SECRET", "")),
        },
        "proxy": {
            "configured": bool(proxy_val),
            "url": proxy_val,
        },
        "engine": core._engine_status(),
        "token_usage": usage,
    }


@router.post("/api/settings")
def api_save_settings(payload: SettingsRequest):
    """保存配置到项目根 .env（本地单机文件，权限 600）。"""
    updates = {}
    if payload.llm_api_key is not None:
        updates["LLM_API_KEY"] = payload.llm_api_key.strip()
    if payload.llm_base_url is not None:
        b_clean = payload.llm_base_url.strip()
        b_clean = re.sub(r"/(?:models|chat/completions)/?$", "", b_clean)
        updates["LLM_BASE_URL"] = b_clean
    if payload.llm_model is not None:
        updates["LLM_MODEL"] = payload.llm_model.strip()
    if payload.llm_engine_mode is not None:
        mode = payload.llm_engine_mode.strip().lower()
        if mode not in ("auto", "api", "codex", "workbuddy"):
            raise HTTPException(status_code=400, detail="引擎模式仅支持 auto / api / codex / workbuddy")
        updates["LLM_ENGINE_MODE"] = mode
    if payload.gzh_app_id is not None:
        updates["GZH_APP_ID"] = payload.gzh_app_id.strip()
    if payload.gzh_app_secret is not None:
        updates["GZH_APP_SECRET"] = payload.gzh_app_secret.strip()
    if payload.proxy_url is not None:
        p_clean = payload.proxy_url.strip()
        updates["SELFMEDIA_PROXY"] = p_clean
        updates["HTTP_PROXY"] = p_clean
        updates["HTTPS_PROXY"] = p_clean
    if updates:
        core._write_env(updates)
        for k, v in updates.items():
            os.environ[k] = v
    return api_settings()


@router.post("/api/settings/llm-clear")
def api_llm_clear():
    """清空 LLM 配置（删除 API Key / 地址 / 模型，恢复未配置状态）。"""
    core._write_env({"LLM_API_KEY": "", "LLM_BASE_URL": "", "LLM_MODEL": ""})
    for k in ("LLM_API_KEY", "LLM_BASE_URL", "LLM_MODEL"):
        os.environ.pop(k, None)
    return api_settings()


@router.post("/api/settings/proxy-test")
def api_proxy_test(payload: ProxyTestRequest):
    """测试代理连通性（检测是否能访问海外源如 Google Trends）。"""
    p_url = payload.proxy_url.strip() or os.environ.get("SELFMEDIA_PROXY", "")
    if not p_url:
        raise HTTPException(status_code=400, detail="请先输入代理地址（如 http://127.0.0.1:7897）")
    try:
        req = urllib.request.Request(
            "https://trends.google.com/trending/rss?geo=US",
            headers={"User-Agent": "Mozilla/5.0"}
        )
        opener = urllib.request.build_opener(urllib.request.ProxyHandler({"http": p_url, "https": p_url}))
        with opener.open(req, timeout=6) as resp:
            return {"ok": True, "status_code": resp.getcode(), "message": "✅ 代理连接正常，可高速访问谷歌趋势与海外热点！"}
    except Exception as e:
        return {"ok": False, "message": f"❌ 代理连接失败: {e}（请检查本地代理软件是否开启）"}


@router.post("/api/license/activate")
def api_license_activate(payload: LicenseActivateRequest):
    """粘贴 token 即激活：验签 + 设备绑定校验，写入本地授权文件。"""
    token = payload.token.strip()
    pl = core.LG.LL.verify_token(token)
    if pl is None:
        raise HTTPException(status_code=400, detail="token 无效或验签失败，请检查是否复制完整")
    bind = pl.get("bind", "")
    if pl.get("tier") != "owner" and bind and bind != core.LG.LL.device_fingerprint():
        fp = core.LG.LL.device_fingerprint()
        raise HTTPException(
            status_code=403,
            detail=f"该 token 绑定的是其他设备（本机指纹 {fp} 不匹配）；请把本机指纹发给卖家重签",
        )
    core.LG._save(core.LG.LICENSE_FILE, {
        "mode": "token", "token": token, "installed_at": core.LG.LL.iso_today(),
    })
    return {"ok": True, "tier": pl.get("tier"), "exp": pl.get("exp", ""),
            "message": f"授权激活成功（{pl.get('tier')}，到期 {pl.get('exp')}）"}


@router.post("/api/settings/llm-test")
def api_llm_test():
    """测试 LLM 连接：发一条极短消息，返回模型回复。"""
    ok, reason, _ = core.llm_engine.engine_status()
    if not ok:
        return {"ok": False, "message": reason}
    try:
        reply = core.llm_engine.chat(
            [{"role": "user", "content": "请只回复两个字：正常"}],
            max_tokens=16, timeout=30,
        )
        return {"ok": True, "message": "连接成功，模型回复：" + (reply or "")[:50]}
    except Exception as e:
        return {"ok": False, "message": str(e)}
