import sys
import os
import re
import json

"""
AI学长小林三层架构 Layer 3: 确定性 Guardrails & Schema 校验脚本
用法: python3 scripts/schema_validator.py <target_markdown_or_html_file>
"""

BLACK_LIST_PATTERNS = [
    r"别再拿.*当玩具了",
    r"听我一句劝",
    r"教你.*个刀法",
    r"凡是.*都是割韭菜",
    r"月入.*万",
    r"在当今.*飞速发展的时代",
    r"不可否认的是",
    r"总结来说"
]

def validate_content_file(filepath):
    abs_path = os.path.abspath(filepath)
    if not os.path.exists(abs_path):
        print(f"❌ 错误: 目标校验文件不存在: {abs_path}")
        return False

    with open(abs_path, 'r', encoding='utf-8') as f:
        content = f.read()

    print(f"🔍 [小林三层架构 Layer 3] 开始校验文件硬规则: {os.path.basename(filepath)}")
    errors = []

    # 1. 检测油腻营销号黑词
    for pattern in BLACK_LIST_PATTERNS:
        matches = re.findall(pattern, content)
        if matches:
            errors.append(f"命中违禁油腻/AI腔词汇 [{pattern}]: 找到 {len(matches)} 处 (如: '{matches[0]}')")

    # 2. 结构完整性校验 (若是文案 md，校验是否有 Hook、正文、标签)
    if filepath.endswith('.md'):
        if len(content.strip()) < 100:
            errors.append("内容过短 (少于 100 字符)，疑似未完成生成")
        if '#' not in content:
            errors.append("缺失 Markdown Heading 结构")

    if errors:
        print("❌ [校验失败 REJECTED] 发现以下阻断问题:")
        for err in errors:
            print(f"   • {err}")
        return False

    print("✅ [校验通过 PASSED] 完美符合硬性 Schema 与去油去爹味规范！")
    return True

if __name__ == '__main__':
    if len(sys.argv) < 2:
        print("用法: python3 scripts/schema_validator.py <file_path>")
        sys.exit(1)

    target_file = sys.argv[1]
    success = validate_content_file(target_file)
    sys.exit(0 if success else 1)
