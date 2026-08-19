# -*- coding: utf-8 -*-
import random
import threading

import customtkinter as ctk

from gui_styles import COLORS, FONTS, style_card, style_btn
from languages import LANG_GROUPS, LANG_MAP, PRESETS


class LangSelectDialog(ctk.CTkToplevel):
    def __init__(self, master, on_select, disabled_langs=()):
        super().__init__(master)
        self.title("选择语言")
        self.geometry("520x500")
        self.resizable(True, True)
        self.minsize(400, 400)
        self.transient(master)
        self.grab_set()
        self.configure(fg_color=COLORS["bg"])
        self._on_select = on_select
        self._disabled = set(disabled_langs)
        self.after(50, self._bring_front)

        self._search_var = ctk.StringVar()
        self._search_var.trace_add("write", lambda *_: self._filter())
        search_entry = ctk.CTkEntry(
            self, placeholder_text="搜索语言...",
            textvariable=self._search_var, font=FONTS["body"](),
            fg_color=COLORS["surface"], border_color=COLORS["border"],
            text_color=COLORS["text"],
        )
        search_entry.pack(fill="x", padx=16, pady=(16, 10))
        search_entry.bind("<FocusIn>", lambda e: search_entry.configure(border_color=COLORS["accent"]))
        search_entry.bind("<FocusOut>", lambda e: search_entry.configure(border_color=COLORS["border"]))

        self._scroll = ctk.CTkScrollableFrame(self, height=360, fg_color=COLORS["bg"])
        self._scroll.pack(fill="both", expand=True, padx=16, pady=(0, 12))

        self._build_groups()

        style_btn(self, "关闭", self.destroy, width=80).pack(pady=(0, 14))

    def _bring_front(self):
        self.lift()
        self.focus_force()

    def _build_groups(self):
        for w in self._scroll.winfo_children():
            w.destroy()
        query = self._search_var.get().strip().lower()
        for group_name, langs in LANG_GROUPS:
            filtered = [l for l in langs if (not query or query in l.lower())]
            if not filtered:
                continue
            gf = style_card(self._scroll, corner_radius=6)
            gf.pack(fill="x", pady=4)
            ctk.CTkLabel(gf, text=group_name, font=FONTS["caption"](),
                         text_color=COLORS["text_secondary"]).pack(anchor="w", padx=10, pady=(6, 4))
            tf = ctk.CTkFrame(gf, fg_color="transparent")
            tf.pack(fill="x", padx=8, pady=(0, 6))
            for lang in filtered:
                if lang in self._disabled:
                    lbl = ctk.CTkLabel(tf, text=lang, padx=10, pady=5,
                                       fg_color=COLORS["surface_hover"], corner_radius=4,
                                       text_color="#555555", font=FONTS["body"]())
                    lbl.pack(side="left", padx=3, pady=3)
                else:
                    lbl = ctk.CTkLabel(tf, text=lang, padx=10, pady=5,
                                       fg_color=COLORS["surface_hover"], corner_radius=4,
                                       font=FONTS["body"](), cursor="hand2",
                                       text_color=COLORS["text"])
                    lbl.pack(side="left", padx=3, pady=3)
                    lbl.bind("<Button-1>", lambda e, l=lang: self._pick(l))
                    lbl.bind("<Enter>", lambda e, w=lbl: w.configure(fg_color=COLORS["accent"], text_color="white"))
                    lbl.bind("<Leave>", lambda e, w=lbl: w.configure(fg_color=COLORS["surface_hover"], text_color=COLORS["text"]))

    def _filter(self):
        self._build_groups()

    def _pick(self, lang):
        self._on_select(lang)
        self.destroy()


class ExcludeLangDialog(ctk.CTkToplevel):
    def __init__(self, master, excluded_langs, on_confirm):
        super().__init__(master)
        self.title("排除语言")
        self.geometry("560x520")
        self.resizable(True, True)
        self.minsize(400, 400)
        self.transient(master)
        self.grab_set()
        self.configure(fg_color=COLORS["bg"])
        self._on_confirm = on_confirm
        self._excluded = set(excluded_langs)
        self._vars = {}
        self.after(50, self._bring_front)

        ctk.CTkLabel(self, text="勾选的语言将被排除在随机选池之外",
                     font=FONTS["caption"](),
                     text_color=COLORS["text_secondary"]).pack(anchor="w", padx=16, pady=(12, 4))

        btn_row = ctk.CTkFrame(self, fg_color="transparent")
        btn_row.pack(fill="x", padx=16, pady=(0, 6))
        style_btn(btn_row, "全选", self._select_all, width=60, height=26,
                  font=FONTS["caption"]()).pack(side="left", padx=(0, 4))
        style_btn(btn_row, "全不选", self._select_none, width=60, height=26,
                  font=FONTS["caption"]()).pack(side="left")

        self._search_var = ctk.StringVar()
        self._search_var.trace_add("write", lambda *_: self._build_groups())
        search_entry = ctk.CTkEntry(
            self, placeholder_text="搜索语言...",
            textvariable=self._search_var, font=FONTS["body"](),
            fg_color=COLORS["surface"], border_color=COLORS["border"],
            text_color=COLORS["text"],
        )
        search_entry.pack(fill="x", padx=16, pady=(0, 8))

        self._scroll = ctk.CTkScrollableFrame(self, height=320, fg_color=COLORS["bg"])
        self._scroll.pack(fill="both", expand=True, padx=16, pady=(0, 8))

        self._build_groups()

        style_btn(self, "确定", self._confirm, width=80).pack(pady=(0, 14))

    def _bring_front(self):
        self.lift()
        self.focus_force()

    def _build_groups(self):
        for w in self._scroll.winfo_children():
            w.destroy()
        query = self._search_var.get().strip().lower()
        for group_name, langs in LANG_GROUPS:
            filtered = [l for l in langs if (not query or query in l.lower())]
            if not filtered:
                continue
            gf = style_card(self._scroll, corner_radius=6)
            gf.pack(fill="x", pady=3)
            ctk.CTkLabel(gf, text=group_name, font=FONTS["caption"](),
                         text_color=COLORS["text_secondary"]).pack(anchor="w", padx=10, pady=(4, 2))
            tf = ctk.CTkFrame(gf, fg_color="transparent")
            tf.pack(fill="x", padx=8, pady=(0, 4))
            for lang in filtered:
                var = self._vars.get(lang)
                if var is None:
                    var = ctk.BooleanVar(value=lang in self._excluded)
                    self._vars[lang] = var
                cb = ctk.CTkCheckBox(
                    tf, text=lang, variable=var,
                    font=FONTS["caption"](), checkbox_width=16, checkbox_height=16,
                    fg_color=COLORS["accent"], hover_color=COLORS["accent_hover"],
                    border_color=COLORS["border"], text_color=COLORS["text"],
                )
                cb.pack(side="left", padx=4, pady=2)

    def _select_all(self):
        for var in self._vars.values():
            var.set(True)

    def _select_none(self):
        for var in self._vars.values():
            var.set(False)

    def _confirm(self):
        excluded = [lang for lang, var in self._vars.items() if var.get()]
        self._on_confirm(excluded)
        self.destroy()


class PresetDialog(ctk.CTkToplevel):
    def __init__(self, master, rounds, on_select):
        super().__init__(master)
        self.title("语言预设")
        self.geometry("640x540")
        self.resizable(True, True)
        self.minsize(500, 400)
        self.transient(master)
        self.grab_set()
        self.configure(fg_color=COLORS["bg"])
        self._on_select = on_select
        self._rounds = rounds
        self.after(50, self._bring_front)

        ctk.CTkLabel(self, text="快速预设", font=FONTS["section"](),
                     text_color=COLORS["text"]).pack(anchor="w", padx=16, pady=(16, 8))

        quick_frame = ctk.CTkFrame(self, fg_color="transparent")
        quick_frame.pack(fill="x", padx=16, pady=(0, 12))
        for preset_name in PRESETS:
            btn = style_btn(quick_frame, preset_name, lambda n=preset_name: self._apply_preset(n),
                            width=90, font=FONTS["caption"]())
            btn.pack(side="left", padx=3)

        ctk.CTkLabel(self, text="按地区选择", font=FONTS["section"](),
                     text_color=COLORS["text"]).pack(anchor="w", padx=16, pady=(8, 8))

        scroll = ctk.CTkScrollableFrame(self, height=370, fg_color=COLORS["bg"])
        scroll.pack(fill="both", expand=True, padx=16, pady=(0, 12))

        for group_name, langs in LANG_GROUPS:
            group_frame = style_card(scroll, corner_radius=6)
            group_frame.pack(fill="x", pady=5)

            header = ctk.CTkFrame(group_frame, fg_color="transparent")
            header.pack(fill="x", padx=10, pady=(6, 4))
            ctk.CTkLabel(header, text=group_name, font=FONTS["body"](),
                         text_color=COLORS["text"]).pack(side="left")
            choose_btn = style_btn(header, "选择", lambda l=langs: self._apply_langs(l),
                                   width=55, height=26, font=FONTS["caption"]())
            choose_btn.pack(side="right")

            tag_frame = ctk.CTkFrame(group_frame, fg_color="transparent")
            tag_frame.pack(fill="x", padx=10, pady=(0, 6))
            for lang in langs:
                l = ctk.CTkLabel(tag_frame, text=lang, padx=10, pady=4,
                                 fg_color=COLORS["surface_hover"], corner_radius=4,
                                 font=FONTS["body"](), text_color=COLORS["text"])
                l.pack(side="left", padx=3, pady=3)

        style_btn(self, "关闭", self.destroy, width=80).pack(pady=(0, 14))

    def _bring_front(self):
        self.lift()
        self.focus_force()

    def _apply_preset(self, name):
        langs = PRESETS[name]
        if langs is None:
            langs = self._random_mix()
        self._fill(langs)
        self.destroy()

    def _apply_langs(self, langs):
        self._fill(langs)
        self.destroy()

    def _random_mix(self):
        all_langs = []
        for _, group_langs in LANG_GROUPS:
            pool = [l for l in group_langs if l != "中文"]
            if pool:
                all_langs.append(random.choice(pool))
        result = []
        for _ in range(self._rounds):
            pool = [l for l in all_langs if not result or l != result[-1]]
            if not pool:
                pool = all_langs
            result.append(random.choice(pool))
        return result

    def _fill(self, langs):
        result = []
        for i in range(self._rounds):
            result.append(langs[i % len(langs)])
        self._on_select(result)


class StepDetailDialog(ctk.CTkToplevel):
    def __init__(self, master, seg_index, steps, final_lang):
        super().__init__(master)
        self.title(f"段{seg_index + 1} 翻译过程")
        self.geometry("750x560")
        self.resizable(True, True)
        self.minsize(500, 350)
        self.transient(master)
        self.grab_set()
        self.configure(fg_color=COLORS["bg"])
        self._master_app = master
        self.after(50, self._bring_front)

        chain_frame = ctk.CTkFrame(self, fg_color=COLORS["surface"], corner_radius=6)
        chain_frame.pack(fill="x", padx=16, pady=(16, 4))
        chain_inner = ctk.CTkFrame(chain_frame, fg_color="transparent")
        chain_inner.pack(padx=10, pady=8)
        lang_chain = []
        for i, (src, tgt, _) in enumerate(steps):
            if i == 0:
                lang_chain.append(src)
            lang_chain.append(tgt)
        for j, lang in enumerate(lang_chain):
            if j > 0:
                ctk.CTkLabel(chain_inner, text="→", font=FONTS["caption"](),
                             text_color=COLORS["text_secondary"]).pack(side="left", padx=2)
            is_final_lang = (j == len(lang_chain) - 1)
            color = COLORS["success"] if is_final_lang else COLORS["accent"]
            ctk.CTkLabel(chain_inner, text=lang, font=FONTS["caption"](),
                         text_color=color).pack(side="left", padx=1)

        btn_row = ctk.CTkFrame(self, fg_color="transparent")
        btn_row.pack(fill="x", padx=16, pady=(4, 4))
        style_btn(btn_row, "全部回译", self._back_translate_all, width=80, height=26,
                  font=FONTS["caption"]()).pack(side="left")

        scroll = ctk.CTkScrollableFrame(self, fg_color=COLORS["bg"])
        scroll.pack(fill="both", expand=True, padx=16, pady=(4, 8))

        self._back_btns = []

        for i, (src, tgt, text) in enumerate(steps):
            row = style_card(scroll, corner_radius=6)
            row.pack(fill="x", pady=4)

            arrow_frame = ctk.CTkFrame(row, fg_color="transparent")
            arrow_frame.pack(fill="x", padx=12, pady=(8, 4))
            ctk.CTkLabel(arrow_frame, text=f"步骤{i+1}", font=FONTS["caption"](),
                         text_color=COLORS["text_secondary"]).pack(side="left", padx=(0, 8))
            ctk.CTkLabel(arrow_frame, text=src, font=FONTS["body"](),
                         text_color=COLORS["accent"]).pack(side="left")
            ctk.CTkLabel(arrow_frame, text=" → ", font=FONTS["body"](),
                         text_color=COLORS["text_secondary"]).pack(side="left")
            ctk.CTkLabel(arrow_frame, text=tgt, font=FONTS["body"](),
                         text_color=COLORS["accent"]).pack(side="left")

            is_final = (i == len(steps) - 1) and (tgt == final_lang)
            text_color = COLORS["success"] if is_final else COLORS["text"]
            ctk.CTkLabel(row, text=text, font=FONTS["body"](),
                         text_color=text_color, wraplength=650, justify="left").pack(
                fill="x", padx=12, pady=(0, 4))

            if tgt != "中文" and not is_final:
                back_frame = ctk.CTkFrame(row, fg_color="transparent")
                back_frame.pack(fill="x", padx=12, pady=(0, 8))
                back_label = ctk.CTkLabel(
                    back_frame, text="", font=FONTS["caption"](),
                    text_color=COLORS["text_secondary"], wraplength=600, justify="left")
                back_label.pack(side="left", fill="x", expand=True)
                back_btn = ctk.CTkButton(
                    back_frame, text="回译中文", width=70, height=22,
                    font=FONTS["caption"](), corner_radius=4,
                    fg_color=COLORS["surface_hover"], hover_color=COLORS["accent"],
                    text_color=COLORS["text"])
                back_btn.pack(side="right", padx=(4, 0))
                back_btn.configure(
                    command=lambda t=text, s=src, lbl=back_label, btn=back_btn: self._back_translate(t, s, lbl, btn))
                self._back_btns.append((text, src, back_label, back_btn))

        style_btn(self, "关闭", self.destroy, width=80).pack(pady=(0, 14))

    def _back_translate(self, text, src_lang, label, btn):
        btn.configure(state="disabled", text="翻译中...")
        label.configure(text="⏳ 正在回译...")

        def _do():
            try:
                from engine import translate_once
                result = translate_once(text, src_lang, "中文")
                self.after(0, lambda: label.configure(text=f"↩ {result}", text_color=COLORS["info"]))
                self.after(0, lambda: btn.configure(text="已回译"))
            except Exception as e:
                self.after(0, lambda: label.configure(text=f"回译失败: {e}", text_color=COLORS["error"]))
                self.after(0, lambda: btn.configure(text="回译中文", state="normal"))

        threading.Thread(target=_do, daemon=True).start()

    def _back_translate_all(self):
        for text, src_lang, label, btn in self._back_btns:
            try:
                if btn.cget("state") != "disabled":
                    self._back_translate(text, src_lang, label, btn)
            except Exception:
                pass

    def _bring_front(self):
        self.lift()
        self.focus_force()


class DeleteConfigDialog(ctk.CTkToplevel):
    def __init__(self, master, config_names, on_delete):
        super().__init__(master)
        self.title("删除配置")
        self.geometry("360x400")
        self.resizable(True, True)
        self.minsize(280, 250)
        self.transient(master)
        self.grab_set()
        self.configure(fg_color=COLORS["bg"])
        self._on_delete = on_delete
        self._config_names = config_names
        self.after(50, self._bring_front)

        ctk.CTkLabel(self, text="选择要删除的配置", font=FONTS["section"](),
                     text_color=COLORS["text"]).pack(anchor="w", padx=16, pady=(16, 8))

        self._scroll = ctk.CTkScrollableFrame(self, fg_color=COLORS["bg"])
        self._scroll.pack(fill="both", expand=True, padx=16, pady=(0, 8))
        self._scroll.grid_columnconfigure(0, weight=1)

        self._vars = {}
        for i, name in enumerate(config_names):
            row_frame = style_card(self._scroll, corner_radius=4, fg_color=COLORS["surface_hover"])
            row_frame.pack(fill="x", pady=3)
            row_frame.grid_columnconfigure(0, weight=1)

            var = ctk.BooleanVar(value=False)
            self._vars[name] = var

            cb = ctk.CTkCheckBox(
                row_frame, text=name, variable=var,
                font=FONTS["body"](), checkbox_width=18, checkbox_height=18,
                fg_color=COLORS["error"], hover_color="#cc3333",
                border_color=COLORS["border"], text_color=COLORS["text"],
            )
            cb.grid(row=0, column=0, sticky="w", padx=10, pady=8)

        btn_row = ctk.CTkFrame(self, fg_color="transparent")
        btn_row.pack(fill="x", padx=16, pady=(0, 14))

        style_btn(btn_row, "全选", self._select_all, width=60, height=28,
                  font=FONTS["caption"]()).pack(side="left", padx=(0, 4))
        style_btn(btn_row, "全不选", self._select_none, width=60, height=28,
                  font=FONTS["caption"]()).pack(side="left")

        style_btn(btn_row, "删除", self._confirm, width=70, height=28,
                  font=FONTS["body"](),
                  fg_color=COLORS["error"], hover_color="#cc3333").pack(side="right")
        style_btn(btn_row, "取消", self.destroy, width=60, height=28,
                  font=FONTS["body"](),
                  fg_color=COLORS["surface_hover"], hover_color=COLORS["accent"]).pack(side="right", padx=(0, 4))

    def _bring_front(self):
        self.lift()
        self.focus_force()

    def _select_all(self):
        for var in self._vars.values():
            var.set(True)

    def _select_none(self):
        for var in self._vars.values():
            var.set(False)

    def _confirm(self):
        to_delete = [name for name, var in self._vars.items() if var.get()]
        if to_delete:
            self._on_delete(to_delete)
        self.destroy()