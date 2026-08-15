# -*- coding: utf-8 -*-
"""小红书导出明细表导入器单测：xlsx 解析、幂等去重、Job 匹配、账号快照。"""
import html
import json
import os
import subprocess
import sys
import zipfile

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
SCRIPT = os.path.join(ROOT, "scripts", "import_xhs_notes.py")

HEADERS = [
    "笔记标题", "首次发布时间", "体裁", "曝光", "观看量", "封面点击率",
    "点赞", "评论", "收藏", "涨粉", "分享", "人均观看时长", "弹幕",
]


def _col_ref(i):
    s = ""
    i += 1
    while i:
        i, rem = divmod(i - 1, 26)
        s = chr(ord("A") + rem) + s
    return s


def _write_xlsx(path, rows):
    """纯标准库构造最小可用 xlsx（sharedStrings + sheet1）。"""
    shared = []
    for row in rows:
        for v in row:
            v = str(v)
            if v not in shared:
                shared.append(v)

    def esc(v):
        return html.escape(str(v), quote=True)

    ss_xml = (
        '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
        '<sst xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main" '
        f'count="{len(shared)}" uniqueCount="{len(shared)}">'
        + "".join(f"<si><t>{esc(v)}</t></si>" for v in shared)
        + "</sst>"
    )
    row_xml = []
    for ri, row in enumerate(rows, start=1):
        cells = []
        for ci, v in enumerate(row):
            cells.append(
                f'<c r="{_col_ref(ci)}{ri}" t="s"><v>{shared.index(str(v))}</v></c>'
            )
        row_xml.append(f'<row r="{ri}">{"".join(cells)}</row>')
    sheet_xml = (
        '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
        '<worksheet xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main">'
        f"<sheetData>{''.join(row_xml)}</sheetData></worksheet>"
    )
    with zipfile.ZipFile(path, "w", zipfile.ZIP_DEFLATED) as zf:
        zf.writestr("xl/sharedStrings.xml", ss_xml)
        zf.writestr("xl/worksheets/sheet1.xml", sheet_xml)


def _write_job(jobs_dir, job_id, theme, title, records=None):
    jdir = os.path.join(str(jobs_dir), job_id)
    os.makedirs(jdir, exist_ok=True)
    with open(os.path.join(jdir, "state.json"), "w", encoding="utf-8") as f:
        json.dump({"job_id": job_id, "theme": theme, "state": "archive"}, f,
                  ensure_ascii=False, indent=2)
    with open(os.path.join(jdir, "publish_log.json"), "w", encoding="utf-8") as f:
        json.dump({
            "job_id": job_id, "title": title, "records": records or [], "publish": [],
        }, f, ensure_ascii=False, indent=2)


def _run(tmp_path, jobs_dir, data_dir, extra=()):
    xlsx = tmp_path / "notes.xlsx"
    _write_xlsx(str(xlsx), [
        HEADERS,
        ["DeepSeek 今天涨价了", "2026年08月07日01时34分24秒", "图文", "23522",
         "7223", "0.243", "19", "29", "14", "1", "1", "33", "0"],
        ["复旦96个实验，老师傅经验被AI打包", "2026年08月08日22时37分27秒", "图文",
         "100", "18", "0.1", "1", "0", "2", "0", "0", "0", "0"],
        ["独篇热点", "2026年08月05日09时00分00秒", "视频", "100", "50", "0.2",
         "3", "4", "5", "2", "1", "20", "0"],
    ])
    r = subprocess.run(
        [sys.executable, SCRIPT, "--file", str(xlsx),
         "--jobs-dir", str(jobs_dir), "--data-dir", str(data_dir), "--json", *extra],
        capture_output=True, text=True,
    )
    assert r.returncode == 0, r.stderr or r.stdout
    return json.loads(r.stdout)


def test_import_matches_jobs_and_is_idempotent(tmp_path):
    jobs = tmp_path / "jobs"
    data = tmp_path / "data" / "stats"
    _write_job(jobs, "2026-08-06_有效token与模型调度",
               theme="DeepSeek 涨价", title="DeepSeek 今天涨价了")
    _write_job(jobs, "2026-08-08_Skill革命",
               theme="Skill 革命",
               title="16 分钟做完 96 个实验：AI 的下一个风口，是把老师傅的经验打包成 Skill")

    summary = _run(tmp_path, jobs, data)
    assert summary["total_rows"] == 3
    assert summary["new_notes"] == 3
    assert summary["matched_jobs"] == 2
    assert summary["unmatched"] == 1
    assert summary["followers_gained_total"] == 3
    assert summary["hits"] == 1  # 7223 观看

    notes = json.load(open(os.path.join(data, "xhs_notes.json"), encoding="utf-8"))
    assert len(notes["notes"]) == 3
    ds = next(n for n in notes["notes"].values() if n["followers_gained"] == 1)
    assert ds["ctr"] == 24.3
    assert ds["format"] == "图文"
    assert ds["matched_job"] == "2026-08-06_有效token与模型调度"

    log = json.load(open(
        os.path.join(jobs, "2026-08-06_有效token与模型调度", "publish_log.json"),
        encoding="utf-8",
    ))
    assert len(log["records"]) == 1
    rec = log["records"][0]
    assert rec["source"] == "xhs_export"
    assert rec["note_id"] == ds["note_id"]
    assert rec["exposure"] == 23522
    assert rec["ctr"] == 24.3
    assert rec["followers_gained"] == 1
    assert rec["hit"] is True

    # 重复导入：不新增记录，只更新笔记库
    summary2 = _run(tmp_path, jobs, data)
    assert summary2["new_notes"] == 0
    assert summary2["updated_notes"] == 3
    log2 = json.load(open(
        os.path.join(jobs, "2026-08-06_有效token与模型调度", "publish_log.json"),
        encoding="utf-8",
    ))
    assert len(log2["records"]) == 1


def test_account_snapshot_args(tmp_path):
    jobs = tmp_path / "jobs"
    data = tmp_path / "data" / "stats"
    _run(tmp_path, jobs, data, extra=[
        "--account-followers", "45",
        "--account-following", "41",
        "--account-likes-collects", "387",
        "--account-profile-visits", "89",
        "--account-period", "08-01 至 08-07",
    ])
    acc = json.load(open(os.path.join(data, "xhs_account.json"), encoding="utf-8"))
    assert acc["followers"] == 45
    assert acc["following"] == 41
    assert acc["likes_collects"] == 387
    assert acc["profile_visits"] == 89
    assert acc["period"] == "08-01 至 08-07"


def test_import_rejects_unrecognized_header(tmp_path):
    xlsx = tmp_path / "bad.xlsx"
    _write_xlsx(str(xlsx), [["A", "B", "C"], ["1", "2", "3"]])
    r = subprocess.run(
        [sys.executable, SCRIPT, "--file", str(xlsx),
         "--jobs-dir", str(tmp_path / "jobs"), "--data-dir", str(tmp_path / "data")],
        capture_output=True, text=True,
    )
    assert r.returncode == 1
    assert "无法识别小红书导出表头" in r.stderr
