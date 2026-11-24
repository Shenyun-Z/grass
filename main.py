# -*- coding: utf-8 -*-
"""程序入口：-​-version 支持、打包版日志重定向、启动 Qt 界面"""
import os
import sys

from version import __version__


def _fix_null_streams() -> None:
    """PyInstaller 的 --windowed 打包后 sys.stdout / sys.stderr 是 None

    某些库（transformers 日志、sentencepiece、tqdm 等）会直接往这些流写东西，
    在 None 上写会抛 AttributeError，表现为"模型加载失败"这类莫名错误。
    这里把它们指向程序目录下的日志文件，既避免崩溃，也方便事后排查。
    """
    if not getattr(sys, "frozen", False):
        return
    log_dir = os.path.dirname(os.path.abspath(sys.executable))
    for name in ("stdout", "stderr"):
        if getattr(sys, name) is None:
            try:
                path = os.path.join(log_dir, "grass.log")
                stream = open(path, "a", encoding="utf-8", buffering=1)
            except OSError:
                stream = open(os.devnull, "w", encoding="utf-8")
            setattr(sys, name, stream)


def main() -> int:
    if "--version" in sys.argv:
        print(f"grass v{__version__}")
        return 0

    _fix_null_streams()

    from grass_ui.app import run

    return run()


if __name__ == "__main__":
    sys.exit(main())
