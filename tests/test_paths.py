# -*- coding: utf-8 -*-
"""模型目录定位测试：源码运行用文件目录，PyInstaller 打包后用 exe 目录"""
import importlib
import os
import sys

import hymt2


def test_base_dir_source_mode():
    expect = os.path.dirname(os.path.abspath(hymt2.__file__))
    assert hymt2.base_dir() == expect


def test_base_dir_frozen_mode(monkeypatch):
    fake_exe = os.path.join("C:\\", "grass", "生草机.exe")
    monkeypatch.setattr(sys, "frozen", True, raising=False)
    monkeypatch.setattr(sys, "executable", fake_exe, raising=False)
    assert hymt2.base_dir() == os.path.dirname(os.path.abspath(fake_exe))


def test_model_path_env_wins(monkeypatch):
    # _MODEL_PATH 在导入期解析，因此用 reload 模拟“启动前已设置环境变量”
    target = os.path.join("C:\\", "models", "hy-mt2")
    monkeypatch.setenv("HYMT2_MODEL_PATH", target)
    try:
        mod = importlib.reload(hymt2)
        assert mod.model_path() == target
    finally:
        monkeypatch.delenv("HYMT2_MODEL_PATH", raising=False)
        importlib.reload(hymt2)


def test_model_path_default_is_sibling_of_base_dir(monkeypatch):
    monkeypatch.delenv("HYMT2_MODEL_PATH", raising=False)
    mod = importlib.reload(hymt2)
    assert mod.model_path() == os.path.join(mod.base_dir(), "hymt2_model")


def test_fix_null_streams_noop_outside_frozen(monkeypatch):
    import sys
    import main
    monkeypatch.delattr(sys, "frozen", raising=False)
    before = sys.stdout
    main._fix_null_streams()
    assert sys.stdout is before
