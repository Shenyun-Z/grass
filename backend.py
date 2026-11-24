# -*- coding: utf-8 -*-
"""翻译后端路由：按模型目录里的 config.json 自动选择 Hy-MT2 或 M2M-100

两个后端都实现同一套接口：
    model_path() / model_label() / get_model(device)
    translate(text, src_lang, tgt_lang, device)
    has_safetensors(dir) / truncate_to_max_len(text, tokenizer, max_len)
    MAX_INPUT_TOKENS / clear_cuda_cache(device)
"""
from __future__ import annotations

import os

import modelpath


class UnknownBackendError(RuntimeError):
    """模型目录无法识别为支持的架构"""


def kind() -> str:
    """当前后端类型：hymt2 / m2m100"""
    detected = modelpath.kind()
    if detected in ("hymt2", "m2m100"):
        return detected
    raise UnknownBackendError(
        f"无法识别模型架构：{modelpath.model_dir()}（只支持 Hy-MT2 与 M2M-100，"
        "请检查 config.json 里的 architectures）")


def module():
    """返回当前后端的实现模块"""
    if kind() == "hymt2":
        import hymt2
        return hymt2
    import m2m100
    return m2m100


def language_table():
    """当前后端支持的语言表（中文名 → 语言代码）"""
    from langdata import LANGS_BY_BACKEND
    return LANGS_BY_BACKEND[kind()]


def model_path() -> str:
    return module().model_path()


def model_label() -> str:
    return module().model_label()


def max_input_tokens() -> int:
    return module().MAX_INPUT_TOKENS


def get_model(device: str):
    return module().get_model(device)


def translate(text: str, src_lang: str, tgt_lang: str, device: str) -> str:
    return module().translate(text, src_lang, tgt_lang, device)


def has_safetensors(path: str) -> bool:
    """目录内是否有 safetensors 权重（与后端无关的通用实现）"""
    try:
        return any(name.endswith(".safetensors") for name in os.listdir(path))
    except OSError:
        return False


def truncate_to_max_len(text: str, tokenizer, max_len: int) -> str:
    """按 token 上限截断（与后端无关的通用实现）"""
    if not text:
        return text
    if len(text) <= max_len:
        return text
    try:
        ids = tokenizer.encode(text, add_special_tokens=False)
        if len(ids) <= max_len:
            return text
        return tokenizer.decode(ids[:max_len], skip_special_tokens=True,
                                clean_up_tokenization_spaces=False).strip()
    except Exception:
        return text[:max_len]


def clear_cuda_cache(device: str) -> None:
    module().clear_cuda_cache(device)
