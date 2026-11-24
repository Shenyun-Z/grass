# -*- coding: utf-8 -*-
"""后端与模型识别测试：不加载模型、不需要 torch"""
import json

import pytest

import backend
import m2m100
import modelpath


def _write_config(path, arch):
    path.mkdir(parents=True, exist_ok=True)
    (path / "config.json").write_text(
        json.dumps({"architectures": [arch]}), encoding="utf-8")


def test_detect_m2m100(tmp_path, monkeypatch):
    _write_config(tmp_path, "M2M100ForConditionalGeneration")
    monkeypatch.setenv("GRASS_MODEL_PATH", str(tmp_path))
    modelpath.reset_cache()
    assert modelpath.kind() == "m2m100"
    assert backend.kind() == "m2m100"
    assert "M2M100" in backend.module().__name__.upper()


def test_detect_hymt2(tmp_path, monkeypatch):
    _write_config(tmp_path, "HunYuanDenseV1ForCausalLM")
    monkeypatch.setenv("GRASS_MODEL_PATH", str(tmp_path))
    modelpath.reset_cache()
    assert modelpath.kind() == "hymt2"
    assert backend.kind() == "hymt2"


def test_unknown_architecture_raises(tmp_path, monkeypatch):
    _write_config(tmp_path, "SomeOtherModel")
    monkeypatch.setenv("GRASS_MODEL_PATH", str(tmp_path))
    modelpath.reset_cache()
    assert modelpath.kind() == "unknown"
    with pytest.raises(backend.UnknownBackendError):
        backend.kind()


def test_env_priority_grass_over_hymt2(tmp_path, monkeypatch):
    first, second = tmp_path / "first", tmp_path / "second"
    first.mkdir()
    _write_config(second, "M2M100ForConditionalGeneration")
    monkeypatch.setenv("HYMT2_MODEL_PATH", str(first))
    monkeypatch.setenv("GRASS_MODEL_PATH", str(second))
    assert modelpath.model_dir() == str(second)


def test_default_dir_when_nothing_found(monkeypatch, tmp_path):
    monkeypatch.delenv("GRASS_MODEL_PATH", raising=False)
    monkeypatch.delenv("HYMT2_MODEL_PATH", raising=False)
    monkeypatch.setattr(modelpath, "base_dir", lambda: str(tmp_path))
    assert modelpath.model_dir("m2m100").endswith("m2m100_model")
    assert modelpath.model_dir("hymt2").endswith("hymt2_model")


# ===== M2M-100 适配层 =====
@pytest.mark.parametrize("name,code", [
    ("中文", "zh"), ("英语", "en"), ("日语", "ja"), ("哈萨克语", "kk"),
])
def test_m2m100_lang_code(name, code):
    assert m2m100.lang_code(name) == code


@pytest.mark.parametrize("name", ["繁体中文", "粤语", "藏语", "维吾尔语", "不存在的语言"])
def test_m2m100_rejects_unsupported_languages(name):
    assert m2m100.lang_code(name) is None


def test_m2m100_clean_output_strips_prefix_and_quotes():
    assert m2m100.clean_output("  译文：你好 ") == "你好"
    assert m2m100.clean_output('"你好"') == "你好"
    assert m2m100.clean_output("他说“再来一次”") == "他说“再来一次”"


def test_m2m100_input_limit_is_smaller_than_hymt2():
    import hymt2
    assert m2m100.MAX_INPUT_TOKENS < hymt2.MAX_INPUT_TOKENS
