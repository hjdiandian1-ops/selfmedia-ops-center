#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
通用 LLM 引擎适配器（OpenAI 兼容 Chat Completions，零第三方依赖）
================================================================
让工作台可以脱离 Codex/Claude 等 Agent 平台独立运行，只需要一个 API Key：
支持 DeepSeek / OpenAI / Moonshot / 本地 Ollama 等任何 OpenAI 兼容端点。

配置（项目根目录 .env 或环境变量）：
    LLM_API_KEY=sk-xxx
    LLM_BASE_URL=https://api.deepseek.com/v1
    LLM_MODEL=deepseek-chat
    LLM_TIMEOUT=120

用法：
    from llm_engine import chat, engine_status
    text = chat([{"role": "user", "content": "你好"}])
"""
import json
import os
import urllib.request
from datetime import datetime

ROOT = os.path.normpath(os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))
ENV_FILE = os.path.join(ROOT, ".env")
USAGE_FILE = os.path.join(ROOT, "data", "llm_usage.json")


def load_env():
    """读取项目根 .env（不覆盖已存在的环境变量）。"""
    if not os.path.isfile(ENV_FILE):
        return
    with open(ENV_FILE, encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            k, v = line.split("=", 1)
            os.environ.setdefault(k.strip(), v.strip().strip('"').strip("'"))


load_env()

DEFAULT_BASE_URL = os.environ.get("LLM_BASE_URL", "https://api.deepseek.com/v1")
DEFAULT_MODEL = os.environ.get("LLM_MODEL", "deepseek-chat")
TIMEOUT = int(os.environ.get("LLM_TIMEOUT", "120"))


def engine_mode():
    """当前引擎接入模式：api（直接接大模型）/ codex（Codex CLI）/ workbuddy（WorkBuddy 等 Agent）。"""
    mode = os.environ.get("LLM_ENGINE_MODE", "auto").strip().lower()
    return mode if mode in ("api", "codex", "workbuddy") else "auto"


def engine_status():
    """返回 (ok: bool, reason: str, config: dict)。"""
    key = os.environ.get("LLM_API_KEY", "").strip()
    base = os.environ.get("LLM_BASE_URL", DEFAULT_BASE_URL).strip()
    model = os.environ.get("LLM_MODEL", DEFAULT_MODEL).strip()
    if not key:
        return False, "缺少 LLM_API_KEY（在项目根目录 .env 中配置，或设置环境变量）", {}
    if not base.startswith(("http://", "https://")):
        return False, "LLM_BASE_URL 必须是 http(s) 地址", {}
    return True, "API 模式就绪", {"base_url": base, "model": model, "mode": engine_mode()}


def _load_usage():
    try:
        with open(USAGE_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return {"total": {"calls": 0, "prompt_tokens": 0, "completion_tokens": 0, "total_tokens": 0},
                "by_model": {}, "recent": []}


def _save_usage(data):
    try:
        os.makedirs(os.path.dirname(USAGE_FILE), exist_ok=True)
        tmp = USAGE_FILE + ".tmp"
        with open(tmp, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
        os.replace(tmp, USAGE_FILE)
    except Exception:
        pass


def _record_usage(model, usage, ok):
    """累计 token 消耗（成功调用才记录 usage），落盘 data/llm_usage.json。"""
    if not usage:
        return
    try:
        pt = int(usage.get("prompt_tokens") or 0)
        ct = int(usage.get("completion_tokens") or 0)
        tt = int(usage.get("total_tokens") or pt + ct)
    except (TypeError, ValueError):
        return
    data = _load_usage()
    tot = data["total"]
    tot["calls"] = (tot.get("calls") or 0) + 1
    tot["prompt_tokens"] = (tot.get("prompt_tokens") or 0) + pt
    tot["completion_tokens"] = (tot.get("completion_tokens") or 0) + ct
    tot["total_tokens"] = (tot.get("total_tokens") or 0) + tt
    bym = data.setdefault("by_model", {}).setdefault(model, {"calls": 0, "prompt_tokens": 0, "completion_tokens": 0, "total_tokens": 0})
    bym["calls"] = (bym.get("calls") or 0) + 1
    bym["prompt_tokens"] = (bym.get("prompt_tokens") or 0) + pt
    bym["completion_tokens"] = (bym.get("completion_tokens") or 0) + ct
    bym["total_tokens"] = (bym.get("total_tokens") or 0) + tt
    recent = data.setdefault("recent", [])
    recent.insert(0, {
        "at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "model": model, "prompt_tokens": pt, "completion_tokens": ct,
        "total_tokens": tt, "ok": bool(ok),
    })
    data["recent"] = recent[:50]
    _save_usage(data)


def get_usage():
    """读取累计 token 消耗统计（供设置页展示）。"""
    data = _load_usage()
    data.setdefault("recent", [])
    return {
        "total": data["total"],
        "by_model": data.get("by_model", {}),
        "recent": data["recent"][:20],
    }


def chat(messages, temperature=0.3, max_tokens=4096, json_mode=False, timeout=TIMEOUT):
    """调用 OpenAI 兼容 Chat Completions，返回文本内容。失败抛 RuntimeError。"""
    ok, reason, cfg = engine_status()
    if not ok:
        raise RuntimeError(reason)
    payload = {
        "model": cfg["model"],
        "messages": messages,
        "temperature": temperature,
        "max_tokens": max_tokens,
    }
    if json_mode:
        payload["response_format"] = {"type": "json_object"}
    clean_base = cfg["base_url"].rstrip("/")
    if clean_base.endswith("/models"):
        clean_base = clean_base[:-7].rstrip("/")
    elif clean_base.endswith("/chat/completions"):
        clean_base = clean_base[:-17].rstrip("/")
    req = urllib.request.Request(
        clean_base + "/chat/completions",
        data=json.dumps(payload).encode("utf-8"),
        headers={
            "Content-Type": "application/json",
            "Authorization": "Bearer " + os.environ.get("LLM_API_KEY", "").strip(),
        },
        method="POST",
    )
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:  # nosec B310  # nosemgrep: dynamic-urllib-use-detected  # 地址经 engine_status 校验 http(s)
            data = json.loads(resp.read().decode("utf-8"))
    except Exception as e:
        raise RuntimeError(f"LLM API 请求失败: {e}") from e
    _record_usage(cfg["model"], data.get("usage") or {}, ok=True)
    try:
        return data["choices"][0]["message"]["content"].strip()
    except (KeyError, IndexError, TypeError) as e:
        raise RuntimeError(f"LLM API 响应格式异常: {data}") from e


def chat_json(messages, temperature=0.2, max_tokens=4096, timeout=TIMEOUT):
    """JSON 模式调用，返回 dict；解析失败抛 RuntimeError。"""
    text = chat(messages, temperature=temperature, max_tokens=max_tokens,
                json_mode=True, timeout=timeout)
    text = text.strip()
    if text.startswith("```"):
        text = text.strip("`")
        if text.startswith("json"):
            text = text[4:]
    try:
        return json.loads(text)
    except json.JSONDecodeError as e:
        raise RuntimeError(f"LLM 返回的不是合法 JSON: {e}") from e
