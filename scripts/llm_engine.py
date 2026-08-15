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

ROOT = os.path.normpath(os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))
ENV_FILE = os.path.join(ROOT, ".env")


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


def engine_status():
    """返回 (ok: bool, reason: str, config: dict)。"""
    key = os.environ.get("LLM_API_KEY", "").strip()
    base = os.environ.get("LLM_BASE_URL", DEFAULT_BASE_URL).strip()
    model = os.environ.get("LLM_MODEL", DEFAULT_MODEL).strip()
    if not key:
        return False, "缺少 LLM_API_KEY（在项目根目录 .env 中配置，或设置环境变量）", {}
    if not base.startswith(("http://", "https://")):
        return False, "LLM_BASE_URL 必须是 http(s) 地址", {}
    return True, "API 模式就绪", {"base_url": base, "model": model}


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
    req = urllib.request.Request(
        cfg["base_url"].rstrip("/") + "/chat/completions",
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
