# -*- coding: utf-8 -*-
"""腾讯混元 Hy-MT2 本地推理封装

模型：tencent/Hy-MT2-1.8B（Apache-2.0），默认读取 ./hymt2_model/，
可用环境变量 HYMT2_MODEL_PATH 指定其他本地目录（同系列的 7B / 30B-A3B 也可直接用）。

提示词与采样参数取自官方模型卡：只发 user 消息、不带 system prompt，
"只需要输出翻译后的结果，不要额外解释"。
"""
from __future__ import annotations

import os
import re
import threading
from typing import Optional, Tuple

# 官方默认提示词：源语言由模型自行判断，只需给出目标语言
PROMPT_TEMPLATE = "将以下文本翻译成{target}，注意只需要输出翻译后的结果，不要额外解释：\n\n{source}"

# 官方推荐采样参数（1.8B / 7B）
TEMPERATURE = 0.7
TOP_P = 0.6
TOP_K = 20
REPETITION_PENALTY = 1.05

# 输入/输出长度上限（按 token 计），避免超长文本把显存打满
MAX_INPUT_TOKENS = 2048
MAX_NEW_TOKENS = 1024

_MODEL_PATH = os.environ.get("HYMT2_MODEL_PATH") or os.path.join(
    os.path.dirname(os.path.abspath(__file__)), "hymt2_model")

_MODEL = None
_TOKENIZER = None
_MODEL_LOCK = threading.Lock()
_LOADED_DEVICE: Optional[str] = None

_TORCH = None
_TRANSFORMERS = None

# 清理模型偶尔多输出的"译文："之类前缀
_LABEL_RE = re.compile(r"^\s*(?:译文|翻译结果|翻译|译文如下|translation|translated text)\s*[:：]\s*", re.I)
# 清理模型把提示词原样吐回来的情况
_ECHO_RE = re.compile(r"^\s*将以下文本翻译成[^\n]*?\n+", re.I)
_QUOTE_PAIRS = {'"': '"', "“": "”", "'": "'", "「": "」", "『": "』", "«": "»"}


def model_path() -> str:
    """当前模型目录（供界面提示与错误信息使用）"""
    return _MODEL_PATH


def torch():
    """惰性导入 torch：缺依赖时给出可读提示，而不是导入期崩溃"""
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
                "（Hy-MT2 需要 transformers>=5.6.0）") from exc
        _TRANSFORMERS = (AutoTokenizer, AutoModelForCausalLM)
    return _TRANSFORMERS


def has_safetensors(model_dir: str) -> bool:
    """模型目录内是否存在 safetensors 权重（优先使用，避免 pickle 反序列化风险）"""
    try:
        return any(name.endswith(".safetensors") for name in os.listdir(model_dir))
    except OSError:
        return False


def _trust_remote_code() -> bool:
    """是否允许加载模型自带的远程代码：默认关闭，仅在显式设置环境变量时开启"""
    return (os.environ.get("GRASS_HYMT2_TRUST_REMOTE_CODE") or "").strip().lower() in ("1", "true", "yes")


def _dtype(device: str):
    """按设备选择推理精度：GPU 优先 bfloat16，CPU 用 float32 保证数值稳定"""
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
                AutoTokenizer, AutoModelForCausalLM = transformers()
                trust = _trust_remote_code()
                load_kwargs = {"local_files_only": True, "trust_remote_code": trust}
                if has_safetensors(_MODEL_PATH):
                    load_kwargs["use_safetensors"] = True
                tokenizer = AutoTokenizer.from_pretrained(_MODEL_PATH, **load_kwargs)
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


def build_prompt(text: str, target_lang: str) -> str:
    """按官方格式拼提示词（target_lang 使用中文语言名）"""
    return PROMPT_TEMPLATE.format(target=target_lang, source=text)


def clean_output(text: str) -> str:
    """清理模型输出：去掉提示词回显、"译文："前缀和整体包裹的引号"""
    out = (text or "").strip()
    if not out:
        return ""
    out = _ECHO_RE.sub("", out, count=1).strip()
    out = _LABEL_RE.sub("", out, count=1).strip()
    if len(out) >= 2 and out[0] in _QUOTE_PAIRS and out[-1] == _QUOTE_PAIRS[out[0]]:
        out = out[1:-1].strip()
    return out


def truncate_to_max_len(text: str, tokenizer, max_len: int = MAX_INPUT_TOKENS) -> str:
    """按 token 校验并截断超长文本，防止模型静默产生乱码/空输出"""
    if not text:
        return text
    # 快速路径：字符数明显超过 token 上限时才做 tokenize 校验
    if len(text) <= max_len:
        return text
    try:
        ids = tokenizer.encode(text, add_special_tokens=False)
        if len(ids) <= max_len:
            return text
        truncated_ids = ids[:max_len]
        return tokenizer.decode(truncated_ids, skip_special_tokens=True).strip()
    except Exception:
        # tokenize 失败时退化为字符级截断，保证不产生超长输入
        return text[:max_len]


def _max_new_tokens(text: str) -> int:
    """按源文本长度估算输出上限：译文一般不会超过原文的 2 倍 token"""
    estimate = int(len(text) * 2.5) + 32
    return max(64, min(MAX_NEW_TOKENS, estimate))


def translate(text: str, target_lang: str, device: str) -> str:
    """单次翻译：显式返回译文（不含提示词与前后空白）"""
    tokenizer, model = get_model(device)
    prompt = build_prompt(text, target_lang)
    messages = [{"role": "user", "content": prompt}]
    if getattr(tokenizer, "chat_template", None):
        inputs = tokenizer.apply_chat_template(
            messages, add_generation_prompt=True, return_tensors="pt")
    else:
        # 极端情况下 tokenizer 没有 chat 模板：退化为纯文本提示
        inputs = tokenizer(prompt, return_tensors="pt")
    inputs = inputs.to(device)
    prompt_tokens = inputs["input_ids"].shape[-1]
    generate_kwargs = dict(
        max_new_tokens=_max_new_tokens(text),
        temperature=TEMPERATURE,
        top_p=TOP_P,
        top_k=TOP_K,
        repetition_penalty=REPETITION_PENALTY,
        do_sample=True,
        pad_token_id=getattr(tokenizer, "pad_token_id", None) or getattr(tokenizer, "eos_token_id", None),
    )
    with torch().no_grad():
        outputs = model.generate(**inputs, **generate_kwargs)
    new_tokens = outputs[0][prompt_tokens:]
    decoded = tokenizer.decode(new_tokens, skip_special_tokens=True)
    return clean_output(decoded)


def clear_cuda_cache(device: str) -> None:
    """推理后释放 CUDA 缓存，避免多段连续推理时显存累积"""
    if device == "cuda":
        try:
            torch().cuda.empty_cache()
        except Exception:
            pass
