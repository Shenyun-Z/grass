# -*- coding: utf-8 -*-
"""拖放支持：把 tkinterdnd2 的拖放能力挂到 customtkinter 的 CTk 窗口

CTk 不是 tkinterdnd2.Tk，本身没有 drag-and-drop 方法；直接用
`app.drop_target_register()` 会抛 AttributeError 让程序启动即崩。
这里统一处理：用 DnDWrapper 作为第二基类，创建后再加载 tkdnd 扩展；
任何一步失败都只返回 False，不影响程序启动。
"""
from __future__ import annotations

import types
from typing import Callable, Optional, Type


def make_app(app_cls: Type) -> Type:
    """返回带拖放能力的窗口类；tkinterdnd2 不可用时原样返回"""
    try:
        from tkinterdnd2.TkinterDnD import DnDWrapper
    except Exception:
        return app_cls
    try:
        if issubclass(app_cls, DnDWrapper):
            return app_cls
    except TypeError:
        return app_cls

    class _DnDApp(app_cls, DnDWrapper):  # type: ignore[misc, valid-type]
        pass

    return _DnDApp


def enable_dnd(app, handler: Optional[Callable] = None) -> bool:
    """在窗口上注册文件拖放事件；成功返回 True，失败返回 False（不抛异常）"""
    try:
        from tkinterdnd2 import DND_FILES
        from tkinterdnd2.TkinterDnD import DnDWrapper, _require
    except Exception:
        return False
    try:
        if not isinstance(app, DnDWrapper):
            # 兼容未继承 DnDWrapper 的普通窗口：把方法补挂到实例上
            for name, fn in vars(DnDWrapper).items():
                if callable(fn) and not name.startswith("__"):
                    setattr(app, name, types.MethodType(fn, app))
            app._subst_format_dnd = DnDWrapper._subst_format_dnd
            app._subst_format_str_dnd = DnDWrapper._subst_format_str_dnd
        _require(app)  # 加载平台对应的 tkdnd 扩展
        app.drop_target_register(DND_FILES)
        if handler is not None:
            app.dnd_bind("<<Drop>>", handler)
        return True
    except Exception:
        # 扩展缺失、平台不支持等都不该阻止程序运行，只是拖放不可用
        return False
