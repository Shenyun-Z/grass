# -*- coding: utf-8 -*-
"""模型目录定位测试：源码运行用文件目录，PyInstaller 打包后用 exe 目录"""
import os
import sys

import modelpath


def test_base_dir_source_mode():
    expect = os.path.dirname(os.path.abspath(modelpath.__file__))
    assert modelpath.base_dir() == expect


def test_base_dir_frozen_mode(monkeypatch):
    fake_exe = os.path.join("C:\\", "grass", "grass.exe")
    monkeypatch.setattr(sys, "frozen", True, raising=False)
    monkeypatch.setattr(sys, "executable", fake_exe, raising=False)
    assert modelpath.base_dir() == os.path.dirname(os.path.abspath(fake_exe))


def test_env_wins(monkeypatch):
    target = os.path.join("C:\\", "models", "milmmt_model")
    monkeypatch.setenv("GRASS_MODEL_PATH", target)
    assert modelpath.model_dir() == target


def test_existing_dir_preferred(monkeypatch, tmp_path):
    monkeypatch.delenv("GRASS_MODEL_PATH", raising=False)
    monkeypatch.setattr(modelpath, "base_dir", lambda: str(tmp_path))
    (tmp_path / "milmmt_model").mkdir()
    (tmp_path / "milmmt_model" / "config.json").write_text("{}", encoding="utf-8")
    assert modelpath.model_dir().endswith("milmmt_model")


def test_legacy_model_dir_supported(monkeypatch, tmp_path):
    monkeypatch.delenv("GRASS_MODEL_PATH", raising=False)
    monkeypatch.setattr(modelpath, "base_dir", lambda: str(tmp_path))
    (tmp_path / "model").mkdir()
    (tmp_path / "model" / "config.json").write_text("{}", encoding="utf-8")
    assert modelpath.model_dir() == str(tmp_path / "model")


def test_default_dir_when_nothing_found(monkeypatch, tmp_path):
    monkeypatch.delenv("GRASS_MODEL_PATH", raising=False)
    monkeypatch.setattr(modelpath, "base_dir", lambda: str(tmp_path))
    assert modelpath.model_dir() == str(tmp_path / "milmmt_model")


def test_fix_null_streams_noop_outside_frozen(monkeypatch):
    import main
    monkeypatch.delattr(sys, "frozen", raising=False)
    before = sys.stdout
    main._fix_null_streams()
    assert sys.stdout is before
