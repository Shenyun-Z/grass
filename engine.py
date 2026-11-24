# -*- coding: utf-8 -*-
"""翻译引擎模块

提供本地多语言中转翻译能力。后端由 backend.py 按模型架构路由：
- milmmt.py：小米 MiLMMT-46（默认，1B，Gemma3 解码器）
- m2m100.py：Meta M2M-100（418M 编码器-解码器）
- hymt2.py：腾讯混元 Hy-MT2（可选）
本模块负责分段、语言链与流程编排。
"""
from __future__ import annotations

import os
import random
import threading
from typing import Generator, List, Optional, Tuple

import backend
import hymt2
from languages import resolve, DEFAULT_PIVOT_LANGS, LANG_NAMES

# 默认切分标点集合：中文/英文的常见句读标点
DEFAULT_SPLIT_PUNCTS = "，,。.!！?？;；:：、"
# 连续标点视为一体（如 ... ？！ ……），切分时一并划入前段
_ALL_PUNCTS = DEFAULT_SPLIT_PUNCTS + "…"
# 兼容旧调用点：权重检查/截断统一由后端提供
_has_safetensors = backend.has_safetensors


def _truncate_to_max_len(text, tokenizer, max_len=None):
    """按后端的上限截断文本（max_len 省略时取后端上限）"""
    if max_len is None:
        max_len = _max_input_len()
    return backend.truncate_to_max_len(text, tokenizer, max_len)


def _max_input_len() -> int:
    """当前后端的输入上限（按 token 计）"""
    try:
        return backend.max_input_tokens()
    except Exception:
        return hymt2.MAX_INPUT_TOKENS

# 计算设备：惰性解析（首次用到才检测），避免模块导入期依赖 CUDA / torch
_DEVICE: Optional[str] = None


def _torch():
    """惰性导入 torch（委托给后端模块，保持旧调用点可用）"""
    return backend.module().torch()


def _device() -> str:
    """解析计算设备：GRASS_DEVICE 优先，其次自动检测 CUDA"""
    global _DEVICE
    if _DEVICE is None:
        forced = (os.environ.get("GRASS_DEVICE") or "").strip().lower()
        if forced:
            if forced not in ("cpu", "cuda"):
                raise ValueError(f"GRASS_DEVICE 取值非法：{forced}（仅支持 cpu / cuda）")
            if forced == "cuda" and not _torch().cuda.is_available():
                raise RuntimeError(
                    "GRASS_DEVICE=cuda 但未检测到可用 CUDA 设备：请改用 CPU 推理"
                    "（取消 GRASS_DEVICE 或设为 cpu）")
            _DEVICE = forced
        else:
            _DEVICE = "cuda" if _torch().cuda.is_available() else "cpu"
    return _DEVICE


def _get_model():
    """加载并缓存模型（供界面预热调用，真正的推理在后端模块内完成）"""
    return backend.get_model(_device())


def get_device_info() -> str:
    """返回当前计算设备信息，供界面显示"""
    try:
        device = _device()
    except Exception:
        return "CPU"
    if device == "cuda":
        try:
            name = _torch().cuda.get_device_name(0)
            return f"GPU（CUDA）· {name}"
        except Exception:
            return "GPU（CUDA）"
    return "CPU"


def get_model_info() -> str:
    """返回模型信息，供界面显示"""
    try:
        return backend.model_label()
    except Exception:
        return f"未知模型 · {os.path.basename(os.path.normpath(backend.model_path()))}"


def _clear_cuda_cache():
    """推理后释放 CUDA 缓存，避免多段连续推理时显存累积"""
    if _DEVICE == "cuda":
        try:
            backend.clear_cuda_cache(_DEVICE)
        except Exception:
            pass


def _clean(text: str) -> str:
    """清理文本（去除首尾空白）"""
    return text.strip()


def _resolve_pair(src_lang: str, tgt_lang: str) -> Tuple[str, str]:
    """解析语言名，非法时抛出带语言名的 ValueError"""
    src = resolve(src_lang)
    tgt = resolve(tgt_lang)
    if src is None or tgt is None:
        try:
            name = backend.model_label()
        except Exception:
            name = "当前模型"
        raise ValueError(
            f"不支持的语言: {src_lang} -> {tgt_lang}（{name} 不支持该语种）")
    return src, tgt


def translate_once(text: str, src_lang: str, tgt_lang: str) -> str:
    """翻译一次文本（包含语言解析、长度截断和清理）"""
    src, tgt = _resolve_pair(src_lang, tgt_lang)
    tokenizer, _model = _get_model()
    safe_text = _truncate_to_max_len(text, tokenizer, _max_input_len())
    return _clean(backend.translate(safe_text, src, tgt, _device()))


def translate_batch(texts: List[str], src_lang: str, tgt_lang: str,
                    batch_size: int = 1,
                    stop_event: Optional[threading.Event] = None) -> List[str]:
    """翻译文本列表（逐条翻译，不做多句批量输入）

    Args:
        texts: 待翻译文本列表
        src_lang: 源语言名
        tgt_lang: 目标语言名
        batch_size: 保留参数但固定为逐条翻译（忽略多句批量）
        stop_event: 可选停止事件；每段之间检查，置位后立即中止

    Returns:
        与 texts 顺序一致的翻译结果列表（若中途停止，未完成项为空字符串）

    Raises:
        FileNotFoundError: 模型文件缺失
        ValueError: 语言配置非法
        RuntimeError: 推理时发生 CUDA OOM 等硬件/运行错误
    """
    if not texts:
        return []
    src, tgt = _resolve_pair(src_lang, tgt_lang)
    tokenizer, _model = _get_model()
    device = _device()
    max_len = _max_input_len()

    results: List[str] = [""] * len(texts)
    try:
        for i, text in enumerate(texts):
            if stop_event is not None and stop_event.is_set():
                break
            # 逐条校验 token 长度，超限时显式截断，避免静默乱码
            safe_text = _truncate_to_max_len(text, tokenizer, max_len)
            results[i] = _clean(backend.translate(safe_text, src, tgt, device))
    finally:
        _clear_cuda_cache()
    return results


def classify_translate_error(exc: BaseException) -> str:
    """将翻译过程中的异常分类为友好提示文本

    Returns:
        面向用户的中文提示；未知异常返回原文描述
    """
    msg = str(exc)
    lowered = msg.lower()
    if isinstance(exc, FileNotFoundError) or "不存在" in msg:
        return ("模型文件缺失：请确认模型目录（默认 milmmt_model/、m2m100_model/ "
                "或 hymt2_model/）内有完整权重（或将 GRASS_MODEL_PATH 指向本地模型目录）。")
    if isinstance(exc, ValueError) and ("不支持的语言" in msg or "语言代码" in msg):
        return f"语言配置非法：{msg} 请在语言选择中选用支持的语种。"
    if "out of memory" in lowered or "显存" in msg:
        return "显存不足（CUDA out of memory）：请关闭其他占用显存的程序，或设置 GRASS_DEVICE=cpu 改用 CPU 推理。"
    if isinstance(exc, ImportError) or "缺少依赖" in msg or "no module named" in lowered:
        return f"依赖缺失：{msg} 请先 pip install -r requirements.txt。"
    if "trust_remote_code" in lowered:
        return ("模型需要加载自定义代码：确认为可信来源后，设置 GRASS_HYMT2_TRUST_REMOTE_CODE=1 再启动。")
    if "无法识别模型架构" in msg:
        return f"模型配置异常：{msg}"
    return f"翻译失败：{msg}"


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
    if threshold < 1:
        threshold = 1
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
        # 尾部若明显超过 2 倍阈值（例如整段无标点的长文），按阈值硬切，
        # 否则单段过长会被模型截断，造成内容静默丢失
        if len(tail) > threshold * 2:
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
    split_puncts: Optional[str] = None,
    stop_event: Optional[threading.Event] = None
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
        stop_event: 可选停止事件；在每段间检查，置位后立即中止生成

    Yields:
        翻译进度和结果元组
    """
    text = _preprocess(text)
    if rounds is None or rounds < 1:
        raise ValueError(f"轮数必须至少为 1（当前: {rounds}）")
    segments = _split_by_threshold(text, threshold, split_puncts)

    all_langs = [name for name in LANG_NAMES if name != "中文"]
    major_langs = list(DEFAULT_PIVOT_LANGS)

    if excluded_langs:
        all_langs = [l for l in all_langs if l not in excluded_langs]
        major_langs = [l for l in major_langs if l not in excluded_langs]

    if random_mode == "off":
        lang_seq = (pivot_langs * ((rounds // len(pivot_langs)) + 1))[:rounds] if pivot_langs else []
    else:
        pool = major_langs if random_mode == "low" else all_langs
        if not pool:
            # 排除语言过多时选池可能为空，显式报错，避免 random.choice 抛 IndexError
            raise ValueError("随机选池为空：被排除的语言过多，请至少保留一种可用语言")
        lang_seq = []
        prev = None
        for _ in range(rounds):
            candidates = [l for l in pool if l != prev] if prev and len(pool) > 1 else pool
            choice = random.choice(candidates)
            lang_seq.append(choice)
            prev = choice

    # 逐句翻译：外层遍历段落，内层遍历轮次。
    # 每一段翻译完一轮立即 yield 进度，再翻译下一段，
    # 保证一句翻译完成前绝不开始下一句，UI 能实时逐句变绿。
    for si, seg in enumerate(segments):
        if stop_event is not None and stop_event.is_set():
            break
        current = seg
        current_lang = "中文"
        for i, lang in enumerate(lang_seq):
            if stop_event is not None and stop_event.is_set():
                break
            src = current_lang
            batch_results = translate_batch([current], src, lang, stop_event=stop_event)
            current = batch_results[0]
            current_lang = lang
            yield ("step", si, i, src, lang, current)

        if stop_event is not None and stop_event.is_set():
            break
        src = current_lang
        batch_results = translate_batch([current], src, final_lang, stop_event=stop_event)
        current = batch_results[0]
        yield ("segment", si, src, final_lang, current)

    yield ("done", len(segments))
