# -*- coding: utf-8 -*-
"""语言白名单（按当前后端自动切换）

v1.7 起同时支持两种后端，语言集合随模型自动变化：
- M2M100（默认）：78 个常用语种（无繁体中文 / 粤语 / 藏语 / 维吾尔语）
- Hy-MT2：38 个语种/变体

所有语言名都必须能在当前 LANG_MAP 中找到，否则配置加载与翻译调用都会被拒绝。
"""
from __future__ import annotations

import modelpath
from langdata import (
    COMMON_ALIASES,
    DEFAULT_PIVOT_BY_BACKEND,
    GROUPS_BY_BACKEND,
    HYMT2_ONLY_ALIASES,
    LANGS_BY_BACKEND,
    PRESETS_BY_BACKEND,
)

DEFAULT_BACKEND = "m2m100"


def current_backend() -> str:
    """当前生效的后端（按模型目录的 architectures 判断，识别失败退 M2M100）"""
    try:
        detected = modelpath.kind()
    except Exception:
        detected = "unknown"
    return detected if detected in LANGS_BY_BACKEND else DEFAULT_BACKEND


_BACKEND = current_backend()

# 中文语言名 → 语言代码（当前后端）
LANG_MAP = dict(LANGS_BY_BACKEND[_BACKEND])
# 语言全量集合（顺序稳定，供随机池与界面遍历使用）
LANG_NAMES = tuple(LANG_MAP)
# 当前后端支持的语种缩写集合
SUPPORTED_ABBR = frozenset(LANG_MAP.values())
# 生草机默认中转语言
DEFAULT_PIVOT_LANGS = [x for x in DEFAULT_PIVOT_BY_BACKEND[_BACKEND] if x in LANG_MAP]
# 语言分组（只保留当前后端支持的条目）
LANG_GROUPS = [
    (title, [x for x in langs if x in LANG_MAP])
    for title, langs in GROUPS_BY_BACKEND[_BACKEND]
]
LANG_GROUPS = [(t, g) for t, g in LANG_GROUPS if g]
# 预设（裁剪成只含当前后端支持的语言）
PRESETS = {}
for _name, _langs in PRESETS_BY_BACKEND[_BACKEND].items():
    PRESETS[_name] = None if _langs is None else [x for x in _langs if x in LANG_MAP]

# 简称
ALIASES = dict(COMMON_ALIASES)
if _BACKEND == "hymt2":
    ALIASES.update(HYMT2_ONLY_ALIASES)

_CODE_TO_NAME = {code.lower(): name for name, code in LANG_MAP.items()}


def backend() -> str:
    """当前后端类型（hymt2 / m2m100）"""
    return _BACKEND


def resolve(lang_name) -> "str | None":
    """解析语言名：支持全称、简称、语言代码。返回规范中文名，非法时返回 None。"""
    if not isinstance(lang_name, str):
        return None
    name = lang_name.strip()
    if name in LANG_MAP:
        return name
    alias = ALIASES.get(name)
    if alias and alias in LANG_MAP:
        return alias
    code_name = _CODE_TO_NAME.get(name.lower())
    if code_name:
        return code_name
    return None


def code(lang_name) -> "str | None":
    """中文语言名 → 语言代码（不支持时返回 None）"""
    canonical = resolve(lang_name)
    if canonical is None:
        return None
    return LANG_MAP[canonical]


def is_supported(lang_name) -> bool:
    """语言是否在当前后端支持范围内"""
    return resolve(lang_name) is not None


def list_languages():
    """列出所有支持的语言（调试用）。"""
    for name, lang_code in LANG_MAP.items():
        print(f"  {name:12s} → {lang_code}   [{_BACKEND}]")
