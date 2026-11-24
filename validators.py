# -*- coding: utf-8 -*-
"""输入校验与安全辅助函数

本模块不依赖 GUI 与 torch，便于在无显示/无模型环境下做单元测试。
负责：配置名消毒、历史记录规整、文本文件安全读取、原子写入、表格公式注入转义。
"""
import json
import os
import re
import tempfile

# 单个文本文件的读取上限（防止误选超大文件导致界面卡死）
MAX_INPUT_BYTES = 8 * 1024 * 1024
# 配置名长度上限
MAX_CONFIG_NAME_LEN = 40
# Windows / POSIX 路径分隔符与文件名非法字符
_ILLEGAL_NAME_CHARS = set('\\/:*?"<>|\r\n\t')
_CONTROL_CHARS = re.compile(r"[\x00-\x1f\x7f]")
# 会触发 Excel/CSV 公式解释的前缀字符
_FORMULA_PREFIXES = ("=", "+", "-", "@", "\t", "\r")
# 历史记录中必须存在的字段类型
_STR_FIELDS = ("date", "time", "input", "result", "elapsed")


# ===== 配置名 =====
def sanitize_config_name(name):
    """把用户输入的配置名转成安全的文件名主干

    拒绝空名、路径分隔符、控制字符、`.` / `..`、首尾点号与超长名称；
    非法时返回 None，由调用方提示用户。
    """
    if not isinstance(name, str):
        return None
    cleaned = _CONTROL_CHARS.sub("", name).strip()
    if not cleaned:
        return None
    if any(c in _ILLEGAL_NAME_CHARS for c in cleaned):
        return None
    if cleaned in (".", "..") or cleaned.startswith("."):
        return None
    if len(cleaned) > MAX_CONFIG_NAME_LEN:
        return None
    return cleaned


# ===== 数值钳制 =====
def coerce_int(value, default):
    """尽力把任意输入转成 int；失败返回 default（bool 不算有效整数）"""
    if isinstance(value, bool):
        return default
    try:
        return int(value)
    except (TypeError, ValueError):
        return default


def clamp_rounds(value, default=10):
    """中转轮数：合法区间 1-30"""
    return max(1, min(30, coerce_int(value, default)))


def clamp_threshold(value, default=20):
    """每段字数：合法区间 5-100"""
    return max(5, min(100, coerce_int(value, default)))


# ===== 文本文件读取 =====
def read_text_file(path, max_bytes=MAX_INPUT_BYTES):
    """安全读取文本文件

    Raises:
        ValueError: 文件过大、不是普通文件、或无法按 UTF-8/GBK 解码
        OSError: 文件不存在或无读取权限
    """
    if not os.path.isfile(path):
        raise ValueError("目标不是普通文件")
    size = os.path.getsize(path)
    if size > max_bytes:
        raise ValueError(f"文件过大（{size / 1024 / 1024:.1f} MB），上限 {max_bytes // 1024 / 1024:.0f} MB")
    with open(path, "rb") as f:
        raw = f.read()
    for encoding in ("utf-8-sig", "gbk"):
        try:
            return raw.decode(encoding)
        except UnicodeDecodeError:
            continue
    raise ValueError("无法识别文件编码（仅支持 UTF-8 / GBK 文本）")


# ===== 原子写入 =====
def atomic_write_text(path, text, encoding="utf-8"):
    """先写临时文件再整体替换，避免中途失败留下半截文件"""
    directory = os.path.dirname(os.path.abspath(path)) or "."
    fd, tmp_path = tempfile.mkstemp(dir=directory, prefix=".tmp-", suffix=".part")
    try:
        with os.fdopen(fd, "w", encoding=encoding) as f:
            f.write(text)
        os.replace(tmp_path, path)
    except Exception:
        try:
            os.remove(tmp_path)
        except OSError:
            pass
        raise


# ===== 表格公式注入 =====
def escape_spreadsheet_cell(value):
    """转义会被 Excel 当作公式执行的单元格

    以 = + - @ 或制表符/回车开头的内容前置单引号，避免 CSV/Excel 公式注入
    （openpyxl 会把 `=` 开头的字符串写成公式）。
    """
    if not isinstance(value, str) or not value:
        return value
    if value.startswith(_FORMULA_PREFIXES):
        return "'" + value
    return value


# ===== 历史记录 =====
def _normalize_seg_map(value):
    """JSON 对象的键一定是字符串，这里还原成 int 键，否则重启后对照视图取不到值"""
    if not isinstance(value, dict):
        return {}
    out = {}
    for key, item in value.items():
        idx = coerce_int(key, None)
        if idx is None or idx < 0:
            continue
        if isinstance(item, str):
            out[idx] = item
    return out


def _normalize_steps(value):
    """规整 seg_steps：{段号: [(源语言, 目标语言, 文本), ...]}"""
    if not isinstance(value, dict):
        return {}
    out = {}
    for key, steps in value.items():
        idx = coerce_int(key, None)
        if idx is None or idx < 0 or not isinstance(steps, list):
            continue
        normalized = []
        for step in steps:
            if isinstance(step, (list, tuple)) and len(step) == 3:
                normalized.append(tuple(str(x) for x in step))
        if normalized:
            out[idx] = normalized
    return out


def normalize_history(records, limit=20):
    """校验并规整历史记录，丢弃结构损坏的条目

    手改或旧版本写入的 history.json 可能出现缺字段、键类型错误、id 重复等问题，
    直接使用会让历史弹窗抛 KeyError。这里统一兜底成可用结构。
    """
    if not isinstance(records, list):
        return []
    valid = []
    by_id = {}
    for index, rec in enumerate(records):
        if not isinstance(rec, dict):
            continue
        rec_id = coerce_int(rec.get("id"), None)
        if rec_id is None or rec_id < 0:
            continue
        clean = {"id": rec_id}
        ok = True
        for field in _STR_FIELDS:
            value = rec.get(field, "")
            if value is None:
                value = ""
            if not isinstance(value, str):
                ok = False
                break
            clean[field] = value
        if not ok:
            continue
        segments = rec.get("segments", [])
        if isinstance(segments, list):
            clean["segments"] = [s for s in segments if isinstance(s, str)]
        else:
            clean["segments"] = []
        clean["seg_results"] = _normalize_seg_map(rec.get("seg_results"))
        clean["seg_steps"] = _normalize_steps(rec.get("seg_steps"))
        params = rec.get("params")
        if isinstance(params, dict):
            clean["params"] = {
                "rounds": clamp_rounds(params.get("rounds"), 10),
                "mode": params.get("mode") if isinstance(params.get("mode"), str) else "-",
                "langs": [l for l in params.get("langs", []) if isinstance(l, str)]
                if isinstance(params.get("langs"), list) else [],
                "final": params.get("final") if isinstance(params.get("final"), str) else "中文",
                "threshold": clamp_threshold(params.get("threshold"), 20),
                "split_puncts": params.get("split_puncts")
                if isinstance(params.get("split_puncts"), str) else "",
            }
        else:
            clean["params"] = {"rounds": 10, "mode": "-", "langs": [], "final": "中文",
                               "threshold": 20, "split_puncts": ""}
        clean["stopped"] = bool(rec.get("stopped", False))
        # 同 id 重复时以较新的（靠后的）记录为准
        if rec_id in by_id:
            valid[by_id[rec_id]] = None
        by_id[rec_id] = len(valid)
        valid.append(clean)
    valid = [r for r in valid if r is not None]
    return valid[-limit:] if limit and limit > 0 else valid


def next_history_id(records):
    """返回下一个可用记录号（空列表时从 1 开始）"""
    ids = [r["id"] for r in records if isinstance(r.get("id"), int)]
    return (max(ids) + 1) if ids else 1


def dump_history(records):
    """序列化为 JSON 文本（保证 int 键在写出时按字符串落盘，读回由 normalize 还原）"""
    return json.dumps(records, ensure_ascii=False, indent=2)
