# -*- coding: utf-8 -*-
"""GUI 工具：颜色动画、Toast 提示"""
import customtkinter as ctk
from gui_styles import COLORS, FONTS


class ToastMixin:
    def _show_toast(self, message, kind="success"):
        color_map = {
            "success": COLORS["success"], "warning": COLORS["warning"],
            "error": COLORS["error"], "info": COLORS["info"]
        }
        toast = ctk.CTkLabel(
            self, text=message, font=FONTS["caption"](),
            fg_color=COLORS["surface"], corner_radius=6,
            text_color=color_map.get(kind, COLORS["success"]),
            padx=12, pady=6, border_width=1, border_color=COLORS["border"])
        toast.lift()
        toast.place(relx=0.5, rely=0.92, anchor="center")
        self.after(2500, toast.destroy)


class ColorAnimMixin:
    @staticmethod
    def _hex_to_rgb(hex_color):
        if isinstance(hex_color, (list, tuple)):
            hex_color = hex_color[0] if hex_color else COLORS["accent"]
        if isinstance(hex_color, str) and hex_color.startswith("#"):
            hex_color = hex_color.lstrip('#')
        else:
            return (0, 122, 204)
        return tuple(int(hex_color[i:i+2], 16) for i in (0, 2, 4))

    @staticmethod
    def _rgb_to_hex(r, g, b):
        return f"#{r:02x}{g:02x}{b:02x}"

    def _interpolate_color(self, c1, c2, t):
        r1, g1, b1 = self._hex_to_rgb(c1)
        r2, g2, b2 = self._hex_to_rgb(c2)
        return self._rgb_to_hex(
            int(r1 + (r2 - r1) * t),
            int(g1 + (g2 - g1) * t),
            int(b1 + (b2 - b1) * t)
        )

    def _animate_btn_color(self, btn, target_fg, target_hover, steps=10, delay=20):
        try:
            current_fg = btn.cget("fg_color")
            current_hover = btn.cget("hover_color")
        except Exception:
            current_fg = COLORS["accent"]
            current_hover = COLORS["accent_hover"]

        def step(i):
            if i > steps:
                btn.configure(fg_color=target_fg, hover_color=target_hover)
                return
            t = i / steps
            fg = self._interpolate_color(current_fg, target_fg, t)
            hover = self._interpolate_color(current_hover, target_hover, t)
            btn.configure(fg_color=fg, hover_color=hover)
            self.after(delay, lambda: step(i + 1))
        step(1)