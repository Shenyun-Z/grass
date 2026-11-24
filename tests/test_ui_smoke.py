# -*- coding: utf-8 -*-
"""v2.0 界面冒烟测试（离屏）

不加载真实模型，只验证：
1. 主窗口能在无显示器环境构建；
2. 分段模型只对更新行发 dataChanged（流式更新不重排全表）；
3. 卡片行高带缓存，同一宽度重复询问不会重复计算；
4. 字号缩放后行高缓存会被清空并重算。
"""
import os

import pytest

pytest.importorskip("PySide6")


@pytest.fixture(scope="session")
def qapp():
    os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
    from PySide6.QtWidgets import QApplication

    app = QApplication.instance() or QApplication([])
    from grass_ui.theme import apply_theme

    apply_theme(app)
    return app


def test_main_window_constructs(qapp, monkeypatch, tmp_path):
    monkeypatch.setenv("GRASS_SKIP_MODEL_LOAD", "1")
    monkeypatch.setenv("GRASS_DATA_DIR", str(tmp_path))
    from grass_ui.mainwindow import MainWindow

    window = MainWindow()
    try:
        assert "生草机 v" in window.windowTitle()
        window._raw_text = "第一句。第二句。第三句。"
        window._on_input_change()
        assert window._split_pane.model.total() >= 1
        assert window._input_pane.text() == ""
        assert window._result_pane.text() == ""
    finally:
        window.close()


def test_translate_message_flow(qapp, monkeypatch, tmp_path):
    """模拟引擎消息：某段结果只更新该行，完成后写入历史"""
    import queue

    monkeypatch.setenv("GRASS_SKIP_MODEL_LOAD", "1")
    monkeypatch.setenv("GRASS_DATA_DIR", str(tmp_path))
    from grass_ui.mainwindow import MainWindow

    window = MainWindow()
    try:
        window._raw_text = "第一段。第二段。"
        window._on_input_change()
        window._running = True
        window._msg_queue = queue.Queue()
        window._start_time = 0.0

        window._handle_msg(("step", 0, 0, "中文", "英语", "first step"))
        window._handle_msg(("segment", 0, "英语", "中文", "第一段译文"))
        assert window._seg_results[0] == "第一段译文"
        assert window._split_pane.model.result(0) == "第一段译文"
        assert window._result_pane.text() == "第一段译文"

        window._handle_msg(("done",))
        assert window._running is False
        assert len(window._history) == 1
        assert window._history[0]["result"] == "第一段译文"
    finally:
        window.close()


def test_segment_model_updates_single_row(qapp):
    from PySide6.QtCore import Qt

    from grass_ui.splitview import ROLE_RESULT, SegmentModel

    model = SegmentModel()
    model.set_segments(["甲", "乙", "丙"])
    changed = []
    model.dataChanged.connect(lambda tl, br, roles: changed.append((tl.row(), br.row())))
    model.update_result(1, "译文")
    assert changed == [(1, 1)]
    assert model.data(model.index(1, 0), ROLE_RESULT) == "译文"
    assert model.index(1, 0).data(ROLE_RESULT) == "译文"
    assert model.index(1, 0).data(Qt.DisplayRole) is None


def test_delegate_height_cache(qapp):
    from grass_ui.splitview import CardDelegate, SegmentModel

    model = SegmentModel()
    model.set_segments(["短句", "很长的句子" * 12])
    delegate = CardDelegate()
    index = model.index(1, 0)
    first = delegate.row_height(index, 600)
    assert first > CardDelegate.MIN_H
    # 第二次命中缓存，结果一致
    assert delegate.row_height(index, 600) == first
    # 缓存失效后按新字号重算
    delegate.invalidate()
    assert delegate.row_height(index, 600) >= CardDelegate.MIN_H


def test_zoom_rebuilds_layout(qapp, monkeypatch, tmp_path):
    monkeypatch.setenv("GRASS_SKIP_MODEL_LOAD", "1")
    monkeypatch.setenv("GRASS_DATA_DIR", str(tmp_path))
    from grass_ui import theme
    from grass_ui.mainwindow import MainWindow

    window = MainWindow()
    try:
        window._set_scale(1.3)
        assert abs(theme.SCALE - 1.3) < 0.01
        window._set_scale(1.0)
        assert abs(theme.SCALE - 1.0) < 0.01
    finally:
        window.close()


def test_langs_and_rounds_stay_in_sync(qapp, monkeypatch, tmp_path):
    """语言列表与轮数必须始终一致，避免链条显示的语言数和列表条数对不上"""
    monkeypatch.setenv("GRASS_SKIP_MODEL_LOAD", "1")
    monkeypatch.setenv("GRASS_DATA_DIR", str(tmp_path))
    from grass_ui.mainwindow import MainWindow

    window = MainWindow()
    try:
        window._params_pane.set_rounds(2)
        window._on_rounds_change(2)
        assert window._langs_pane.langs() == ["英语", "法语"]
        assert window._params_pane.rounds() == 2

        # 预设/配置带来的语言条数不同时，轮数要跟着语言数走
        window._apply_langs(["英语", "法语", "俄语"])
        assert window._params_pane.rounds() == 3
        assert window._langs_pane.langs() == ["英语", "法语", "俄语"]
        assert window._langs_pane._chain.text() == "中文 → 英语 → 法语 → 俄语 → 中文"

        # 反向兜底：语言列表被直接改动后，刷新链条也会把轮数纠正过来
        window._params_pane.set_rounds(2)
        window._langs_pane.set_langs(["日语", "德语", "俄语"])
        window._update_chain_label()
        assert window._params_pane.rounds() == 3
        assert window._langs_pane._chain.text() == "中文 → 日语 → 德语 → 俄语 → 中文"
    finally:
        window.close()


def test_lang_chips_not_clipped(qapp):
    """多语言方块换行后，滚动区高度要覆盖所有行，不能把后面的语言裁掉"""
    from grass_ui.panes import LangsPane

    pane = LangsPane()
    pane.resize(360, 220)
    pane.show()
    pane.set_langs(["英语", "法语", "俄语", "日语", "德语"])
    for _ in range(5):
        qapp.processEvents()
    host = pane._host
    assert len(pane._buttons) == 5
    bottoms = [b.mapTo(host, b.rect().bottomLeft()).y() for b in pane._buttons]
    # 方块必须全部落在宿主控件高度内（换行后的每一行都可见）
    assert max(bottoms) < host.height()
    pane.close()
