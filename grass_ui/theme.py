# -*- coding: utf-8 -*-
"""主题：配色、字体与全局 QSS

所有尺寸都经过 ``SCALE`` 缩放，Ctrl+滚轮调字号时整窗（含间距、圆角）等比变化，
避免只放大文字导致控件被截断。
"""
from __future__ import annotations

from PySide6.QtGui import QFont
from PySide6.QtWidgets import QApplication

COLORS = {
    "bg": "#1e1e1e",
    "surface": "#252526",
    "surface_hover": "#2d2d30",
    "border": "#3c3c3c",
    "text": "#cccccc",
    "text_secondary": "#858585",
    "text_disabled": "#555555",
    "accent": "#007acc",
    "accent_hover": "#0098ff",
    "success": "#4ec9b0",
    "warning": "#cca700",
    "error": "#f44747",
    "info": "#4fc1ff",
    "card_waiting": "#2d2d30",
    "card_translating": "#5a4a10",
    "card_done": "#2a4a2a",
}

# 优先使用能同时覆盖中英文的界面字体
FONT_FAMILIES = [
    "Microsoft YaHei UI",
    "Microsoft YaHei",
    "PingFang SC",
    "Noto Sans CJK SC",
    "Source Han Sans SC",
    "Segoe UI",
]
MONO_FAMILIES = ["Consolas", "Cascadia Mono", "Menlo", "DejaVu Sans Mono"]

BASE_PT = 10.0
SCALE = 1.0
# 字号缩放的上下限（Ctrl+滚轮）
SCALE_MIN = 0.8
SCALE_MAX = 1.8


def font(size: float | None = None, bold: bool = False,
         family: str | None = None) -> QFont:
    """按当前缩放比例构造字体；size 为未缩放的字号（pt）"""
    f = QFont()
    f.setFamilies([family] if family else FONT_FAMILIES)
    f.setPointSizeF(max(6.0, round((BASE_PT if size is None else size) * SCALE, 2)))
    f.setWeight(QFont.Weight.DemiBold if bold else QFont.Weight.Normal)
    return f


def mono_font(size: float | None = None) -> QFont:
    return font(size, family=MONO_FAMILIES[0])


def px(value: float) -> int:
    """逻辑像素按缩放比例换算（用于固定高度、边距）"""
    return max(1, int(round(value * SCALE)))


def qss() -> str:
    """生成完整样式表。

    注意：QSS 中凡是 px 数值都走 ``_p()``，这样字号缩放时布局一起变，
    不会出现字变大、按钮装不下的情况。
    """
    def _p(v: float) -> int:
        return px(v)

    c = COLORS
    fs = round(BASE_PT * SCALE, 2)
    fs_small = round((BASE_PT - 1) * SCALE, 2)
    fs_section = round((BASE_PT + 1.5) * SCALE, 2)
    fs_title = round((BASE_PT + 3.5) * SCALE, 2)

    return f"""
    QWidget {{
        color: {c['text']};
        font-size: {fs}pt;
    }}
    QMainWindow, QDialog {{
        background: {c['bg']};
    }}
    QFrame#card {{
        background: {c['surface']};
        border: 1px solid {c['border']};
        border-radius: {_p(8)}px;
    }}
    QFrame#cardFlat {{
        background: {c['bg']};
        border: 1px solid {c['border']};
        border-radius: {_p(6)}px;
    }}
    QLabel {{
        background: transparent;
    }}
    QLabel#section {{
        font-size: {fs_section}pt;
        font-weight: 600;
    }}
    QLabel#title {{
        font-size: {fs_title}pt;
        font-weight: 600;
    }}
    QLabel#caption {{
        font-size: {fs_small}pt;
        color: {c['text_secondary']};
    }}
    QLabel#chain {{
        color: {c['accent']};
    }}
    QLabel#toast {{
        background: {c['surface']};
        border: 1px solid {c['border']};
        border-radius: {_p(6)}px;
        padding: {_p(7)}px {_p(14)}px;
        font-size: {fs_small}pt;
    }}
    QLabel#toast[kind="success"] {{ color: {c['success']}; }}
    QLabel#toast[kind="warning"] {{ color: {c['warning']}; }}
    QLabel#toast[kind="error"] {{ color: {c['error']}; }}
    QLabel#toast[kind="info"] {{ color: {c['info']}; }}

    QPushButton {{
        background: {c['surface_hover']};
        color: {c['text']};
        border: 1px solid {c['border']};
        border-radius: {_p(5)}px;
        padding: {_p(4)}px {_p(12)}px;
        font-size: {fs}pt;
    }}
    QPushButton:hover {{
        border-color: {c['accent']};
    }}
    QPushButton:disabled {{
        color: {c['text_disabled']};
        background: {c['surface']};
    }}
    QPushButton[variant="primary"] {{
        background: {c['accent']};
        color: white;
        border: 1px solid {c['accent']};
        font-weight: 600;
    }}
    QPushButton[variant="primary"]:hover {{
        background: {c['accent_hover']};
        border-color: {c['accent_hover']};
    }}
    QPushButton[variant="primary"]:disabled {{
        background: {c['surface_hover']};
        border-color: {c['border']};
        color: {c['text_disabled']};
    }}
    QPushButton[variant="danger"] {{
        background: #aa3333;
        color: white;
        border: 1px solid #aa3333;
    }}
    QPushButton[variant="danger"]:hover {{
        background: #cc4444;
        border-color: #cc4444;
    }}
    QPushButton[variant="chip"] {{
        background: {c['surface_hover']};
        border: 1px solid {c['border']};
        border-radius: {_p(4)}px;
        padding: {_p(3)}px {_p(10)}px;
    }}
    QPushButton[variant="chip"]:hover {{
        background: {c['accent']};
        border-color: {c['accent']};
        color: white;
    }}
    QPushButton[variant="chip"]:checked {{
        background: {c['accent']};
        border-color: {c['accent']};
        color: white;
    }}
    QPushButton[variant="chip"]:disabled {{
        color: {c['text_disabled']};
        background: {c['surface']};
        border-color: {c['border']};
    }}
    QPushButton[variant="segment"] {{
        background: {c['surface_hover']};
        border: 1px solid {c['border']};
        border-radius: {_p(5)}px;
        padding: {_p(2)}px {_p(10)}px;
        font-size: {fs_small}pt;
    }}
    QPushButton[variant="segment"]:hover {{
        background: {c['surface_hover']};
        border-color: {c['accent']};
    }}
    QPushButton[variant="segment"]:checked {{
        background: {c['accent']};
        border-color: {c['accent']};
        color: white;
    }}
    QPushButton[variant="segment"]:disabled {{
        color: {c['text_disabled']};
    }}

    QToolButton {{
        background: transparent;
        border: none;
        color: {c['text_secondary']};
        padding: 0px;
    }}
    QToolButton:hover {{
        color: {c['accent']};
    }}

    QLineEdit, QPlainTextEdit, QTextEdit {{
        background: {c['surface']};
        color: {c['text']};
        border: 1px solid {c['border']};
        border-radius: {_p(6)}px;
        padding: {_p(4)}px;
        selection-background-color: {c['accent']};
        selection-color: white;
    }}
    QLineEdit:focus, QPlainTextEdit:focus, QTextEdit:focus {{
        border-color: {c['accent']};
    }}
    QLineEdit:disabled, QPlainTextEdit:disabled {{
        color: {c['text_disabled']};
    }}

    QComboBox {{
        background: {c['surface']};
        color: {c['text']};
        border: 1px solid {c['border']};
        border-radius: {_p(4)}px;
        padding: {_p(3)}px {_p(8)}px;
    }}
    QComboBox:focus {{
        border-color: {c['accent']};
    }}
    QComboBox:disabled {{
        color: {c['text_disabled']};
    }}
    QComboBox::drop-down {{
        border: none;
        width: {_p(18)}px;
    }}
    QComboBox::down-arrow {{
        image: none;
        border-left: {_p(4)}px solid transparent;
        border-right: {_p(4)}px solid transparent;
        border-top: {_p(5)}px solid {c['text_secondary']};
        width: 0px;
        height: 0px;
        margin-right: {_p(6)}px;
    }}
    QComboBox QAbstractItemView {{
        background: {c['surface']};
        color: {c['text']};
        border: 1px solid {c['border']};
        selection-background-color: {c['accent']};
        selection-color: white;
        outline: 0;
    }}

    QCheckBox {{
        background: transparent;
        spacing: {_p(6)}px;
        color: {c['text']};
    }}
    QCheckBox::indicator {{
        width: {_p(13)}px;
        height: {_p(13)}px;
        border: 1px solid {c['border']};
        border-radius: {_p(3)}px;
        background: {c['surface']};
    }}
    QCheckBox::indicator:hover {{
        border-color: {c['accent']};
    }}
    QCheckBox::indicator:checked {{
        background: {c['accent']};
        border-color: {c['accent']};
    }}
    QCheckBox::indicator:disabled {{
        border-color: {c['border']};
        background: {c['surface']};
    }}

    QProgressBar {{
        background: {c['surface']};
        border: 1px solid {c['border']};
        border-radius: {_p(4)}px;
        text-align: center;
        color: {c['text_secondary']};
        font-size: {fs_small}pt;
        min-height: {_p(14)}px;
        max-height: {_p(14)}px;
    }}
    QProgressBar::chunk {{
        background: {c['accent']};
        border-radius: {_p(3)}px;
    }}

    QScrollBar:vertical {{
        background: transparent;
        width: {_p(10)}px;
        margin: 0px;
    }}
    QScrollBar::handle:vertical {{
        background: {c['border']};
        border-radius: {_p(5)}px;
        min-height: {_p(24)}px;
    }}
    QScrollBar::handle:vertical:hover {{
        background: {c['accent']};
    }}
    QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {{
        height: 0px;
    }}
    QScrollBar::add-page:vertical, QScrollBar::sub-page:vertical {{
        background: transparent;
    }}
    QScrollBar:horizontal {{
        background: transparent;
        height: {_p(10)}px;
        margin: 0px;
    }}
    QScrollBar::handle:horizontal {{
        background: {c['border']};
        border-radius: {_p(5)}px;
        min-width: {_p(24)}px;
    }}
    QScrollBar::handle:horizontal:hover {{
        background: {c['accent']};
    }}
    QScrollBar::add-line:horizontal, QScrollBar::sub-line:horizontal {{
        width: 0px;
    }}
    QScrollBar::add-page:horizontal, QScrollBar::sub-page:horizontal {{
        background: transparent;
    }}

    QScrollArea {{
        background: transparent;
        border: none;
    }}
    QScrollArea > QWidget > QWidget {{
        background: transparent;
    }}

    QListView, QListWidget {{
        background: {c['bg']};
        border: 1px solid {c['border']};
        border-radius: {_p(6)}px;
        outline: 0;
        font-size: {fs}pt;
    }}
    QListWidget::item {{
        padding: {_p(4)}px;
    }}
    QListWidget::item:selected {{
        background: {c['accent']};
        color: white;
    }}

    QSplitter::handle {{
        background: {c['border']};
    }}
    QSplitter::handle:hover {{
        background: {c['accent']};
    }}

    QToolTip {{
        background: {c['surface']};
        color: {c['text']};
        border: 1px solid {c['border']};
        padding: {_p(4)}px;
    }}
    QMenu {{
        background: {c['surface']};
        color: {c['text']};
        border: 1px solid {c['border']};
    }}
    QMenu::item:selected {{
        background: {c['accent']};
        color: white;
    }}

    QWidget#grip {{
        background: {c['border']};
        border-radius: {_p(3)}px;
    }}
    QWidget#grip:hover {{
        background: {c['accent']};
    }}
    QWidget#flowHost, QWidget#rowHost, QWidget#page {{
        background: transparent;
    }}
    """


def apply_theme(app: QApplication, scale: float | None = None) -> None:
    """应用（或按新缩放比例重应用）全局样式"""
    global SCALE
    if scale is not None:
        SCALE = scale
    app.setFont(font())
    app.setStyleSheet(qss())
