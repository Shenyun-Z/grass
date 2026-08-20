# -*- coding: utf-8 -*-
"""对照视图组件

提供双栏卡片对照展示（左栏：原文或某次历史结果，右栏：当前结果），
支持虚拟滚动与控件复用，复用 SplitCard 卡片单元。
"""
import tkinter as tk

import customtkinter as ctk

from gui_styles import COLORS, FONTS
from gui_split_view import SplitCard


class CompareView:
    """对照视图：双栏条目逐行对比

    左栏可以是原文分段，也可以是某次历史记录的分段结果；
    右栏始终为当前翻译结果。行号按索引对齐，行数不足一侧留空。
    """

    HEAD_H = 28
    CARD_GAP = 6
    CARD_MIN_H = 28
    CARD_MAX_H = 80

    def __init__(self, parent):
        self._parent = parent
        self._cards = []
        self._left_title = "原文"
        self._right_title = "当前结果"
        self._left_items = []
        self._right_items = []
        self._canvas_width = 0
        self._build()

    def _build(self):
        self._canvas = tk.Canvas(self._parent, bg=COLORS["bg"], highlightthickness=0, bd=0)
        self._canvas.pack(side="left", fill="both", expand=True)

        self._scrollbar = ctk.CTkScrollbar(self._parent, command=self._canvas.yview)
        self._scrollbar.pack(side="right", fill="y")
        self._canvas.configure(yscrollcommand=self._scrollbar.set)

        self._inner = ctk.CTkFrame(self._canvas, fg_color="transparent")
        self._canvas_window = self._canvas.create_window((0, 0), window=self._inner, anchor='nw')

        self._inner.bind('<Configure>', lambda e: self._canvas.configure(
            scrollregion=self._canvas.bbox('all')))
        self._canvas.bind('<Configure>', self._on_canvas_configure)

        self._canvas.bind('<MouseWheel>', self._on_mousewheel)
        self._canvas.bind('<Button-4>', lambda e: self._canvas.yview_scroll(-3, "units"))
        self._canvas.bind('<Button-5>', lambda e: self._canvas.yview_scroll(3, "units"))

        self._left_title_label = ctk.CTkLabel(
            self._inner, text=self._left_title, font=FONTS["caption"](),
            text_color=COLORS["accent"], anchor="w", width=200)
        self._right_title_label = ctk.CTkLabel(
            self._inner, text=self._right_title, font=FONTS["caption"](),
            text_color=COLORS["success"], anchor="w", width=200)

        self._empty_label = ctk.CTkLabel(
            self._inner, text="暂无对照内容\n开始翻译后，这里将按段展示对照",
            font=FONTS["caption"](), text_color=COLORS["text_secondary"],
            justify="center", width=300)

    def _on_mousewheel(self, event):
        self._canvas.yview_scroll(int(-1 * (event.delta / 120)), "units")
        return "break"

    def _on_canvas_configure(self, event):
        self._canvas.itemconfig(self._canvas_window, width=event.width)
        self._canvas_width = event.width
        self._render()

    def set_data(self, left_title, left_items, right_title, right_items):
        """设置对照数据并重渲染"""
        self._left_title = left_title
        self._right_title = right_title
        self._left_items = list(left_items)
        self._right_items = list(right_items)
        self._render()

    def _get_or_create_card(self, index):
        if index < len(self._cards):
            return self._cards[index]
        card = SplitCard(self._inner, index)
        self._cards.append(card)
        return card

    def _estimate_card_height(self, left, right, card_width):
        wl = max(50, card_width - 36)
        ll = max(1, len(left) // max(1, wl // 12) + 1) if left else 1
        rl = max(1, len(right) // max(1, wl // 12) + 1) if right else 1
        return min(self.CARD_MAX_H, max(self.CARD_MIN_H, max(ll, rl) * 20 + 16))

    def _render(self):
        n = max(len(self._left_items), len(self._right_items))
        if n == 0:
            for card in self._cards:
                card.hide()
            self._left_title_label.place_forget()
            self._right_title_label.place_forget()
            width = max(100, self._canvas_width - 20)
            self._empty_label.configure(width=width)
            self._empty_label.place(x=10, y=10, anchor='nw')
            self._inner.configure(height=80)
            self._canvas.configure(scrollregion=self._canvas.bbox('all'))
            return

        self._empty_label.place_forget()
        canvas_w = self._canvas_width or 800
        card_width = (canvas_w - 10) // 2 - 5

        self._left_title_label.configure(text=self._left_title, width=card_width)
        self._right_title_label.configure(text=self._right_title, width=card_width)
        self._left_title_label.place(x=3, y=4, anchor='nw')
        self._right_title_label.place(x=card_width + 8, y=4, anchor='nw')

        current_y = self.HEAD_H
        for i in range(n):
            card = self._get_or_create_card(i)
            left = self._left_items[i] if i < len(self._left_items) else ""
            right = self._right_items[i] if i < len(self._right_items) else ""
            card_h = self._estimate_card_height(left, right, card_width)
            card.configure(left, right, card_width, card_width)
            card.place(3, current_y, card_width, card_h)
            current_y += card_h + self.CARD_GAP

        for i in range(n, len(self._cards)):
            self._cards[i].hide()

        self._inner.configure(height=max(current_y + 5, 80))
        self._canvas.configure(scrollregion=self._canvas.bbox('all'))
