# -*- coding: utf-8 -*-
"""通用界面组件：卡片、流式布局、分段按钮、Toast、可拖拽高度手柄"""
from __future__ import annotations

from PySide6.QtCore import (QEasingCurve, QPoint, QPropertyAnimation, QRect, QSize,
                            Qt, Signal, QTimer)
from PySide6.QtWidgets import (QButtonGroup, QFrame, QGraphicsOpacityEffect,
                               QHBoxLayout, QLabel, QLayout, QPushButton,
                               QSizePolicy, QVBoxLayout, QWidget)

from .theme import COLORS, font, px


class Card(QFrame):
    """统一卡片容器（圆角 + 边框 + 内边距）"""

    def __init__(self, parent: QWidget | None = None, margins=(14, 10, 14, 10),
                 spacing: int = 6):
        super().__init__(parent)
        self.setObjectName("card")
        self._layout = QVBoxLayout(self)
        self._layout.setContentsMargins(*[px(v) for v in margins])
        self._layout.setSpacing(px(spacing))

    def body(self) -> QVBoxLayout:
        return self._layout


def section_label(text: str) -> QLabel:
    label = QLabel(text)
    label.setObjectName("section")
    label.setFont(font(size=11.5, bold=True))
    return label


def caption_label(text: str = "") -> QLabel:
    label = QLabel(text)
    label.setObjectName("caption")
    label.setFont(font(size=9))
    return label


def chip_button(text: str, on_click=None, variant: str = "chip",
                checkable: bool = False) -> QPushButton:
    btn = QPushButton(text)
    btn.setProperty("variant", variant)
    btn.setFont(font(size=10))
    btn.setCursor(Qt.PointingHandCursor)
    if checkable:
        btn.setCheckable(True)
    if on_click is not None:
        btn.clicked.connect(on_click)
    return btn


class FlowLayout(QLayout):
    """自动换行布局（Qt 官方示例实现，用于语言方块与标签流）

    窗口拉伸时由 heightForWidth 重新分行，不需要重建控件，
    因此拖动窗口边框不会产生卡顿。
    """

    def __init__(self, parent: QWidget | None = None, margin: int = 0,
                 hspacing: int = 6, vspacing: int = 6):
        super().__init__(parent)
        self._items: list = []
        self._hspacing = px(hspacing)
        self._vspacing = px(vspacing)
        self.setContentsMargins(margin, margin, margin, margin)

    def __del__(self):
        while self.count():
            self.takeAt(0)

    def addItem(self, item):
        self._items.append(item)

    def count(self) -> int:
        return len(self._items)

    def itemAt(self, index: int):
        if 0 <= index < len(self._items):
            return self._items[index]
        return None

    def takeAt(self, index: int):
        if 0 <= index < len(self._items):
            return self._items.pop(index)
        return None

    def expandingDirections(self):
        return Qt.Orientations(Qt.Orientation(0))

    def hasHeightForWidth(self) -> bool:
        return True

    def heightForWidth(self, width: int) -> int:
        return self._do_layout(QRect(0, 0, width, 0), test_only=True)

    def setGeometry(self, rect: QRect) -> None:
        super().setGeometry(rect)
        self._do_layout(rect, test_only=False)

    def sizeHint(self) -> QSize:
        return self.minimumSize()

    def minimumSize(self) -> QSize:
        size = QSize()
        for item in self._items:
            size = size.expandedTo(item.minimumSize())
        margins = self.contentsMargins()
        size += QSize(margins.left() + margins.right(), margins.top() + margins.bottom())
        return size

    def _do_layout(self, rect: QRect, test_only: bool) -> int:
        margins = self.contentsMargins()
        effective = rect.adjusted(margins.left(), margins.top(),
                                  -margins.right(), -margins.bottom())
        x = effective.x()
        y = effective.y()
        line_height = 0
        for item in self._items:
            widget = item.widget()
            if widget is not None and not widget.isVisible():
                continue
            hint = item.sizeHint()
            next_x = x + hint.width() + self._hspacing
            if next_x - self._hspacing > effective.right() and line_height > 0:
                x = effective.x()
                y = y + line_height + self._vspacing
                next_x = x + hint.width() + self._hspacing
                line_height = 0
            if not test_only:
                item.setGeometry(QRect(QPoint(x, y), hint))
            x = next_x
            line_height = max(line_height, hint.height())
        return y + line_height - rect.y() + margins.bottom()


class SegmentedControl(QWidget):
    """互斥分段按钮组；点击时发出 changed(str)"""

    changed = Signal(str)

    def __init__(self, options, current: str | None = None, parent=None):
        super().__init__(parent)
        lay = QHBoxLayout(self)
        lay.setContentsMargins(0, 0, 0, 0)
        lay.setSpacing(px(2))
        self._group = QButtonGroup(self)
        self._group.setExclusive(True)
        self._buttons: dict[str, QPushButton] = {}
        for i, text in enumerate(options):
            btn = chip_button(text, variant="segment", checkable=True)
            btn.setSizePolicy(QSizePolicy.Fixed, QSizePolicy.Fixed)
            self._group.addButton(btn, i)
            lay.addWidget(btn)
            self._buttons[text] = btn
        self._group.buttonClicked.connect(self._on_clicked)
        if current is None and options:
            current = options[0]
        if current is not None:
            self.set_current(current, emit=False)

    def _on_clicked(self, btn: QPushButton) -> None:
        self.changed.emit(btn.text())

    def set_current(self, text: str, emit: bool = False) -> None:
        btn = self._buttons.get(text)
        if btn is None:
            return
        for other in self._buttons.values():
            other.setChecked(other is btn)
        if emit:
            self.changed.emit(text)

    def current(self) -> str:
        for text, btn in self._buttons.items():
            if btn.isChecked():
                return text
        return ""

    def set_enabled(self, enabled: bool) -> None:
        for btn in self._buttons.values():
            btn.setEnabled(enabled)


class Toast(QLabel):
    """底部居中的轻提示，淡入淡出"""

    def __init__(self, parent: QWidget):
        super().__init__(parent)
        self.setObjectName("toast")
        self.setAlignment(Qt.AlignCenter)
        self.setAttribute(Qt.WA_TransparentForMouseEvents, True)
        self.setVisible(False)
        self._effect = QGraphicsOpacityEffect(self)
        self._effect.setOpacity(1.0)
        self.setGraphicsEffect(self._effect)
        self._anim = QPropertyAnimation(self._effect, b"opacity", self)
        self._anim.setDuration(180)
        self._anim.setEasingCurve(QEasingCurve.InOutQuad)
        self._anim.finished.connect(self._on_anim_finished)
        self._hide_timer = QTimer(self)
        self._hide_timer.setSingleShot(True)
        self._hide_timer.timeout.connect(self._fade_out)
        self._fading_out = False

    def show_message(self, text: str, kind: str = "success", duration: int = 2400) -> None:
        self._fading_out = False
        self.setProperty("kind", kind)
        self.style().unpolish(self)
        self.style().polish(self)
        self.setText(text)
        self.setFont(font(size=9))
        self.adjustSize()
        self._reposition()
        self.setVisible(True)
        self.raise_()
        self._anim.stop()
        self._anim.setStartValue(0.0)
        self._anim.setEndValue(1.0)
        self._anim.start()
        self._hide_timer.start(max(600, duration))

    def _reposition(self) -> None:
        parent = self.parentWidget()
        if parent is None:
            return
        hint = self.sizeHint()
        w = max(hint.width(), self.width())
        h = max(hint.height(), self.height())
        self.resize(w, h)
        self.move((parent.width() - w) // 2, int(parent.height() * 0.9) - h)

    def _fade_out(self) -> None:
        self._fading_out = True
        self._anim.stop()
        self._anim.setStartValue(self._effect.opacity())
        self._anim.setEndValue(0.0)
        self._anim.start()

    def _on_anim_finished(self) -> None:
        if self._fading_out:
            self._fading_out = False
            self.setVisible(False)


class GripHandle(QWidget):
    """可拖拽调高的细手柄（替代 v1.x 的 tk 拖拽逻辑）

    只发出增量位移，由持有者决定修改哪个控件的高度。
    """

    deltaDragged = Signal(int)

    def __init__(self, parent: QWidget | None = None):
        super().__init__(parent)
        self.setObjectName("grip")
        self.setFixedHeight(px(6))
        self.setCursor(Qt.SizeVerCursor)
        self.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
        self._last_y: float | None = None

    def mousePressEvent(self, event) -> None:
        if event.button() == Qt.LeftButton:
            self._last_y = event.globalPosition().y()
            event.accept()
        else:
            super().mousePressEvent(event)

    def mouseMoveEvent(self, event) -> None:
        if self._last_y is None:
            super().mouseMoveEvent(event)
            return
        y = event.globalPosition().y()
        delta = int(y - self._last_y)
        if delta:
            self._last_y = y
            self.deltaDragged.emit(delta)
        event.accept()

    def mouseReleaseEvent(self, event) -> None:
        self._last_y = None
        event.accept()


def hline() -> QFrame:
    line = QFrame()
    line.setFrameShape(QFrame.HLine)
    line.setStyleSheet(f"color: {COLORS['border']};")
    return line


class ChipFlow(QWidget):
    """流式方块的宿主：按自身宽度自动收缩/伸展高度

    弹窗里的语言方块用它，避免在 QScrollArea 里算出 0 高度或出现大片空白。
    """

    def __init__(self, parent: QWidget | None = None, hspacing: int = 6,
                 vspacing: int = 6):
        super().__init__(parent)
        self.setObjectName("flowHost")
        self.flow = FlowLayout(self, margin=0, hspacing=hspacing, vspacing=vspacing)
        self.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Minimum)

    def resizeEvent(self, event) -> None:
        super().resizeEvent(event)
        self._sync_height()

    def _sync_height(self) -> None:
        width = self.width() or 400
        height = self.flow.heightForWidth(width)
        if height and abs(self.minimumHeight() - height) > 1:
            self.setMinimumHeight(height)

    def add_widget(self, widget: QWidget) -> None:
        self.flow.addWidget(widget)
        self._sync_height()

    def clear_widgets(self) -> None:
        while self.flow.count():
            item = self.flow.takeAt(0)
            widget = item.widget() if item else None
            if widget is not None:
                widget.setParent(None)
                widget.deleteLater()
        self._sync_height()

    def sizeHint(self) -> QSize:
        width = self.width() or 400
        return QSize(width, self.flow.heightForWidth(width))
