# -*- coding: utf-8 -*-
"""主窗口的各个功能面板（输入 / 参数 / 语言 / 分块预览 / 控制 / 进度 / 结果）"""
from __future__ import annotations

from PySide6.QtCore import QEasingCurve, Qt, QTimer, QVariantAnimation, Signal
from PySide6.QtWidgets import (QCheckBox, QComboBox, QFrame, QHBoxLayout, QLabel,
                               QPlainTextEdit, QProgressBar, QPushButton,
                               QScrollArea, QSizePolicy, QStackedWidget,
                               QToolButton, QVBoxLayout, QWidget)

from .splitview import CardDelegate, CompareModel, SegmentModel, VirtualCardsView
from .theme import COLORS, font, px
from .widgets import (Card, FlowLayout, GripHandle, SegmentedControl, caption_label,
                      chip_button, section_label)


def _tool_arrow() -> QToolButton:
    btn = QToolButton()
    btn.setText("▼")
    btn.setFont(font(size=9))
    btn.setCursor(Qt.PointingHandCursor)
    btn.setFixedWidth(px(18))
    btn.setAutoRaise(True)
    return btn


class InputTextEdit(QPlainTextEdit):
    """输入框：接受 .txt 拖放"""

    fileDropped = Signal(str)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setAcceptDrops(True)
        self.setPlaceholderText("在此输入待翻译的文本，或把 .txt 文件拖到这里…")
        self.setTabChangesFocus(True)
        self.setFont(font(size=10))

    def dragEnterEvent(self, event) -> None:
        urls = event.mimeData().urls() if event.mimeData().hasUrls() else []
        paths = [u.toLocalFile() for u in urls]
        if any(p.lower().endswith(".txt") for p in paths):
            event.acceptProposedAction()
        else:
            event.ignore()

    def dragMoveEvent(self, event) -> None:
        event.acceptProposedAction()

    def dropEvent(self, event) -> None:
        paths = [u.toLocalFile() for u in event.mimeData().urls()]
        candidates = [p for p in paths if p.lower().endswith(".txt")]
        if candidates:
            self.fileDropped.emit(candidates[0])
            event.acceptProposedAction()
        else:
            event.ignore()


class InputPane(Card):
    textChanged = Signal()
    viewModeChanged = Signal(str)
    fileDropped = Signal(str)
    loadClicked = Signal()
    clipboardClicked = Signal()

    BOX_MIN = 60
    BOX_MAX = 400

    def __init__(self, parent=None):
        super().__init__(parent)
        self._collapsed = False
        self._box_height = px(120)

        header = QHBoxLayout()
        header.setSpacing(px(6))
        self._arrow = _tool_arrow()
        self._arrow.clicked.connect(self._toggle)
        header.addWidget(self._arrow)
        header.addWidget(section_label("输入"))
        header.addStretch(1)
        self._mode = SegmentedControl(["原文", "去空格"], "原文")
        self._mode.changed.connect(self.viewModeChanged.emit)
        header.addWidget(self._mode)
        self.body().addLayout(header)

        self._box = InputTextEdit()
        self._box.setFixedHeight(self._box_height)
        self._box.textChanged.connect(self.textChanged.emit)
        self._box.fileDropped.connect(self.fileDropped.emit)
        self.body().addWidget(self._box)

        self._actions = QWidget()
        self._actions.setObjectName("rowHost")
        row = QHBoxLayout(self._actions)
        row.setContentsMargins(0, 0, 0, 0)
        row.setSpacing(px(6))
        self._load_btn = chip_button("从文件读取", self.loadClicked.emit)
        self._paste_btn = chip_button("读剪贴板", self.clipboardClicked.emit)
        row.addWidget(self._load_btn)
        row.addWidget(self._paste_btn)
        row.addStretch(1)
        self._hint = caption_label("可拖放 .txt  ·  Ctrl+Shift+V 读入剪贴板")
        row.addWidget(self._hint)
        self._count = caption_label("字符数: 0")
        row.addWidget(self._count)
        self.body().addWidget(self._actions)

        self._grip = GripHandle()
        self._grip.deltaDragged.connect(self._on_grip)
        self.body().addWidget(self._grip)

    # --- 状态 ---
    def text(self) -> str:
        return self._box.toPlainText()

    def set_text(self, text: str) -> None:
        blocked = self._box.blockSignals(True)
        self._box.setPlainText(text)
        self._box.blockSignals(blocked)

    def set_char_count(self, n: int) -> None:
        self._count.setText(f"字符数: {n}")

    def set_view_mode(self, mode: str, emit: bool = False) -> None:
        self._mode.set_current(mode, emit=emit)

    def view_mode(self) -> str:
        return self._mode.current()

    def _toggle(self) -> None:
        self._collapsed = not self._collapsed
        self._arrow.setText("▶" if self._collapsed else "▼")
        self._box.setVisible(not self._collapsed)
        self._actions.setVisible(not self._collapsed)
        self._grip.setVisible(not self._collapsed)

    def is_collapsed(self) -> bool:
        return self._collapsed

    def _on_grip(self, delta: int) -> None:
        new_h = max(px(self.BOX_MIN), min(px(self.BOX_MAX), self._box_height + delta))
        self._box_height = new_h
        self._box.setFixedHeight(new_h)

    def set_enabled_state(self, enabled: bool) -> None:
        self._mode.set_enabled(enabled)
        self._box.setReadOnly(not enabled)
        for w in (self._load_btn, self._paste_btn):
            w.setEnabled(enabled)


class ParamsPane(Card):
    roundsChanged = Signal(int)
    thresholdChanged = Signal(int)
    finalLangClicked = Signal()
    randomModeChanged = Signal(str)
    excludeClicked = Signal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self.body().addWidget(section_label("参数"))

        row = QHBoxLayout()
        row.setSpacing(px(6))
        row.addWidget(caption_label("轮数"))
        self._rounds = QComboBox()
        for i in range(1, 31):
            self._rounds.addItem(str(i), i)
        self._rounds.setFixedWidth(px(60))
        self._rounds.setCurrentIndex(self._rounds.findData(10))
        self._rounds.currentIndexChanged.connect(self._on_rounds)

        row.addWidget(self._rounds)

        row.addSpacing(px(8))
        row.addWidget(caption_label("段字数"))
        self._threshold = QComboBox()
        for i in range(5, 101, 5):
            self._threshold.addItem(str(i), i)
        self._threshold.setFixedWidth(px(60))
        self._threshold.setCurrentIndex(self._threshold.findData(20))
        self._threshold.currentIndexChanged.connect(self._on_threshold)
        row.addWidget(self._threshold)

        row.addSpacing(px(8))
        row.addWidget(caption_label("译回"))
        self._final_btn = chip_button("中文", self.finalLangClicked.emit)
        self._final_btn.setProperty("variant", "primary")
        self._final_btn.style().unpolish(self._final_btn)
        self._final_btn.style().polish(self._final_btn)
        row.addWidget(self._final_btn)

        row.addStretch(1)
        self._exclude = chip_button("排除语言...", self.excludeClicked.emit)
        row.addWidget(self._exclude)
        self._random = SegmentedControl(["固定", "低强度", "高强度"], "固定")
        self._random.changed.connect(self.randomModeChanged.emit)
        row.addWidget(self._random)

        self.body().addLayout(row)

    def _on_rounds(self, _index: int) -> None:
        self.roundsChanged.emit(self.rounds())

    def _on_threshold(self, _index: int) -> None:
        self.thresholdChanged.emit(self.threshold())

    # --- 取值 ---
    def rounds(self) -> int:
        return int(self._rounds.currentData() or 10)

    def threshold(self) -> int:
        return int(self._threshold.currentData() or 20)

    def final_lang(self) -> str:
        return self._final_btn.text()

    def random_mode(self) -> str:
        return self._random.current()

    # --- 设值 ---
    def set_rounds(self, n: int, emit: bool = False) -> None:
        index = self._rounds.findData(n)
        if index < 0:
            index = self._rounds.findText(str(n))
        if index >= 0:
            blocked = self._rounds.blockSignals(not emit)
            self._rounds.setCurrentIndex(index)
            self._rounds.blockSignals(blocked)

    def set_threshold(self, n: int) -> None:
        index = self._threshold.findData(n)
        if index < 0:
            index = self._threshold.findText(str(n))
        if index >= 0:
            blocked = self._threshold.blockSignals(True)
            self._threshold.setCurrentIndex(index)
            self._threshold.blockSignals(blocked)

    def set_final_lang(self, lang: str) -> None:
        self._final_btn.setText(lang)

    def set_random_mode(self, mode: str, emit: bool = False) -> None:
        self._random.set_current(mode, emit=emit)

    def set_enabled_state(self, enabled: bool, fixed_mode: bool = True) -> None:
        self._rounds.setEnabled(enabled)
        self._threshold.setEnabled(enabled)
        self._final_btn.setEnabled(enabled)
        self._random.set_enabled(enabled)
        self._exclude.setEnabled(enabled and not fixed_mode)

    def set_exclude_enabled(self, enabled: bool) -> None:
        self._exclude.setEnabled(enabled)


class FlowHost(QWidget):
    """FlowLayout 宿主：负责按宽度返回高度"""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setObjectName("flowHost")
        self.flow = FlowLayout(self, margin=0, hspacing=6, vspacing=6)
        self.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Preferred)

    def height_for_width(self, width: int) -> int:
        return self.flow.heightForWidth(width)

    def hasHeightForWidth(self) -> bool:
        return True

    def sizeHint(self):
        from PySide6.QtCore import QSize
        width = self.width() or 600
        return QSize(width, self.height_for_width(width))


class LangsPane(Card):
    langClicked = Signal(int)
    presetClicked = Signal()
    exportClicked = Signal()
    importClicked = Signal()
    configAction = Signal(str)

    MAX_HEIGHT = 190
    MIN_HEIGHT = 60

    def __init__(self, parent=None):
        super().__init__(parent)

        header = QHBoxLayout()
        header.setSpacing(px(6))
        header.addWidget(section_label("中转语言"))
        header.addStretch(1)

        self._config = QComboBox()
        self._config.setFixedWidth(px(140))
        self._config.activated.connect(self._on_config_activated)
        self._config_menu_items: list[str] = []
        header.addWidget(self._config)

        self._import_btn = chip_button("导入", self.importClicked.emit)
        self._export_btn = chip_button("导出", self.exportClicked.emit)
        self._preset_btn = chip_button("语言预设...", self.presetClicked.emit)
        self._export_btn.setFont(font(size=9))
        self._import_btn.setFont(font(size=9))
        header.addWidget(self._export_btn)
        header.addWidget(self._import_btn)
        header.addWidget(self._preset_btn)
        self.body().addLayout(header)

        self._chain = QLabel("")
        self._chain.setObjectName("chain")
        self._chain.setWordWrap(True)
        self._chain.setFont(font(size=10))
        self.body().addWidget(self._chain)

        self._scroll = QScrollArea()
        self._scroll.setWidgetResizable(True)
        self._scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        self._scroll.setFrameShape(QFrame.NoFrame)
        self._scroll.setMinimumHeight(px(self.MIN_HEIGHT))
        self._scroll.setMaximumHeight(px(self.MAX_HEIGHT))
        self._host = FlowHost()
        self._scroll.setWidget(self._host)
        self.body().addWidget(self._scroll)

        self._langs: list[str] = []
        self._buttons: list[QPushButton] = []
        self._last_width = 0
        self._height_timer = QTimer(self)
        self._height_timer.setSingleShot(True)
        self._height_timer.setInterval(0)
        self._height_timer.timeout.connect(self._refresh_height)

        self._langs: list[str] = []
        self._buttons: list[QPushButton] = []
        self._last_width = 0

    # --- 数据 ---
    def set_langs(self, langs: list[str]) -> None:
        self._langs = list(langs)
        self._rebuild()

    def langs(self) -> list[str]:
        return [b.text() for b in self._buttons]

    def set_lang_text(self, index: int, lang: str) -> None:
        if 0 <= index < len(self._buttons):
            self._buttons[index].setText(lang)
            if index < len(self._langs):
                self._langs[index] = lang
        self._refresh_height(force=True)

    def set_chain(self, text: str) -> None:
        self._chain.setText(text)

    def set_config_names(self, names: list[str], current: str = "配置") -> None:
        self._config_menu_items = list(names)
        blocked = self._config.blockSignals(True)
        self._config.clear()
        for name in names:
            self._config.addItem(name, name)
        index = self._config.findText(current)
        self._config.setCurrentIndex(index if index >= 0 else 0)
        self._config.blockSignals(blocked)

    def set_config_current(self, name: str) -> None:
        blocked = self._config.blockSignals(True)
        index = self._config.findText(name)
        if index >= 0:
            self._config.setCurrentIndex(index)
        self._config.blockSignals(blocked)

    def _on_config_activated(self, index: int) -> None:
        if 0 <= index < len(self._config_menu_items):
            self.configAction.emit(self._config_menu_items[index])

    # --- 重建 ---
    def _rebuild(self) -> None:
        while self._host.flow.count():
            item = self._host.flow.takeAt(0)
            widget = item.widget() if item else None
            if widget is not None:
                widget.setParent(None)
                widget.deleteLater()
        self._buttons.clear()
        for i, lang in enumerate(self._langs):
            row_widget = QWidget()
            row_widget.setObjectName("rowHost")
            row = QHBoxLayout(row_widget)
            row.setContentsMargins(0, 0, 0, 0)
            row.setSpacing(px(3))
            num = QLabel(f"{i + 1}.")
            num.setFont(font(size=10))
            num.setStyleSheet(f"color: {COLORS['text_secondary']};")
            num.setFixedWidth(px(22))
            row.addWidget(num)
            btn = chip_button(lang, lambda _=False, idx=i: self.langClicked.emit(idx))
            btn.setFixedWidth(px(104))
            row.addWidget(btn)
            arrow = QLabel("→")
            arrow.setStyleSheet(f"color: {COLORS['text_secondary']};")
            row.addWidget(arrow)
            self._buttons.append(btn)
            self._host.flow.addWidget(row_widget)
        self._refresh_height(force=True)

    def _refresh_height(self, force: bool = False) -> None:
        width = self._host.width() or self._scroll.viewport().width() or 600
        if not force and abs(width - self._last_width) < 2 and self._last_width:
            return
        self._last_width = width
        content_h = self._host.height_for_width(width) + px(4)
        target = max(px(self.MIN_HEIGHT), min(px(self.MAX_HEIGHT), content_h))
        if self._scroll.height() != target:
            self._scroll.setFixedHeight(target)
            self._host.updateGeometry()

    def resizeEvent(self, event) -> None:
        super().resizeEvent(event)
        self._height_timer.start()

    def set_state(self, enabled: bool, fixed_mode: bool = True) -> None:
        self._config.setEnabled(enabled)
        self._export_btn.setEnabled(enabled)
        self._import_btn.setEnabled(enabled)
        self._preset_btn.setEnabled(enabled and fixed_mode)
        for btn in self._buttons:
            btn.setEnabled(enabled and fixed_mode)


class SplitPane(Card):
    segClicked = Signal(int)
    punctClicked = Signal()
    autoFollowChanged = Signal(bool)

    MIN_HEIGHT = 70
    MAX_HEIGHT = 420

    def __init__(self, parent=None):
        super().__init__(parent)
        self._view_height = px(110)

        header = QHBoxLayout()
        header.setSpacing(px(6))
        self._arrow = _tool_arrow()
        self._arrow.clicked.connect(self._toggle)
        header.addWidget(self._arrow)
        header.addWidget(section_label("分块预览"))
        self._auto_follow = QCheckBox("自动跟随")
        self._auto_follow.setFont(font(size=9))
        self._auto_follow.setChecked(True)
        self._auto_follow.toggled.connect(self.autoFollowChanged.emit)
        header.addWidget(self._auto_follow)
        self._punct_btn = chip_button("切分符...", self.punctClicked.emit)
        header.addWidget(self._punct_btn)
        header.addStretch(1)
        self._info = caption_label("")
        header.addWidget(self._info)
        self.body().addLayout(header)

        self.model = SegmentModel(self)
        self._delegate = CardDelegate("segment")
        self.view = VirtualCardsView(self._delegate)
        self.view.setModel(self.model)
        self.view.setFixedHeight(self._view_height)
        self.view.rowClicked.connect(self.segClicked.emit)
        self.body().addWidget(self.view)

        self._grip = GripHandle()
        self._grip.deltaDragged.connect(self._on_grip)
        self.body().addWidget(self._grip)

    def _toggle(self) -> None:
        collapsed = self.view.isVisible()
        self._arrow.setText("▶" if collapsed else "▼")
        self.view.setVisible(not collapsed)
        self._grip.setVisible(not collapsed)
        if not collapsed:
            self.view.setFixedHeight(self._view_height)

    def auto_follow(self) -> bool:
        return self._auto_follow.isChecked()

    def set_segments(self, segments: list[str]) -> None:
        self.model.set_segments(segments)
        self.view.refresh_layout()

    def update_result(self, row: int, text: str) -> None:
        self.model.update_result(row, text)
        self.view.schedule_layout()
        self.update_info()

    def update_state(self, row: int, state: str) -> None:
        self.model.update_state(row, state)
        self.view.viewport().update()

    def update_info(self) -> None:
        total = self.model.total()
        if total == 0:
            self._info.setText("")
            return
        avg = self.model.average_length()
        self._info.setText(f"共 {total} 段，段均 {avg:.0f} 字")

    def counter(self) -> str:
        total = self.model.total()
        return f"{self.model.done_count()} / {total}"

    def follow(self, row: int) -> None:
        self.view.follow_row(row)

    def _on_grip(self, delta: int) -> None:
        new_h = max(px(self.MIN_HEIGHT), min(px(self.MAX_HEIGHT), self._view_height + delta))
        self._view_height = new_h
        self.view.setFixedHeight(new_h)

    def refresh_fonts(self) -> None:
        self.view.refresh_layout(clear_cache=True)

    def set_state(self, enabled: bool) -> None:
        self._punct_btn.setEnabled(enabled)
        self._auto_follow.setEnabled(enabled)


class ControlBar(Card):
    startClicked = Signal()
    autoCopyChanged = Signal(bool)

    def __init__(self, parent=None):
        super().__init__(parent)
        row = QHBoxLayout()
        row.setSpacing(px(10))
        self._status = QLabel("⟳ 加载模型中...")
        self._status.setFont(font(size=10))
        self._status.setStyleSheet(f"color: {COLORS['info']};")
        row.addWidget(self._status, 1)

        self._auto_copy = QCheckBox("完成后自动复制")
        self._auto_copy.setFont(font(size=9))
        self._auto_copy.toggled.connect(self.autoCopyChanged.emit)
        row.addWidget(self._auto_copy)

        self._start = QPushButton("⟳ 模型加载中...")
        self._start.setProperty("variant", "primary")
        self._start.setFont(font(size=12, bold=True))
        self._start.setFixedWidth(px(160))
        self._start.setFixedHeight(px(42))
        self._start.setCursor(Qt.PointingHandCursor)
        self._start.setEnabled(False)
        self._start.clicked.connect(self.startClicked.emit)
        row.addWidget(self._start)
        self.body().addLayout(row)

    def set_status(self, text: str, kind: str = "info") -> None:
        self._status.setText(text)
        color = {
            "info": COLORS["info"], "success": COLORS["success"],
            "warning": COLORS["warning"], "error": COLORS["error"],
            "secondary": COLORS["text_secondary"], "accent": COLORS["accent"],
        }.get(kind, COLORS["info"])
        self._status.setStyleSheet(f"color: {color};")

    def set_start(self, text: str, enabled: bool, danger: bool = False) -> None:
        self._start.setText(text)
        self._start.setEnabled(enabled)
        self._start.setProperty("variant", "danger" if danger else "primary")
        self._start.style().unpolish(self._start)
        self._start.style().polish(self._start)

    def auto_copy(self) -> bool:
        return self._auto_copy.isChecked()

    def set_auto_copy_enabled(self, enabled: bool) -> None:
        self._auto_copy.setEnabled(enabled)


class ProgressCard(Card):
    def __init__(self, parent=None):
        super().__init__(parent)
        header = QHBoxLayout()
        header.addWidget(section_label("进度"))
        header.addStretch(1)
        self._counter = caption_label("0 / 0")
        header.addWidget(self._counter)
        self.body().addLayout(header)

        self._bar = QProgressBar()
        self._bar.setRange(0, 1000)
        self._bar.setValue(0)
        self._bar.setTextVisible(False)
        self._bar.setFixedHeight(px(14))
        self.body().addWidget(self._bar)

        self._step = caption_label("")
        self.body().addWidget(self._step)

        self._anim = QVariantAnimation(self)
        self._anim.setDuration(200)
        self._anim.setEasingCurve(QEasingCurve.OutCubic)
        self._anim.valueChanged.connect(lambda v: self._bar.setValue(int(v)))

    def set_progress(self, ratio: float, animate: bool = True) -> None:
        target = max(0, min(1000, int(ratio * 1000)))
        if not animate:
            self._anim.stop()
            self._bar.setValue(target)
            return
        if abs(target - self._bar.value()) <= 2:
            self._bar.setValue(target)
            return
        self._anim.stop()
        self._anim.setStartValue(self._bar.value())
        self._anim.setEndValue(target)
        self._anim.start()

    def reset(self) -> None:
        self._anim.stop()
        self._bar.setValue(0)

    def set_counter(self, text: str) -> None:
        self._counter.setText(text)

    def set_step(self, text: str) -> None:
        self._step.setText(text)


class ResultPane(Card):
    viewChanged = Signal(str)
    compareSourceChanged = Signal(str)
    historyClicked = Signal()
    copyClicked = Signal()
    saveClicked = Signal()

    def __init__(self, parent=None):
        super().__init__(parent)
        header = QHBoxLayout()
        header.setSpacing(px(6))
        header.addWidget(section_label("结果"))
        self._view = SegmentedControl(["结果", "对照"], "结果")
        self._view.changed.connect(self._on_view_changed)
        header.addWidget(self._view)
        self._source = QComboBox()
        self._source.setFixedWidth(px(160))
        self._source.addItem("原文")
        self._source.currentIndexChanged.connect(self._on_source_changed)
        self._source.setVisible(False)
        header.addWidget(self._source)
        header.addStretch(1)
        self._history_btn = chip_button("历史", self.historyClicked.emit)
        self._copy_btn = chip_button("复制", self.copyClicked.emit)
        self._save_btn = chip_button("保存", self.saveClicked.emit)
        header.addWidget(self._history_btn)
        header.addWidget(self._copy_btn)
        header.addWidget(self._save_btn)
        self.body().addLayout(header)

        self._stack = QStackedWidget()
        self._stack.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)

        self._text = QPlainTextEdit()
        self._text.setReadOnly(True)
        self._text.setPlaceholderText("翻译结果会在这里按段累积显示…")
        self._text.setFont(font(size=10))
        self._stack.addWidget(self._text)

        compare_page = QWidget()
        compare_page.setObjectName("page")
        page_layout = QVBoxLayout(compare_page)
        page_layout.setContentsMargins(0, 0, 0, 0)
        page_layout.setSpacing(px(4))
        titles = QHBoxLayout()
        titles.setContentsMargins(px(6), 0, px(6), 0)
        self._left_title = QLabel("原文")
        self._left_title.setFont(font(size=9))
        self._left_title.setStyleSheet(f"color: {COLORS['accent']};")
        self._right_title = QLabel("当前结果")
        self._right_title.setFont(font(size=9))
        self._right_title.setStyleSheet(f"color: {COLORS['success']};")
        titles.addWidget(self._left_title, 1)
        titles.addWidget(self._right_title, 1)
        page_layout.addLayout(titles)

        self.compare_model = CompareModel(self)
        self._compare_delegate = CardDelegate("compare")
        self.compare_view = VirtualCardsView(self._compare_delegate)
        self.compare_view.setModel(self.compare_model)
        page_layout.addWidget(self.compare_view, 1)
        self._compare_page = compare_page
        self._stack.addWidget(compare_page)

        self.body().addWidget(self._stack, 1)
        self._context_menu_actions()

    def _context_menu_actions(self) -> None:
        # 结果框保留系统右键菜单（复制/全选）
        self._text.setContextMenuPolicy(Qt.DefaultContextMenu)

    # --- 结果文本 ---
    def text(self) -> str:
        return self._text.toPlainText()

    def clear_text(self) -> None:
        self._text.clear()

    def append_text(self, text: str) -> None:
        cursor = self._text.textCursor()
        cursor.movePosition(cursor.MoveOperation.End)
        cursor.insertText(text)
        self._text.setTextCursor(cursor)
        self._text.ensureCursorVisible()

    def set_text(self, text: str) -> None:
        self._text.setPlainText(text)

    # --- 视图切换 ---
    def _on_view_changed(self, value: str) -> None:
        self._stack.setCurrentWidget(self._compare_page if value == "对照" else self._text)
        self._source.setVisible(value == "对照")
        self.viewChanged.emit(value)

    def _on_source_changed(self, _index: int) -> None:
        self.compareSourceChanged.emit(self._source.currentText())

    def view_mode(self) -> str:
        return self._view.current()

    def set_view_mode(self, mode: str, emit: bool = False) -> None:
        self._view.set_current(mode, emit=emit)
        self._stack.setCurrentWidget(self._compare_page if mode == "对照" else self._text)
        self._source.setVisible(mode == "对照")

    def set_compare_sources(self, sources: list[str]) -> None:
        blocked = self._source.blockSignals(True)
        self._source.clear()
        for s in sources:
            self._source.addItem(s)
        self._source.blockSignals(blocked)

    def set_compare_source(self, source: str) -> None:
        blocked = self._source.blockSignals(True)
        index = self._source.findText(source)
        if index >= 0:
            self._source.setCurrentIndex(index)
        self._source.blockSignals(blocked)

    def compare_source(self) -> str:
        return self._source.currentText()

    def set_compare_titles(self, left: str, right: str) -> None:
        self._left_title.setText(left)
        self._right_title.setText(right)

    def set_compare_data(self, left: list[str], right: list[str]) -> None:
        self.compare_model.set_data(left, right)
        self.compare_view.refresh_layout()

    def update_compare_right(self, row: int, text: str) -> None:
        self.compare_model.update_right(row, text)

    def refresh_fonts(self) -> None:
        self._text.setFont(font(size=10))
        self.compare_view.refresh_layout(clear_cache=True)

    def set_state(self, enabled: bool) -> None:
        self._view.set_enabled(enabled)
        self._source.setEnabled(enabled)
