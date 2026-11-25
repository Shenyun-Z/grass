# -*- coding: utf-8 -*-
"""MiLMMT-46 模型适配与语言表测试：不加载模型、不需要 torch"""
import os

import pytest

import langdata
import languages
import milmmt


# ===== 语言表 =====
def test_language_names_official():
    # 提示词里的语言名必须和官方模型卡逐字一致
    assert langdata.LANGS["中文"] == "Chinese (Simplified)"
    assert langdata.LANGS["繁体中文"] == "Chinese (Traditional)"
    assert langdata.LANGS["粤语"] == "Cantonese"
    assert len(set(langdata.LANGS.values())) == 46
    # 官方 46 语种里没有这些
    for missing in ("藏语", "维吾尔语", "蒙古语", "乌克兰语"):
        assert missing not in langdata.LANGS


def test_lang_name_lookup():
    assert milmmt.lang_name("中文") == "Chinese (Simplified)"
    assert milmmt.lang_name("chinese (simplified)") == "Chinese (Simplified)"
    assert milmmt.lang_name("English") == "English"
    assert milmmt.lang_name("藏语") is None


def test_resolve_language():
    assert languages.resolve("中") == "中文"
    assert languages.resolve("英语") == "英语"
    assert languages.resolve("English") == "英语"
    assert languages.resolve("不存在的语言") is None
    assert languages.resolve("藏语") is None
    assert languages.code("中文") == "Chinese (Simplified)"
    assert languages.is_supported("粤语") is True


def test_language_groups_and_presets_cover_only_supported():
    assert languages.LANG_GROUPS
    for _, group in languages.LANG_GROUPS:
        for name in group:
            assert name in languages.LANG_MAP
    for preset, names in languages.PRESETS.items():
        if names is not None:
            for name in names:
                assert name in languages.LANG_MAP
    assert all(x in languages.LANG_MAP for x in languages.DEFAULT_PIVOT_LANGS)


# ===== 提示词与输出清理 =====
def test_prompt_format():
    prompt = milmmt.build_prompt("我爱机器翻译", "中文", "英语")
    assert prompt == ("Translate this from Chinese (Simplified) to English:\n"
                      "Chinese (Simplified): 我爱机器翻译\n"
                      "English:")
    with pytest.raises(ValueError):
        milmmt.build_prompt("文本", "中文", "藏语")


def test_clean_output():
    assert milmmt.clean_output("  I love machine translation.\n\nHope it helps.") == \
        "I love machine translation."
    assert milmmt.clean_output("English: I love machine translation.") == \
        "I love machine translation."
    assert milmmt.clean_output("“我爱机器翻译”") == "我爱机器翻译"
    assert milmmt.clean_output("") == ""


# ===== 非 ASCII 路径下的分词器镜像 =====
def test_tokenizer_dir_passthrough_ascii(tmp_path):
    assert milmmt.tokenizer_dir(str(tmp_path)) == str(tmp_path)


def test_tokenizer_dir_mirrors_chinese_path(tmp_path):
    model_dir = tmp_path / "模型"
    model_dir.mkdir()
    for name in milmmt.TOKENIZER_FILES:
        (model_dir / name).write_text("x", encoding="utf-8")
    mirror = milmmt.tokenizer_dir(str(model_dir))
    assert mirror != str(model_dir)
    assert mirror.isascii()
    for name in milmmt.TOKENIZER_FILES:
        assert os.path.exists(os.path.join(mirror, name))
