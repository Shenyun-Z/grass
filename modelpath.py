# -*- coding: utf-8 -*-
"""模型目录定位与后端识别

目录优先级：
1. 环境变量 GRASS_MODEL_PATH
2. 环境变量 HYMT2_MODEL_PATH（v1.6 及以前的写法，继续兼容）
3. 程序目录下依次探测 milmmt_model / hymt2_model / m2m100_model / model
4. 都没有时返回程序目录下的 milmmt_model（v1.7 起的默认）

后端识别看 model 目录里 config.json 的 architectures。
"""
from __future__ import annotations

import json
import os
import sys

CANDIDATE_DIRS = ("milmmt_model", "hymt2_model", "m2m100_model", "model")
DEFAULT_DIR_BY_KIND = {
    "milmmt": "milmmt_model",
    "hymt2": "hymt2_model",
    "m2m100": "m2m100_model",
}

_KIND_CACHE: dict = {}


def base_dir() -> str:
    """程序所在目录：源码运行时是本文件目录，PyInstaller 打包后是 exe 所在目录"""
    if getattr(sys, "frozen", False):
        return os.path.dirname(os.path.abspath(sys.executable))
    return os.path.dirname(os.path.abspath(__file__))


def _env_dir() -> str:
    for name in ("GRASS_MODEL_PATH", "HYMT2_MODEL_PATH"):
        value = (os.environ.get(name) or "").strip()
        if value:
            return value
    return ""


def _has_config(path: str) -> bool:
    try:
        return os.path.isfile(os.path.join(path, "config.json"))
    except OSError:
        return False


def discovered_dir() -> str:
    """已存在的模型目录；都没找到返回空串"""
    env = _env_dir()
    if env:
        return env
    for name in CANDIDATE_DIRS:
        path = os.path.join(base_dir(), name)
        if _has_config(path):
            return path
    return ""


def model_dir(kind: str | None = None) -> str:
    """模型目录：找到就用找到的，否则给该后端的默认目录名"""
    found = discovered_dir()
    if found:
        return found
    name = DEFAULT_DIR_BY_KIND.get(kind or "milmmt", "milmmt_model")
    return os.path.join(base_dir(), name)


def _architectures(path: str) -> list:
    try:
        with open(os.path.join(path, "config.json"), "r", encoding="utf-8") as f:
            cfg = json.load(f)
        arch = cfg.get("architectures") or []
        if isinstance(arch, str):
            arch = [arch]
        return [str(a) for a in arch]
    except (OSError, ValueError):
        return []


def kind(path: str | None = None) -> str:
    """识别模型类型：milmmt / hymt2 / m2m100 / unknown"""
    target = path or model_dir()
    key = (target, os.path.getmtime(os.path.join(target, "config.json"))
           if _has_config(target) else 0)
    if key in _KIND_CACHE:
        return _KIND_CACHE[key]
    arch = " ".join(_architectures(target)).lower()
    if "m2m100" in arch:
        result = "m2m100"
    elif "hunyuan" in arch or "hymt" in arch:
        result = "hymt2"
    elif "gemma3forcausallm" in arch or "milmmt" in arch:
        # MiLMMT-46 是 Gemma3-1B 继续训练的解码器模型
        result = "milmmt"
    else:
        result = "unknown"
    _KIND_CACHE[key] = result
    return result


def reset_cache() -> None:
    """清空识别缓存（测试用）"""
    _KIND_CACHE.clear()
