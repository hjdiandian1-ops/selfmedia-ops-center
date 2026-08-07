# -*- coding: utf-8 -*-
"""数据可视化组件生成器单测。仅依赖标准库，不触网、不启浏览器。"""
import generate_data_viz as GDV


def _spec(typ):
    return {
        "type": typ,
        "title": "测试标题",
        "primary": "#DC2626",
        "items": [{"label": "A", "value": 1, "display": "1 元"},
                  {"label": "B", "value": 2, "display": "2 元"}],
        "item": {"label": "占比", "value": 25, "display": "25%"},
        "headers": ["项目", "数据"],
        "source": "测试来源",
    }


def test_table_has_marker_and_style():
    html = GDV.render_component(_spec("table"))
    assert 'data-viz="table"' in html
    assert "style=" in html
    assert "1 元" in html


def test_bar_has_marker_and_width():
    html = GDV.render_component(_spec("bar"))
    assert 'data-viz="bar"' in html
    assert "width:100%" in html
    assert "inline-block" in html


def test_ratio_has_marker_and_pct():
    html = GDV.render_component(_spec("ratio"))
    assert 'data-viz="ratio"' in html
    assert "width:25%" in html


def test_kpi_has_marker_and_values():
    html = GDV.render_component(_spec("kpi"))
    assert 'data-viz="kpi"' in html
    assert "1 元" in html
    assert "2 元" in html


def test_unknown_type_raises():
    try:
        GDV.render_component(_spec("nope"))
    except ValueError:
        return
    raise AssertionError("未知组件类型应抛 ValueError")
