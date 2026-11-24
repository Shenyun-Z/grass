# -*- coding: utf-8 -*-
"""Hy-MT2 封装层测试：不加载模型、不需要 torch

覆盖提示词格式、输出清理、长度截断与语言表一致性。
"""
import pytest

import hymt2
import languages


# ===== 提示词 =====
def test_build_prompt_matches_official_format():
    prompt = hymt2.build_prompt("今天天气真好。", "英语")
    assert prompt.startswith("将以下文本翻译成英语")
    assert "只需要输出翻译后的结果" in prompt
    assert prompt.endswith("今天天气真好。")
    assert "\n\n今天" in prompt


def test_prompt_uses_chinese_language_name():
    assert "日语" in hymt2.build_prompt("hello", "日语")


# ===== 输出清理 =====
@pytest.mark.parametrize("raw,expected", [
    ("  你好  ", "你好"),
    ("译文：你好", "你好"),
    ("翻译结果： 你好", "你好"),
    ('"你好"', "你好"),
    ("「你好」", "你好"),
    ("将以下文本翻译成英语，注意只需要输出翻译后的结果，不要额外解释：\n\n你好", "你好"),
    ("", ""),
])
def test_clean_output(raw, expected):
    assert hymt2.clean_output(raw) == expected


def test_clean_output_keeps_inner_quotes():
    assert hymt2.clean_output('他说"再来一次"') == '他说"再来一次"'


# ===== 截断 =====
class _StubTokenizer:
    def encode(self, text, add_special_tokens=False):
        return list(range(len(text)))

    def decode(self, ids, skip_special_tokens=True):
        return "-" * len(ids)


def test_truncate_short_text_untouched():
    assert hymt2.truncate_to_max_len("short", _StubTokenizer(), max_len=10) == "short"


def test_truncate_long_text_by_tokens():
    assert hymt2.truncate_to_max_len("x" * 30, _StubTokenizer(), max_len=10) == "-" * 10


def test_truncate_never_raises_on_bad_tokenizer():
    class _Bad:
        def encode(self, *a, **k):
            raise RuntimeError("boom")

        def decode(self, *a, **k):
            raise RuntimeError("boom")

    assert hymt2.truncate_to_max_len("y" * 50, _Bad(), max_len=10) == "y" * 10


# ===== 语言表一致性 =====
def test_language_table_has_no_duplicate_abbr():
    codes = list(languages.LANG_MAP.values())
    assert len(codes) == len(set(codes))


def test_all_group_languages_are_supported():
    for _, group in languages.LANG_GROUPS:
        for lang in group:
            assert languages.resolve(lang) == lang


def test_presets_only_use_supported_languages():
    for name, preset in languages.PRESETS.items():
        if preset is None:
            continue
        assert preset, f"{name} 预设为空"
        for lang in preset:
            assert languages.resolve(lang) == lang


def test_default_pivots_are_supported():
    for lang in languages.DEFAULT_PIVOT_LANGS:
        assert languages.resolve(lang) == lang


def test_supported_count_matches_model_card():
    # Hy-MT2 官方语言表为 38 个语种/变体
    assert len(languages.LANG_MAP) == 38
