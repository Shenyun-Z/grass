# -*- coding: utf-8 -*-
"""Meta M2M-100（418M）本地推理封装

模型：facebook/m2m100_418M（MIT），默认读取程序目录下的 m2m100_model/，
可用 GRASS_MODEL_PATH / HYMT2_MODEL_PATH 指定其他本地目录。

M2M-100 是编码器-解码器结构的多语言翻译模型（100 个语言代码、支持任意语言对），
翻译时必须显式指定源语言和目标语言：
  tokenizer.src_lang = 源语言代码
  generate(forced_bos_token_id=tokenizer.get_lang_id(目标语言代码))
"""
from __future__ import annotations

import hashlib
import os
import re
import shutil
import tempfile
import threading
from typing import Optional, Tuple

import langdata
import modelpath

# M2M-100 的输入上限按 512 token（position embedding 最多 1024，留余量给解码）
MAX_INPUT_TOKENS = 512
MAX_NEW_TOKENS = 512

# 采样参数：生草机要的就是模型自己的“直译味”，用贪心解码保证可复现
NUM_BEAMS = 1

_MODEL_PATH = modelpath.model_dir("m2m100")

_MODEL = None
_TOKENIZER = None
_MODEL_LOCK = threading.Lock()
_LOADED_DEVICE: Optional[str] = None

_TORCH = None
_TRANSFORMERS = None

_LANG_CODE = {name.lower(): code for name, code in langdata.M2M100_LANGS.items()}
# 清理译文外层的引号
_QUOTE_PAIRS = {'"': '"', "“": "”", "'": "'", "「": "」", "『": "』", "«": "»"}
_LABEL_RE = re.compile(r"^\s*(?:译文|翻译结果|翻译|译文如下)\s*[:：]\s*", re.I)
# M2M-100 遇到词表外词会输出 <unk>，直接去掉而不是留在译文里
_UNK_RE = re.compile(r"\s*<unk>\s*")


def model_path() -> str:
    """当前模型目录"""
    return _MODEL_PATH


def model_label() -> str:
    """界面显示用的模型名"""
    return f"M2M-100 · {os.path.basename(os.path.normpath(_MODEL_PATH))}"


def lang_code(lang_name: str) -> Optional[str]:
    """中文语言名 → M2M100 语言代码；不支持返回 None"""
    if not isinstance(lang_name, str):
        return None
    name = lang_name.strip()
    if name in langdata.M2M100_LANGS:
        return langdata.M2M100_LANGS[name]
    return _LANG_CODE.get(name.lower())


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
    """惰性导入 transformers，返回 (AutoTokenizer, AutoModelForSeq2SeqLM)"""
    global _TRANSFORMERS
    if _TRANSFORMERS is None:
        try:
            from transformers import AutoModelForSeq2SeqLM, AutoTokenizer
        except ImportError as exc:
            raise ImportError(
                "缺少依赖 transformers：请执行 pip install -r requirements.txt") from exc
        _TRANSFORMERS = (AutoTokenizer, AutoModelForSeq2SeqLM)
    return _TRANSFORMERS


# Windows 上 sentencepiece 的 C++ 实现打不开非 ASCII 路径，
# 所以分词器小文件需要镜像到纯 ASCII 的临时目录再加载（权重仍从原目录读取）
TOKENIZER_FILES = (
    "tokenizer_config.json",
    "special_tokens_map.json",
    "vocab.json",
    "sentencepiece.bpe.model",
)


def _is_ascii(path: str) -> bool:
    try:
        path.encode("ascii")
        return True
    except UnicodeEncodeError:
        return False


def ascii_tokenizer_dir(model_dir: str) -> str:
    """返回可用于加载分词器的目录：原目录纯 ASCII 就用原目录，否则返回临时镜像目录"""
    if _is_ascii(os.path.abspath(model_dir)):
        return model_dir
    digest = hashlib.sha1(os.path.abspath(model_dir).encode("utf-8")).hexdigest()[:10]
    mirror = os.path.join(tempfile.gettempdir(), "grass-m2m100-tokenizer-" + digest)
    try:
        os.makedirs(mirror, exist_ok=True)
        for name in TOKENIZER_FILES:
            src = os.path.join(model_dir, name)
            dst = os.path.join(mirror, name)
            if os.path.exists(src) and (not os.path.exists(dst)
                                        or os.path.getsize(src) != os.path.getsize(dst)):
                shutil.copyfile(src, dst)
    except OSError:
        # 复制失败就退回原目录，让加载过程报出更准确的错误
        return model_dir
    return mirror


def _quiet_transformers() -> None:
    try:
        import transformers as _tf
        _tf.utils.logging.set_verbosity_error()
        _tf.utils.logging.disable_progress_bar()
    except Exception:
        pass


def has_safetensors(model_dir: str) -> bool:
    """模型目录内是否存在 safetensors 权重"""
    try:
        return any(name.endswith(".safetensors") for name in os.listdir(model_dir))
    except OSError:
        return False


def _dtype(device: str):
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
                AutoTokenizer, AutoModelForSeq2SeqLM = transformers()
                load_kwargs = {"local_files_only": True}
                if has_safetensors(_MODEL_PATH):
                    load_kwargs["use_safetensors"] = True
                tokenizer = AutoTokenizer.from_pretrained(
                    ascii_tokenizer_dir(_MODEL_PATH), **load_kwargs)
                dtype = _dtype(device)
                try:
                    model = AutoModelForSeq2SeqLM.from_pretrained(
                        _MODEL_PATH, dtype=dtype, low_cpu_mem_usage=True, **load_kwargs)
                except TypeError:
                    model = AutoModelForSeq2SeqLM.from_pretrained(
                        _MODEL_PATH, torch_dtype=dtype, low_cpu_mem_usage=True, **load_kwargs)
                model.to(device)
                model.eval()
                _TOKENIZER, _MODEL, _LOADED_DEVICE = tokenizer, model, device
    return _TOKENIZER, _MODEL


def _lang_id(tokenizer, code: str) -> int:
    """取语言标记对应的 token id（兼容不同 transformers 版本）"""
    try:
        return tokenizer.get_lang_id(code)
    except Exception:
        pass
    mapping = getattr(tokenizer, "lang_code_to_id", None) or {}
    if code in mapping:
        return mapping[code]
    raise ValueError(f"语言代码不受支持: {code}")


def clean_output(text: str) -> str:
    """清理译文：去掉“译文：”前缀与整体包裹的引号"""
    out = (text or "").strip()
    if not out:
        return ""
    out = _LABEL_RE.sub("", out, count=1).strip()
    out = _UNK_RE.sub(" ", out).strip()
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
    estimate = int(len(text) * 2.5) + 32
    return max(32, min(MAX_NEW_TOKENS, estimate))


def translate(text: str, src_lang: str, tgt_lang: str, device: str) -> str:
    """单次翻译：src_lang / tgt_lang 传中文语言名"""
    src_code = lang_code(src_lang)
    tgt_code = lang_code(tgt_lang)
    if src_code is None or tgt_code is None:
        raise ValueError(f"不支持的语言: {src_lang} -> {tgt_lang}（M2M-100 不支持该语种）")
    tokenizer, model = get_model(device)
    tokenizer.src_lang = src_code
    inputs = tokenizer(text, return_tensors="pt", truncation=True,
                       max_length=MAX_INPUT_TOKENS).to(device)
    with torch().no_grad():
        outputs = model.generate(
            **inputs,
            forced_bos_token_id=_lang_id(tokenizer, tgt_code),
            num_beams=NUM_BEAMS,
            do_sample=False,
            max_new_tokens=_max_new_tokens(text),
            pad_token_id=getattr(tokenizer, "pad_token_id", None) or 1,
            eos_token_id=getattr(tokenizer, "eos_token_id", None) or 2,
        )
    decoded = tokenizer.decode(outputs[0], skip_special_tokens=True,
                               clean_up_tokenization_spaces=False)
    return clean_output(decoded)


def clear_cuda_cache(device: str) -> None:
    if device == "cuda":
        try:
            torch().cuda.empty_cache()
        except Exception:
            pass
