# -*- coding: utf-8 -*-
"""
内置定时调度器 (Built-in Scheduler)
====================================
让工作台不再依赖外部 Agent 才能定时跑：选题抓取 / 爆款采集拆解 / 周经验聚合 /
48h 回收检查，全部由本模块在服务进程内按用户配置的时间点自动触发。

配置：data/scheduler.json（用户可在「设置 → 定时任务」中修改）
  {
    "enabled": false,
    "tasks": {
      "topics":  {"enabled": false, "times": ["08:00", "12:00", "20:00"]},
      "viral":   {"enabled": false, "times": ["09:00", "21:00"]},
      "weekly":  {"enabled": false, "times": ["21:00"], "weekday": 0},
      "recycle": {"enabled": false, "times": ["21:30"]}
    }
  }

说明：调度器仅在「应用打开期间」运行；到期时应用未打开则下次启动补跑当分钟的任务。
"""
import json
import os
import subprocess  # nosec B404
import sys
import threading
import time
from datetime import datetime

ROOT = os.path.normpath(os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))
SCRIPTS = os.path.join(ROOT, "scripts")
SCHEDULER_FILE = os.path.join(ROOT, "data", "scheduler.json")

TASKS_META = {
    "topics": {"label": "热点采集 + 选题推荐", "hint": "抓取多源热点雷达并生成日/周选题推荐", "default_times": ["08:00", "12:00", "20:00"]},
    "viral": {"label": "三平台爆款榜单 + Top5 拆解", "hint": "采集小红书/抖音/公众号 Top10 并自动拆解热度前 5", "default_times": ["09:00", "21:00"]},
    "weekly": {"label": "爆款周经验包聚合", "hint": "聚合近 7 天拆解为经验包并升级 Agent SOP（周一）", "default_times": ["21:00"], "weekday": 0},
    "recycle": {"label": "48h 数据回收检查", "hint": "扫描发布超 48h 未回填的任务，提醒补录数据", "default_times": ["21:30"]},
}

# 记录本次进程内已触发的 (task, YYYY-MM-DD HH:MM)，避免同一分钟重复触发
_last_fired = {}


def default_config():
    return {
        "enabled": False,
        "tasks": {
            key: {
                "enabled": False,
                "times": list(meta.get("default_times", [])),
                **({"weekday": meta["weekday"]} if "weekday" in meta else {}),
            }
            for key, meta in TASKS_META.items()
        },
        "updated_at": "",
    }


def load_config():
    try:
        with open(SCHEDULER_FILE, "r", encoding="utf-8") as f:
            data = json.load(f)
    except Exception:
        return default_config()
    if not isinstance(data, dict) or "tasks" not in data:
        return default_config()
    # 合并缺省字段，保证结构完整
    base = default_config()
    base["enabled"] = bool(data.get("enabled", False))
    base["updated_at"] = data.get("updated_at", "")
    for key, meta in TASKS_META.items():
        t = data.get("tasks", {}).get(key, {})
        if not isinstance(t, dict):
            t = {}
        base["tasks"][key] = {
            "enabled": bool(t.get("enabled", False)),
            "times": _sanitize_times(t.get("times", meta.get("default_times", []))),
            **({"weekday": int(t.get("weekday", meta["weekday"]))} if "weekday" in meta else {}),
        }
    return base


def _sanitize_times(times):
    out = []
    for t in times or []:
        t = str(t).strip()
        parts = t.split(":")
        if len(parts) == 2 and parts[0].isdigit() and parts[1].isdigit():
            h, m = int(parts[0]), int(parts[1])
            if 0 <= h <= 23 and 0 <= m <= 59:
                out.append(f"{h:02d}:{m:02d}")
    # 去重保序
    seen, uniq = set(), []
    for t in out:
        if t not in seen:
            seen.add(t)
            uniq.append(t)
    return uniq


def save_config(cfg):
    cfg = cfg or {}
    base = load_config()
    if "enabled" in cfg:
        base["enabled"] = bool(cfg["enabled"])
    tasks = cfg.get("tasks", {})
    if isinstance(tasks, dict):
        for key, meta in TASKS_META.items():
            t = tasks.get(key, {})
            if not isinstance(t, dict):
                continue
            base["tasks"][key]["enabled"] = bool(t.get("enabled", False))
            if t.get("times") is not None:
                base["tasks"][key]["times"] = _sanitize_times(t.get("times", []))
    base["updated_at"] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    os.makedirs(os.path.dirname(SCHEDULER_FILE), exist_ok=True)
    tmp = SCHEDULER_FILE + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(base, f, ensure_ascii=False, indent=2)
    os.replace(tmp, SCHEDULER_FILE)
    return base


def _run_sync(cmd, timeout=600):
    """同步执行一个白名单脚本（按依赖顺序阻塞执行），返回 (ok, stdout_tail)。"""
    try:
        r = subprocess.run(  # nosec B603  # 命令为内部固定参数列表，无 shell
            [sys.executable, os.path.join(SCRIPTS, cmd[0])] + cmd[1:],
            cwd=ROOT, capture_output=True, text=True, timeout=timeout,
        )
        return r.returncode == 0, (r.stdout or "")[-500:]
    except Exception:
        return False, ""


def _run_bg(cmd):
    """后台执行一个白名单脚本（用于耗时很长的批量拆解，不阻塞调度循环）。"""
    subprocess.Popen(  # nosec B603  # 命令为内部固定参数列表，无 shell
        [sys.executable, os.path.join(SCRIPTS, cmd[0])] + cmd[1:],
        cwd=ROOT, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
        start_new_session=True,
    )


def run_action(key):
    """执行某个调度动作（选题/爆款/周聚合/回收），并记录最近一次运行。

    依赖顺序：选题先抓热点再出推荐；爆款先采集榜单再后台拆解 Top5。
    """
    if key == "topics":
        _run_sync(["fetch_hot_topics.py"])
        _run_sync(["suggest_topics.py"])
    elif key == "viral":
        _run_sync(["collect_platform_virals.py", "--json"])
        _run_bg(["run_viral_breakdown_daily.py", "--json"])
    elif key == "weekly":
        _run_sync(["aggregate_viral_lessons.py", "--json"])
    elif key == "recycle":
        _run_sync(["run_daily_pipeline.py", "--recycle"])
    else:
        return {"ok": False, "error": f"未知调度动作: {key}"}
    _record_last_run(key)
    return {"ok": True, "task": key, "at": datetime.now().strftime("%Y-%m-%d %H:%M:%S")}


def _record_last_run(key):
    try:
        cfg = load_config()
        cfg.setdefault("last_runs", {})[key] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        os.makedirs(os.path.dirname(SCHEDULER_FILE), exist_ok=True)
        tmp = SCHEDULER_FILE + ".tmp"
        with open(tmp, "w", encoding="utf-8") as f:
            json.dump(cfg, f, ensure_ascii=False, indent=2)
        os.replace(tmp, SCHEDULER_FILE)
    except Exception:
        pass


def _tick():
    cfg = load_config()
    if not cfg.get("enabled"):
        return
    now = datetime.now()
    hm = now.strftime("%H:%M")
    stamp = now.strftime("%Y-%m-%d %H:%M")
    for key, meta in TASKS_META.items():
        t = cfg.get("tasks", {}).get(key, {})
        if not t.get("enabled") or hm not in t.get("times", []):
            continue
        if "weekday" in meta and now.weekday() != int(t.get("weekday", meta["weekday"])):
            continue
        if _last_fired.get(key) == stamp:
            continue
        _last_fired[key] = stamp
        run_action(key)


def _loop():
    while True:
        try:
            _tick()
        except Exception:
            pass
        time.sleep(30)


def start_scheduler():
    """启动调度后台线程（daemon，随服务退出自动回收）。"""
    t = threading.Thread(target=_loop, daemon=True, name="selfmedia-scheduler")
    t.start()
    return t
