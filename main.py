# -*- coding: utf-8 -*-
import sys

from version import __version__


if __name__ == "__main__":
    if "--version" in sys.argv:
        print(f"grass v{__version__}")
        sys.exit(0)

    from dnd import enable_dnd, make_app
    from gui import App

    app = make_app(App)()
    # 拖放是增强功能：不可用时静默降级，绝不因它崩溃
    enable_dnd(app, getattr(app, "_on_drop", None))
    app.mainloop()
