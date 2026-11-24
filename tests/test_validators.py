# -*- coding: utf-8 -*-
"""validators 单元测试：配置名消毒、历史规整、文件读取与表格转义"""
import json

import pytest

import validators as v


# ===== 配置名 =====
@pytest.mark.parametrize("name", ["", "   ", None, 123, "../evil", "a/b", "a\\b",
                                  "..", ".hidden", "x" * 41, "a*b"])
def test_sanitize_rejects_unsafe(name):
    assert v.sanitize_config_name(name) is None


@pytest.mark.parametrize("name,expected", [
    (" 我的配置 ", "我的配置"),
    ("cfg-1", "cfg-1"),
    ("テスト", "テスト"),
    ("a\nb", "ab"),          # 控制字符被剔除而不是拒绝
])
def test_sanitize_accepts_and_cleans(name, expected):
    assert v.sanitize_config_name(name) == expected


def test_sanitize_length_boundary():
    assert v.sanitize_config_name("x" * 40) == "x" * 40
    assert v.sanitize_config_name("x" * 41) is None


# ===== 数值钳制 =====
@pytest.mark.parametrize("value,expected", [(0, 1), (5, 5), (31, 30), ("7", 7),
                                            (None, 10), (True, 10), ("abc", 10)])
def test_clamp_rounds(value, expected):
    assert v.clamp_rounds(value, 10) == expected


@pytest.mark.parametrize("value,expected", [(0, 5), (20, 20), (200, 100), ("12", 12),
                                            (None, 20), (False, 20)])
def test_clamp_threshold(value, expected):
    assert v.clamp_threshold(value, 20) == expected


# ===== 文本文件读取 =====
def test_read_text_file_utf8(tmp_path):
    p = tmp_path / "a.txt"
    p.write_text("你好\n世界", encoding="utf-8")
    assert v.read_text_file(str(p)) == "你好\n世界"


def test_read_text_file_gbk_fallback(tmp_path):
    p = tmp_path / "b.txt"
    p.write_bytes("生草机".encode("gbk"))
    assert v.read_text_file(str(p)) == "生草机"


def test_read_text_file_normalizes_newlines(tmp_path):
    p = tmp_path / "d.txt"
    p.write_bytes("第一行\r\n第二行\r第三行".encode("utf-8"))
    assert v.read_text_file(str(p)) == "第一行\n第二行\n第三行"


def test_read_text_file_rejects_oversize(tmp_path):
    p = tmp_path / "c.txt"
    p.write_bytes(b"x" * 20)
    with pytest.raises(ValueError):
        v.read_text_file(str(p), max_bytes=10)


def test_read_text_file_rejects_binary(tmp_path):
    p = tmp_path / "d.txt"
    p.write_bytes(b"\xff" * 8)
    with pytest.raises(ValueError):
        v.read_text_file(str(p))


def test_read_text_file_rejects_directory(tmp_path):
    with pytest.raises(ValueError):
        v.read_text_file(str(tmp_path))


# ===== 原子写入 =====
def test_atomic_write_replaces_and_leaves_no_temp(tmp_path):
    target = tmp_path / "history.json"
    target.write_text("old", encoding="utf-8")
    v.atomic_write_text(str(target), "new")
    assert target.read_text(encoding="utf-8") == "new"
    assert [p.name for p in tmp_path.iterdir()] == ["history.json"]


# ===== 表格公式注入 =====
@pytest.mark.parametrize("value,expected", [
    ("=1+1", "'=1+1"),
    ("+86 138", "'+86 138"),
    ("-5", "'-5"),
    ("@SUM(A1)", "'@SUM(A1)"),
    ("普通文本", "普通文本"),
    ("", ""),
    (42, 42),
])
def test_escape_spreadsheet_cell(value, expected):
    assert v.escape_spreadsheet_cell(value) == expected


# ===== 历史记录规整 =====
def _good_record(rec_id=2):
    return {
        "id": rec_id, "date": "11-24", "time": "10:00:00",
        "input": "原文", "result": "结果", "segments": ["原文"],
        "seg_results": {"0": "结果"},
        "seg_steps": {"0": [["中文", "英语", "temp"]]},
        "params": {"rounds": 999, "mode": "固定", "langs": ["英语"],
                   "final": "中文", "threshold": 1},
        "stopped": False, "elapsed": "1.0秒",
    }


def test_normalize_history_repairs_types_and_drops_invalid():
    out = v.normalize_history([{"id": "bad"}, _good_record(), 42, {"id": 2, "date": 1}])
    assert len(out) == 1
    rec = out[0]
    assert rec["id"] == 2
    # JSON 里的字符串键必须还原为 int，否则重启后对照视图取不到值
    assert rec["seg_results"] == {0: "结果"}
    assert rec["seg_steps"][0][0] == ("中文", "英语", "temp")
    assert rec["params"]["rounds"] == 30
    assert rec["params"]["threshold"] == 5


def test_normalize_history_dedupes_keeping_latest():
    out = v.normalize_history([_good_record(1), _good_record(1)])
    assert len(out) == 1


def test_normalize_history_limits_and_orders():
    records = [_good_record(i) for i in range(1, 26)]
    out = v.normalize_history(records, limit=20)
    assert len(out) == 20
    assert out[-1]["id"] == 25
    assert out[0]["id"] == 6


def test_normalize_history_tolerates_non_list():
    assert v.normalize_history(None) == []
    assert v.normalize_history({"id": 1}) == []


def test_history_roundtrip_through_json():
    rec = v.normalize_history([_good_record()])[0]
    restored = v.normalize_history(json.loads(v.dump_history([rec])))[0]
    assert restored["seg_results"] == rec["seg_results"]
    assert restored["seg_steps"] == rec["seg_steps"]


def test_next_history_id():
    assert v.next_history_id([]) == 1
    assert v.next_history_id([{"id": 3}, {"id": 7}]) == 8
