# -*- coding: utf-8 -*-
"""小米 MiLMMT-46（1B）本地推理封装

模型：xiaomi-research/MiLMMT-46-1B-v1.0（Gemma 许可），默认读取程序目录下的
milmmt_model/，可用 GRASS_MODEL_PATH 指定其他本地目录。

MiLMMT-46 是 Gemma3-1B 继续训练出来的**纯解码器**翻译模型，46 个语种，
官方要求使用固定提示词、且必须显式写出源语言（模型没有自动识别源语言的模式）：

    Translate this from <source language name> to <target language name>:
    <source language name>: <source language sentence>
    <target language name>:

它的指令跟随能力在后训练阶段被大幅削弱，额外的系统提示词/前后缀会被当成正文，
所以这里只拼官方这一种格式。
"""
from __future__ import annotations

import os
import re
import threading
from typing import Optional, Tuple

import langdata
import modelpath
import pathmirror

# 提示词 + 原文的总 token 上限（模型本身支持 32k，但 CPU 上要控制单次推理开销）
MAX_INPUT_TOKENS = 512
MAX_NEW_TOKENS = 512

# 分词器文件（MiLMMT 用 tokenizer.json + tokenizer.model，两种都带上）
TOKENIZER_FILES = (
    "config.json",
    "tokenizer_config.json",
    "special_tokens_map.json",
    "added_tokens.json",
    "tokenizer.json",
    "tokenizer.model",
    "chat_template.jinja",
    "generation_config.json",
)

_MODEL_PATH = modelpath.model_dir("milmmt")

_MODEL = None
_TOKENIZER = None
_MODEL_LOCK = threading.Lock()
_LOADED_DEVICE: Optional[str] = None

_TORCH = None
_TRANSFORMERS = None

# 输入语言名（中文名或英文名，大小写不敏感）→ 提示词里用的官方英文名
_LANG_EN = {name.lower(): en for name, en in langdata.MILMMT_LANGS.items()}
_LANG_EN.update({en.lower(): en for en in langdata.MILMMT_LANGS.values()})

_QUOTE_PAIRS = {'"': '"', "“": "”", "'": "'", "「": "」", "『": "』", "«": "»"}
# 个别时候模型会多吐一行 "English:" 之类的标签
_LABEL_RE = re.compile(r"^\s*[A-Z][A-Za-z ()]{1,24}:\s*")


def model_path() -> str:
    """当前模型目录"""
    return _MODEL_PATH


def model_label() -> str:
    """界面显示用的模型名"""
    return f"MiLMMT-46 · {os.path.basename(os.path.normpath(_MODEL_PATH))}"


def lang_name(lang_name: str) -> Optional[str]:
    """中文/英文语言名 → MiLMMT 提示词里的官方英文名；不支持返回 None"""
    if not isinstance(lang_name, str):
        return None
    name = lang_name.strip()
    if name in langdata.MILMMT_LANGS:
        return langdata.MILMMT_LANGS[name]
    return _LANG_EN.get(name.lower())


def tokenizer_dir(model_dir: str) -> str:
    """分词器加载目录：中文路径时走 ASCII 临时镜像"""
    return pathmirror.mirrored_dir(model_dir, TOKENIZER_FILES, "milmmt")


def torch():
    """惰性导入 torch"""
    global _TORCH
    if _TORCH is None:
        try:
            import torch as _t
        except ImportError as exc:
            raise ImportError("缺少依赖 torch：请先执行 pip install -r requirements.txt") from exc
        _TORCH = _t
    return _TORCH


def transformers():
    """惰性导入 transformers，返回 (AutoTokenizer, AutoModelForCausalLM)"""
    global _TRANSFORMERS
    if _TRANSFORMERS is None:
        try:
            from transformers import AutoModelForCausalLM, AutoTokenizer
        except ImportError as exc:
            raise ImportError(
                "缺少依赖 transformers：请执行 pip install -r requirements.txt"
                "（MiLMMT-46 需要 transformers>=4.57）") from exc
        _TRANSFORMERS = (AutoTokenizer, AutoModelForCausalLM)
    return _TRANSFORMERS


def _quiet_transformers() -> None:
    """降低 transformers 的控制台噪声"""
    try:
        import transformers as _tf
        _tf.utils.logging.set_verbosity_error()
        _tf.utils.logging.disable_progress_bar()
    except Exception:
        pass


def _dtype(device: str):
    """按设备选择推理精度：GPU 优先 bfloat16，CPU 用 float32"""
    t = torch()
    if device == "cuda":
        try:
            if t.cuda.is_bf16_supported():
                return t.bfloat16
        except Exception:
            pass
        return t.float16
    return t.float32


def get_model(device: str) -> Tuple[object, object]:
    """加载并缓存模型（懒加载、加锁防并发半初始化）"""
    global _MODEL, _TOKENIZER, _LOADED_DEVICE
    if _MODEL is None:
        with _MODEL_LOCK:
            if _MODEL is None:
                if not os.path.exists(_MODEL_PATH):
                    raise FileNotFoundError(f"模型路径不存在: {_MODEL_PATH}")
                _quiet_transformers()
                AutoTokenizer, AutoModelForCausalLM = transformers()
                load_kwargs = {"local_files_only": True}
                tokenizer = AutoTokenizer.from_pretrained(
                    tokenizer_dir(_MODEL_PATH), **load_kwargs)
                dtype = _dtype(device)
                try:
                    model = AutoModelForCausalLM.from_pretrained(
                        _MODEL_PATH, dtype=dtype, low_cpu_mem_usage=True, **load_kwargs)
                except TypeError:
                    # 兼容仍使用 torch_dtype 参数的旧版 transformers
                    model = AutoModelForCausalLM.from_pretrained(
                        _MODEL_PATH, torch_dtype=dtype, low_cpu_mem_usage=True, **load_kwargs)
                model.to(device)
                model.eval()
                _TOKENIZER, _MODEL, _LOADED_DEVICE = tokenizer, model, device
    return _TOKENIZER, _MODEL


def build_prompt(text: str, src_lang: str, tgt_lang: str) -> str:
    """按官方格式拼提示词（src_lang / tgt_lang 用中文语言名）"""
    src_en = lang_name(src_lang)
    tgt_en = lang_name(tgt_lang)
    if src_en is None or tgt_en is None:
        raise ValueError(f"不支持的语言: {src_lang} -> {tgt_lang}（MiLMMT-46 不支持该语种）")
    return (f"Translate this from {src_en} to {tgt_en}:\n"
            f"{src_en}: {text}\n"
            f"{tgt_en}:")


def clean_output(text: str) -> str:
    """清理输出：只保留第一行译文，去掉语言标签、外层引号与多余空白"""
    out = (text or "").strip()
    if not out:
        return ""
    # 模型偶尔会自己续写第二句解释，只取第一行
    for sep in ("\n\n", "\n"):
        if sep in out:
            out = out.split(sep, 1)[0].strip()
    out = _LABEL_RE.sub("", out, count=1).strip()
    if len(out) >= 2 and out[0] in _QUOTE_PAIRS and out[-1] == _QUOTE_PAIRS[out[0]]:
        out = out[1:-1].strip()
    return out


def truncate_to_max_len(text: str, tokenizer, max_len: int = MAX_INPUT_TOKENS) -> str:
    """按 token 校验并截断超长文本"""
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


def _max_new_tokens(text: str) -> int:
    """按源文本长度估算输出上限：译文一般不超过原文的 3 倍 token"""
    estimate = int(len(text) * 3) + 64
    return max(64, min(MAX_NEW_TOKENS, estimate))


def translate(text: str, src_lang: str, tgt_lang: str, device: str) -> str:
    """单次翻译：src_lang / tgt_lang 传中文语言名"""
    prompt = build_prompt(text, src_lang, tgt_lang)
    tokenizer, model = get_model(device)
    inputs = tokenizer(prompt, return_tensors="pt", add_special_tokens=False,
                       truncation=True, max_length=MAX_INPUT_TOKENS).to(device)
    prompt_tokens = inputs["input_ids"].shape[-1]
    pad_id = getattr(tokenizer, "pad_token_id", None)
    if pad_id is None:
        pad_id = getattr(tokenizer, "bos_token_id", None) or 0
    with torch().no_grad():
        outputs = model.generate(
            **inputs,
            do_sample=False,
            num_beams=1,
            max_new_tokens=_max_new_tokens(text),
            pad_token_id=pad_id,
        )
    new_tokens = outputs[0][prompt_tokens:]
    decoded = tokenizer.decode(new_tokens, skip_special_tokens=True,
                               clean_up_tokenization_spaces=False)
    return clean_output(decoded)


def clear_cuda_cache(device: str) -> None:
    """推理后释放 CUDA 缓存"""
    if device == "cuda":
        try:
            torch().cuda.empty_cache()
        except Exception:
            pass
