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

# 默认切分标点集合：中文/英文的常见句读标点
DEFAULT_SPLIT_PUNCTS = "，,。.!！?？;；:：、"
# 连续标点视为一体（如 ... ？！ ……），切分时一并划入前段
_ALL_PUNCTS = DEFAULT_SPLIT_PUNCTS + "…"

_MODEL = None
_TOKENIZER = None
_MODEL_PATH = os.environ.get("NLLB_MODEL_PATH") or os.path.join(os.path.dirname(os.path.abspath(__file__)), "nllb_model")
# 计算设备：优先 GRASS_DEVICE 环境变量强制指定，否则自动检测 CUDA
_DEVICE = os.environ.get("GRASS_DEVICE") or ("cuda" if torch.cuda.is_available() else "cpu")


def _get_model():
    """加载并缓存模型（懒加载，自动使用 GPU 加速）"""
    global _MODEL, _TOKENIZER
    if _MODEL is None:
        if not os.path.exists(_MODEL_PATH):
            raise FileNotFoundError(f"模型路径不存在: {_MODEL_PATH}")
        _TOKENIZER = AutoTokenizer.from_pretrained(_MODEL_PATH, local_files_only=True)
        _MODEL = AutoModelForSeq2SeqLM.from_pretrained(_MODEL_PATH, local_files_only=True)
        _MODEL.to(_DEVICE)
        _MODEL.eval()
    return _TOKENIZER, _MODEL


def _clean(text: str) -> str:
    """清理文本（去除首尾空白）"""
    return text.strip()


def _nllb_translate(text: str, src_lang: str, tgt_lang: str) -> str:
    """执行单次 NLLB 翻译"""
    tokenizer, model = _get_model()
    tokenizer.src_lang = src_lang
    inputs = tokenizer(text, return_tensors="pt", truncation=True, max_length=512)
    inputs = {k: v.to(_DEVICE) for k, v in inputs.items()}
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


def _split_by_threshold(text: str, threshold: int = 20, puncts: Optional[str] = None) -> List[str]:
    """按阈值分割文本
    
    Args:
        text: 待分割文本
        threshold: 每段最大字符数
        puncts: 切分标点集合。None 时使用 DEFAULT_SPLIT_PUNCTS；
                传空字符串表示禁用标点切分（仅按阈值硬切）
        
    Returns:
        分割后的文本段列表
    """
    if not text:
        return []
    punct_set = DEFAULT_SPLIT_PUNCTS if puncts is None else puncts

    segments = []
    start = 0
    cnt = 0
    i = 0
    n = len(text)
    while i < n:
        ch = text[i]
        cnt += 1
        if ch in punct_set and cnt >= threshold:
            # 吞并切分点后的连续标点（含省略号 …），避免拆散 ... ？！ …… 等组合
            j = i + 1
            while j < n and text[j] in _ALL_PUNCTS:
                j += 1
            segments.append(text[start:j])
            start = j
            cnt = 0
            i = j
        else:
            i += 1
    if start < n:
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
    excluded_langs: Optional[List[str]] = None,
    split_puncts: Optional[str] = None
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
        split_puncts: 切分标点集合（None 使用默认集合）
        
    Yields:
        翻译进度和结果元组
    """
    text = _preprocess(text)
    segments = _split_by_threshold(text, threshold, split_puncts)

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