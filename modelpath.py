# -*- coding: utf-8 -*-
"""模型目录定位（只支持 MiLMMT-46）

目录优先级：
1. 环境变量 GRASS_MODEL_PATH
2. 程序目录下的 milmmt_model/
3. 程序目录下的 model/（旧目录名，继续兼容）
4. 都没有时返回程序目录下的 milmmt_model，便于报错时给出正确路径
"""
from __future__ import annotations

import os
import sys

CANDIDATE_DIRS = ("milmmt_model", "model")
DEFAULT_DIR = "milmmt_model"


def base_dir() -> str:
    """程序所在目录：源码运行时是本文件目录，PyInstaller 打包后是 exe 所在目录"""
    if getattr(sys, "frozen", False):
        return os.path.dirname(os.path.abspath(sys.executable))
    return os.path.dirname(os.path.abspath(__file__))


def _has_config(path: str) -> bool:
    try:
        return os.path.isfile(os.path.join(path, "config.json"))
    except OSError:
        return False


def model_dir() -> str:
    """模型目录：环境变量 > 已存在的候选目录 > 默认目录名"""
    env = (os.environ.get("GRASS_MODEL_PATH") or "").strip()
    if env:
        return env
    for name in CANDIDATE_DIRS:
        path = os.path.join(base_dir(), name)
        if _has_config(path):
            return path
    return os.path.join(base_dir(), DEFAULT_DIR)
