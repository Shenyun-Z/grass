# -*- coding: utf-8 -*-
"""路径：配置文件与历史记录写在程序目录（打包后即 exe 同级目录）"""
from __future__ import annotations

import os
import sys


def app_dir() -> str:
    """程序数据目录

    - 测试可用 GRASS_DATA_DIR 改写（避免污染仓库里的 history.json）
    - 源码运行：仓库根目录（与 v1.x 的 history.json / configs 位置一致）
    - 打包运行：exe 所在目录（onedir 下即 dist\\grass\\）
    """
    override = os.environ.get("GRASS_DATA_DIR")
    if override:
        os.makedirs(override, exist_ok=True)
        return override
    if getattr(sys, "frozen", False):
        return os.path.dirname(os.path.abspath(sys.executable))
    return os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
