# -*- coding: utf-8 -*-
"""GUI 语言管理：语言选择、预设、随机模式、排除语言"""
import customtkinter as ctk
from gui_dialogs import LangSelectDialog, ExcludeLangDialog, PresetDialog
from languages import DEFAULT_PIVOT_LANGS


class LangMixin:
    def _set_default_langs(self, n):
        self._rounds_var.set(n)
        self._on_rounds_change(str(n))

    def _on_rounds_change(self, val):
        if self._running:
            return
        n = int(val)
        for w in self._lang_container.winfo_children():
            w.destroy()
        self._lang_vars.clear()
        for i in range(n):
            lang = DEFAULT_PIVOT_LANGS[i % len(DEFAULT_PIVOT_LANGS)]
            var = ctk.StringVar(value=lang)
            self._lang_vars.append(var)
        self._relayout_langs()
        self._update_chain_label()
        self._on_input_change()

    def _on_random_mode_change(self, val):
        is_fixed = (val == "固定")
        for btn in self._lang_btns:
            btn.configure(state="normal" if is_fixed else "disabled")
        self._preset_btn.configure(state="normal" if is_fixed else "disabled")
        self._exclude_btn.configure(state="disabled" if is_fixed else "normal")
        if is_fixed:
            self._update_chain_label()
        else:
            self._update_random_chain_label()

    def _update_random_chain_label(self):
        val = self._random_mode_var.get()
        mode_desc = "低强度: 大语种随机" if val == "低强度" else "高强度: 全语种随机"
        n = self._rounds_var.get()
        excluded = self._excluded_langs
        ex_str = f"，排除{'+'.join(excluded)}" if excluded else ""
        self._chain_label.configure(text=f"随机 × {n} 轮 ({mode_desc}{ex_str})")

    def _update_chain_label(self):
        if not self._lang_vars:
            self._chain_label.configure(text="")
            return
        langs = [v.get() for v in self._lang_vars]
        final = self._final_lang_var.get()
        chain = "中文 → " + " → ".join(langs) + " → " + final
        self._chain_label.configure(text=chain)

    def _relayout_langs(self):
        if not self._lang_vars:
            return
        new_cols = max(1, (self.winfo_width() - 80) // 152)
        if new_cols == self._last_cols and len(self._lang_vars) == self._last_lang_count:
            return
        self._last_cols = new_cols
        self._last_lang_count = len(self._lang_vars)
        for w in self._lang_container.winfo_children():
            w.destroy()
        self._lang_btns.clear()
        for col in range(new_cols):
            self._lang_container.grid_columnconfigure(col, weight=1)
        for i, var in enumerate(self._lang_vars):
            row = i // new_cols
            col = i % new_cols
            item = ctk.CTkFrame(self._lang_container, fg_color="transparent")
            item.grid(row=row, column=col, padx=2, pady=2, sticky="ew")
            ctk.CTkLabel(item, text=f"{i+1}.", font=self._FONTS["body"](),
                         text_color=self._COLORS["text_secondary"], width=24).pack(side="left")
            btn = ctk.CTkButton(
                item, textvariable=var, width=100, height=28,
                font=self._FONTS["body"](),
                command=lambda idx=i: self._open_lang_picker(idx),
                fg_color=self._COLORS["surface_hover"], hover_color=self._COLORS["accent"],
                text_color=self._COLORS["text"], corner_radius=4)
            btn.pack(side="left", padx=(2, 4))
            self._lang_btns.append(btn)
            ctk.CTkLabel(item, text="→", font=self._FONTS["body"](),
                         text_color=self._COLORS["text_secondary"]).pack(side="left")

    def _open_lang_picker(self, idx):
        prev = self._lang_vars[idx - 1].get() if idx > 0 else None
        nxt = self._lang_vars[idx + 1].get() if idx + 1 < len(self._lang_vars) else None
        disabled = set()
        if prev:
            disabled.add(prev)
        if nxt:
            disabled.add(nxt)
        LangSelectDialog(self, on_select=lambda lang: self._set_lang(idx, lang), disabled_langs=disabled)

    def _set_lang(self, idx, lang):
        self._lang_vars[idx].set(lang)
        self._update_chain_label()
        self._on_input_change()

    def _open_final_lang_picker(self):
        LangSelectDialog(self, on_select=lambda lang: self._set_final_lang(lang))

    def _set_final_lang(self, lang):
        self._final_lang_var.set(lang)
        self._FINAL_LANG = lang
        self._update_chain_label()
        self._on_input_change()

    def _open_preset(self):
        PresetDialog(self, len(self._lang_vars), self._apply_langs)

    def _apply_langs(self, langs):
        for i, var in enumerate(self._lang_vars):
            if i < len(langs):
                var.set(langs[i])
        self._update_chain_label()
        self._on_input_change()

    def _open_exclude_dialog(self):
        ExcludeLangDialog(self, self._excluded_langs, self._apply_excluded)

    def _apply_excluded(self, excluded):
        self._excluded_langs = excluded
        self._update_random_chain_label()