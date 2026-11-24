# -*- coding: utf-8 -*-
import sys

from version import __version__


if __name__ == "__main__":
    if "--version" in sys.argv:
        print(f"grass v{__version__}")
        sys.exit(0)
    from gui import App

    app = App()
    try:
        from tkinterdnd2 import DND_FILES
        app.drop_target_register(DND_FILES)
        app.dnd_bind('<<Drop>>', app._on_drop)
    except ImportError:
        pass
    app.mainloop()
