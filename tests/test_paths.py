# -*- coding: utf-8 -*-
"""模型目录定位测试：源码运行用文件目录，PyInstaller 打包后用 exe 目录"""
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
    monkeypatch.setenv("HYMT2_MODEL_PATH", os.path.join("C:\\", "models", "hy-mt2"))
    assert hymt2._MODEL_PATH == os.environ["HYMT2_MODEL_PATH"]


def test_model_path_default_is_sibling_of_base_dir():
    assert hymt2._MODEL_PATH == os.environ.get("HYMT2_MODEL_PATH") or \
        hymt2._MODEL_PATH == os.path.join(hymt2.base_dir(), "hymt2_model")
