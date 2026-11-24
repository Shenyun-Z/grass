# -*- coding: utf-8 -*-
"""分块预览 / 对照视图：QListView + 自定义绘制 delegate

v2.0 性能要点（对应 v1.x 卡顿的根因）：
1. **虚拟化**：只有视口内的 1~2 屏行会被 paint，滚动不重排整棵控件树；
2. **行级更新**：某段结果到达时只 dataChanged 该行，不触发全量重排；
3. **高度缓存**：每行换行高度按（行号 + 宽度桶 + 内容版本）缓存，
   窗口拉伸时只做查表，几乎零成本；
4. **逐像素滚动**：ScrollPerPixel + 自定义滚轮步长，缩放/滚动跟手。
"""
from __future__ import annotations

from PySide6.QtCore import QAbstractListModel, QModelIndex, QRect, QRectF, \
    QSize, Qt, QTimer, Signal
from PySide6.QtGui import QColor, QFontMetrics, QPainter, QPen
from PySide6.QtWidgets import QAbstractItemView, QFrame, QListView, QStyle, \
    QStyledItemDelegate

from .theme import COLORS, font, px

ROLE_TEXT = Qt.UserRole + 1      # 左栏文字（原文 / 分段原文）
ROLE_RESULT = Qt.UserRole + 2    # 右栏文字（译文 / 对照结果）
ROLE_STATE = Qt.UserRole + 3     # waiting / translating / done
ROLE_REV = Qt.UserRole + 4       # 该行内容版本（缓存失效用）


class SegmentModel(QAbstractListModel):
    """分段结果模型：一行 = 一段，左原文右译文"""

    def __init__(self, parent=None):
        super().__init__(parent)
        self._segments: list[str] = []
        self._results: dict[int, str] = {}
        self._states: dict[int, str] = {}
        self._revs: dict[int, int] = {}
        self._rev = 0

    # --- Qt 模型接口 ---
    def rowCount(self, parent=QModelIndex()) -> int:
        if parent.isValid():
            return 0
        return len(self._segments)

    def data(self, index: QModelIndex, role: int = Qt.DisplayRole):
        if not index.isValid() or not (0 <= index.row() < len(self._segments)):
            return None
        row = index.row()
        if role == ROLE_TEXT:
            return self._segments[row]
        if role == ROLE_RESULT:
            return self._results.get(row, "")
        if role == ROLE_STATE:
            return self._states.get(row, "waiting")
        if role == ROLE_REV:
            return self._revs.get(row, 0)
        return None

    def flags(self, index: QModelIndex):
        return Qt.ItemIsEnabled

    # --- 业务接口 ---
    def set_segments(self, segments: list[str]) -> None:
        self.beginResetModel()
        self._segments = list(segments)
        self._results = {}
        self._states = {i: "waiting" for i in range(len(self._segments))}
        # 每一行都打上新版本号，否则 delegate 的行高缓存会按旧内容复用，
        # 长段落沿用短段落的单行高度，预览里就被裁成一行
        self._revs = {i: self._rev for i in range(len(self._segments))}
        self._rev += 1
        self.endResetModel()

    def clear_results(self) -> None:
        self.beginResetModel()
        self._results = {}
        self._states = {i: "waiting" for i in range(len(self._segments))}
        self._revs = {i: self._rev for i in range(len(self._segments))}
        self._rev += 1
        self.endResetModel()

    def _touch(self, row: int) -> None:
        self._rev += 1
        self._revs[row] = self._rev
        idx = self.index(row, 0)
        self.dataChanged.emit(idx, idx, [ROLE_RESULT, ROLE_STATE, ROLE_REV])

    def update_result(self, row: int, text: str) -> None:
        if not (0 <= row < len(self._segments)):
            return
        self._results[row] = text
        self._states[row] = "done"
        self._touch(row)

    def update_state(self, row: int, state: str) -> None:
        if not (0 <= row < len(self._segments)):
            return
        self._states[row] = state
        self._touch(row)

    def segment(self, row: int) -> str:
        return self._segments[row] if 0 <= row < len(self._segments) else ""

    def result(self, row: int) -> str:
        return self._results.get(row, "")

    def segments(self) -> list[str]:
        return list(self._segments)

    def total(self) -> int:
        return len(self._segments)

    def done_count(self) -> int:
        return sum(1 for state in self._states.values() if state == "done")

    def average_length(self) -> float:
        if not self._segments:
            return 0.0
        return sum(len(s) for s in self._segments) / len(self._segments)


class CompareModel(QAbstractListModel):
    """对照模型：左栏为原文或历史结果，右栏为当前结果"""

    def __init__(self, parent=None):
        super().__init__(parent)
        self._left: list[str] = []
        self._right: list[str] = []
        self._revs: dict[int, int] = {}
        self._rev = 0

    def rowCount(self, parent=QModelIndex()) -> int:
        if parent.isValid():
            return 0
        return max(len(self._left), len(self._right))

    def data(self, index: QModelIndex, role: int = Qt.DisplayRole):
        if not index.isValid():
            return None
        row = index.row()
        if role == ROLE_TEXT:
            return self._left[row] if row < len(self._left) else ""
        if role == ROLE_RESULT:
            return self._right[row] if row < len(self._right) else ""
        if role == ROLE_STATE:
            return "done" if row < len(self._right) and self._right[row] else "waiting"
        if role == ROLE_REV:
            return self._revs.get(row, 0)
        return None

    def flags(self, index: QModelIndex):
        return Qt.ItemIsEnabled

    def set_data(self, left: list[str], right: list[str]) -> None:
        self.beginResetModel()
        self._left = list(left)
        self._right = list(right)
        self._rev += 1
        n = max(len(self._left), len(self._right))
        self._revs = {i: self._rev for i in range(n)}
        self.endResetModel()

    def update_right(self, row: int, text: str) -> None:
        n = max(len(self._left), len(self._right))
        if row >= n:
            return
        while len(self._right) <= row:
            self._right.append("")
        self._right[row] = text
        self._rev += 1
        self._revs[row] = self._rev
        idx = self.index(row, 0)
        self.dataChanged.emit(idx, idx, [ROLE_RESULT, ROLE_STATE, ROLE_REV])

    def set_right(self, right: list[str]) -> None:
        self.beginResetModel()
        self._right = list(right)
        self._rev += 1
        n = max(len(self._left), len(self._right))
        self._revs = {i: self._rev for i in range(n)}
        self.endResetModel()


class CardDelegate(QStyledItemDelegate):
    """双栏卡片绘制：左原文 / 右译文（或对照）"""

    MIN_H = 30
    MAX_H = 200
    GAP = 6
    PAD_X = 10
    PAD_Y = 8
    NUM_W = 22
    # 列宽按 32px 分桶：拖动窗口时只有跨桶才需要重算行高，
    # 桶宽不大于实际宽度，算出的行高只会偏大不会截断文字。
    WIDTH_BUCKET = 32

    def __init__(self, mode: str = "segment", parent=None):
        super().__init__(parent)
        self._mode = mode
        self._height_cache: dict[tuple[int, int], tuple[int, int]] = {}
        self._body = font(size=10)
        self._caption = font(size=9)
        self._title = font(size=9)

    def invalidate(self) -> None:
        """字号/主题变化后清空缓存并重算行高"""
        self._height_cache.clear()
        self._body = font(size=10)
        self._caption = font(size=9)
        self._title = font(size=9)

    # --- 尺寸 ---
    def _view_width(self) -> int:
        view = self.parent()
        if isinstance(view, QListView):
            return view.viewport().width()
        return 800

    def _col_width(self, width: int) -> int:
        return max(px(70), (width - px(10) - px(self.GAP)) // 2)

    def _text_width(self, col_width: int) -> int:
        # 留 2px 余量：Qt 的换行测量与实际绘制在浮点宽度上会差一两个像素，
        # 不留余量时恰好占满一行的文字会被裁掉最后一个字
        return max(px(40), col_width - px(self.PAD_X * 2) - px(self.NUM_W) - px(2))

    def _wrap_height(self, text: str, text_width: int) -> int:
        if not text:
            text = "…"
        metrics = QFontMetrics(self._body)
        rect = metrics.boundingRect(
            QRect(0, 0, text_width, 0),
            int(Qt.TextWordWrap | Qt.AlignLeft | Qt.AlignTop), text)
        return max(self.MIN_H, min(self.MAX_H, rect.height() + px(self.PAD_Y * 2)))

    def row_height(self, index: QModelIndex, width: int) -> int:
        bucket = max(200, (width // self.WIDTH_BUCKET) * self.WIDTH_BUCKET)
        key = (index.row(), bucket)
        rev = index.data(ROLE_REV) or 0
        cached = self._height_cache.get(key)
        if cached is not None and cached[0] == rev:
            return cached[1]
        col_width = self._col_width(bucket)
        text_width = self._text_width(col_width)
        left = index.data(ROLE_TEXT) or ""
        right = index.data(ROLE_RESULT) or ""
        height = max(self._wrap_height(left, text_width),
                     self._wrap_height(right, text_width))
        if len(self._height_cache) > 6000:
            self._height_cache.clear()
        self._height_cache[key] = (rev, height)
        return height

    def sizeHint(self, option, index: QModelIndex) -> QSize:
        width = option.rect.width()
        if width <= 0:
            width = self._view_width()
        return QSize(width, self.row_height(index, width))

    # --- 绘制 ---
    def paint(self, painter: QPainter, option, index: QModelIndex) -> None:
        painter.save()
        painter.setRenderHint(QPainter.Antialiasing, True)
        rect = option.rect
        width = rect.width()
        col_width = self._col_width(width)
        left_rect = QRectF(rect.x() + px(5), rect.y() + px(2),
                           col_width, rect.height() - px(4))
        right_rect = QRectF(left_rect.right() + px(self.GAP), left_rect.y(),
                            col_width, left_rect.height())

        left_text = index.data(ROLE_TEXT) or ""
        right_text = index.data(ROLE_RESULT) or ""
        state = index.data(ROLE_STATE) or "waiting"
        hovered = bool(option.state & QStyle.State_MouseOver)

        left_color = {
            "waiting": COLORS["card_waiting"],
            "translating": COLORS["card_translating"],
            "done": COLORS["card_done"],
        }.get(state, COLORS["card_waiting"])
        if self._mode == "compare":
            left_color = COLORS["card_waiting"]
        right_color = COLORS["card_done"] if right_text else COLORS["card_waiting"]

        border = QColor(COLORS["accent"] if hovered else COLORS["border"])
        pen = QPen(border)
        pen.setWidthF(1.0)

        for box, color in ((left_rect, left_color), (right_rect, right_color)):
            painter.setPen(pen)
            painter.setBrush(QColor(color))
            painter.drawRoundedRect(box, px(6), px(6))

        # 段号
        painter.setFont(self._caption)
        painter.setPen(QColor(COLORS["accent"]))
        num_rect = QRectF(left_rect.x() + px(self.PAD_X), left_rect.y() + px(self.PAD_Y),
                          px(self.NUM_W), left_rect.height() - px(self.PAD_Y * 2))
        painter.drawText(num_rect, int(Qt.AlignLeft | Qt.AlignTop),
                         str(index.row() + 1))
        num_rect_right = QRectF(right_rect.x() + px(self.PAD_X),
                                right_rect.y() + px(self.PAD_Y),
                                px(self.NUM_W),
                                right_rect.height() - px(self.PAD_Y * 2))
        painter.drawText(num_rect_right, int(Qt.AlignLeft | Qt.AlignTop),
                         str(index.row() + 1))

        # 正文
        painter.setFont(self._body)
        flags = int(Qt.AlignLeft | Qt.AlignTop | Qt.TextWordWrap)
        text_rect_left = QRectF(
            left_rect.x() + px(self.PAD_X) + px(self.NUM_W),
            left_rect.y() + px(self.PAD_Y),
            left_rect.width() - px(self.PAD_X * 2) - px(self.NUM_W),
            left_rect.height() - px(self.PAD_Y * 2))
        painter.setPen(QColor(COLORS["text"]))
        painter.drawText(text_rect_left, flags, left_text)

        text_rect_right = QRectF(
            right_rect.x() + px(self.PAD_X) + px(self.NUM_W),
            right_rect.y() + px(self.PAD_Y),
            right_rect.width() - px(self.PAD_X * 2) - px(self.NUM_W),
            right_rect.height() - px(self.PAD_Y * 2))
        if right_text:
            painter.setPen(QColor(COLORS["text"]))
            painter.drawText(text_rect_right, flags, right_text)
        else:
            painter.setPen(QColor(COLORS["text_secondary"]))
            painter.drawText(text_rect_right, flags, "…")

        painter.restore()


class VirtualCardsView(QListView):
    """虚拟化卡片列表

    - 逐像素滚动，Ctrl+滚轮发出字号缩放请求
    - 点击某行发出 rowClicked(row)
    """

    rowClicked = Signal(int)
    zoomRequested = Signal(int)

    def __init__(self, delegate: CardDelegate, parent=None):
        super().__init__(parent)
        self._delegate = delegate
        delegate.setParent(self)
        self.setItemDelegate(delegate)
        self.setVerticalScrollMode(QAbstractItemView.ScrollPerPixel)
        self.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        self.setVerticalScrollBarPolicy(Qt.ScrollBarAsNeeded)
        self.setSelectionMode(QAbstractItemView.NoSelection)
        self.setEditTriggers(QAbstractItemView.NoEditTriggers)
        self.setUniformItemSizes(False)
        self.setResizeMode(QListView.Adjust)
        self.setMouseTracking(True)
        self.setFrameShape(QFrame.NoFrame)
        self.setSpacing(0)
        self.setWordWrap(False)
        self.viewport().setAutoFillBackground(False)
        self.clicked.connect(lambda idx: self.rowClicked.emit(idx.row()))
        # 行高随宽度变化时合并重排，避免拖动窗口时逐像素重算
        self._layout_timer = QTimer(self)
        self._layout_timer.setSingleShot(True)
        self._layout_timer.setInterval(0)
        self._layout_timer.timeout.connect(self._flush_layout)
        self._pending_layout = False

    # --- 滚动 ---
    def wheelEvent(self, event) -> None:
        if event.modifiers() & Qt.ControlModifier:
            self.zoomRequested.emit(event.angleDelta().y())
            event.accept()
            return
        bar = self.verticalScrollBar()
        pixel = event.pixelDelta().y()
        if pixel:
            bar.setValue(bar.value() - pixel)
            event.accept()
            return
        delta = event.angleDelta().y()
        if delta:
            bar.setValue(bar.value() - int(delta / 120 * px(66)))
        event.accept()

    # --- 重排 ---
    def refresh_layout(self, clear_cache: bool = False) -> None:
        if clear_cache:
            self._delegate.invalidate()
        self.doItemsLayout()
        self.viewport().update()

    def schedule_layout(self) -> None:
        if self._pending_layout:
            return
        self._pending_layout = True
        self._layout_timer.start()

    def _flush_layout(self) -> None:
        self._pending_layout = False
        self.doItemsLayout()

    def resizeEvent(self, event) -> None:
        width_changed = event.size().width() != event.oldSize().width()
        super().resizeEvent(event)
        if width_changed:
            self.schedule_layout()

    # --- 自动跟随 ---
    def follow_row(self, row: int) -> None:
        if row < 0 or row >= self.model().rowCount():
            return
        index_rect = self.visualRect(self.model().index(row, 0))
        viewport = self.viewport().rect()
        if index_rect.top() >= viewport.bottom() or index_rect.bottom() <= viewport.top():
            self.scrollTo(self.model().index(row, 0),
                          QAbstractItemView.PositionAtBottom)
