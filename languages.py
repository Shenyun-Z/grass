# -*- coding: utf-8 -*-
"""语言白名单（只支持 MiLMMT-46 的 46 个语种）

所有语言名都必须能在 LANG_MAP 中找到，否则配置加载与翻译调用都会被拒绝。
"""
from __future__ import annotations

import langdata

# 中文语言名 → 提示词里的官方英文名
LANG_MAP = dict(langdata.LANGS)
# 语言全量集合（顺序稳定，供随机池与界面遍历使用）
LANG_NAMES = tuple(LANG_MAP)
# 支持的语种取值集合
SUPPORTED_ABBR = frozenset(LANG_MAP.values())
# 生草机默认中转语言
DEFAULT_PIVOT_LANGS = [x for x in langdata.DEFAULT_PIVOT_LANGS if x in LANG_MAP]
# 语言分组（只保留实际支持的条目）
LANG_GROUPS = [
    (title, [x for x in langs if x in LANG_MAP])
    for title, langs in langdata.LANG_GROUPS
]
LANG_GROUPS = [(t, g) for t, g in LANG_GROUPS if g]
# 预设（裁剪成只含支持的语言）
PRESETS = {}
for _name, _langs in langdata.PRESETS.items():
    PRESETS[_name] = None if _langs is None else [x for x in _langs if x in LANG_MAP]

# 简称
ALIASES = dict(langdata.ALIASES)

_CODE_TO_NAME = {code.lower(): name for name, code in LANG_MAP.items()}


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
    """中文语言名 → 提示词里的官方英文名（不支持时返回 None）"""
    canonical = resolve(lang_name)
    if canonical is None:
        return None
    return LANG_MAP[canonical]


def is_supported(lang_name) -> bool:
    """语言是否支持"""
    return resolve(lang_name) is not None


def list_languages():
    """列出所有支持的语言（调试用）。"""
    for name, lang_code in LANG_MAP.items():
        print(f"  {name:12s} → {lang_code}")
