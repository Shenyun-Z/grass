# -*- coding: utf-8 -*-
"""拖放降级测试：不需要 tkinter/customtkinter

覆盖两条路径：
1. tkinterdnd2 未安装 -> make_app 原样返回、enable_dnd 返回 False；
2. 环境异常（窗口对象没有 tk 扩展）-> enable_dnd 返回 False 而不是抛异常。
"""
import dnd


class _DummyApp:
    """模拟一个没有 tkdnd 能力的窗口对象"""

    def __init__(self, fail=False):
        self.fail = fail

    @property
    def tk(self):
        raise RuntimeError("no tcl interpreter")


class _FailingApp(_DummyApp):
    pass


def test_make_app_returns_same_class_without_tkinterdnd2(monkeypatch):
    # 明确模拟“没装 tkinterdnd2”的环境
    import sys
    monkeypatch.setitem(sys.modules, "tkinterdnd2", None)
    out = dnd.make_app(_DummyApp)
    assert out is _DummyApp


def test_enable_dnd_returns_false_without_tkinterdnd2(monkeypatch):
    import sys
    monkeypatch.setitem(sys.modules, "tkinterdnd2", None)
    assert dnd.enable_dnd(_DummyApp()) is False


def test_enable_dnd_never_raises_on_broken_window():
    # 未安装 tkinterdnd2 时应直接返回 False；装了也不能抛异常
    try:
        result = dnd.enable_dnd(_DummyApp())
    except Exception as exc:  # pragma: no cover - 这里显式要求不抛
        raise AssertionError(f"enable_dnd 不应抛异常，实际: {exc!r}")
    assert result in (True, False)
