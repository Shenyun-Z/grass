# -*- coding: utf-8 -*-
"""翻译引擎模块

提供基于 NLLB-200 模型的多语言翻译功能。
"""
import os
import random
import threading
from typing import Generator, List, Optional, Tuple

from languages import resolve, DEFAULT_PIVOT_LANGS, LANG_MAP

# 默认切分标点集合：中文/英文的常见句读标点
DEFAULT_SPLIT_PUNCTS = "，,。.!！?？;；:：、"
# 连续标点视为一体（如 ... ？！ ……），切分时一并划入前段
_ALL_PUNCTS = DEFAULT_SPLIT_PUNCTS + "…"
# NLLB tokenizer 的最大输入长度
_MAX_INPUT_LEN = 512

_MODEL = None
_TOKENIZER = None
_MODEL_PATH = os.environ.get("NLLB_MODEL_PATH") or os.path.join(os.path.dirname(os.path.abspath(__file__)), "nllb_model")
# 计算设备：惰性解析（首次用到才检测），避免模块导入期依赖 CUDA / torch
_DEVICE: Optional[str] = None
# 模型加载锁：防止并发进入 _get_model 造成半初始化
_MODEL_LOCK = threading.Lock()

_TORCH = None
_TRANSFORMERS = None


def _torch():
    """惰性导入 torch：缺依赖时抛出可读的 ImportError，而不是让程序在导入期崩溃"""
    global _TORCH
    if _TORCH is None:
        try:
            import torch
        except ImportError as exc:
            raise ImportError("缺少依赖 torch：请先执行 pip install -r requirements.txt") from exc
        _TORCH = torch
    return _TORCH


def _transformers():
    """惰性导入 transformers，返回 (AutoTokenizer, AutoModelForSeq2SeqLM)"""
    global _TRANSFORMERS
    if _TRANSFORMERS is None:
        try:
            from transformers import AutoModelForSeq2SeqLM, AutoTokenizer
        except ImportError as exc:
            raise ImportError("缺少依赖 transformers：请先执行 pip install -r requirements.txt") from exc
        _TRANSFORMERS = (AutoTokenizer, AutoModelForSeq2SeqLM)
    return _TRANSFORMERS


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
    """加载并缓存模型（懒加载，自动使用 GPU 加速，加锁防并发半初始化）"""
    global _MODEL, _TOKENIZER
    if _MODEL is None:
        with _MODEL_LOCK:
            if _MODEL is None:  # 双重检查，避免重复加载
                if not os.path.exists(_MODEL_PATH):
                    raise FileNotFoundError(f"模型路径不存在: {_MODEL_PATH}")
                AutoTokenizer, AutoModelForSeq2SeqLM = _transformers()
                device = _device()
                tokenizer = AutoTokenizer.from_pretrained(_MODEL_PATH, local_files_only=True)
                model = AutoModelForSeq2SeqLM.from_pretrained(_MODEL_PATH, local_files_only=True)
                if device == "cuda":
                    # 显式启用 CUDA 并转半精度，显著降低显存占用、提升推理速度
                    model.half()
                model.to(device)
                model.eval()
                # 全部初始化成功后才对外发布，避免异常时留下半初始化的全局状态
                _TOKENIZER, _MODEL = tokenizer, model
    return _TOKENIZER, _MODEL


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


def _clear_cuda_cache():
    """推理后释放 CUDA 缓存，避免多段连续推理时显存累积"""
    if _DEVICE == "cuda":
        try:
            _torch().cuda.empty_cache()
        except Exception:
            pass


def _clean(text: str) -> str:
    """清理文本（去除首尾空白）"""
    return text.strip()


def _nllb_translate(text: str, src_lang: str, tgt_lang: str) -> str:
    """执行单次 NLLB 翻译"""
    tokenizer, model = _get_model()
    device = _device()
    tokenizer.src_lang = src_lang
    inputs = tokenizer(text, return_tensors="pt", truncation=True, max_length=_MAX_INPUT_LEN)
    inputs = {k: v.to(device) for k, v in inputs.items()}
    forced_bos_token_id = tokenizer.convert_tokens_to_ids(tgt_lang)
    if forced_bos_token_id is None or forced_bos_token_id == tokenizer.unk_token_id:
        raise ValueError(f"不支持的目标语言代码: {tgt_lang}")
    with _torch().no_grad():
        outputs = model.generate(
            **inputs,
            forced_bos_token_id=forced_bos_token_id,
            max_length=_MAX_INPUT_LEN,
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


def _resolve_pair(src_lang: str, tgt_lang: str) -> Tuple[str, str]:
    """解析语言代码，非法时抛出带语言名的 ValueError"""
    src = resolve(src_lang)
    tgt = resolve(tgt_lang)
    if src is None or tgt is None:
        raise ValueError(f"不支持的语言: {src_lang} -> {tgt_lang}")
    return src, tgt


def _truncate_to_max_len(text: str, tokenizer, max_len: int = _MAX_INPUT_LEN) -> str:
    """按 token 校验并截断超长文本，防止模型静默产生乱码/空输出"""
    if not text:
        return text
    # 快速路径：短文本无需 tokenize 校验
    if len(text) <= max_len:
        return text
    try:
        ids = tokenizer.encode(text, add_special_tokens=False)
        if len(ids) <= max_len:
            return text
        # 按 token 长度截断（保留前 max_len 个 token）
        truncated_ids = ids[:max_len]
        return tokenizer.decode(truncated_ids, skip_special_tokens=True).strip()
    except Exception:
        # tokenize 失败时退化为字符级截断，保证不产生超长输入
        return text[:max_len]


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
        ValueError: 语言配置非法或目标语言代码不受支持
        RuntimeError: 推理时发生 CUDA OOM 等硬件/运行错误
    """
    if not texts:
        return []
    src, tgt = _resolve_pair(src_lang, tgt_lang)
    tokenizer, model = _get_model()
    device = _device()
    tokenizer.src_lang = src
    forced_bos_token_id = tokenizer.convert_tokens_to_ids(tgt)
    if forced_bos_token_id is None or forced_bos_token_id == tokenizer.unk_token_id:
        raise ValueError(f"不支持的目标语言代码: {tgt}")

    results: List[str] = [""] * len(texts)
    try:
        with _torch().no_grad():
            for i, text in enumerate(texts):
                if stop_event is not None and stop_event.is_set():
                    break
                # 逐条校验 token 长度，超限时显式截断，避免静默乱码
                safe_text = _truncate_to_max_len(text, tokenizer)
                inputs = tokenizer(
                    safe_text, return_tensors="pt", truncation=True,
                    max_length=_MAX_INPUT_LEN)
                inputs = {k: v.to(device) for k, v in inputs.items()}
                outputs = model.generate(
                    **inputs,
                    forced_bos_token_id=forced_bos_token_id,
                    max_length=_MAX_INPUT_LEN,
                    num_beams=1,
                    repetition_penalty=1.2,
                )
                decoded = tokenizer.batch_decode(outputs, skip_special_tokens=True)
                results[i] = _clean(decoded[0])
    except Exception:
        # 异常向上抛给上层（gui 层捕获并分类提示），避免线程静默死亡
        raise
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
        return "模型文件缺失：请确认 ./nllb_model/ 目录存在，或通过 NLLB_MODEL_PATH 指定模型路径。"
    if isinstance(exc, (ValueError,)) and ("不支持的语言" in msg or "语言代码" in msg):
        return f"语言配置非法：{msg} 请在语言选择中选用支持的语种。"
    if "cuda out of memory" in lowered or "out of memory" in lowered or "显存" in msg:
        return "显存不足（CUDA out of memory）：请关闭其他占用显存的程序，或设置 GRASS_DEVICE=cpu 改用 CPU 推理。"
    if isinstance(exc, ImportError) or "缺少依赖" in msg or "module 'torch'" in lowered or "no module named" in lowered:
        return f"依赖缺失：{msg} 请先 pip install -r requirements.txt。"
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

    all_langs = [k for k in LANG_MAP if k not in ("中文", "中文（简体）", "中文（繁体）")]
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