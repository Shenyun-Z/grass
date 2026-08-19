# -*- coding: utf-8 -*-
"""分块预览组件

提供文本分段的双栏卡片视图，支持虚拟滚动和控件复用。
"""
import tkinter as tk
import customtkinter as ctk

from gui_styles import COLORS, FONTS


class SplitCard:
    """单个分块卡片组件（左右双栏）"""
    __slots__ = ('left_card', 'right_card', 'seg_label', 'res_label',
                 'left_num', 'right_num', 'index', 'visible')

    def __init__(self, parent, index):
        self.index = index
        self.visible = False
        self.left_card = None
        self.right_card = None
        self.seg_label = None
        self.res_label = None
        self.left_num = None
        self.right_num = None
        self._build(parent)

    def _build(self, parent):
        self.left_card = ctk.CTkFrame(parent, fg_color=COLORS["surface_hover"],
                                      corner_radius=6, border_width=1,
                                      border_color=COLORS["border"])
        self.left_card.bind("<Button-1>", lambda e, idx=self.index: None)
        self.left_card.configure(cursor="hand2")

        self.right_card = ctk.CTkFrame(parent, fg_color=COLORS["surface_hover"],
                                       corner_radius=6, border_width=1,
                                       border_color=COLORS["border"])
        self.right_card.bind("<Button-1>", lambda e, idx=self.index: None)
        self.right_card.configure(cursor="hand2")

        self.left_num = ctk.CTkLabel(self.left_card, text="", font=FONTS["caption"](),
                                     text_color=COLORS["accent"])
        self.left_num.place(x=5, y=4, anchor='nw')

        self.seg_label = ctk.CTkLabel(self.left_card, text="", font=FONTS["body"](),
                                      text_color=COLORS["text"],
                                      justify="left", anchor='nw')
        self.seg_label.place(x=28, y=4, anchor='nw')
        self.seg_label._is_seg_text = True

        self.right_num = ctk.CTkLabel(self.right_card, text="", font=FONTS["caption"](),
                                      text_color=COLORS["accent"])
        self.right_num.place(x=5, y=4, anchor='nw')

        self.res_label = ctk.CTkLabel(self.right_card, text="", font=FONTS["body"](),
                                      text_color=COLORS["text_secondary"],
                                      justify="left", anchor='nw')
        self.res_label.place(x=28, y=4, anchor='nw')
        self.res_label._is_seg_text = True

    def configure(self, seg_text, res_text, seg_width, res_width, on_click=None):
        """配置卡片内容"""
        self.left_num.configure(text=str(self.index + 1))
        self.right_num.configure(text=str(self.index + 1))
        wl = max(50, seg_width - 36)
        self.seg_label.configure(text=seg_text, wraplength=wl)
        if res_text:
            self.res_label.configure(text=res_text, text_color=COLORS["text"], wraplength=wl)
            self.right_card.configure(fg_color="#2a4a2a")
        else:
            self.res_label.configure(text="…", text_color=COLORS["text_secondary"], wraplength=wl)
            self.right_card.configure(fg_color=COLORS["surface_hover"])
        if on_click:
            self.left_card.bind("<Button-1>", lambda e, idx=self.index: on_click(idx))
            self.right_card.bind("<Button-1>", lambda e, idx=self.index: on_click(idx))

    def set_state(self, state):
        """设置卡片状态颜色"""
        colors = {"waiting": COLORS["surface_hover"], "translating": "#5a4a10", "done": "#2a4a2a"}
        self.left_card.configure(fg_color=colors.get(state, COLORS["surface_hover"]))

    def place(self, x, y, width, height):
        """放置卡片"""
        self.left_card.configure(width=width, height=height)
        self.right_card.configure(width=width, height=height)
        self.left_card.place(x=x, y=y)
        self.right_card.place(x=x + width + 5, y=y)
        self.visible = True

    def hide(self):
        """隐藏卡片"""
        self.left_card.place_forget()
        self.right_card.place_forget()
        self.visible = False


class SplitView:
    """分块预览视图组件

    使用控件池复用策略，避免全量销毁重建。
    """
    CARD_GAP = 6
    CARD_MIN_H = 28
    CARD_MAX_H = 80

    def __init__(self, parent, on_seg_click=None):
        self._parent = parent
        self._on_seg_click = on_seg_click
        self._cards = []  # 控件池
        self._segments = []
        self._results = {}
        self._states = {}
        self._total_height = 0
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

        self._canvas.bind('<MouseWheel>', lambda e: self._canvas.yview_scroll(int(-1*(e.delta/120)), "units"))
        self._canvas.bind('<Button-4>', lambda e: self._canvas.yview_scroll(-3, "units"))
        self._canvas.bind('<Button-5>', lambda e: self._canvas.yview_scroll(3, "units"))

    def _on_canvas_configure(self, event):
        self._canvas.itemconfig(self._canvas_window, width=event.width)
        self._canvas_width = event.width
        self._render()

    def _get_or_create_card(self, index):
        """从控件池获取或创建卡片"""
        if index < len(self._cards):
            return self._cards[index]
        card = SplitCard(self._inner, index)
        self._cards.append(card)
        return card

    def _estimate_card_height(self, seg_text, res_text, card_width):
        """估算卡片高度"""
        wl = max(50, card_width - 36)
        if wl <= 0:
            return self.CARD_MIN_H
        seg_lines = max(1, len(seg_text) // max(1, wl // 12) + 1)
        res_lines = max(1, len(res_text) // max(1, wl // 12) + 1) if res_text else 1
        return min(self.CARD_MAX_H, max(self.CARD_MIN_H, max(seg_lines, res_lines) * 20 + 16))

    def set_segments(self, segments):
        """设置分段数据"""
        self._segments = segments
        self._states = {i: "waiting" for i in range(len(segments))}
        self._results = {}
        self._render()

    def update_result(self, index, result):
        """更新某段翻译结果"""
        self._results[index] = result
        self._states[index] = "done"
        self._render()

    def update_state(self, index, state):
        """更新某段状态"""
        self._states[index] = state
        self._render()

    def _render(self):
        """渲染视图（控件复用）"""
        if not self._segments:
            for card in self._cards:
                card.hide()
            self._inner.configure(height=100)
            self._total_height = 100
            return

        canvas_w = self._canvas.winfo_width() or 900
        card_width = (canvas_w - 10) // 2 - 5
        current_y = 2

        for i, seg in enumerate(self._segments):
            card = self._get_or_create_card(i)
            result_text = self._results.get(i, "")
            card_h = self._estimate_card_height(seg, result_text, card_width)

            card.configure(seg, result_text, card_width, card_width, self._on_seg_click)
            card.set_state(self._states.get(i, "waiting"))
            card.place(3, current_y, card_width, card_h)

            current_y += card_h + self.CARD_GAP

        # 隐藏多余的卡片
        for i in range(len(self._segments), len(self._cards)):
            self._cards[i].hide()

        self._total_height = max(current_y + 5, 100)
        self._inner.configure(height=self._total_height)
        self._canvas.configure(scrollregion=self._canvas.bbox('all'))

    def get_info(self):
        """获取统计信息"""
        if not self._segments:
            return "", "0 / 0"
        avg = sum(len(s) for s in self._segments) / len(self._segments)
        done = sum(1 for s in self._states.values() if s == "done")
        total = len(self._segments)
        return f"共 {total} 段，段均 {avg:.0f} 字", f"{done} / {total}"

    def set_height(self, height):
        """设置组件高度"""
        self._parent.configure(height=height)

    def yview_moveto(self, ratio):
        """滚动到指定位置"""
        self._canvas.yview_moveto(ratio)

    def auto_follow(self, index):
        """自动跟随指定段"""
        if index >= len(self._cards):
            return
        try:
            card = self._cards[index]
            if not card.visible:
                return
            canvas = self._canvas
            card_y = card.left_card.winfo_y()
            card_h = card.left_card.winfo_height()
            canvas_h = canvas.winfo_height()
            content_h = int(canvas.bbox("all")[3]) if canvas.bbox("all") else 1
            target_y = card_y + card_h - canvas_h + 20
            if target_y < 0:
                target_y = 0
            if target_y > content_h - canvas_h:
                target_y = content_h - canvas_h
            if content_h > canvas_h:
                ratio = target_y / (content_h - canvas_h)
                canvas.yview_moveto(ratio)
        except Exception:
            pass