#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
小红书创作服务「数据看板」导出 xlsx 导入器
==========================================
支持四个页签的导出文件（近 7 日 / 近 30 日）：
  - 发布数据（账号总体发布数据 / 总发布趋势 / 发布视频趋势 / 发布图文趋势）
  - 观看数据（曝光数/观看数/封面点击率/观看总时长/完播率 + 观看来源 + 观看时段）
  - 互动数据（点赞/评论/收藏/分享 + 趋势）
  - 涨粉数据（净涨粉/新增关注/取消关注/主页访客 + 趋势）

解析器按表头/页签名自动识别页签类型；识别不了可传 --kind 手工指定。
未知列不报错，全部写进识别报告，便于后续校准。

用法：
    python3 scripts/import_dashboard_xlsx.py --file 近30日发布数据.xlsx
    python3 scripts/import_dashboard_xlsx.py --file 观看数据.xlsx --kind watch
    python3 scripts/import_dashboard_xlsx.py --file x.xlsx --json   # 只打印摘要

输出：
    data/stats/dashboard/<kind>.json        按页签分类的结构化数据
    data/stats/dashboard/import_report.json 识别报告（含未识别列/表）
"""
import argparse
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
DEFAULT_DASHBOARD_DIR = os.path.join(ROOT, "data", "stats", "dashboard")

NS = {"m": "http://schemas.openxmlformats.org/spreadsheetml/2006/main"}
CELL_T = "{http://schemas.openxmlformats.org/spreadsheetml/2006/main}t"

# 页签识别关键词（按优先级）
KIND_KEYWORDS = [
    ("publish", ("发布",)),
    ("watch", ("观看",)),
    ("interact", ("互动",)),
    ("follower", ("涨粉",)),
]

# 账号总览指标里不需要进 account 的列名（环比类保留，仅跳过“指标/数值”本身）
ACCOUNT_EXCLUDE = {"指标", "数值", "日期"}

CHINESE_DATE_RE = re.compile(r"^(\d{4})年(\d{1,2})月(\d{1,2})日")


def _col_to_idx(ref):
    m = re.match(r"([A-Z]+)", ref or "")
    if not m:
        return None
    idx = 0
    for ch in m.group(1):
        idx = idx * 26 + (ord(ch) - ord("A") + 1)
    return idx - 1


def _sheet_names(path):
    """返回 [(name, sheet_file)]，纯标准库解析 workbook.xml。"""
    out = []
    with safe_xlsx_zip(path) as zf:
        names = zf.namelist()
        if "xl/workbook.xml" not in names:
            # 单表简版：直接按数字序号回退
            for i in range(1, 20):
                f = f"xl/worksheets/sheet{i}.xml"
                if f in names:
                    out.append((f"Sheet{i}", f))
            return out
        root = ET.fromstring(zf.read("xl/workbook.xml"))  # nosec B314  # 见 B405 说明
        rels = {}
        rel_path = "xl/_rels/workbook.xml.rels"
        if rel_path in names:
            rroot = ET.fromstring(zf.read(rel_path))  # nosec B314  # 见 B405 说明
            nsr = {"r": "http://schemas.openxmlformats.org/package/2006/relationships"}
            for rel in rroot.findall("r:Relationship", nsr):
                rels[rel.get("Id")] = rel.get("Target", "")
        for sh in root.iter("{http://schemas.openxmlformats.org/spreadsheetml/2006/main}sheet"):
            name = sh.get("name", "")
            rid = sh.get("{http://schemas.openxmlformats.org/officeDocument/2006/relationships}id")
            target = rels.get(rid or "", "")
            target = re.sub(r"^/", "", target)
            if target and "worksheets" in target:
                out.append((name, "xl/" + target if not target.startswith("xl/") else target))
            elif target:
                out.append((name, target))
    return out


def _read_sheet(path, sheet_file):
    rows = []
    with safe_xlsx_zip(path) as zf:
        names = zf.namelist()
        shared = []
        if "xl/sharedStrings.xml" in names:
            root = ET.fromstring(zf.read("xl/sharedStrings.xml"))  # nosec B314  # 见 B405 说明
            for si in root.findall("m:si", NS):
                shared.append("".join(t.text or "" for t in si.iter(CELL_T)))
        root = ET.fromstring(zf.read(sheet_file))  # nosec B314  # 见 B405 说明
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
            rows.append([cells.get(i) for i in range(max(cells) + 1)])
    return rows


def _to_num(val):
    if val is None or val == "":
        return None
    if isinstance(val, (int, float)):
        return float(val)
    s = str(val).replace(",", "").strip()
    if s.endswith("%"):
        s = s[:-1]
    try:
        return float(s)
    except ValueError:
        return None


def _iso_date(val):
    m = CHINESE_DATE_RE.match(str(val or ""))
    if m:
        y, mo, d = m.groups()
        return f"{int(y):04d}-{int(mo):02d}-{int(d):02d}"
    s = str(val or "").strip()
    m2 = re.match(r"^(\d{4})[-/](\d{1,2})[-/](\d{1,2})", s)
    if m2:
        y, mo, d = m2.groups()
        return f"{int(y):04d}-{int(mo):02d}-{int(d):02d}"
    return s


def detect_kind(sheet_names, forced=None):
    if forced:
        return forced
    joined = "|".join(sheet_names)
    for kind, kws in KIND_KEYWORDS:
        if any(k in joined for k in kws):
            return kind
    return None


def _parse_sheet(name, rows):
    """按形状解析单个表：账户指标 / 日期趋势 / 标签数值分解 / 其他。"""
    if not rows:
        return {"type": "empty", "name": name}
    header = [str(c or "").strip() for c in rows[0]]
    # 日期趋势
    if header and ("日期" in header or header[0] == "日期"):
        series = []
        for r in rows[1:]:
            if not r or r[0] is None:
                continue
            date = _iso_date(r[0])
            val = _to_num(r[1]) if len(r) > 1 else None
            if date and val is not None:
                series.append({"date": date, "value": val})
        return {"type": "series", "name": name, "series": series}
    # 账户总览：首行含“指标/数值”或只有 2 列且首列是文本指标
    if "指标" in header or ("数值" in header and len(header) == 2):
        account = {}
        for r in rows[1:]:
            if not r or r[0] is None:
                continue
            key = str(r[0]).strip()
            if key in ACCOUNT_EXCLUDE:
                continue
            val = _to_num(r[1]) if len(r) > 1 else None
            account[key] = val if val is not None else str(r[1] or "").strip()
        return {"type": "account", "name": name, "account": account}
    # 标签/数值分解（观看来源、观看时段等）
    if len(header) >= 2:
        breakdown = []
        numeric = 0
        for r in rows[1:]:
            if not r or r[0] is None or len(r) < 2:
                continue
            v = _to_num(r[1])
            if v is not None:
                numeric += 1
            breakdown.append({"label": str(r[0]).strip(), "value": v if v is not None else str(r[1]).strip()})
        if numeric >= max(1, len(breakdown) * 0.5):
            return {"type": "breakdown", "name": name, "breakdown": breakdown}
    return {"type": "other", "name": name, "rows": rows[:5]}


def parse_file(path, forced_kind=None):
    sheets = _sheet_names(path)
    kind = detect_kind([n for n, _ in sheets], forced_kind)
    parsed = []
    for name, file in sheets:
        try:
            rows = _read_sheet(path, file)
            parsed.append(_parse_sheet(name, rows))
        except Exception as e:
            parsed.append({"type": "error", "name": name, "error": str(e)})

    account = {}
    series = {}
    breakdown = {}
    other_sheets = []
    for p in parsed:
        if p["type"] == "account":
            account.update(p["account"])
        elif p["type"] == "series":
            series[p["name"]] = p["series"]
        elif p["type"] == "breakdown":
            breakdown[p["name"]] = p["breakdown"]
        elif p["type"] == "other":
            other_sheets.append({"name": p["name"], "sample": p.get("rows", [])})
        elif p["type"] == "error":
            other_sheets.append({"name": p["name"], "error": p["error"]})

    return {
        "kind": kind,
        "detected": kind is not None,
        "account": account,
        "series": series,
        "breakdown": breakdown,
        "other_sheets": other_sheets,
        "sheet_count": len(sheets),
    }


def save_dashboard(data_dir, payload):
    os.makedirs(data_dir, exist_ok=True)
    kind = payload["kind"]
    out = {
        "kind": kind,
        "imported_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "account": payload["account"],
        "series": payload["series"],
        "breakdown": payload["breakdown"],
        "other_sheets": payload["other_sheets"],
    }
    path = os.path.join(data_dir, f"{kind}.json")
    tmp = path + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(out, f, ensure_ascii=False, indent=2)
    os.replace(tmp, path)
    return path


def append_report(data_dir, entry):
    os.makedirs(data_dir, exist_ok=True)
    report_path = os.path.join(data_dir, "import_report.json")
    report = []
    if os.path.exists(report_path):
        try:
            with open(report_path, "r", encoding="utf-8") as f:
                report = json.load(f)
        except Exception:
            report = []
    report.append(entry)
    with open(report_path, "w", encoding="utf-8") as f:
        json.dump(report[-20:], f, ensure_ascii=False, indent=2)
    return report_path


def main():
    ap = argparse.ArgumentParser(description="小红书数据看板导出 xlsx 导入器")
    ap.add_argument("--file", required=True, help="导出的 xlsx 路径")
    ap.add_argument("--kind", default="", choices=("", "publish", "watch", "interact", "follower"),
                    help="页签类型（自动识别失败时手工指定）")
    ap.add_argument("--data-dir", default=DEFAULT_DASHBOARD_DIR, help="输出目录")
    ap.add_argument("--json", action="store_true", help="只打印 JSON 摘要")
    args = ap.parse_args()

    payload = parse_file(args.file, forced_kind=args.kind or None)
    if not payload["kind"]:
        print(f"❌ 无法识别页签类型（表名：{', '.join(n for n, _ in _sheet_names(args.file))}），"
              f"请用 --kind publish|watch|interact|follower 指定", file=sys.stderr)
        sys.exit(1)

    path = save_dashboard(args.data_dir, payload)
    entry = {
        "file": os.path.basename(args.file),
        "kind": payload["kind"],
        "imported_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "sheet_count": payload["sheet_count"],
        "account_keys": list(payload["account"].keys()),
        "series_sheets": list(payload["series"].keys()),
        "breakdown_sheets": list(payload["breakdown"].keys()),
        "other_sheets": payload["other_sheets"],
    }
    append_report(args.data_dir, entry)

    summary = {
        "ok": True,
        "kind": payload["kind"],
        "detected": payload["detected"],
        "path": path,
        "account_keys": list(payload["account"].keys()),
        "series": {k: len(v) for k, v in payload["series"].items()},
        "breakdown": {k: len(v) for k, v in payload["breakdown"].items()},
        "other_sheets": payload["other_sheets"],
    }
    if args.json:
        print(json.dumps(summary, ensure_ascii=False))
    else:
        print(f"✅ 已导入「{payload['kind']}」看板数据：{path}")
        print(f"   指标 {len(summary['account_keys'])} 个：{'、'.join(summary['account_keys'][:12])}")
        print(f"   趋势表 {len(summary['series'])} 个：{summary['series']}")
        if summary["breakdown"]:
            print(f"   分解表 {len(summary['breakdown'])} 个：{summary['breakdown']}")
        if summary["other_sheets"]:
            print(f"   ⚠️ 未识别表 {len(summary['other_sheets'])} 个："
                  f"{[s['name'] for s in summary['other_sheets']]}（已写入识别报告）")


if __name__ == "__main__":
    main()
