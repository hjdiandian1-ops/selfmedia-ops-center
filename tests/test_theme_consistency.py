# -*- coding: utf-8 -*-
"""主题一致性测试：palettes.json ↔ style.css ↔ 设置入口。"""
import json
import os
import re
import subprocess
import sys

ROOT = os.path.normpath(os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))
PALETTES = os.path.join(ROOT, "skills", "theme-design-skill", "references", "palettes.json")
STYLE = os.path.join(ROOT, "webapp", "static", "style.css")
INDEX = os.path.join(ROOT, "webapp", "static", "index.html")
APPJS = os.path.join(ROOT, "webapp", "static", "app.js")


def _read(path):
    with open(path, "r", encoding="utf-8") as f:
        return f.read()


def _block(css, theme_id):
    if theme_id == "default":
        m = re.search(r":root \{(.*?)\n\}", css, re.S)
        return m.group(1) if m else ""
    m = re.search(r':root\[data-theme="' + theme_id + r'"\] \{(.*?)\n\}', css, re.S)
    return m.group(1) if m else ""


def test_every_theme_has_css_block_and_tokens():
    data = json.loads(_read(PALETTES))
    css = _read(STYLE)
    default_block = _block(css, "default")
    for theme in data["themes"]:
        if not theme.get("implemented", False):
            continue  # 第二批主题仅存在于色板，尚未实现
        block = _block(css, theme["id"])
        assert block, f"style.css 缺少 [data-theme={theme['id']}] 块"
        missing = [k for k in theme["tokens"] if f"--{k}" not in block and f"--{k}" not in default_block]
        assert not missing, f"主题 {theme['id']} 缺少 token: {missing}"


def test_theme_contrast_all_pass():
    script = os.path.join(ROOT, "skills", "theme-design-skill", "scripts", "theme_contrast_check.py")
    r = subprocess.run([sys.executable, script, "--all"], capture_output=True, text=True)
    assert r.returncode == 0, r.stdout + r.stderr


def test_theme_switcher_present():
    html = _read(INDEX)
    js = _read(APPJS)
    assert 'id="set-theme"' in html
    assert 'localStorage.setItem("selfmedia_theme"' in js
    assert "function applyTheme" in js
    for theme_id in ("default", "brand-red", "midnight", "pink", "doraemon", "cyberpunk", "hermes"):
        assert f'value="{theme_id}"' in html
