#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
评分报告生成器（P0：每个 Job 必须落盘 评分报告.md）
=====================================================
从 validate_report.json + harsh_report.json 渲染机器初筛版 评分报告.md，
并在报告中强制声明人工复核清单（Hook 六维 / 事实来源 / 视觉排版）。

用法：
    python3 scripts/generate_score_report.py outputs/YYYY-MM-DD_主题名/

退出码：0 = 报告已落盘（无论机器 PASS/REJECTED）；1 = 缺少输入报告。
"""
import argparse
import json
import os
from datetime import datetime


def read_json(path):
    try:
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return None


def icon(level):
    return {"PASS": "✅", "WARN": "⚠️", "FAIL": "❌"}.get(level, "•")  # nosec B105  # 状态图标非密码


def main():
    ap = argparse.ArgumentParser(description="从机器质检报告生成 评分报告.md")
    ap.add_argument("output_dir", help="产出目录 outputs/YYYY-MM-DD_主题名/")
    args = ap.parse_args()

    out_dir = os.path.normpath(args.output_dir)
    vp = os.path.join(out_dir, "validate_report.json")
    hp = os.path.join(out_dir, "harsh_report.json")
    ap = os.path.join(out_dir, "ai_flavor_report.json")
    vr, hr, ar = read_json(vp), read_json(hp), read_json(ap)
    if vr is None or hr is None:
        print("❌ 缺少 validate_report.json 或 harsh_report.json，先运行质检链（run_daily_pipeline.py --qa）。")
        return 1

    job = os.path.basename(out_dir)
    lines = [
        f"# 🛑 Harsh Critic 评分报告：{job}（机器初筛版）",
        "",
        f"> 生成时间：{datetime.now().strftime('%Y-%m-%d %H:%M:%S')} ｜ 生成器：scripts/generate_score_report.py",
        "> ⚠️ 本报告仅为机器初筛汇总。**必须由资深校对排版人工复核后定稿**：",
        "> 在下方『人工复核结论』逐条写出证据，确认后才可视为正式 评分报告.md。",
        "",
        "## 一、机器校验汇总",
        "",
        f"- 素材契约：`{vr.get('verdict', '?')}`（FAIL {vr.get('fails', '?')} / WARN {vr.get('warns', '?')}）",
        f"- Harsh 机器分：{hr.get('score', '?')}/100 → `{hr.get('verdict', '?')}`（阈值 85）",
        f"- 去 AI 味：`{ar.get('verdict', '未运行') if ar else '未运行'}`（high {ar.get('summary', {}).get('high', 0) if ar else 0} / medium {ar.get('summary', {}).get('medium', 0) if ar else 0}）",
        f"- 素材包：`{hr.get('materials') or vr.get('materials') or '未定位'}`",
        f"- 机器复核要求：{hr.get('manual_review', '见 harsh_report.json')}",
        "",
        "## 二、素材契约明细（validate_report.json）",
        "",
    ]
    for r in vr.get("results", []):
        lines.append(f"- {icon(r['level'])} [{r['code']}] {r['message']}")

    lines += ["", "## 三、Harsh 机器评分明细（harsh_report.json）", ""]
    for r in hr.get("results", []):
        lines.append(f"- {icon(r['level'])} [{r['code']}] {r['message']}")

    lines += ["", "## 四、去 AI 味明细（ai_flavor_report.json）", ""]
    if ar:
        if ar.get("hits"):
            for h in ar["hits"]:
                sev = "🛑" if h["severity"] == "high" else "⚠️"
                lines.append(f"- {sev} [{h['rule']}]（{h.get('source', '')}）×{h['count']} "
                             f"平台：{'、'.join(h.get('platforms', []))}")
                for ex in h.get("examples", [])[:2]:
                    lines.append(f"  - 例：{ex}")
        else:
            lines.append("- 未命中结构级 AI 腔规则。")
        for note in ar.get("manual_review", []):
            lines.append(f"- 人工复核：{note}")
    else:
        lines.append("- ⚠️ 未运行（旧产物可直接补跑 scripts/ai_flavor_check.py）。")

    pos = hr.get("pos") or {}
    lines += [
        "",
        f"- 正向质量分：{hr.get('pos_total', '?')}/60（素材引用率 {pos.get('素材引用率', '?')} / "
        f"数据密度 {pos.get('数据密度', '?')} / 真实感 {pos.get('真实感', '?')} / "
        f"Hook 冲击力 {pos.get('Hook冲击力', '?')}）",
        f"- 负向扣分：-{hr.get('neg_deducted', '?')}/40",
        "",
        "## 五、人工复核清单（定稿前必须逐条完成）",
        "",
        "- [ ] **Hook 六维**：独立性 / Hook 抓手 / 悬念 / 可信度 / 口播友好 / 开头承诺与正文匹配——逐平台写证据",
        "- [ ] **事实来源**：素材包每条『真实数据』链接可打开，数字与来源一致；无虚构案例",
        "- [ ] **视觉排版**：小红书卡片 1080×1440 无溢出；公众号移动端无孤行/断行；无过程临时文件",
        "- [ ] **平台规格**：小红书 ≥5 标签 + 互动引导；公众号参考来源带链接、无整段重复",
        "- [ ] **去 AI 味**：展示型三拍 / 均匀段落形状 / 引号破折号例外（真实引语、技术标识）逐条确认",
        "",
        "## 六、人工复核结论",
        "",
        "- [ ] 小红书：",
        "- [ ] 公众号：",
        "- [ ] 短视频：",
        "- 终审分数（人工）：__/100 → PASSED / REJECTED",
        "",
    ]
    out_path = os.path.join(out_dir, "评分报告.md")
    with open(out_path, "w", encoding="utf-8") as f:
        f.write("\n".join(lines))
    print(f"📄 机器初筛版 评分报告.md 已落盘：{out_path}")
    print("⚠️ 提醒：需人工复核后定稿；REJECTED 时按第 3 节明细退回对应主编。")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
