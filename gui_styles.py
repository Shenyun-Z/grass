# -*- coding: utf-8 -*-
import customtkinter as ctk

ctk.set_appearance_mode("dark")
ctk.set_default_color_theme("blue")

COLORS = {
    "bg": "#1e1e1e",
    "surface": "#252526",
    "surface_hover": "#2d2d30",
    "border": "#3c3c3c",
    "border_focus": "#007acc",
    "text": "#cccccc",
    "text_secondary": "#858585",
    "accent": "#007acc",
    "accent_hover": "#0098ff",
    "success": "#4ec9b0",
    "warning": "#cca700",
    "error": "#f44747",
    "info": "#4fc1ff",
}

FONTS = {
    "title": lambda: ctk.CTkFont(size=18, weight="bold"),
    "section": lambda: ctk.CTkFont(size=15, weight="bold"),
    "body": lambda: ctk.CTkFont(size=14),
    "caption": lambda: ctk.CTkFont(size=12),
    "tiny": lambda: ctk.CTkFont(size=10),
    "mono": lambda: ctk.CTkFont(size=13, family="Consolas"),
}


def style_card(parent, **kwargs):
    defaults = dict(
        fg_color=COLORS["surface"],
        border_width=1,
        border_color=COLORS["border"],
        corner_radius=8,
    )
    defaults.update(kwargs)
    return ctk.CTkFrame(parent, **defaults)


def style_btn(parent, text, command, **kwargs):
    defaults = dict(
        text=text,
        command=command,
        font=FONTS["body"](),
        corner_radius=6,
        fg_color=COLORS["accent"],
        hover_color=COLORS["accent_hover"],
        text_color="white",
        textvariable=None,
        height=32,
    )
    tv = defaults.pop("textvariable", None)
    defaults.update(kwargs)
    btn = ctk.CTkButton(parent, **defaults)
    if tv is not None:
        btn.configure(textvariable=tv)
    return btn