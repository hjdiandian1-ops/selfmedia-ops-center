#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
小红书笔记导出明细表导入器（数据闭环 · 免手工回填）
====================================================
读取小红书创作服务平台「笔记管理 → 导出」的 笔记列表明细表.xlsx，
把全部字段落盘 data/stats/xhs_notes.json，并按标题自动匹配
仓库中的 Job，把阅读/赞/藏/评/涨粉等写入 jobs/<job_id>/publish_log.json
（records[]，带 note_id，重复导入幂等更新）。

用法：
    python3 scripts/import_xhs_notes.py --file /path/笔记列表明细表.xlsx
    # 顺带更新账号快照（粉丝/关注/赞藏/主页访客，均非导出表字段）
    python3 scripts/import_xhs_notes.py --file /path/笔记列表明细表.xlsx \
        --account-followers 45 --account-following 41 \
        --account-likes-collects 387 --account-profile-visits 89 \
        --account-period "08-01 至 08-07"
    # 测试/隔离环境
    python3 scripts/import_xhs_notes.py --file /tmp/a.xlsx \
        --jobs-dir /tmp/jobs --data-dir /tmp/data/stats --json

仅依赖标准库（xlsx 为 zip+XML，无需 openpyxl）。
"""
import argparse
import glob
import json
import os
import re
import sys
import zipfile
import xml.etree.ElementTree as ET  # nosec B405  # 已做 zip 炸弹防护；ElementTree 不解析外部实体
from datetime import datetime

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from security_utils import safe_xlsx_zip  # noqa: E402

ROOT = os.path.normpath(os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))
DEFAULT_JOBS_DIR = os.path.join(ROOT, "jobs")
DEFAULT_DATA_DIR = os.path.join(ROOT, "data", "stats")

NS = {"m": "http://schemas.openxmlformats.org/spreadsheetml/2006/main"}
CELL_T = "{http://schemas.openxmlformats.org/spreadsheetml/2006/main}t"

# 小红书导出表表头 → 内部字段
HEADER_ALIASES = {
    "笔记标题": "title",
    "首次发布时间": "first_published_at",
    "体裁": "format",
    "曝光": "exposure",
    "观看量": "reads",
    "封面点击率": "ctr",
    "点赞": "likes",
    "评论": "comments",
    "收藏": "collects",
    "涨粉": "followers_gained",
    "分享": "shares",
    "人均观看时长": "avg_watch_seconds",
    "弹幕": "danmaku",
}

NUM_FIELDS = {
    "exposure", "reads", "likes", "comments", "collects",
    "followers_gained", "shares", "avg_watch_seconds", "danmaku", "ctr",
}


def _col_to_idx(ref):
    m = re.match(r"([A-Z]+)", ref or "")
    if not m:
        return None
    idx = 0
    for ch in m.group(1):
        idx = idx * 26 + (ord(ch) - ord("A") + 1)
    return idx - 1


def read_xlsx_rows(path):
    """读取 xlsx 第一个工作表，返回二维列表（首行为表头）。纯标准库实现。"""
    rows = []
    with safe_xlsx_zip(path) as zf:
        names = zf.namelist()
        shared = []
        if "xl/sharedStrings.xml" in names:
            root = ET.fromstring(zf.read("xl/sharedStrings.xml"))  # nosec B314  # 见 B405 说明
            for si in root.findall("m:si", NS):
                shared.append("".join(t.text or "" for t in si.iter(CELL_T)))

        sheet_path = next(
            (n for n in names if re.match(r"xl/worksheets/sheet\d+\.xml$", n)),
            None,
        )
        if not sheet_path:
            raise ValueError("xlsx 中找不到工作表（xl/worksheets/sheet*.xml）")
        root = ET.fromstring(zf.read(sheet_path))  # nosec B314  # 见 B405 说明
        for row_el in root.findall("m:sheetData/m:row", NS):
            cells = {}
            for c in row_el.findall("m:c", NS):
                idx = _col_to_idx(c.get("r"))
                if idx is None:
                    continue
                t = c.get("t")
                v_el = c.find("m:v", NS)
                if t == "s" and v_el is not None:
                    val = shared[int(v_el.text)]
                elif t == "inlineStr":
                    val = "".join(tt.text or "" for tt in c.iter(CELL_T))
                else:
                    val = v_el.text if v_el is not None else None
                cells[idx] = val
            if not cells:
                continue
            row = [cells.get(i) for i in range(max(cells) + 1)]
            rows.append(row)
    return rows


def to_num(val):
    if val is None or val == "":
        return 0
    if isinstance(val, (int, float)):
        return float(val)
    s = str(val).replace(",", "").strip()
    if s.endswith("%"):
        return float(s[:-1])
    try:
        return float(s)
    except ValueError:
        return 0


def to_int(val):
    return int(to_num(val))


def parse_rows(rows):
    """按表头映射导出行为 note dict。"""
    if not rows:
        return []
    # 导出表可能带说明行（如“最多导出排序后前1000条笔记”），自动定位真实表头行
    header_idx, col_map = None, {}
    for i, raw in enumerate(rows[:20]):
        candidate = {}
        for j, h in enumerate(raw):
            key = HEADER_ALIASES.get(str(h or "").strip())
            if key:
                candidate[j] = key
        if len(candidate) >= 3 and "title" in candidate.values() and "reads" in candidate.values():
            header_idx, col_map = i, candidate
            break
    if header_idx is None:
        raise ValueError("无法识别小红书导出表头，请确认是「笔记管理 → 导出」的明细表")

    notes = []
    for raw in rows[header_idx + 1:]:
        note = {}
        for idx, key in col_map.items():
            val = raw[idx] if idx < len(raw) else None
            if key in NUM_FIELDS:
                note[key] = to_num(val)
            else:
                note[key] = (str(val or "").strip()) if val is not None else ""
        note["title"] = note.get("title", "").strip()
        if not note["title"] and not note.get("first_published_at"):
            continue  # 空行
        note["format"] = note.get("format", "") or "图文"
        # 封面点击率统一存百分比（如 24.3）；源表可能是 0.243 或 "24.3%"
        ctr = note.get("ctr", 0)
        note["ctr"] = round(ctr * 100, 2) if ctr and ctr < 1 else round(ctr, 2)
        for f in ("exposure", "reads", "likes", "comments", "collects",
                  "followers_gained", "shares", "avg_watch_seconds", "danmaku"):
            note[f] = to_int(note.get(f, 0))
        note["reads"] = note.get("reads", 0)
        engagement = (note["likes"] + note["collects"] + note["comments"]) / note["reads"] if note["reads"] else 0.0
        note["engagement"] = round(engagement, 4)
        note["follower_rate"] = round(note["followers_gained"] / note["reads"], 6) if note["reads"] else 0.0
        note["hit"] = bool(note["reads"] >= 5000 or note["likes"] >= 200)
        note["note_id"] = make_note_id(note["title"], note["first_published_at"])
        note["matched_job"] = None
        notes.append(note)
    return notes


def normalize_title(s):
    return re.sub(r"[\s\W_]+", "", str(s or "").lower())


def shingle_set(s, n=4):
    """含中文字符的 n-gram 集合，用于中文标题模糊匹配（如 Ds今天涨价 ↔ DeepSeek 今天涨价）。
    纯 ASCII 片段（如 token/DeepSeek）不参与，避免“烧 token ↔ 有效 token”误匹配。"""
    s = normalize_title(s)
    grams = set()
    for i in range(len(s) - n + 1):
        g = s[i:i + n]
        if re.search(r"[\u4e00-\u9fff]", g):
            grams.add(g)
    return grams


def make_note_id(title, first_published_at):
    return f"{normalize_title(title)}|{first_published_at or ''}"


def load_json(path):
    try:
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return None


def save_json(path, data):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)


def load_store(path):
    data = load_json(path) or {}
    data.setdefault("last_import_at", "")
    data.setdefault("notes", {})
    return data


def load_account(path):
    return load_json(path) or {}


def iter_job_candidates(jobs_dir):
    """返回 [(job_id, [标题候选...])]：优先 publish_log.title，其次 state.theme。"""
    for sf in sorted(glob.glob(os.path.join(jobs_dir, "*", "state.json"))):
        job_id = os.path.basename(os.path.dirname(sf))
        state = load_json(sf) or {}
        lg = load_json(os.path.join(jobs_dir, job_id, "publish_log.json")) or {}
        cands = [lg.get("title", ""), state.get("theme", ""), state.get("job_id", "")]
        cands = [c for c in cands if c]
        if cands:
            yield job_id, cands


def match_job(title, jobs_dir):
    t_norm = normalize_title(title)
    if not t_norm:
        return None
    t_shingles = shingle_set(title)
    for job_id, cands in iter_job_candidates(jobs_dir):
        for cand in cands:
            c_norm = normalize_title(cand)
            if not c_norm:
                continue
            if t_norm == c_norm:
                return job_id
    # 子串匹配（短标题如无标点差异）
    for job_id, cands in iter_job_candidates(jobs_dir):
        for cand in cands:
            c_norm = normalize_title(cand)
            if not c_norm:
                continue
            if len(t_norm) >= 4 and t_norm in c_norm:
                return job_id
            if len(c_norm) >= 4 and c_norm in t_norm:
                return job_id
    # 兜底：4-gram 重叠 ≥2 个（同一主题但措辞不同的 Job）
    for job_id, cands in iter_job_candidates(jobs_dir):
        for cand in cands:
            overlap = len(t_shingles & shingle_set(cand))
            if overlap >= 2:
                return job_id
    return None


def build_record(note):
    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    return {
        "platform": "小红书",
        "source": "xhs_export",
        "note_id": note["note_id"],
        "first_published_at": note["first_published_at"],
        "collected_at": now,
        "reads": note["reads"],
        "likes": note["likes"],
        "collects": note["collects"],
        "comments": note["comments"],
        "exposure": note["exposure"],
        "ctr": note["ctr"],
        "followers_gained": note["followers_gained"],
        "shares": note["shares"],
        "avg_watch_seconds": note["avg_watch_seconds"],
        "format": note["format"],
        "danmaku": note["danmaku"],
        "url": "",
        "engagement": note["engagement"],
        "follower_rate": note["follower_rate"],
        "hit": note["hit"],
    }


def upsert_log_record(log_path, note):
    log = load_json(log_path) or {"job_id": os.path.basename(os.path.dirname(log_path)), "records": [], "publish": []}
    log.setdefault("records", [])
    log.setdefault("publish", [])
    log.setdefault("platforms", [])
    if note["title"] and not log.get("title"):
        log["title"] = note["title"]
    if "小红书" not in log["platforms"]:
        log["platforms"].append("小红书")
        log["platforms"] = sorted(log["platforms"])
    rec = build_record(note)
    for i, r in enumerate(log["records"]):
        if r.get("note_id") == note["note_id"] or (
            r.get("source") == "xhs_export"
            and r.get("first_published_at") == note["first_published_at"]
        ):
            log["records"][i] = rec
            save_json(log_path, log)
            return False  # updated
    log["records"].append(rec)
    save_json(log_path, log)
    return True  # new


def main():
    ap = argparse.ArgumentParser(description="小红书笔记导出明细表导入器")
    ap.add_argument("--file", required=True, help="小红书导出的 笔记列表明细表.xlsx 路径")
    ap.add_argument("--jobs-dir", default=DEFAULT_JOBS_DIR, help="jobs 根目录（默认仓库 jobs/）")
    ap.add_argument("--data-dir", default=DEFAULT_DATA_DIR, help="data/stats 目录（默认仓库 data/stats）")
    ap.add_argument("--account-followers", type=int, default=None, help="当前粉丝数（导出表不含，可选）")
    ap.add_argument("--account-following", type=int, default=None, help="当前关注数（可选）")
    ap.add_argument("--account-likes-collects", type=int, default=None, help="获赞与收藏（可选）")
    ap.add_argument("--account-profile-visits", type=int, default=None, help="主页访客数（可选）")
    ap.add_argument("--account-period", default="", help="账号快照统计周期，如 08-01 至 08-07")
    ap.add_argument("--json", action="store_true", help="只输出 JSON 汇总（供 webapp 使用）")
    args = ap.parse_args()

    if not os.path.exists(args.file):
        print(f"❌ 文件不存在：{args.file}", file=sys.stderr)
        sys.exit(1)

    rows = read_xlsx_rows(args.file)
    notes = parse_rows(rows)
    if not notes:
        print("❌ 明细表为空或表头无法识别", file=sys.stderr)
        sys.exit(1)

    store_path = os.path.join(args.data_dir, "xhs_notes.json")
    account_path = os.path.join(args.data_dir, "xhs_account.json")
    store = load_store(store_path)
    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    new_notes, updated_notes, matched_jobs, unmatched = 0, 0, 0, 0
    for note in notes:
        job_id = match_job(note["title"], args.jobs_dir)
        note["matched_job"] = job_id
        old = store["notes"].get(note["note_id"])
        note["imported_at"] = old.get("imported_at", now) if old else now
        note["updated_at"] = now
        store["notes"][note["note_id"]] = note
        if old is None:
            new_notes += 1
        else:
            updated_notes += 1
        if job_id:
            matched_jobs += 1
            upsert_log_record(os.path.join(args.jobs_dir, job_id, "publish_log.json"), note)
        else:
            unmatched += 1

    store["last_import_at"] = now
    store["import_stats"] = {
        "imported_at": now,
        "total_rows": len(notes),
        "new_notes": new_notes,
        "updated_notes": updated_notes,
        "matched_jobs": matched_jobs,
        "unmatched": unmatched,
    }
    save_json(store_path, store)

    if any(v is not None for v in (
        args.account_followers, args.account_following,
        args.account_likes_collects, args.account_profile_visits,
    )):
        account = load_account(account_path)
        if args.account_followers is not None:
            account["followers"] = args.account_followers
        if args.account_following is not None:
            account["following"] = args.account_following
        if args.account_likes_collects is not None:
            account["likes_collects"] = args.account_likes_collects
        if args.account_profile_visits is not None:
            account["profile_visits"] = args.account_profile_visits
        if args.account_period:
            account["period"] = args.account_period
        account["updated_at"] = now
        save_json(account_path, account)

    total_followers = sum(n["followers_gained"] for n in store["notes"].values())
    total_reads = sum(n["reads"] for n in store["notes"].values())
    hits = sum(1 for n in store["notes"].values() if n["hit"])
    summary = {
        "ok": True,
        "imported_at": now,
        "total_rows": len(notes),
        "new_notes": new_notes,
        "updated_notes": updated_notes,
        "matched_jobs": matched_jobs,
        "unmatched": unmatched,
        "notes_total": len(store["notes"]),
        "followers_gained_total": total_followers,
        "reads_total": total_reads,
        "hits": hits,
        "account_path": account_path if os.path.exists(account_path) else None,
        "notes_path": store_path,
    }

    if args.json:
        print(json.dumps(summary, ensure_ascii=False, indent=2))
        return

    print(f"✅ 已导入 {len(notes)} 条笔记（新增 {new_notes} / 更新 {updated_notes}）")
    print(f"📊 匹配 Job：{matched_jobs} 条（已写入 publish_log.json）｜ 未匹配：{unmatched} 条")
    print(f"🔥 爆款：{hits} 条 ｜ 累计导入涨粉：{total_followers} ｜ 累计观看：{total_reads}")
    print(f"💾 笔记库：{store_path}")
    if os.path.exists(account_path):
        print(f"👤 账号快照：{account_path}")


if __name__ == "__main__":
    main()
