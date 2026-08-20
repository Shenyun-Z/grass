# -*- coding: utf-8 -*-
"""生草机 GUI 主应用 — 使用 Mixin 组合模式拆分职责"""
import copy
import os
import threading
import time
import tkinter as tk
from tkinter import filedialog

import customtkinter as ctk

from gui_styles import COLORS, FONTS, style_card, style_btn
from gui_split_view import SplitView
from gui_compare import CompareView
from gui_utils import ToastMixin, ColorAnimMixin
from gui_lang import LangMixin
from gui_config import ConfigMixin
from gui_translate import TranslateMixin
from gui_dialogs import StepDetailDialog, HistoryDialog, SplitPunctDialog
from engine import _preprocess, _split_by_threshold, _get_model, DEFAULT_SPLIT_PUNCTS


class App(ToastMixin, ColorAnimMixin, LangMixin, ConfigMixin, TranslateMixin, ctk.CTk):
    """主应用类 — 通过 Mixin 组合 UI、语言、配置、翻译等能力"""

    def __init__(self):
        super().__init__()
        self.title("生草机")
        self.geometry("960x820")
        self.minsize(550, 350)
        self.configure(fg_color=COLORS["bg"])

        # 状态变量
        self._rounds_var = ctk.IntVar(value=10)
        self._threshold_var = ctk.IntVar(value=20)
        self._final_lang_var = ctk.StringVar(value="中文")
        self._random_mode_var = ctk.StringVar(value="固定")
        self._lang_vars = []
        self._excluded_langs = ["英语"]

        # 运行状态
        self._segments = []
        self._running = False
        self._model_ready = False
        self._input_view = "原文"
        self._raw_text = ""
        self._input_collapsed = False
        self._split_collapsed = False
        self._input_height = 120
        self._split_height = 110
        self._drag_target = None
        self._drag_start_y = 0
        self._drag_start_h = 0
        self._relayout_after_id = None
        self._last_cols = 0
        self._last_lang_count = 0
        self._seg_states = {}
        self._lang_btns = []
        self._poll_after_id = None
        self._msg_queue = None
        self._drag_tip = None
        self._seg_steps = {}
        self._seg_results = {}
        self._auto_follow_var = ctk.BooleanVar(value=True)
        self._initial_layout_done = False
        self._split_view = None

        # 切分标点与历史记录
        self._split_puncts = DEFAULT_SPLIT_PUNCTS
        self._history = []
        self._history_limit = 20
        self._history_next_id = 1

        # 结果视图（结果 / 对照）与对照源（原文 / 历史记录）
        self._result_view = "结果"
        self._compare_source = "原文"

        # 共享引用（供 Mixin 使用）
        self._STOP_EVENT = threading.Event()
        self._FINAL_LANG = "中文"
        self._COLORS = COLORS
        self._FONTS = FONTS

        self._build_ui()
        self._set_default_langs(10)
        self.bind("<Configure>", self._on_window_resize)
        self.bind("<Return>", lambda e: self._on_return_key(e))
        self.bind("<Control-Key-Return>", lambda e: self._on_ctrl_enter(e))
        self.bind("<Control-s>", lambda e: self._save_result())
        self.bind("<Control-S>", lambda e: self._save_result())
        self.bind("<Escape>", lambda e: self._stop() if self._running else None)
        self.bind("<Control-Shift-KeyPress-V>", lambda e: self._paste_from_clipboard())
        self.bind("<Control-h>", lambda e: self._open_history_dialog())
        self.bind("<Control-H>", lambda e: self._open_history_dialog())
        self._load_model_async()
        self.after(300, self._deferred_initial_layout)

    # ===== 初始化 =====
    def _deferred_initial_layout(self):
        self.update_idletasks()
        self._canvas.itemconfig("inner", width=self._canvas.winfo_width())
        self.update_idletasks()
        self._on_input_change()
        self._initial_layout_done = True

    # ===== 快捷键 =====
    def _on_return_key(self, event):
        if event.widget == self._input_box:
            self._on_input_edit()

    def _on_ctrl_enter(self, event):
        w = event.widget
        while w is not None:
            if w is self._input_box:
                return
            try:
                w = w.master
            except Exception:
                break
        self._toggle()
        return "break"

    # ===== UI 构建 =====
    def _build_ui(self):
        self.grid_columnconfigure(0, weight=1)
        self.grid_rowconfigure(0, weight=1)

        self._canvas = tk.Canvas(self, highlightthickness=0, bg=COLORS["bg"])
        self._canvas.grid(row=0, column=0, sticky="nsew")
        self._scrollbar = ctk.CTkScrollbar(self, orientation="vertical", command=self._canvas.yview)
        self._scrollbar.grid(row=0, column=1, sticky="ns")
        self._canvas.configure(yscrollcommand=self._scrollbar.set)

        self._main_scroll = ctk.CTkFrame(self._canvas, fg_color=COLORS["bg"])
        self._canvas.create_window((0, 0), window=self._main_scroll, anchor="nw", tags="inner")
        self._main_scroll.grid_columnconfigure(0, weight=1)
        self._main_scroll.bind("<Configure>", self._on_inner_configure)
        self._canvas.bind("<Configure>", self._on_canvas_configure)
        self._bind_mousewheel()

        self._build_input()
        self._build_params()
        self._build_langs()
        self._build_split_preview()
        self._build_control_bar()
        self._build_progress()
        self._build_result()
        self.after(100, self._fix_split_mousewheel)

    def _on_canvas_configure(self, event):
        self._canvas.itemconfig("inner", width=event.width)

    def _on_inner_configure(self, event):
        self.after_idle(self._update_scroll_region)

    def _update_scroll_region(self):
        try:
            self._canvas.configure(scrollregion=self._canvas.bbox("all"))
        except Exception:
            pass

    def _bind_mousewheel(self):
        def _on_mousewheel(event):
            w = event.widget
            while w is not None:
                # 滚轮位于弹窗内时，交给弹窗组件自身处理，不滚动主窗口
                if w is not self and isinstance(w, ctk.CTkToplevel):
                    return
                if hasattr(w, '_split_view') and w._split_view:
                    try:
                        w._split_view._canvas.yview_scroll(int(-1 * (event.delta / 120)), "units")
                    except Exception:
                        pass
                    return "break"
                if w is self._result_box:
                    return
                if w is self._input_box:
                    return
                try:
                    w = w.master
                except Exception:
                    break
            self._canvas.yview_scroll(int(-1 * (event.delta / 10)), "units")
        self.bind_all("<MouseWheel>", _on_mousewheel)

    def _fix_split_mousewheel(self):
        pass

    # ===== 输入区 =====
    def _build_input(self):
        frame = style_card(self._main_scroll)
        frame.grid(row=0, column=0, sticky="ew", padx=16, pady=(16, 8))
        frame.grid_columnconfigure(0, weight=1)

        header = ctk.CTkFrame(frame, fg_color="transparent")
        header.grid(row=0, column=0, sticky="ew", padx=14, pady=(10, 6))
        self._input_toggle_btn = ctk.CTkLabel(
            header, text="▼", font=FONTS["caption"](), cursor="hand2", width=20,
            text_color=COLORS["text_secondary"])
        self._input_toggle_btn.pack(side="left", padx=(0, 6))
        self._input_toggle_btn.bind("<Button-1>", lambda e: self._toggle_input())
        ctk.CTkLabel(header, text="输入", font=FONTS["section"](),
                     text_color=COLORS["text"]).pack(side="left")
        self._view_toggle = ctk.CTkSegmentedButton(
            header, values=["原文", "去空格"], command=self._on_view_toggle,
            font=FONTS["body"](), fg_color=COLORS["surface"],
            selected_color=COLORS["accent"], selected_hover_color=COLORS["accent_hover"],
            unselected_color=COLORS["surface_hover"], text_color=COLORS["text"],
        )
        self._view_toggle.pack(side="right")
        self._view_toggle.set("原文")

        self._input_box = ctk.CTkTextbox(
            frame, height=self._input_height, wrap="word",
            font=FONTS["body"](), border_width=1,
            border_color=COLORS["border"], fg_color=COLORS["surface"],
            text_color=COLORS["text"], scrollbar_button_color=COLORS["border"],
            scrollbar_button_hover_color=COLORS["accent"],
        )
        self._input_box.grid(row=1, column=0, columnspan=2, sticky="ew", padx=14, pady=(0, 6))
        self._input_box.bind("<KeyRelease>", lambda e: self._on_input_edit())
        self._input_box.bind("<FocusIn>", lambda e: self._input_box.configure(border_color=COLORS["accent"]))
        self._input_box.bind("<FocusOut>", lambda e: self._input_box.configure(border_color=COLORS["border"]))

        self._input_action_frame = ctk.CTkFrame(frame, fg_color="transparent")
        self._input_action_frame.grid(row=2, column=0, columnspan=2, sticky="ew", padx=14, pady=(0, 6))
        self._input_action_frame.grid_columnconfigure(0, weight=0)
        self._input_action_frame.grid_columnconfigure(1, weight=0)
        self._input_action_frame.grid_columnconfigure(2, weight=1)
        self._input_action_frame.grid_columnconfigure(3, weight=0)

        self._load_file_btn = style_btn(
            self._input_action_frame, "从文件读取", self._load_file,
            width=100, font=FONTS["body"](), height=28)
        self._load_file_btn.grid(row=0, column=0, sticky="w")

        self._clipboard_btn = style_btn(
            self._input_action_frame, "读剪贴板", self._paste_from_clipboard,
            width=90, font=FONTS["body"](), height=28,
            fg_color=COLORS["surface_hover"], hover_color=COLORS["accent"],
            text_color=COLORS["text"])
        self._clipboard_btn.grid(row=0, column=1, sticky="w", padx=(6, 0))

        ctk.CTkLabel(
            self._input_action_frame, text="可拖放 .txt  ·  Ctrl+Shift+V 读入剪贴板",
            font=FONTS["caption"](), text_color=COLORS["text_secondary"]
        ).grid(row=0, column=2, sticky="e", padx=(0, 12))

        self._char_count_label = ctk.CTkLabel(
            self._input_action_frame, text="字符数: 0",
            font=FONTS["caption"](), text_color=COLORS["text_secondary"])
        self._char_count_label.grid(row=0, column=3, sticky="e")

        self._input_grip = ctk.CTkFrame(
            frame, height=6, fg_color=COLORS["border"], cursor="sb_v_double_arrow")
        self._input_grip.grid(row=3, column=0, columnspan=2, sticky="ew", padx=14, pady=(0, 10))
        self._input_grip.bind("<Button-1>", lambda e: self._start_drag(e, self._input_box, "_input_height"))
        self._input_grip.bind("<Enter>", lambda e: self._input_grip.configure(fg_color=COLORS["accent"]))
        self._input_grip.bind("<Leave>", lambda e: self._input_grip.configure(fg_color=COLORS["border"]))

    # ===== 参数区 =====
    def _build_params(self):
        frame = style_card(self._main_scroll)
        frame.grid(row=1, column=0, sticky="ew", padx=16, pady=8)
        frame.grid_columnconfigure(0, weight=1)

        ctk.CTkLabel(frame, text="参数", font=FONTS["section"](),
                     text_color=COLORS["text"]).grid(row=0, column=0, sticky="w", padx=14, pady=(10, 6))

        top = ctk.CTkFrame(frame, fg_color="transparent")
        top.grid(row=1, column=0, sticky="ew", padx=14, pady=(0, 10))

        ctk.CTkLabel(top, text="轮数", font=FONTS["caption"](),
                     text_color=COLORS["text_secondary"]).pack(side="left")
        self._rounds_menu = ctk.CTkOptionMenu(
            top, values=[str(i) for i in range(1, 31)],
            variable=self._rounds_var, width=50, font=FONTS["body"](),
            command=self._on_rounds_change,
            fg_color=COLORS["surface"], button_color=COLORS["accent"],
            button_hover_color=COLORS["accent_hover"],
            dropdown_fg_color=COLORS["surface"],
            dropdown_hover_color=COLORS["surface_hover"],
            text_color=COLORS["text"],
        )
        self._rounds_menu.pack(side="left", padx=(4, 16))

        ctk.CTkLabel(top, text="段字数", font=FONTS["caption"](),
                     text_color=COLORS["text_secondary"]).pack(side="left")
        self._threshold_menu = ctk.CTkOptionMenu(
            top, values=[str(i) for i in range(5, 101, 5)],
            variable=self._threshold_var, width=50, font=FONTS["body"](),
            command=lambda v: self._on_input_change(),
            fg_color=COLORS["surface"], button_color=COLORS["accent"],
            button_hover_color=COLORS["accent_hover"],
            dropdown_fg_color=COLORS["surface"],
            dropdown_hover_color=COLORS["surface_hover"],
            text_color=COLORS["text"],
        )
        self._threshold_menu.pack(side="left", padx=(4, 16))

        ctk.CTkLabel(top, text="译回", font=FONTS["caption"](),
                     text_color=COLORS["text_secondary"]).pack(side="left")
        self._final_lang_btn = ctk.CTkButton(
            top, textvariable=self._final_lang_var, command=self._open_final_lang_picker,
            width=80, height=28, font=FONTS["body"](),
            fg_color=COLORS["accent"], hover_color=COLORS["accent_hover"],
            text_color="white", corner_radius=6)
        self._final_lang_btn.pack(side="left", padx=(4, 0))

        self._random_mode_seg = ctk.CTkSegmentedButton(
            top, values=["固定", "低强度", "高强度"],
            variable=self._random_mode_var,
            command=self._on_random_mode_change,
            font=FONTS["caption"](), fg_color=COLORS["surface"],
            selected_color=COLORS["accent"], selected_hover_color=COLORS["accent_hover"],
            unselected_color=COLORS["surface_hover"], text_color=COLORS["text"],
        )
        self._random_mode_seg.pack(side="right", padx=(16, 0))

        self._exclude_btn = ctk.CTkButton(
            top, text="排除语言...", command=self._open_exclude_dialog,
            width=90, height=28, font=FONTS["caption"](),
            fg_color=COLORS["surface_hover"], hover_color=COLORS["accent"],
            text_color=COLORS["text"], corner_radius=4, state="disabled")
        self._exclude_btn.pack(side="right", padx=(8, 0))

    # ===== 中转语言区 =====
    def _build_langs(self):
        frame = style_card(self._main_scroll)
        frame.grid(row=2, column=0, sticky="ew", padx=16, pady=8)
        frame.grid_columnconfigure(0, weight=1)

        header = ctk.CTkFrame(frame, fg_color="transparent")
        header.grid(row=0, column=0, sticky="ew", padx=14, pady=(10, 8))
        ctk.CTkLabel(header, text="中转语言", font=FONTS["section"](),
                     text_color=COLORS["text"]).pack(side="left")

        right_btns = ctk.CTkFrame(header, fg_color="transparent")
        right_btns.pack(side="right")

        self._preset_btn = style_btn(
            right_btns, "语言预设...", self._open_preset,
            width=100, font=FONTS["body"](), height=28)
        self._preset_btn.pack(side="right", padx=(4, 0))

        style_btn(right_btns, "导入", self._import_config,
                  width=50, height=28, font=FONTS["caption"](),
                  fg_color=COLORS["surface_hover"], hover_color=COLORS["accent"]).pack(side="right", padx=(0, 2))
        style_btn(right_btns, "导出", self._export_config,
                  width=50, height=28, font=FONTS["caption"](),
                  fg_color=COLORS["surface_hover"], hover_color=COLORS["accent"]).pack(side="right", padx=(0, 2))

        self._config_menu = ctk.CTkOptionMenu(
            right_btns, values=self._get_config_names(),
            width=100, height=28, font=FONTS["caption"](),
            fg_color=COLORS["surface"], button_color=COLORS["accent"],
            button_hover_color=COLORS["accent_hover"],
            dropdown_fg_color=COLORS["surface"],
            dropdown_hover_color=COLORS["surface_hover"],
            text_color=COLORS["text"],
            command=self._on_config_menu_change,
        )
        self._config_menu.pack(side="right", padx=(0, 2))
        self._config_menu.set("配置")

        self._chain_label = ctk.CTkLabel(
            frame, text="", font=FONTS["body"](),
            text_color=COLORS["accent"], wraplength=800, justify="left")
        self._chain_label.grid(row=1, column=0, sticky="ew", padx=14, pady=(0, 4))

        self._lang_container = ctk.CTkFrame(frame, fg_color="transparent")
        self._lang_container.grid(row=2, column=0, sticky="ew", padx=14, pady=(0, 10))

    # ===== 分块预览区 =====
    def _build_split_preview(self):
        frame = style_card(self._main_scroll)
        frame.grid(row=3, column=0, sticky="ew", padx=16, pady=8)
        frame.grid_columnconfigure(0, weight=1)

        header = ctk.CTkFrame(frame, fg_color="transparent")
        header.grid(row=0, column=0, sticky="ew", padx=14, pady=(10, 6))
        self._split_toggle_btn = ctk.CTkLabel(
            header, text="▼", font=FONTS["caption"](), cursor="hand2", width=20,
            text_color=COLORS["text_secondary"])
        self._split_toggle_btn.pack(side="left", padx=(0, 6))
        self._split_toggle_btn.bind("<Button-1>", lambda e: self._toggle_split())
        ctk.CTkLabel(header, text="分块预览", font=FONTS["section"](),
                     text_color=COLORS["text"]).pack(side="left")
        self._auto_follow_cb = ctk.CTkCheckBox(
            header, text="自动跟随", variable=self._auto_follow_var,
            font=FONTS["caption"](), checkbox_width=16, checkbox_height=16,
            fg_color=COLORS["accent"], hover_color=COLORS["accent_hover"],
            border_color=COLORS["border"], text_color=COLORS["text_secondary"])
        self._auto_follow_cb.pack(side="left", padx=(10, 0))
        self._punct_btn = style_btn(
            header, "切分符...", self._open_split_punct_dialog,
            width=80, height=24, font=FONTS["caption"](),
            fg_color=COLORS["surface_hover"], hover_color=COLORS["accent"],
            text_color=COLORS["text"])
        self._punct_btn.pack(side="left", padx=(10, 0))
        self._split_info = ctk.CTkLabel(
            header, text="", font=FONTS["caption"](),
            text_color=COLORS["text_secondary"])
        self._split_info.pack(side="right")

        content_frame = ctk.CTkFrame(frame, fg_color="transparent")
        content_frame.grid(row=1, column=0, sticky="ew", padx=14, pady=(0, 6))

        scroll_container = ctk.CTkFrame(content_frame, fg_color=COLORS["bg"],
                                       border_width=1, border_color=COLORS["border"], corner_radius=6,
                                       height=self._split_height)
        scroll_container.pack(fill="both", expand=True)
        scroll_container.pack_propagate(False)

        self._split_view = SplitView(scroll_container, on_seg_click=self._show_seg_detail)
        self._split_container = scroll_container

        self._split_grip = ctk.CTkFrame(
            frame, height=6, fg_color=COLORS["border"], cursor="sb_v_double_arrow")
        self._split_grip.grid(row=2, column=0, sticky="ew", padx=14, pady=(0, 10))
        self._split_grip.bind("<Button-1>", lambda e: self._start_drag(e, scroll_container, "_split_height", allow_during_running=True))
        self._split_grip.bind("<Enter>", lambda e: self._split_grip.configure(fg_color=COLORS["accent"]))
        self._split_grip.bind("<Leave>", lambda e: self._split_grip.configure(fg_color=COLORS["border"]))

    # ===== 控制栏 =====
    def _build_control_bar(self):
        frame = style_card(self._main_scroll)
        frame.grid(row=4, column=0, sticky="ew", padx=16, pady=8)
        frame.grid_columnconfigure(0, weight=1)
        frame.grid_columnconfigure(1, weight=0)

        self._status_label = ctk.CTkLabel(
            frame, text="⟳ 加载模型中...", font=FONTS["body"](),
            text_color=COLORS["info"])
        self._status_label.grid(row=0, column=0, sticky="w", padx=14, pady=12)

        self._start_btn = style_btn(
            frame, "▶ 开始翻译", self._toggle,
            width=150, height=44, font=ctk.CTkFont(size=16, weight="bold"),
            corner_radius=8)
        self._start_btn.grid(row=0, column=1, padx=14, pady=12)
        self._start_btn.configure(state="disabled")

    # ===== 进度区 =====
    def _build_progress(self):
        frame = style_card(self._main_scroll)
        frame.grid(row=5, column=0, sticky="ew", padx=16, pady=8)
        frame.grid_columnconfigure(0, weight=1)
        frame.grid_columnconfigure(1, weight=0)

        ctk.CTkLabel(frame, text="进度", font=FONTS["section"](),
                     text_color=COLORS["text"]).grid(
            row=0, column=0, sticky="w", padx=14, pady=(10, 6), columnspan=2)

        self._progress_bar = ctk.CTkProgressBar(
            frame, height=16, corner_radius=8,
            fg_color=COLORS["surface"], progress_color=COLORS["accent"])
        self._progress_bar.grid(row=1, column=0, sticky="ew", padx=(14, 8), pady=(0, 6))
        self._progress_bar.set(0)

        self._seg_counter = ctk.CTkLabel(
            frame, text="0 / 0", font=FONTS["body"](),
            text_color=COLORS["text_secondary"], width=60)
        self._seg_counter.grid(row=1, column=1, sticky="e", padx=(0, 14), pady=(0, 6))

        self._step_label = ctk.CTkLabel(
            frame, text="", font=FONTS["caption"](),
            text_color=COLORS["text_secondary"])
        self._step_label.grid(row=2, column=0, sticky="w", padx=14, pady=(0, 10), columnspan=2)

    def _animate_progress(self, target, steps=8, delay=16):
        current = self._progress_bar.get()
        if steps <= 0 or abs(target - current) < 0.001:
            self._progress_bar.set(target)
            return
        delta = (target - current) / steps
        self._progress_bar.set(current + delta)
        self.after(delay, lambda: self._animate_progress(target, steps - 1, delay))

    # ===== 结果区 =====
    def _build_result(self):
        frame = style_card(self._main_scroll)
        frame.grid(row=6, column=0, sticky="ew", padx=16, pady=(8, 16))
        frame.grid_columnconfigure(0, weight=1)

        header = ctk.CTkFrame(frame, fg_color="transparent")
        header.grid(row=0, column=0, sticky="ew", padx=14, pady=(10, 6))
        header.grid_columnconfigure(0, weight=1)

        ctk.CTkLabel(header, text="结果", font=FONTS["section"](),
                     text_color=COLORS["text"]).grid(row=0, column=0, sticky="w")

        self._result_view_seg = ctk.CTkSegmentedButton(
            header, values=["结果", "对照"], command=self._on_result_view_change,
            font=FONTS["caption"](), fg_color=COLORS["surface"],
            selected_color=COLORS["accent"], selected_hover_color=COLORS["accent_hover"],
            unselected_color=COLORS["surface_hover"], text_color=COLORS["text"],
        )
        self._result_view_seg.grid(row=0, column=1, padx=(8, 3))
        self._result_view_seg.set("结果")

        self._compare_menu = ctk.CTkOptionMenu(
            header, values=["原文"], command=self._on_compare_source_change,
            width=150, height=28, font=FONTS["caption"](),
            fg_color=COLORS["surface"], button_color=COLORS["accent"],
            button_hover_color=COLORS["accent_hover"],
            dropdown_fg_color=COLORS["surface"],
            dropdown_hover_color=COLORS["surface_hover"],
            text_color=COLORS["text"],
        )
        self._compare_menu.grid(row=0, column=2, padx=3)
        self._compare_menu.set("原文")
        self._compare_menu.grid_remove()

        self._history_btn = style_btn(header, "历史", self._open_history_dialog,
                                      width=55, height=28, font=FONTS["body"](),
                                      fg_color=COLORS["surface_hover"],
                                      hover_color=COLORS["accent"],
                                      text_color=COLORS["text"])
        self._history_btn.grid(row=0, column=3, padx=3)
        style_btn(header, "复制", self._copy_result, width=55, height=28,
                  font=FONTS["body"]()).grid(row=0, column=4, padx=3)
        style_btn(header, "保存", self._save_result, width=55, height=28,
                  font=FONTS["body"]()).grid(row=0, column=5, padx=3)

        self._result_box = ctk.CTkTextbox(
            frame, height=200, wrap="word", state="disabled",
            font=FONTS["body"](), border_width=1,
            border_color=COLORS["border"], fg_color=COLORS["surface"],
            text_color=COLORS["text"], scrollbar_button_color=COLORS["border"],
            scrollbar_button_hover_color=COLORS["accent"],
        )
        self._result_box.grid(row=1, column=0, sticky="ew", padx=14, pady=(0, 10))

        self._compare_container = ctk.CTkFrame(
            frame, fg_color=COLORS["bg"], border_width=1,
            border_color=COLORS["border"], corner_radius=6, height=240)
        self._compare_container.grid(row=1, column=0, sticky="ew", padx=14, pady=(0, 10))
        self._compare_container.pack_propagate(False)
        self._compare_view = CompareView(self._compare_container)
        self._compare_container.grid_remove()

    # ===== 窗口缩放 =====
    def _on_window_resize(self, event):
        if event.widget is not self:
            return
        if self._relayout_after_id is not None:
            self.after_cancel(self._relayout_after_id)
        self._relayout_after_id = self.after(500, self._on_resize_done)

    def _on_resize_done(self):
        self._canvas.itemconfig("inner", width=self._canvas.winfo_width())
        self.update_idletasks()
        self._canvas.configure(scrollregion=self._canvas.bbox("all"))
        self._relayout_langs()
        if self._split_view:
            self._split_view._render()

    # ===== 折叠/拖拽 =====
    def _toggle_input(self):
        if self._running:
            return
        self._input_collapsed = not self._input_collapsed
        if self._input_collapsed:
            self._input_toggle_btn.configure(text="▶")
            self._input_box.grid_remove()
            self._input_action_frame.grid_remove()
            self._input_grip.grid_remove()
        else:
            self._input_toggle_btn.configure(text="▼")
            self._input_box.grid()
            self._input_action_frame.grid()
            self._input_grip.grid()
        self._on_resize_done()

    def _toggle_split(self):
        if self._running:
            return
        self._split_collapsed = not self._split_collapsed
        if self._split_collapsed:
            self._split_toggle_btn.configure(text="▶")
            self._split_container.grid_remove()
            self._split_grip.grid_remove()
        else:
            self._split_toggle_btn.configure(text="▼")
            self._split_container.grid()
            self._split_grip.grid()
        self._on_resize_done()

    def _start_drag(self, event, target, height_attr, allow_during_running=False):
        if self._running and not allow_during_running:
            return
        self._drag_target = target
        self._drag_height_attr = height_attr
        self._drag_start_y = event.y_root
        self._drag_start_h = getattr(self, height_attr)
        self.bind("<B1-Motion>", self._on_drag, add=True)
        self.bind("<ButtonRelease-1>", self._stop_drag, add=True)
        if self._drag_tip is None:
            self._drag_tip = ctk.CTkLabel(
                self, text="", font=FONTS["caption"](),
                fg_color=COLORS["surface"], corner_radius=4,
                text_color=COLORS["text_secondary"], padx=8, pady=4)
        self._drag_tip.lift()
        self._drag_tip.place(x=event.x_root - self.winfo_rootx() + 16,
                             y=event.y_root - self.winfo_rooty())
        self._update_drag_tip()

    def _on_drag(self, event):
        if self._drag_target is None:
            return
        dy = event.y_root - self._drag_start_y
        new_h = max(30, self._drag_start_h + dy)
        setattr(self, self._drag_height_attr, new_h)
        self._drag_target.configure(height=new_h)
        if self._split_view:
            self._split_view._canvas.configure(scrollregion=self._split_view._canvas.bbox('all'))
        if self._drag_tip:
            self._drag_tip.place(x=event.x_root - self.winfo_rootx() + 16,
                                 y=event.y_root - self.winfo_rooty())
            self._update_drag_tip()

    def _update_drag_tip(self):
        if self._drag_tip:
            h = getattr(self, self._drag_height_attr, 0)
            self._drag_tip.configure(text=f"{h}px")

    def _stop_drag(self, event):
        self._drag_target = None
        self.unbind("<B1-Motion>")
        self.unbind("<ButtonRelease-1>")
        if self._drag_tip:
            self._drag_tip.place_forget()
        self._on_resize_done()
        if self._split_view:
            self._split_view._canvas.configure(scrollregion=self._split_view._canvas.bbox('all'))

    # ===== 输入处理 =====
    def _on_view_toggle(self, value):
        if value == "去空格":
            raw = self._input_box.get("1.0", "end-1c")
            if self._input_view == "原文":
                self._raw_text = raw
            clean = _preprocess(raw)
            self._input_box.configure(state="normal")
            self._input_box.delete("1.0", "end")
            self._input_box.insert("1.0", clean)
            self._input_box.configure(state="disabled")
        else:
            self._input_box.configure(state="normal")
            self._input_box.delete("1.0", "end")
            self._input_box.insert("1.0", self._raw_text)
        self._input_view = value
        self._on_input_change()

    def _on_input_edit(self):
        if self._running or self._input_view != "原文":
            return
        self._raw_text = self._input_box.get("1.0", "end-1c")
        self._on_input_change()

    def _load_file(self):
        path = filedialog.askopenfilename(
            title="选择文本文件", filetypes=[("文本文件", "*.txt"), ("所有文件", "*.*")])
        if not path:
            return
        self._set_input_text_from_file(path)

    def _paste_from_clipboard(self):
        """一键读取剪贴板内容填入输入区"""
        if self._running:
            return
        try:
            text = self.clipboard_get()
        except Exception:
            self._show_toast("剪贴板为空或不可读", "warning")
            return
        text = (text or "").strip()
        if not text:
            self._show_toast("剪贴板为空", "warning")
            return
        self._raw_text = text
        self._view_toggle.set("原文")
        self._input_view = "原文"
        self._input_box.configure(state="normal")
        self._input_box.delete("1.0", "end")
        self._input_box.insert("1.0", text)
        self._on_input_change()
        self._show_toast(f"已读入剪贴板（{len(text)} 字符）")

    def _set_input_text_from_file(self, path):
        try:
            with open(path, "r", encoding="utf-8") as f:
                text = f.read()
        except Exception:
            return
        self._raw_text = text
        self._view_toggle.set("原文")
        self._input_view = "原文"
        self._input_box.configure(state="normal")
        self._input_box.delete("1.0", "end")
        self._input_box.insert("1.0", text)
        self._on_input_change()
        self._show_toast(f"已读取 {os.path.basename(path)}")

    def _on_input_change(self):
        if self._running:
            return
        clean = _preprocess(self._raw_text)
        self._char_count_label.configure(text=f"字符数: {len(clean)}")
        try:
            thr = self._threshold_var.get()
        except Exception:
            thr = 20
        if thr < 1:
            thr = 20
        self._segments = _split_by_threshold(clean, thr, self._split_puncts)
        self._seg_states = {i: "waiting" for i in range(len(self._segments))}
        self._seg_results = {}
        if self._split_view:
            self._split_view.set_segments(self._segments)
            info, counter = self._split_view.get_info()
            self._split_info.configure(text=info)
            self._seg_counter.configure(text=counter)

    def _show_seg_detail(self, idx):
        steps = self._seg_steps.get(idx, [])
        if not steps:
            return
        final_lang = self._final_lang_var.get()
        StepDetailDialog(self, idx, steps, final_lang)

    def _set_params_enabled(self, enabled):
        state = "normal" if enabled else "disabled"
        self._rounds_menu.configure(state=state)
        self._threshold_menu.configure(state=state)
        is_fixed = self._random_mode_var.get() == "固定"
        self._preset_btn.configure(state=state if is_fixed else "disabled")
        self._final_lang_btn.configure(state=state)
        self._view_toggle.configure(state=state)
        self._load_file_btn.configure(state=state)
        self._clipboard_btn.configure(state=state)
        self._punct_btn.configure(state=state)
        self._result_view_seg.configure(state=state)
        self._compare_menu.configure(state=state)
        self._random_mode_seg.configure(state=state)
        self._exclude_btn.configure(state="disabled" if (not enabled or is_fixed) else "normal")
        for btn in self._lang_btns:
            btn.configure(state=state if is_fixed else "disabled")

    # ===== 切分标点 =====
    def _open_split_punct_dialog(self):
        SplitPunctDialog(self, self._split_puncts, self._apply_split_puncts)

    def _apply_split_puncts(self, puncts):
        self._split_puncts = puncts
        self._on_input_change()
        if puncts:
            self._show_toast(f"切分符已更新（{len(puncts)} 个字符）")
        else:
            self._show_toast("已禁用标点切分（仅按段字数硬切）", "warning")

    # ===== 结果视图切换 =====
    def _on_result_view_change(self, value):
        self._result_view = value
        if value == "对照":
            self._result_box.grid_remove()
            self._compare_container.grid()
            self._compare_menu.grid()
            self._render_compare_view()
        else:
            self._compare_container.grid_remove()
            self._compare_menu.grid_remove()
            self._result_box.grid()

    def _on_compare_source_change(self, value):
        self._compare_source = value
        self._render_compare_view()

    def _render_compare_view(self):
        """渲染对照视图：左栏为原文或某次历史结果，右栏为当前结果"""
        if self._compare_view is None:
            return
        right_items = [self._seg_results.get(i, "") for i in range(len(self._segments))]
        left_title, left_items = "原文", list(self._segments)
        if self._compare_source != "原文":
            rec = next((r for r in self._history
                        if self._history_label(r) == self._compare_source), None)
            if rec is not None:
                left_title = self._compare_source
                left_items = [rec["seg_results"].get(i, "")
                              for i in range(len(rec["segments"]))]
        self._compare_view.set_data(left_title, left_items, "当前结果", right_items)

    # ===== 历史记录 =====
    def _history_label(self, rec):
        mark = " ⏹" if rec.get("stopped") else ""
        return f"#{rec['id']} {rec['time']}{mark}"

    def _add_history_entry(self, stopped=False, elapsed_str=""):
        """翻译完成/停止后将本次结果写入内存历史（最多保留 N 条）"""
        if not self._seg_results:
            return
        result_text = self._result_box.get("1.0", "end-1c")
        rec = {
            "id": self._history_next_id,
            "date": time.strftime("%m-%d"),
            "time": time.strftime("%H:%M:%S"),
            "input": self._raw_text,
            "result": result_text,
            "segments": list(self._segments),
            "seg_results": dict(self._seg_results),
            "seg_steps": copy.deepcopy(self._seg_steps),
            "params": {
                "rounds": self._rounds_var.get(),
                "mode": self._random_mode_var.get(),
                "langs": [v.get() for v in self._lang_vars],
                "final": self._final_lang_var.get(),
                "threshold": self._threshold_var.get(),
                "split_puncts": self._split_puncts,
            },
            "stopped": stopped,
            "elapsed": elapsed_str,
        }
        self._history_next_id += 1
        self._history.append(rec)
        while len(self._history) > self._history_limit:
            self._history.pop(0)
        self._update_compare_menu()
        if self._result_view == "对照":
            self._render_compare_view()

    def _update_compare_menu(self):
        """历史变化后刷新对照源下拉，保持当前选择有效"""
        values = ["原文"] + [self._history_label(r) for r in reversed(self._history)]
        self._compare_menu.configure(values=values)
        if self._compare_source not in values:
            self._compare_source = "原文"
            self._compare_menu.set("原文")

    def _open_history_dialog(self):
        if not self._history:
            self._show_toast("暂无历史记录", "warning")
            return
        HistoryDialog(
            self, self._history,
            on_compare=self._history_compare,
            on_delete=self._history_delete,
            on_clear=self._history_clear)

    def _history_compare(self, rec_id):
        """在主窗口对照视图中与指定历史记录对比"""
        rec = next((r for r in self._history if r["id"] == rec_id), None)
        if rec is None:
            self._show_toast("记录不存在", "warning")
            return
        label = self._history_label(rec)
        self._compare_source = label
        self._compare_menu.set(label)
        self._result_view_seg.set("对照")
        self._on_result_view_change("对照")

    def _history_delete(self, rec_id):
        # 原地修改，保持 HistoryDialog 持有的引用有效
        self._history[:] = [r for r in self._history if r["id"] != rec_id]
        self._update_compare_menu()
        if self._result_view == "对照":
            self._render_compare_view()

    def _history_clear(self):
        self._history.clear()
        self._update_compare_menu()
        if self._result_view == "对照":
            self._render_compare_view()
        self._show_toast("历史记录已清空")

    # ===== 结果操作 =====
    def _copy_result(self):
        text = self._result_box.get("1.0", "end-1c")
        if text:
            self.clipboard_clear()
            self.clipboard_append(text)
            self._show_toast("已复制到剪贴板")

    def _save_result(self):
        text = self._result_box.get("1.0", "end-1c")
        if not text:
            return
        path = filedialog.asksaveasfilename(
            title="保存结果", defaultextension=".txt",
            filetypes=[("文本文件", "*.txt"), ("Excel 文件", "*.xlsx")], initialfile="output.txt")
        if not path:
            return
        if path.endswith(".xlsx"):
            try:
                import openpyxl
                wb = openpyxl.Workbook()
                ws = wb.active
                ws.title = "生草结果"
                ws.append(["段号", "原文", "结果"])
                for i, seg in enumerate(self._segments):
                    result = self._seg_results.get(i, "")
                    ws.append([i + 1, seg, result])
                detail_ws = wb.create_sheet("翻译过程")
                detail_ws.append(["段号", "步骤", "源语言", "目标语言", "翻译结果"])
                for si in sorted(self._seg_steps.keys()):
                    for step_i, (src, tgt, txt) in enumerate(self._seg_steps[si]):
                        detail_ws.append([si + 1, step_i + 1, src, tgt, txt])
                for col in ws.columns:
                    ws.column_dimensions[col[0].column_letter].width = 40
                for col in detail_ws.columns:
                    detail_ws.column_dimensions[col[0].column_letter].width = 40
                wb.save(path)
                self._show_toast(f"已保存到 {os.path.basename(path)}")
            except ImportError:
                self._show_toast("需要 openpyxl: pip install openpyxl")
        else:
            with open(path, "w", encoding="utf-8") as f:
                f.write(text)
            self._show_toast(f"已保存到 {os.path.basename(path)}")

    # ===== 模型加载 =====
    def _load_model_async(self):
        self._status_label.configure(text="⟳ 加载模型中...", text_color=COLORS["info"])
        self.title("生草机 — 加载模型中...")
        self._model_exc = None

        def load():
            try:
                _get_model()
            except Exception as e:
                self._model_exc = e

        t = threading.Thread(target=load, daemon=True)
        t.start()

        def check():
            if t.is_alive():
                self.after(200, check)
            elif self._model_exc:
                self._status_label.configure(text=f"✗ 模型加载失败: {self._model_exc}", text_color=COLORS["error"])
                self.title("生草机 — 模型加载失败")
            else:
                self._model_ready = True
                self._start_btn.configure(state="normal")
                self._status_label.configure(text="✓ 就绪", text_color=COLORS["success"])
                self.title("生草机")
                self._on_input_change()
        self.after(200, check)

    # ===== 拖放 =====
    def _on_drop(self, event):
        path = event.data.strip('{}')
        if path.lower().endswith('.txt'):
            self._set_input_text_from_file(path)