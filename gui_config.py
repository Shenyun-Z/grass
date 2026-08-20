# -*- coding: utf-8 -*-
"""GUI 配置管理：保存、加载、导入、导出、删除配置"""
import json
import os
import shutil
from tkinter import filedialog, simpledialog
from gui_styles import COLORS


class ConfigMixin:
    CONFIG_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "configs")

    def _get_config_names(self):
        names = ["配置", "保存当前配置...", "删除配置..."]
        try:
            for f in os.listdir(self.CONFIG_DIR):
                if f.endswith(".json"):
                    names.append(os.path.splitext(f)[0])
        except Exception:
            pass
        return names

    def _list_config_names(self):
        """列出已保存的配置名（目录不存在时安全返回空列表）"""
        try:
            return [os.path.splitext(f)[0] for f in os.listdir(self.CONFIG_DIR)
                    if f.endswith(".json")]
        except OSError:
            return []

    def _on_config_menu_change(self, val):
        if val == "配置":
            return
        if val == "保存当前配置...":
            self._save_config()
            return
        if val == "删除配置...":
            self._delete_config()
            return
        self._load_config()

    def _save_config(self):
        name = simpledialog.askstring("保存配置", "配置名称:", parent=self)
        if not name or not name.strip():
            return
        name = name.strip()
        os.makedirs(self.CONFIG_DIR, exist_ok=True)
        langs = [v.get() for v in self._lang_vars]
        final = self._final_lang_var.get()
        data = {"langs": langs, "final": final, "rounds": self._rounds_var.get(),
                "split_puncts": self._split_puncts}
        path = os.path.join(self.CONFIG_DIR, f"{name}.json")
        with open(path, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
        self._config_menu.configure(values=self._get_config_names())
        self._config_menu.set(name)
        self._show_toast(f"配置「{name}」已保存")

    def _delete_config(self):
        from gui_dialogs import DeleteConfigDialog
        configs = self._list_config_names()
        if not configs:
            self._show_toast("没有已保存的配置", "warning")
            return
        DeleteConfigDialog(self, configs, self._do_delete_configs)

    def _do_delete_configs(self, names):
        for name in names:
            path = os.path.join(self.CONFIG_DIR, f"{name}.json")
            if os.path.exists(path):
                os.remove(path)
        self._config_menu.configure(values=self._get_config_names())
        self._config_menu.set("配置")
        self._show_toast(f"已删除 {len(names)} 个配置")

    def _load_config(self):
        name = self._config_menu.get()
        if name in ("配置", "保存当前配置...", "删除配置..."):
            return
        path = os.path.join(self.CONFIG_DIR, f"{name}.json")
        if not os.path.exists(path):
            self._show_toast(f"配置「{name}」不存在", "error")
            return
        try:
            with open(path, "r", encoding="utf-8") as f:
                data = json.load(f)
        except Exception as e:
            self._show_toast(f"读取失败: {e}", "error")
            return
        langs = data.get("langs", [])
        final = data.get("final", "中文")
        rounds = data.get("rounds", 10)
        self._rounds_var.set(rounds)
        self._on_rounds_change(str(rounds))
        for i, var in enumerate(self._lang_vars):
            if i < len(langs):
                var.set(langs[i])
        self._final_lang_var.set(final)
        self._FINAL_LANG = final
        split_puncts = data.get("split_puncts")
        if split_puncts is not None:
            self._split_puncts = split_puncts
        self._update_chain_label()
        self._on_input_change()
        self._show_toast(f"已加载配置「{name}」")

    def _export_config(self):
        configs = self._list_config_names()
        if not configs:
            self._show_toast("没有已保存的配置可导出", "warning")
            return
        name = simpledialog.askstring("导出配置", f"可选配置: {', '.join(configs)}\n输入要导出的配置名:", parent=self)
        if not name or not name.strip():
            return
        name = name.strip()
        src_path = os.path.join(self.CONFIG_DIR, f"{name}.json")
        if not os.path.exists(src_path):
            self._show_toast(f"配置「{name}」不存在", "error")
            return
        dst = filedialog.asksaveasfilename(
            title="导出配置", defaultextension=".json",
            filetypes=[("JSON 文件", "*.json")], initialfile=f"{name}.json")
        if not dst:
            return
        shutil.copy2(src_path, dst)
        self._show_toast(f"已导出到 {os.path.basename(dst)}")

    def _import_config(self):
        src = filedialog.askopenfilename(
            title="导入配置", filetypes=[("JSON 文件", "*.json")])
        if not src:
            return
        try:
            with open(src, "r", encoding="utf-8") as f:
                data = json.load(f)
            if "langs" not in data:
                self._show_toast("无效的配置文件", "error")
                return
        except Exception as e:
            self._show_toast(f"读取失败: {e}", "error")
            return
        name = os.path.splitext(os.path.basename(src))[0]
        os.makedirs(self.CONFIG_DIR, exist_ok=True)
        dst_path = os.path.join(self.CONFIG_DIR, f"{name}.json")
        with open(dst_path, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
        self._config_menu.configure(values=self._get_config_names())
        self._config_menu.set(name)
        langs = data.get("langs", [])
        final = data.get("final", "中文")
        rounds = data.get("rounds", 10)
        self._rounds_var.set(rounds)
        self._on_rounds_change(str(rounds))
        for i, var in enumerate(self._lang_vars):
            if i < len(langs):
                var.set(langs[i])
        self._final_lang_var.set(final)
        self._FINAL_LANG = final
        split_puncts = data.get("split_puncts")
        if split_puncts is not None:
            self._split_puncts = split_puncts
        self._update_chain_label()
        self._on_input_change()
        self._show_toast(f"已导入并应用配置「{name}」")