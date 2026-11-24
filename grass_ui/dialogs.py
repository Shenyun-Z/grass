# -*- coding: utf-8 -*-
"""全部弹窗（语言选择 / 排除语言 / 预设 / 翻译过程 / 删除配置 / 历史 / 切分标点）

全部改为 QDialog 实现：模态、可拉伸、按窗口宽度自动排版，
不再出现 v1.x 里「滚动容器 + 几百个控件」的卡顿。
"""
from __future__ import annotations

import random
import threading

from PySide6.QtCore import QSize, Qt, Signal
from PySide6.QtGui import QGuiApplication
from PySide6.QtWidgets import (QCheckBox, QDialog, QGridLayout, QHBoxLayout,
                               QLabel, QLineEdit, QListWidget, QListWidgetItem,
                               QPlainTextEdit, QPushButton, QScrollArea,
                               QSizePolicy, QVBoxLayout, QWidget)

from languages import LANG_GROUPS, LANG_NAMES, PRESETS

from .theme import COLORS, font, px
from .widgets import ChipFlow, Card, caption_label, chip_button, section_label

# 切分标点预设组：(组名, 包含的字符)
PUNCT_GROUPS = [
    ("逗号", "，,"),
    ("句号", "。。."),
    ("叹号", "！！"),
    ("问号", "？?"),
    ("分号", "；;"),
    ("冒号", "：:"),
    ("顿号", "、"),
]
_PRESET_CHARS = "".join(chars for _, chars in PUNCT_GROUPS)


class BaseDialog(QDialog):
    def __init__(self, parent, title: str, width: int, height: int,
                 min_width: int | None = None, min_height: int | None = None):
        super().__init__(parent)
        self.setWindowTitle(title)
        self.resize(px(width), px(height))
        if min_width and min_height:
            self.setMinimumSize(px(min_width), px(min_height))
        self.setSizeGripEnabled(True)
        self.setModal(True)


def _make_scroll() -> QScrollArea:
    scroll = QScrollArea()
    scroll.setWidgetResizable(True)
    scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
    scroll.setFrameShape(QScrollArea.NoFrame)
    return scroll


def _host() -> QWidget:
    widget = QWidget()
    widget.setObjectName("flowHost")
    return widget


class LangSelectDialog(BaseDialog):
    """语言选择：搜索 + 分组方块，点击即选中"""

    def __init__(self, parent, disabled_langs=()):
        super().__init__(parent, "选择语言", 580, 640, 420, 420)
        self.selected: str | None = None
        self._disabled = set(disabled_langs)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(px(16), px(16), px(16), px(14))
        layout.setSpacing(px(10))

        self._search = QLineEdit()
        self._search.setPlaceholderText("搜索语言...")
        self._search.setFont(font(size=10))
        self._search.textChanged.connect(lambda _t: self._rebuild())
        layout.addWidget(self._search)

        self._scroll = _make_scroll()
        layout.addWidget(self._scroll, 1)
        self._rebuild()

        footer = QHBoxLayout()
        footer.addStretch(1)
        footer.addWidget(chip_button("关闭", self.reject))
        layout.addLayout(footer)

    def _rebuild(self) -> None:
        query = self._search.text().strip().lower()
        content = _host()
        vbox = QVBoxLayout(content)
        vbox.setContentsMargins(0, 0, 0, 0)
        vbox.setSpacing(px(6))
        for group_name, langs in LANG_GROUPS:
            filtered = [lang for lang in langs if not query or query in lang.lower()]
            if not filtered:
                continue
            vbox.addWidget(caption_label(group_name))
            flow = ChipFlow()
            for lang in filtered:
                btn = chip_button(lang, lambda _checked=False, l=lang: self._pick(l))
                if lang in self._disabled:
                    btn.setEnabled(False)
                    btn.setToolTip("已用于相邻段，不能重复选择")
                flow.add_widget(btn)
            vbox.addWidget(flow)
        vbox.addStretch(1)
        self._scroll.setWidget(content)

    def _pick(self, lang: str) -> None:
        self.selected = lang
        self.accept()


class ExcludeLangDialog(BaseDialog):
    """排除语言：勾选后不进入随机池"""

    def __init__(self, parent, excluded_langs):
        super().__init__(parent, "排除语言", 640, 640, 460, 420)
        self._state = {name: name in set(excluded_langs) for name in LANG_NAMES}

        layout = QVBoxLayout(self)
        layout.setContentsMargins(px(16), px(14), px(16), px(14))
        layout.setSpacing(px(8))
        layout.addWidget(caption_label("勾选的语言将被排除在随机选池之外"))

        quick = QHBoxLayout()
        quick.addWidget(chip_button("全选", lambda: self._set_all(True)))
        quick.addWidget(chip_button("全不选", lambda: self._set_all(False)))
        quick.addStretch(1)
        layout.addLayout(quick)

        self._search = QLineEdit()
        self._search.setPlaceholderText("搜索语言...")
        self._search.setFont(font(size=10))
        self._search.textChanged.connect(lambda _t: self._rebuild())
        layout.addWidget(self._search)

        self._scroll = _make_scroll()
        layout.addWidget(self._scroll, 1)
        self._chips: dict[str, QPushButton] = {}
        self._rebuild()

        footer = QHBoxLayout()
        footer.addStretch(1)
        footer.addWidget(chip_button("确定", self._confirm, variant="primary"))
        layout.addLayout(footer)

    def _rebuild(self) -> None:
        query = self._search.text().strip().lower()
        content = _host()
        vbox = QVBoxLayout(content)
        vbox.setContentsMargins(0, 0, 0, 0)
        vbox.setSpacing(px(6))
        self._chips.clear()
        for group_name, langs in LANG_GROUPS:
            filtered = [lang for lang in langs if not query or query in lang.lower()]
            if not filtered:
                continue
            vbox.addWidget(caption_label(group_name))
            flow = ChipFlow()
            for lang in filtered:
                btn = chip_button(lang, checkable=True)
                btn.setChecked(self._state.get(lang, False))
                btn.toggled.connect(
                    lambda checked, l=lang: self._state.__setitem__(l, checked))
                flow.add_widget(btn)
                self._chips[lang] = btn
            vbox.addWidget(flow)
        vbox.addStretch(1)
        self._scroll.setWidget(content)

    def _set_all(self, value: bool) -> None:
        for lang in self._state:
            self._state[lang] = value
        for btn in self._chips.values():
            btn.blockSignals(True)
            btn.setChecked(value)
            btn.blockSignals(False)

    def _confirm(self) -> None:
        self.excluded = [name for name, checked in self._state.items() if checked]
        self.accept()


class PresetDialog(BaseDialog):
    """语言预设：预设组合 + 按地区整组套用"""

    def __init__(self, parent, rounds: int):
        super().__init__(parent, "语言预设", 700, 640, 500, 440)
        self._rounds = max(1, int(rounds))
        self.result_langs: list[str] | None = None

        layout = QVBoxLayout(self)
        layout.setContentsMargins(px(16), px(16), px(16), px(14))
        layout.setSpacing(px(10))
        layout.addWidget(section_label("快速预设"))

        quick = QHBoxLayout()
        quick.setSpacing(px(4))
        for preset_name in PRESETS:
            quick.addWidget(chip_button(
                preset_name, lambda _checked=False, n=preset_name: self._apply_preset(n)))
        quick.addStretch(1)
        layout.addLayout(quick)

        layout.addWidget(section_label("按地区选择"))
        self._scroll = _make_scroll()
        layout.addWidget(self._scroll, 1)

        content = _host()
        vbox = QVBoxLayout(content)
        vbox.setContentsMargins(0, 0, 0, 0)
        vbox.setSpacing(px(6))
        for group_name, langs in LANG_GROUPS:
            card = Card(margins=(12, 8, 12, 8), spacing=4)
            header = QHBoxLayout()
            header.addWidget(QLabel(group_name))
            header.addStretch(1)
            header.addWidget(chip_button(
                "选择", lambda _checked=False, l=langs: self._apply_langs(l)))
            card.body().addLayout(header)
            flow = ChipFlow(hspacing=4, vspacing=4)
            for lang in langs:
                lbl = QLabel(lang)
                lbl.setFont(font(size=9))
                lbl.setAlignment(Qt.AlignCenter)
                lbl.setStyleSheet(
                    f"background: {COLORS['surface_hover']};"
                    f"border: 1px solid {COLORS['border']};"
                    f"border-radius: {px(4)}px;"
                    f"padding: {px(3)}px {px(9)}px;")
                flow.add_widget(lbl)
            card.body().addWidget(flow)
            vbox.addWidget(card)
        vbox.addStretch(1)
        self._scroll.setWidget(content)

        footer = QHBoxLayout()
        footer.addStretch(1)
        footer.addWidget(chip_button("关闭", self.reject))
        layout.addLayout(footer)

    def _apply_preset(self, name: str) -> None:
        langs = PRESETS[name]
        if langs is None:
            langs = self._random_mix()
        self._fill(langs)

    def _apply_langs(self, langs) -> None:
        self._fill(langs)

    def _random_mix(self) -> list[str]:
        all_langs = []
        for _, group_langs in LANG_GROUPS:
            pool = [lang for lang in group_langs if lang != "中文"]
            if pool:
                all_langs.append(random.choice(pool))
        result: list[str] = []
        for _ in range(self._rounds):
            pool = [lang for lang in all_langs if not result or lang != result[-1]]
            if not pool:
                pool = all_langs
            result.append(random.choice(pool))
        return result

    def _fill(self, langs) -> None:
        if not langs:
            return
        self.result_langs = [langs[i % len(langs)] for i in range(self._rounds)]
        self.accept()


class StepDetailDialog(BaseDialog):
    """段翻译过程：语言链 + 每步译文 + 一键回译中文"""

    backDone = Signal(int, bool, str)

    def __init__(self, parent, seg_index: int, steps, final_lang: str):
        super().__init__(parent, f"段{seg_index + 1} 翻译过程", 820, 660, 540, 420)
        self._final_lang = final_lang
        self._rows: dict[int, tuple[QLabel, QPushButton]] = {}

        layout = QVBoxLayout(self)
        layout.setContentsMargins(px(16), px(16), px(16), px(14))
        layout.setSpacing(px(8))

        chain_langs = []
        for i, (src, _tgt, _text) in enumerate(steps):
            if i == 0:
                chain_langs.append(src)
            chain_langs.append(_tgt)
        chain = QHBoxLayout()
        chain.setSpacing(px(3))
        for j, lang in enumerate(chain_langs):
            if j > 0:
                arrow = QLabel("→")
                arrow.setStyleSheet(f"color: {COLORS['text_secondary']};")
                chain.addWidget(arrow)
            lbl = QLabel(lang)
            lbl.setFont(font(size=9))
            color = COLORS["success"] if j == len(chain_langs) - 1 else COLORS["accent"]
            lbl.setStyleSheet(f"color: {color};")
            chain.addWidget(lbl)
        chain.addStretch(1)
        chain.addWidget(chip_button("全部回译", self._back_translate_all))
        layout.addLayout(chain)

        scroll = _make_scroll()
        layout.addWidget(scroll, 1)
        content = _host()
        vbox = QVBoxLayout(content)
        vbox.setContentsMargins(0, 0, 0, 0)
        vbox.setSpacing(px(6))

        last_index = len(steps) - 1
        for i, (src, tgt, text) in enumerate(steps):
            card = Card(margins=(12, 8, 12, 8), spacing=4)
            head = QHBoxLayout()
            head.setSpacing(px(6))
            head.addWidget(caption_label(f"步骤{i + 1}"))
            src_lbl = QLabel(src)
            src_lbl.setStyleSheet(f"color: {COLORS['accent']};")
            head.addWidget(src_lbl)
            head.addWidget(QLabel("→"))
            tgt_lbl = QLabel(tgt)
            tgt_lbl.setStyleSheet(f"color: {COLORS['accent']};")
            head.addWidget(tgt_lbl)
            head.addStretch(1)
            card.body().addLayout(head)

            final = (i == last_index and tgt == final_lang)
            text_lbl = QLabel(text)
            text_lbl.setWordWrap(True)
            text_lbl.setFont(font(size=10))
            text_lbl.setTextInteractionFlags(Qt.TextSelectableByMouse)
            color = COLORS["success"] if final else COLORS["text"]
            text_lbl.setStyleSheet(f"color: {color};")
            card.body().addWidget(text_lbl)

            if tgt != "中文" and not final:
                back_row = QHBoxLayout()
                back_lbl = QLabel("")
                back_lbl.setWordWrap(True)
                back_lbl.setFont(font(size=9))
                back_lbl.setStyleSheet(f"color: {COLORS['text_secondary']};")
                back_row.addWidget(back_lbl, 1)
                back_btn = chip_button("回译中文")
                back_btn.clicked.connect(
                    lambda _checked=False, idx=i, t=text, s=src: self._back_translate(idx, t, s))
                back_row.addWidget(back_btn)
                card.body().addLayout(back_row)
                self._rows[i] = (back_lbl, back_btn)

            vbox.addWidget(card)
        vbox.addStretch(1)
        scroll.setWidget(content)

        footer = QHBoxLayout()
        footer.addStretch(1)
        footer.addWidget(chip_button("关闭", self.reject))
        layout.addLayout(footer)

        self.backDone.connect(self._on_back_done)

    def _back_translate(self, idx: int, text: str, src: str) -> None:
        row = self._rows.get(idx)
        if row is None:
            return
        label, btn = row
        btn.setEnabled(False)
        btn.setText("翻译中...")
        label.setText("⏳ 正在回译...")

        def run():
            try:
                from engine import translate_once
                result = translate_once(text, src, "中文")
                self.backDone.emit(idx, True, result)
            except Exception as exc:  # noqa: BLE001
                self.backDone.emit(idx, False, str(exc))

        threading.Thread(target=run, daemon=True).start()

    def _on_back_done(self, idx: int, ok: bool, text: str) -> None:
        row = self._rows.get(idx)
        if row is None:
            return
        label, btn = row
        if ok:
            label.setText(f"↩ {text}")
            label.setStyleSheet(f"color: {COLORS['info']};")
            btn.setText("已回译")
        else:
            label.setText(f"回译失败: {text}")
            label.setStyleSheet(f"color: {COLORS['error']};")
            btn.setText("回译中文")
            btn.setEnabled(True)

    def _back_translate_all(self) -> None:
        for idx, (_label, btn) in self._rows.items():
            if btn.isEnabled():
                btn.click()


class DeleteConfigDialog(BaseDialog):
    def __init__(self, parent, config_names):
        super().__init__(parent, "删除配置", 400, 480, 300, 260)
        self.selected: list[str] = []
        self._vars: dict[str, QCheckBox] = {}

        layout = QVBoxLayout(self)
        layout.setContentsMargins(px(16), px(16), px(16), px(14))
        layout.setSpacing(px(8))
        layout.addWidget(section_label("选择要删除的配置"))

        scroll = _make_scroll()
        layout.addWidget(scroll, 1)
        content = _host()
        vbox = QVBoxLayout(content)
        vbox.setContentsMargins(0, 0, 0, 0)
        vbox.setSpacing(px(4))
        for name in config_names:
            cb = QCheckBox(name)
            cb.setFont(font(size=10))
            self._vars[name] = cb
            vbox.addWidget(cb)
        vbox.addStretch(1)
        scroll.setWidget(content)

        row = QHBoxLayout()
        row.addWidget(chip_button("全选", lambda: self._set_all(True)))
        row.addWidget(chip_button("全不选", lambda: self._set_all(False)))
        row.addStretch(1)
        row.addWidget(chip_button("删除", self._confirm, variant="danger"))
        row.addWidget(chip_button("取消", self.reject))
        layout.addLayout(row)

    def _set_all(self, value: bool) -> None:
        for cb in self._vars.values():
            cb.setChecked(value)

    def _confirm(self) -> None:
        self.selected = [name for name, cb in self._vars.items() if cb.isChecked()]
        if self.selected:
            self.accept()


class HistoryDialog(BaseDialog):
    """历史记录：左侧列表 + 右侧详情（原文 / 结果）

    关闭后由主窗口根据 action 处理：compare（切到对照）/ changed（列表有增删）
    """

    def __init__(self, parent, history):
        super().__init__(parent, "历史记录", 980, 660, 740, 460)
        self._history = history       # 与主窗口共享同一个列表对象
        self._selected_id: int | None = None
        self.action: str | None = None
        self.target_id: int | None = None

        layout = QVBoxLayout(self)
        layout.setContentsMargins(px(16), px(14), px(16), px(14))
        layout.setSpacing(px(8))

        header = QHBoxLayout()
        self._count = section_label("")
        header.addWidget(self._count)
        header.addStretch(1)
        header.addWidget(chip_button("清空历史", self._clear, variant="danger"))
        layout.addLayout(header)

        body = QHBoxLayout()
        body.setSpacing(px(10))
        self._list = QListWidget()
        self._list.setFixedWidth(px(300))
        self._list.setFont(font(size=10))
        self._list.setWordWrap(True)
        self._list.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        self._list.setSpacing(px(2))
        self._list.currentRowChanged.connect(self._on_row_changed)
        body.addWidget(self._list)

        detail_card = Card(margins=(12, 10, 12, 10), spacing=6)
        detail_card.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        self._detail_layout = detail_card.body()
        body.addWidget(detail_card, 1)
        layout.addLayout(body, 1)

        self._rebuild()
        self._show_placeholder()

    # --- 列表 ---
    def _rebuild(self) -> None:
        self._count.setText(f"历史记录（{len(self._history)}）")
        self._list.blockSignals(True)
        self._list.clear()
        for rec in reversed(self._history):
            mark = " ⏹" if rec.get("stopped") else ""
            summary = (rec.get("input") or "").replace("\n", " ")
            if len(summary) > 24:
                summary = summary[:24] + "…"
            item = QListWidgetItem(f"#{rec['id']}  {rec['date']} {rec['time']}{mark}\n{summary}")
            item.setData(Qt.UserRole, rec["id"])
            item.setSizeHint(QSize(0, px(46)))
            self._list.addItem(item)
        self._list.blockSignals(False)
        if not self._history:
            self._selected_id = None

    def _current_record(self) -> dict | None:
        item = self._list.currentItem()
        if item is None:
            return None
        rec_id = item.data(Qt.UserRole)
        return next((r for r in self._history if r["id"] == rec_id), None)

    def _on_row_changed(self, _row: int) -> None:
        rec = self._current_record()
        if rec is not None:
            self._selected_id = rec["id"]
            self._show_detail(rec)

    # --- 详情 ---
    def _clear_detail(self) -> None:
        while self._detail_layout.count():
            item = self._detail_layout.takeAt(0)
            widget = item.widget() if item else None
            if widget is not None:
                widget.setParent(None)
                widget.deleteLater()
            elif item is not None and item.layout() is not None:
                self._clear_layout(item.layout())

    def _clear_layout(self, layout) -> None:
        while layout.count():
            item = layout.takeAt(0)
            widget = item.widget() if item else None
            if widget is not None:
                widget.setParent(None)
                widget.deleteLater()
            elif item is not None and item.layout() is not None:
                self._clear_layout(item.layout())

    def _show_placeholder(self) -> None:
        self._clear_detail()
        label = QLabel("← 选择一条记录查看详情")
        label.setStyleSheet(f"color: {COLORS['text_secondary']};")
        self._detail_layout.addWidget(label, 1, Qt.AlignCenter)

    def _show_detail(self, rec: dict) -> None:
        self._clear_detail()
        params = rec.get("params", {})
        stopped = " · 已停止" if rec.get("stopped") else ""
        info = (f"#{rec['id']} · {rec['date']} {rec['time']} · "
                f"{params.get('rounds', '-')}轮 {params.get('mode', '-')} · "
                f"译回{params.get('final', '-')} · 段字数{params.get('threshold', '-')}{stopped}")
        if rec.get("elapsed"):
            info += f" · 耗时{rec['elapsed']}"
        self._detail_layout.addWidget(caption_label(info))

        self._detail_layout.addWidget(caption_label("原文"))
        src = QPlainTextEdit(rec.get("input") or "（空）")
        src.setReadOnly(True)
        src.setFont(font(size=10))
        src.setMaximumHeight(px(120))
        self._detail_layout.addWidget(src)

        self._detail_layout.addWidget(caption_label("结果"))
        res = QPlainTextEdit(rec.get("result") or "（空）")
        res.setReadOnly(True)
        res.setFont(font(size=10))
        self._detail_layout.addWidget(res, 1)

        row = QHBoxLayout()
        copy_btn = chip_button("复制结果", lambda: self._copy(rec))
        compare_btn = chip_button("对照查看", lambda: self._compare(rec))
        delete_btn = chip_button("删除此条", lambda: self._delete(rec), variant="danger")
        row.addWidget(copy_btn)
        row.addWidget(compare_btn)
        row.addStretch(1)
        row.addWidget(delete_btn)
        self._detail_layout.addLayout(row)

    # --- 操作 ---
    def _copy(self, rec: dict) -> None:
        QGuiApplication.clipboard().setText(rec.get("result") or "")

    def _compare(self, rec: dict) -> None:
        self.action = "compare"
        self.target_id = rec["id"]
        self.accept()

    def _delete(self, rec: dict) -> None:
        self._history[:] = [r for r in self._history if r["id"] != rec["id"]]
        self.action = "changed"
        self._selected_id = None
        self._rebuild()
        self._show_placeholder()

    def _clear(self) -> None:
        if not self._history:
            return
        self._history.clear()
        self.action = "changed"
        self._selected_id = None
        self._rebuild()
        self._show_placeholder()


class SplitPunctDialog(BaseDialog):
    """切分标点：预设分组勾选 + 自定义分隔符"""

    def __init__(self, parent, puncts: str):
        super().__init__(parent, "切分标点设置", 520, 540, 460, 480)
        self.puncts = ""
        selected = set(puncts or "")
        self._vars: list[tuple[QCheckBox, str]] = []

        layout = QVBoxLayout(self)
        layout.setContentsMargins(px(16), px(14), px(16), px(14))
        layout.setSpacing(px(8))
        hint = caption_label("分段时累计达到「段字数」阈值后，在最近的一个所选标点处切分。")
        hint.setWordWrap(True)
        layout.addWidget(hint)

        grid = QGridLayout()
        grid.setSpacing(px(4))
        for i, (name, chars) in enumerate(PUNCT_GROUPS):
            cb = QCheckBox(f"{name} {''.join(chars)}")
            cb.setFont(font(size=9))
            cb.setChecked(set(chars).issubset(selected))
            cb.toggled.connect(lambda _c: self._update_preview())
            self._vars.append((cb, chars))
            grid.addWidget(cb, i // 4, i % 4)
        layout.addLayout(grid)

        quick = QHBoxLayout()
        quick.addWidget(chip_button("全选", lambda: self._apply_preset("all")))
        quick.addWidget(chip_button("仅逗号句号", lambda: self._apply_preset("common")))
        quick.addWidget(chip_button("全不选", lambda: self._apply_preset("none")))
        quick.addStretch(1)
        layout.addLayout(quick)

        layout.addWidget(caption_label("自定义分隔符（额外字符，如 | ~ ·）"))
        self._custom = QLineEdit()
        custom = "".join(c for c in (puncts or "") if c not in _PRESET_CHARS)
        self._custom.setText(custom)
        self._custom.setFont(font(size=10))
        self._custom.textChanged.connect(lambda _t: self._update_preview())
        layout.addWidget(self._custom)

        self._preview = QLabel("")
        self._preview.setWordWrap(True)
        self._preview.setFont(font(size=9))
        self._preview.setStyleSheet(f"color: {COLORS['accent']};")
        layout.addWidget(self._preview)
        layout.addStretch(1)

        row = QHBoxLayout()
        row.addStretch(1)
        row.addWidget(chip_button("取消", self.reject))
        row.addWidget(chip_button("确定", self._confirm, variant="primary"))
        layout.addLayout(row)

        self._update_preview()

    def _apply_preset(self, kind: str) -> None:
        if kind == "all":
            values = [True] * len(self._vars)
        elif kind == "common":
            values = [chars[0] in "，。" for _cb, chars in self._vars]
        else:
            values = [False] * len(self._vars)
        for (cb, _chars), value in zip(self._vars, values):
            cb.blockSignals(True)
            cb.setChecked(value)
            cb.blockSignals(False)
        self._update_preview()

    def _collect(self) -> str:
        chars: list[str] = []
        for cb, group_chars in self._vars:
            if cb.isChecked():
                chars.extend(group_chars)
        chars.extend(self._custom.text())
        seen = set()
        out = []
        for ch in chars:
            if ch and ch not in seen:
                seen.add(ch)
                out.append(ch)
        return "".join(out)

    def _update_preview(self) -> None:
        value = self._collect()
        if value:
            self._preview.setText(f"当前生效分隔符（{len(value)} 个）：{value}")
        else:
            self._preview.setText("当前未选择任何标点：仅在超过 2 倍段字数时按阈值硬切")

    def _confirm(self) -> None:
        self.puncts = self._collect()
        self.accept()
