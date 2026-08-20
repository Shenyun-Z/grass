# -*- coding: utf-8 -*-
import random
import threading

import customtkinter as ctk

from gui_styles import COLORS, FONTS, style_card, style_btn
from languages import LANG_GROUPS, LANG_MAP, PRESETS

# 切分标点预设组：(组名, 包含的字符)
PUNCT_GROUPS = [
    ("逗号", "，,"),
    ("句号", "。。."),
    ("叹号", "！！"),
    ("问号", "？?"),
    ("分号", "；;"),
    ("冒号", "：:"),
    ("顿号", "、"),
]
_PRESET_CHARS = "".join(chars for _, chars in PUNCT_GROUPS)


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


class HistoryDialog(ctk.CTkToplevel):
    """历史记录对话框：左侧记录列表 + 右侧详情（原文/结果/参数）

    支持复制结果、删除单条、清空全部，以及「对照查看」——
    将主窗口切换到对照视图并与该条记录对比。
    """

    def __init__(self, master, history, on_compare=None, on_delete=None, on_clear=None):
        super().__init__(master)
        self.title("历史记录")
        self.geometry("920x580")
        self.resizable(True, True)
        self.minsize(720, 440)
        self.transient(master)
        self.grab_set()
        self.configure(fg_color=COLORS["bg"])
        self._history = history  # 与主应用共享同一列表对象（原地修改）
        self._on_compare = on_compare
        self._on_delete = on_delete
        self._on_clear = on_clear
        self._selected_id = None
        self._restore_after_id = None
        self.after(50, self._bring_front)

        header = ctk.CTkFrame(self, fg_color="transparent")
        header.pack(fill="x", padx=16, pady=(14, 8))
        self._count_label = ctk.CTkLabel(header, text="", font=FONTS["section"](),
                                         text_color=COLORS["text"])
        self._count_label.pack(side="left")
        style_btn(header, "清空历史", self._clear, width=80, height=26,
                  font=FONTS["caption"](),
                  fg_color=COLORS["surface_hover"],
                  hover_color=COLORS["error"]).pack(side="right")

        body = ctk.CTkFrame(self, fg_color="transparent")
        body.pack(fill="both", expand=True, padx=16, pady=(0, 8))
        body.grid_columnconfigure(0, weight=0, minsize=280)
        body.grid_columnconfigure(1, weight=1)
        body.grid_rowconfigure(0, weight=1)

        self._list_frame = ctk.CTkScrollableFrame(body, fg_color=COLORS["bg"])
        self._list_frame.grid(row=0, column=0, sticky="nsw", padx=(0, 8))

        self._detail = style_card(body, corner_radius=6)
        self._detail.grid(row=0, column=1, sticky="nsew")
        self._detail.grid_columnconfigure(0, weight=1)

        self._show_placeholder()
        self._rebuild_list()

    def _bring_front(self):
        try:
            if self.winfo_exists():
                self.lift()
                self.focus_force()
        except Exception:
            pass

    def destroy(self):
        """销毁前取消未触发的回调，避免访问已销毁的控件"""
        try:
            if self._restore_after_id is not None:
                self.after_cancel(self._restore_after_id)
                self._restore_after_id = None
        except Exception:
            pass
        super().destroy()

    # ===== 列表 =====
    def _rebuild_list(self):
        self._count_label.configure(text=f"历史记录（{len(self._history)}）")
        for w in self._list_frame.winfo_children():
            w.destroy()
        if not self._history:
            ctk.CTkLabel(self._list_frame, text="暂无记录",
                         font=FONTS["caption"](),
                         text_color=COLORS["text_secondary"]).pack(pady=12)
            return
        for rec in reversed(self._history):  # 最新在前
            mark = " ⏹" if rec.get("stopped") else ""
            summary = rec["input"].replace("\n", " ")
            if len(summary) > 24:
                summary = summary[:24] + "…"
            text = f"#{rec['id']}  {rec['date']} {rec['time']}{mark}\n{summary}"
            selected = (rec["id"] == self._selected_id)
            row = ctk.CTkButton(
                self._list_frame, text=text, anchor="w",
                height=44, font=FONTS["caption"](),
                fg_color=COLORS["accent"] if selected else COLORS["surface_hover"],
                hover_color=COLORS["accent_hover"],
                text_color="white" if selected else COLORS["text"],
                corner_radius=6,
                command=lambda r=rec: self._select(r))
            row.pack(fill="x", pady=2)

    def _select(self, rec):
        self._selected_id = rec["id"]
        self._rebuild_list()
        self._show_detail(rec)

    # ===== 详情 =====
    def _show_placeholder(self):
        for w in self._detail.winfo_children():
            w.destroy()
        ctk.CTkLabel(self._detail, text="← 选择一条记录查看详情",
                     font=FONTS["body"](),
                     text_color=COLORS["text_secondary"]).pack(expand=True)

    def _show_detail(self, rec):
        for w in self._detail.winfo_children():
            w.destroy()

        p = rec["params"]
        mode = p.get("mode", "-")
        stopped = " · 已停止" if rec.get("stopped") else ""
        info = (f"#{rec['id']} · {rec['date']} {rec['time']} · "
                f"{p.get('rounds', '-')}轮 {mode} · 译回{p.get('final', '-')} · "
                f"段字数{p.get('threshold', '-')}{stopped}")
        if rec.get("elapsed"):
            info += f" · 耗时{rec['elapsed']}"
        ctk.CTkLabel(self._detail, text=info, font=FONTS["caption"](),
                     text_color=COLORS["text_secondary"], anchor="w",
                     justify="left").grid(row=0, column=0, sticky="ew", padx=12, pady=(10, 4))

        ctk.CTkLabel(self._detail, text="原文", font=FONTS["caption"](),
                     text_color=COLORS["accent"], anchor="w").grid(
            row=1, column=0, sticky="w", padx=12, pady=(4, 2))
        src_frame = ctk.CTkScrollableFrame(self._detail, height=110, fg_color=COLORS["bg"])
        src_frame.grid(row=2, column=0, sticky="ew", padx=12, pady=(0, 6))
        ctk.CTkLabel(src_frame, text=rec["input"] or "（空）", font=FONTS["body"](),
                     text_color=COLORS["text"], wraplength=480,
                     justify="left").pack(anchor="w", padx=8, pady=6)

        ctk.CTkLabel(self._detail, text="结果", font=FONTS["caption"](),
                     text_color=COLORS["success"], anchor="w").grid(
            row=3, column=0, sticky="w", padx=12, pady=(4, 2))
        res_frame = ctk.CTkScrollableFrame(self._detail, height=140, fg_color=COLORS["bg"])
        res_frame.grid(row=4, column=0, sticky="ew", padx=12, pady=(0, 6))
        ctk.CTkLabel(res_frame, text=rec["result"] or "（空）", font=FONTS["body"](),
                     text_color=COLORS["text"], wraplength=480,
                     justify="left").pack(anchor="w", padx=8, pady=6)

        btn_row = ctk.CTkFrame(self._detail, fg_color="transparent")
        btn_row.grid(row=5, column=0, sticky="ew", padx=12, pady=(2, 10))

        self._copy_btn = style_btn(btn_row, "复制结果", lambda: self._copy_result(rec),
                                   width=85, height=28, font=FONTS["body"]())
        self._copy_btn.pack(side="left")
        style_btn(btn_row, "对照查看", lambda: self._compare(rec),
                  width=85, height=28, font=FONTS["body"](),
                  fg_color=COLORS["surface_hover"],
                  hover_color=COLORS["accent"]).pack(side="left", padx=(6, 0))
        style_btn(btn_row, "删除此条", lambda: self._delete(rec),
                  width=85, height=28, font=FONTS["body"](),
                  fg_color=COLORS["surface_hover"],
                  hover_color=COLORS["error"]).pack(side="right")

    # ===== 操作 =====
    def _copy_result(self, rec):
        try:
            self.clipboard_clear()
            self.clipboard_append(rec["result"])
        except Exception:
            return
        btn = getattr(self, "_copy_btn", None)
        if btn is not None:
            btn.configure(text="已复制", state="disabled")

            def _restore():
                try:
                    if btn.winfo_exists():
                        btn.configure(text="复制结果", state="normal")
                except Exception:
                    pass
            self._restore_after_id = self.after(1500, _restore)

    def _compare(self, rec):
        if self._on_compare:
            self._on_compare(rec["id"])
        self.destroy()

    def _delete(self, rec):
        if self._on_delete:
            self._on_delete(rec["id"])
        self._selected_id = None
        self._rebuild_list()
        self._show_placeholder()

    def _clear(self):
        if not self._history:
            return
        if self._on_clear:
            self._on_clear()
        self._selected_id = None
        self._rebuild_list()
        self._show_placeholder()


class SplitPunctDialog(ctk.CTkToplevel):
    """切分标点设置对话框：预设标点分组勾选 + 自定义分隔符"""

    def __init__(self, master, puncts, on_confirm):
        super().__init__(master)
        self.title("切分标点设置")
        self.geometry("460x440")
        self.resizable(False, False)
        self.transient(master)
        self.grab_set()
        self.configure(fg_color=COLORS["bg"])
        self._on_confirm = on_confirm
        self.after(50, self._bring_front)

        ctk.CTkLabel(
            self, text="分段时累计达到「段字数」阈值后，在最近的一个所选标点处切分。",
            font=FONTS["caption"](), text_color=COLORS["text_secondary"],
            wraplength=420, justify="left").pack(anchor="w", padx=16, pady=(14, 8))

        grid_frame = ctk.CTkFrame(self, fg_color="transparent")
        grid_frame.pack(fill="x", padx=16, pady=(0, 8))
        for col in range(4):
            grid_frame.grid_columnconfigure(col, weight=1)

        selected = set(puncts or "")
        self._vars = []
        for i, (name, chars) in enumerate(PUNCT_GROUPS):
            var = ctk.BooleanVar(value=set(chars).issubset(selected))
            var.trace_add("write", lambda *_: self._update_preview())
            self._vars.append((var, chars))
            cb = ctk.CTkCheckBox(
                grid_frame, text=f"{name} {''.join(chars)}", variable=var,
                font=FONTS["caption"](), checkbox_width=16, checkbox_height=16,
                fg_color=COLORS["accent"], hover_color=COLORS["accent_hover"],
                border_color=COLORS["border"], text_color=COLORS["text"])
            cb.grid(row=i // 4, column=i % 4, padx=4, pady=4, sticky="w")

        quick = ctk.CTkFrame(self, fg_color="transparent")
        quick.pack(fill="x", padx=16, pady=(0, 8))
        style_btn(quick, "全选", lambda: self._apply_preset("all"), width=55, height=26,
                  font=FONTS["caption"](), fg_color=COLORS["surface_hover"],
                  hover_color=COLORS["accent"]).pack(side="left")
        style_btn(quick, "仅逗号句号", lambda: self._apply_preset("common"), width=85, height=26,
                  font=FONTS["caption"](), fg_color=COLORS["surface_hover"],
                  hover_color=COLORS["accent"]).pack(side="left", padx=(4, 0))
        style_btn(quick, "全不选", lambda: self._apply_preset("none"), width=60, height=26,
                  font=FONTS["caption"](), fg_color=COLORS["surface_hover"],
                  hover_color=COLORS["accent"]).pack(side="left", padx=(4, 0))

        ctk.CTkLabel(self, text="自定义分隔符（额外字符，如 | ~ ·）",
                     font=FONTS["caption"](),
                     text_color=COLORS["text_secondary"]).pack(anchor="w", padx=16, pady=(4, 2))
        self._custom_entry = ctk.CTkEntry(
            self, placeholder_text="输入额外的切分字符", font=FONTS["body"](),
            fg_color=COLORS["surface"], border_color=COLORS["border"],
            text_color=COLORS["text"])
        self._custom_entry.pack(fill="x", padx=16, pady=(0, 8))
        custom = "".join(c for c in (puncts or "") if c not in _PRESET_CHARS)
        if custom:
            self._custom_entry.insert(0, custom)
        self._custom_entry.bind("<KeyRelease>", lambda e: self._update_preview())

        self._preview_label = ctk.CTkLabel(
            self, text="", font=FONTS["caption"](), text_color=COLORS["accent"],
            wraplength=420, justify="left", height=42)
        self._preview_label.pack(anchor="w", padx=16, pady=(0, 10), fill="x")

        btn_row = ctk.CTkFrame(self, fg_color="transparent")
        btn_row.pack(fill="x", padx=16, pady=(0, 14))
        style_btn(btn_row, "取消", self.destroy, width=70, height=28,
                  font=FONTS["body"](), fg_color=COLORS["surface_hover"],
                  hover_color=COLORS["accent"]).pack(side="right")
        style_btn(btn_row, "确定", self._confirm, width=70, height=28,
                  font=FONTS["body"]()).pack(side="right", padx=(0, 6))

        self._update_preview()

    def _bring_front(self):
        try:
            if self.winfo_exists():
                self.lift()
                self.focus_force()
        except Exception:
            pass

    def _apply_preset(self, kind):
        if kind == "all":
            values = [True] * len(self._vars)
        elif kind == "common":
            values = [chars[0] in "，。" for _, chars in self._vars]
        else:
            values = [False] * len(self._vars)
        for (var, _), v in zip(self._vars, values):
            var.set(v)

    def _collect(self):
        chars = []
        for var, group_chars in self._vars:
            if var.get():
                chars.extend(group_chars)
        chars.extend(self._custom_entry.get())
        seen = set()
        out = []
        for c in chars:
            if c and c not in seen:
                seen.add(c)
                out.append(c)
        return "".join(out)

    def _update_preview(self):
        s = self._collect()
        if s:
            self._preview_label.configure(text=f"当前生效分隔符（{len(s)} 个）：\n{s}")
        else:
            self._preview_label.configure(
                text="当前未选择任何标点：\n将仅在超过 2 倍段字数时按阈值硬切")

    def _confirm(self):
        self._on_confirm(self._collect())
        self.destroy()