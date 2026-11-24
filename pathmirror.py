# -*- coding: utf-8 -*-
"""Windows 上部分分词器库打不开非 ASCII 路径，这里把分词器小文件镜像到纯 ASCII 临时目录

背景：sentencepiece 的 C++ 实现直接用 fopen 打开 UTF-8 路径，Windows 下遇到
"生草机" 这类中文目录会直接报 NOT_FOUND；Rust 版 tokenizers 也同理。
处理办法：只把分词器用到的几个小文件复制到 %TEMP%/grass-tokenizer-<tag>-<hash>，
权重仍然从原模型目录读取，这样中文目录下也能正常加载。
"""
from __future__ import annotations

import hashlib
import os
import shutil
import tempfile


def is_ascii(path: str) -> bool:
    """路径是否只含 ASCII 字符"""
    try:
        path.encode("ascii")
        return True
    except UnicodeEncodeError:
        return False


def mirrored_dir(model_dir: str, files, tag: str = "tok") -> str:
    """返回可用于加载分词器的目录

    - 模型目录是纯 ASCII：直接返回原目录，不做任何复制
    - 否则把 files 里的小文件复制到临时镜像目录（按目录名做哈希，避免互相覆盖）
    - 复制失败时退回原目录，让加载过程报出更准确的错误
    """
    if is_ascii(os.path.abspath(model_dir)):
        return model_dir
    digest = hashlib.sha1(os.path.abspath(model_dir).encode("utf-8")).hexdigest()[:10]
    mirror = os.path.join(tempfile.gettempdir(), f"grass-tokenizer-{tag}-{digest}")
    try:
        os.makedirs(mirror, exist_ok=True)
        for name in files:
            src = os.path.join(model_dir, name)
            dst = os.path.join(mirror, name)
            if os.path.exists(src) and (not os.path.exists(dst)
                                        or os.path.getsize(src) != os.path.getsize(dst)):
                shutil.copyfile(src, dst)
    except OSError:
        return model_dir
    return mirror
