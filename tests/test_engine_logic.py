# -*- coding: utf-8 -*-
"""engine 逻辑测试：不加载模型、不需要 torch

通过 monkeypatch 替换 translate_batch，验证分段、语言链、停止事件等纯逻辑。
"""
import threading

import pytest

import engine


# ===== 预处理与分段 =====
def test_preprocess_collapses_blank_lines():
    assert engine._preprocess("  a \n\n b  \n") == "a b"


def test_split_keeps_all_chars():
    text = "一二三四五六七八九十，十一十二十三十四十五，"
    segs = engine._split_by_threshold(text, 10)
    assert "".join(segs) == text
    assert all(s.endswith("，") for s in segs[:-1])


def test_split_long_unpunctuated_tail_hard_splits():
    text = "开头一句。" + "字" * 60
    segs = engine._split_by_threshold(text, 20)
    assert "".join(segs) == text
    assert len(segs) >= 3
    assert all(len(s) <= 40 for s in segs)


def test_split_without_puncts_uses_threshold():
    segs = engine._split_by_threshold("字" * 45, 20, "")
    assert segs == ["字" * 20, "字" * 20, "字" * 5]


def test_split_threshold_floor():
    assert engine._split_by_threshold("ab", 0) == ["ab"]


# ===== 完整流程 =====
def test_grass_translate_emits_step_segment_done(monkeypatch):
    calls = []

    def fake_batch(texts, src_lang, tgt_lang, batch_size=1, stop_event=None):
        calls.append((src_lang, tgt_lang))
        return [f"{texts[0]}|{tgt_lang}"]

    monkeypatch.setattr(engine, "translate_batch", fake_batch)
    events = list(engine.grass_translate("一句话，两句话。", 2, ["英语", "日语"], "中文",
                                        threshold=3))
    kinds = [e[0] for e in events]
    assert kinds.count("segment") == 2
    assert kinds.count("step") == 2 * 2
    assert events[-1] == ("done", 2)
    # 语言链：每段 英语→日语→中文
    assert calls[:3] == [("中文", "英语"), ("英语", "日语"), ("日语", "中文")]


def test_grass_translate_stop_event_aborts(monkeypatch):
    monkeypatch.setattr(engine, "translate_batch", lambda *a, **k: ["x"])
    stop = threading.Event()
    stop.set()
    events = list(engine.grass_translate("abc", 3, ["英语"], "中文", stop_event=stop))
    assert events == [("done", 1)]


def test_grass_translate_rejects_non_positive_rounds():
    with pytest.raises(ValueError):
        list(engine.grass_translate("abc", 0, ["英语"], "中文"))


def test_grass_translate_empty_random_pool_raises():
    with pytest.raises(ValueError):
        list(engine.grass_translate(
            "abc", 3, [], "中文", random_mode="low",
            excluded_langs=list(engine.DEFAULT_PIVOT_LANGS)))


# ===== 设备解析 =====
def test_device_rejects_invalid_override(monkeypatch):
    saved = engine._DEVICE
    engine._DEVICE = None
    monkeypatch.setenv("GRASS_DEVICE", "tpu")
    try:
        with pytest.raises(ValueError):
            engine._device()
    finally:
        engine._DEVICE = saved


# ===== 超长截断（stub tokenizer，不涉及真实模型）=====
class _StubTokenizer:
    unk_token_id = 1

    def __init__(self):
        self.src_lang = None

    def encode(self, text, add_special_tokens=False):
        return list(range(len(text)))

    def decode(self, ids, skip_special_tokens=True):
        return "-" * len(ids)


def test_truncate_to_max_len():
    tok = _StubTokenizer()
    assert engine._truncate_to_max_len("short", tok, max_len=10) == "short"
    assert engine._truncate_to_max_len("x" * 30, tok, max_len=10) == "-" * 10


def test_has_safetensors(tmp_path):
    assert engine._has_safetensors(str(tmp_path)) is False
    (tmp_path / "model.safetensors").write_bytes(b"")
    assert engine._has_safetensors(str(tmp_path)) is True
    assert engine._has_safetensors(str(tmp_path / "missing")) is False


def test_resolve_language():
    from languages import resolve
    assert resolve("中") == "中文"
    assert resolve("英语") == "英语"
    assert resolve("zh-Hant") == "繁体中文"
    assert resolve("中文（繁体）") == "繁体中文"
    assert resolve("不存在的语言") is None


# ===== 错误分类 =====
@pytest.mark.parametrize("exc,fragment", [
    (ImportError("缺少依赖 torch"), "依赖缺失"),
    (FileNotFoundError("模型路径不存在: ./hymt2_model"), "模型文件缺失"),
    (RuntimeError("CUDA out of memory"), "显存不足"),
    (ValueError("不支持的语言: xx -> yy"), "语言配置非法"),
])
def test_classify_translate_error(exc, fragment):
    assert fragment in engine.classify_translate_error(exc)
