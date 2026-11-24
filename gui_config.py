# -*- coding: utf-8 -*-
"""GUI 配置管理：保存、加载、导入、导出、删除配置"""
import json
import os
import shutil
from tkinter import filedialog, simpledialog
from languages import resolve
from validators import (atomic_write_text, clamp_rounds, sanitize_config_name)

# 下拉菜单中的固定操作项，不能与用户配置名重复
RESERVED_MENU_ITEMS = ("配置", "保存当前配置...", "删除配置...")


class ConfigMixin:
    CONFIG_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "configs")

    def _get_config_names(self):
        names = list(RESERVED_MENU_ITEMS)
        names.extend(n for n in self._list_config_names() if n not in RESERVED_MENU_ITEMS)
        return names

    def _list_config_names(self):
        """列出已保存的配置名（目录不存在时安全返回空列表）"""
        try:
            return [os.path.splitext(f)[0] for f in os.listdir(self.CONFIG_DIR)
                    if f.endswith(".json")]
        except OSError:
            return []

    def _config_path(self, name):
        """把配置名安全地映射为目录内路径；名字非法时返回 None"""
        safe = sanitize_config_name(name)
        if safe is None:
            return None
        return os.path.join(self.CONFIG_DIR, f"{safe}.json")

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

    # ===== 结构校验与应用 =====
    def _normalize_config(self, data):
        """校验配置结构，返回 (langs, final, rounds, split_puncts)；结构非法返回 None

        不做任何文件系统操作，便于被单元测试直接调用。
        """
        if not isinstance(data, dict):
            return None
        raw_langs = data.get("langs")
        if not isinstance(raw_langs, list):
            return None
        # 只保留当前版本认识的语言名，避免配置里塞入任意字符串传给引擎
        langs = [l for l in raw_langs if isinstance(l, str) and resolve(l) is not None]
        final = data.get("final", "中文")
        if not isinstance(final, str) or resolve(final) is None:
            final = "中文"
        rounds = clamp_rounds(data.get("rounds"), 10)
        split = data.get("split_puncts")
        if not isinstance(split, str):
            split = None
        return langs, final, rounds, split

    def _apply_config_data(self, data):
        """把配置数据应用到界面；返回是否成功"""
        normalized = self._normalize_config(data)
        if normalized is None:
            return False
        langs, final, rounds, split = normalized
        self._rounds_var.set(rounds)
        self._on_rounds_change(str(rounds))
        for i, var in enumerate(self._lang_vars):
            if i < len(langs):
                var.set(langs[i])
        self._final_lang_var.set(final)
        self._FINAL_LANG = final
        if split is not None:
            self._split_puncts = split
        self._update_chain_label()
        self._on_input_change()
        return True

    # ===== 保存 / 删除 / 加载 =====
    def _save_config(self):
        raw = simpledialog.askstring("保存配置", "配置名称:", parent=self)
        if not raw or not raw.strip():
            return
        name = sanitize_config_name(raw)
        if name is None:
            self._show_toast("配置名非法：不能包含路径分隔符或控制字符，且不超过 40 个字符", "warning")
            return
        path = self._config_path(name)
        if path is None:
            self._show_toast("配置名非法", "error")
            return
        langs = [v.get() for v in self._lang_vars]
        final = self._final_lang_var.get()
        data = {"langs": langs, "final": final, "rounds": self._rounds_var.get(),
                "split_puncts": self._split_puncts}
        try:
            os.makedirs(self.CONFIG_DIR, exist_ok=True)
            atomic_write_text(path, json.dumps(data, ensure_ascii=False, indent=2))
        except Exception as e:
            self._show_toast(f"保存失败: {e}", "error")
            return
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
        deleted = 0
        for name in names:
            path = self._config_path(name)
            if path and os.path.isfile(path):
                try:
                    os.remove(path)
                    deleted += 1
                except OSError:
                    pass
        self._config_menu.configure(values=self._get_config_names())
        self._config_menu.set("配置")
        self._show_toast(f"已删除 {deleted} 个配置")

    def _load_config(self):
        name = self._config_menu.get()
        if name in ("配置", "保存当前配置...", "删除配置..."):
            return
        path = self._config_path(name)
        if not path or not os.path.exists(path):
            self._show_toast(f"配置「{name}」不存在", "error")
            return
        try:
            with open(path, "r", encoding="utf-8") as f:
                data = json.load(f)
        except Exception as e:
            self._show_toast(f"读取失败: {e}", "error")
            return
        if not self._apply_config_data(data):
            self._show_toast(f"配置「{name}」格式无效", "error")
            return
        self._show_toast(f"已加载配置「{name}」")

    # ===== 导出 / 导入 =====
    def _export_config(self):
        configs = self._list_config_names()
        if not configs:
            self._show_toast("没有已保存的配置可导出", "warning")
            return
        raw = simpledialog.askstring(
            "导出配置", f"可选配置: {', '.join(configs)}\n输入要导出的配置名:", parent=self)
        if not raw or not raw.strip():
            return
        name = sanitize_config_name(raw)
        src_path = self._config_path(name) if name else None
        if not name or not src_path or not os.path.exists(src_path):
            self._show_toast(f"配置「{raw.strip()}」不存在", "error")
            return
        dst = filedialog.asksaveasfilename(
            title="导出配置", defaultextension=".json",
            filetypes=[("JSON 文件", "*.json")], initialfile=f"{name}.json")
        if not dst:
            return
        try:
            shutil.copy2(src_path, dst)
        except Exception as e:
            self._show_toast(f"导出失败: {e}", "error")
            return
        self._show_toast(f"已导出到 {os.path.basename(dst)}")

    def _import_config(self):
        src = filedialog.askopenfilename(
            title="导入配置", filetypes=[("JSON 文件", "*.json")])
        if not src:
            return
        try:
            with open(src, "r", encoding="utf-8") as f:
                data = json.load(f)
        except Exception as e:
            self._show_toast(f"读取失败: {e}", "error")
            return
        if self._normalize_config(data) is None:
            self._show_toast("无效的配置文件（缺少 langs 字段或结构错误）", "error")
            return
        name = sanitize_config_name(os.path.splitext(os.path.basename(src))[0])
        if name is None:
            self._show_toast("配置文件名不可用，请重命名后重试", "error")
            return
        dst_path = os.path.join(self.CONFIG_DIR, f"{name}.json")
        try:
            os.makedirs(self.CONFIG_DIR, exist_ok=True)
            atomic_write_text(dst_path, json.dumps(data, ensure_ascii=False, indent=2))
        except Exception as e:
            self._show_toast(f"导入失败: {e}", "error")
            return
        self._config_menu.configure(values=self._get_config_names())
        self._config_menu.set(name)
        if not self._apply_config_data(data):
            self._show_toast("已保存配置，但内容无法应用", "warning")
            return
        self._show_toast(f"已导入并应用配置「{name}」")
