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
    for theme_id in ("default", "midnight", "doraemon", "fuji", "cyberpunk", "hermes", "chanel", "lv"):
        assert f'value="{theme_id}"' in html


def test_implemented_themes_have_palette_and_scheme():
    data = json.loads(_read(PALETTES))
    for theme in data["themes"]:
        if not theme.get("implemented", False):
            continue
        assert theme.get("scheme"), f"主题 {theme['id']} 缺少配色方案 scheme"
        for k in ("palette-1", "palette-2", "palette-3", "palette-4"):
            assert k in theme["tokens"], f"主题 {theme['id']} 缺少 {k}"


def test_style_presets_present():
    css = _read(STYLE)
    html = _read(INDEX)
    js = _read(APPJS)
    # google-rounded 是默认档（不覆盖主题自带质感），只需出现在设置项
    for preset in ("sharp-flat", "paper-layered", "neon-glow"):
        assert f'[data-style="{preset}"]' in css
    assert 'value="google-rounded"' in html
    assert 'id="set-style"' in html
    assert "selfmedia_style" in js and "dataset.style" in js
    assert 'localStorage.getItem("selfmedia_style")' in html
    assert "document.documentElement.dataset.style = s" in html
    assert 'class="style-preview"' in html and 'class="sp-sample"' in html


def test_glass_config_present():
    """透明毛玻璃无极调档：滑块、跟随开关、内联变量覆盖齐全。"""
    css = _read(STYLE)
    html = _read(INDEX)
    js = _read(APPJS)
    assert 'id="set-glass"' in html
    assert 'type="range" id="set-glass"' in html
    assert 'id="set-glass-follow"' in html
    assert "selfmedia_glass" in js
    assert 'setProperty("--style-glass-alpha"' in js
    assert 'localStorage.getItem("selfmedia_glass")' in html
    assert 'setProperty("--style-glass-alpha"' in html
    assert 'input[type="range"].range' in css


def test_lv_theme_decor_assets_and_tokens():
    """LV 奢华风的 4 个 SVG 素材存在，且 palettes.json 与 style.css 同步。"""
    css = _read(STYLE)
    data = json.loads(_read(PALETTES))
    lv = next(t for t in data["themes"] if t["id"] == "lv")
    tokens = lv["tokens"]

    assets = {
        "lv-monogram.svg": "lv-asset-monogram",
        "lv-chain.svg": "lv-asset-chain",
        "lv-lock.svg": "lv-asset-lock",
        "lv-bow.svg": "lv-asset-bow",
    }
    themes_dir = os.path.join(ROOT, "webapp", "static", "themes")
    lv_block = _block(css, "lv")
    for fname, token in assets.items():
        assert os.path.isfile(os.path.join(themes_dir, fname)), f"缺少素材 {fname}"
        assert token in tokens, f"palettes.json 缺少 {token}"
        assert f"--{token}" in lv_block, f"style.css LV 块缺少 --{token}"

    for key in ("lv-orange", "lv-orange-soft", "lv-gold-soft"):
        assert key in tokens, f"palettes.json 缺少 {key}"
        assert f"--{key}" in lv_block, f"style.css LV 块缺少 --{key}"
    assert tokens["palette-3"] == "#d9772c"
    assert "--palette-3: #d9772c" in lv_block


def test_brand_theme_decor_assets_and_tokens():
    """爱马仕/香奈儿的 5 个 SVG 素材存在，palettes.json 与 style.css 同步。"""
    css = _read(STYLE)
    data = json.loads(_read(PALETTES))
    themes_dir = os.path.join(ROOT, "webapp", "static", "themes")
    plan = {
        "hermes": {
            "assets": {
                "hermes-ribbon.svg": "hermes-asset-ribbon",
                "hermes-stitch.svg": "hermes-asset-stitch",
            },
            "extra": ("hermes-ribbon", "hermes-stitch", "hermes-ribbon-soft"),
        },
        "chanel": {
            "assets": {
                "chanel-camellia.svg": "chanel-asset-camellia",
                "chanel-pearl.svg": "chanel-asset-pearl",
                "chanel-chain.svg": "chanel-asset-chain",
            },
            "extra": ("chanel-pearl", "chanel-blush", "chanel-chain"),
        },
    }
    for theme_id, spec in plan.items():
        theme = next(t for t in data["themes"] if t["id"] == theme_id)
        tokens = theme["tokens"]
        block = _block(css, theme_id)
        for fname, token in spec["assets"].items():
            assert os.path.isfile(os.path.join(themes_dir, fname)), f"缺少素材 {fname}"
            assert token in tokens, f"palettes.json {theme_id} 缺少 {token}"
            assert f"--{token}" in block, f"style.css {theme_id} 块缺少 --{token}"
        for key in spec["extra"]:
            assert key in tokens, f"palettes.json {theme_id} 缺少 {key}"
            assert f"--{key}" in block, f"style.css {theme_id} 块缺少 --{key}"
