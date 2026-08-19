# -*- coding: utf-8 -*-
from gui import App


if __name__ == "__main__":
    app = App()
    try:
        from tkinterdnd2 import DND_FILES
        app.drop_target_register(DND_FILES)
        app.dnd_bind('<<Drop>>', app._on_drop)
    except ImportError:
        pass
    app.mainloop()