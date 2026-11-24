# -*- coding: utf-8 -*-
"""Qt 应用入口：创建 QApplication、应用主题、打开主窗口"""
from __future__ import annotations

import sys


def run(argv: list[str] | None = None) -> int:
    from PySide6.QtGui import QColor, QPalette
    from PySide6.QtWidgets import QApplication

    app = QApplication(argv if argv is not None else sys.argv)
    app.setApplicationName("grass")
    app.setApplicationDisplayName("生草机")
    app.setStyle("Fusion")

    # 原生绘制的部分（菜单、输入框右键菜单、滚动条箭头等）也使用深色调色板
    palette = QPalette()
    palette.setColor(QPalette.Window, QColor("#1e1e1e"))
    palette.setColor(QPalette.WindowText, QColor("#cccccc"))
    palette.setColor(QPalette.Base, QColor("#252526"))
    palette.setColor(QPalette.AlternateBase, QColor("#2d2d30"))
    palette.setColor(QPalette.Text, QColor("#cccccc"))
    palette.setColor(QPalette.Button, QColor("#2d2d30"))
    palette.setColor(QPalette.ButtonText, QColor("#cccccc"))
    palette.setColor(QPalette.Highlight, QColor("#007acc"))
    palette.setColor(QPalette.HighlightedText, QColor("white"))
    palette.setColor(QPalette.ToolTipBase, QColor("#252526"))
    palette.setColor(QPalette.ToolTipText, QColor("#cccccc"))
    app.setPalette(palette)

    from .theme import apply_theme

    apply_theme(app)

    from .mainwindow import MainWindow

    window = MainWindow()
    window.show()
    return app.exec()
