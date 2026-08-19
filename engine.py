# -*- coding: utf-8 -*-
"""翻译引擎模块

提供基于 NLLB-200 模型的多语言翻译功能。
"""
import os
import random
import re
from typing import Generator, List, Optional, Tuple

import torch
from transformers import AutoTokenizer, AutoModelForSeq2SeqLM

from languages import resolve, DEFAULT_PIVOT_LANGS, LANG_MAP

_MODEL = None
_TOKENIZER = None
_MODEL_PATH = os.environ.get("NLLB_MODEL_PATH") or os.path.join(os.path.dirname(os.path.abspath(__file__)), "nllb_model")


def _get_model():
    """加载并缓存模型（懒加载）"""
    global _MODEL, _TOKENIZER
    if _MODEL is None:
        if not os.path.exists(_MODEL_PATH):
            raise FileNotFoundError(f"模型路径不存在: {_MODEL_PATH}")
        _TOKENIZER = AutoTokenizer.from_pretrained(_MODEL_PATH, local_files_only=True)
        _MODEL = AutoModelForSeq2SeqLM.from_pretrained(_MODEL_PATH, local_files_only=True)
    return _TOKENIZER, _MODEL


def _clean(text: str) -> str:
    """清理文本（去除首尾空白）"""
    return text.strip()


def _nllb_translate(text: str, src_lang: str, tgt_lang: str) -> str:
    """执行单次 NLLB 翻译"""
    tokenizer, model = _get_model()
    tokenizer.src_lang = src_lang
    inputs = tokenizer(text, return_tensors="pt", truncation=True, max_length=512)
    forced_bos_token_id = tokenizer.convert_tokens_to_ids(tgt_lang)
    if forced_bos_token_id is None or forced_bos_token_id == tokenizer.unk_token_id:
        raise ValueError(f"不支持的目标语言代码: {tgt_lang}")
    with torch.no_grad():
        outputs = model.generate(
            **inputs,
            forced_bos_token_id=forced_bos_token_id,
            max_length=512,
            num_beams=1,
            repetition_penalty=1.2,
        )
    return tokenizer.batch_decode(outputs, skip_special_tokens=True)[0].strip()


def translate_once(text: str, src_lang: str, tgt_lang: str) -> str:
    """翻译一次文本（包含语言解析和清理）"""
    src = resolve(src_lang)
    tgt = resolve(tgt_lang)
    if src is None or tgt is None:
        raise ValueError(f"不支持的语言: {src_lang} -> {tgt_lang}")
    return _clean(_nllb_translate(text, src, tgt))


def _preprocess(text: str) -> str:
    """预处理文本（删除空行，合并连续空格为单个空格，保留单词间空格）"""
    lines = text.splitlines()
    non_empty = [line.strip() for line in lines if line.strip()]
    return " ".join(non_empty)


def _split_by_threshold(text: str, threshold: int = 20) -> List[str]:
    """按阈值分割文本
    
    Args:
        text: 待分割文本
        threshold: 每段最大字符数
        
    Returns:
        分割后的文本段列表
    """
    if not text:
        return []
        
    segments = []
    start = 0
    cnt = 0
    for i, ch in enumerate(text):
        cnt += 1
        if ch in "，,。":
            if cnt >= threshold:
                segments.append(text[start:i + 1])
                start = i + 1
                cnt = 0
    if start < len(text):
        tail = text[start:]
        if not segments and len(tail) > threshold * 2:
            for j in range(0, len(tail), threshold):
                segments.append(tail[j:j + threshold])
        else:
            segments.append(tail)
    return segments


def grass_translate(
    text: str, 
    rounds: int, 
    pivot_langs: List[str], 
    final_lang: str, 
    threshold: int = 20, 
    random_mode: str = "off", 
    excluded_langs: Optional[List[str]] = None
) -> Generator[Tuple, None, None]:
    """执行完整的生草翻译流程
    
    Args:
        text: 输入文本
        rounds: 翻译轮数
        pivot_langs: 中转语言列表
        final_lang: 最终译回语言
        threshold: 分段阈值
        random_mode: 随机模式 ("off", "low", "high")
        excluded_langs: 排除的语言列表
        
    Yields:
        翻译进度和结果元组
    """
    text = _preprocess(text)
    segments = _split_by_threshold(text, threshold)

    all_langs = [k for k in LANG_MAP if k not in ("中文", "中文（简体）", "中文（繁体）")]
    major_langs = list(DEFAULT_PIVOT_LANGS)

    if excluded_langs:
        all_langs = [l for l in all_langs if l not in excluded_langs]
        major_langs = [l for l in major_langs if l not in excluded_langs]

    if random_mode == "off":
        lang_seq = (pivot_langs * ((rounds // len(pivot_langs)) + 1))[:rounds] if pivot_langs else []
    else:
        pool = major_langs if random_mode == "low" else all_langs
        lang_seq = []
        prev = None
        for _ in range(rounds):
            candidates = [l for l in pool if l != prev] if prev and len(pool) > 1 else pool
            choice = random.choice(candidates)
            lang_seq.append(choice)
            prev = choice

    for si, seg in enumerate(segments):
        current = seg
        current_lang = "中文"
        for i, lang in enumerate(lang_seq):
            src = current_lang
            current = translate_once(current, current_lang, lang)
            current_lang = lang
            yield ("step", si, i, src, lang, current)

        src = current_lang
        current = translate_once(current, current_lang, final_lang)
        yield ("segment", si, src, final_lang, current)

    yield ("done", len(segments))