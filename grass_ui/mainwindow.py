# -*- coding: utf-8 -*-
"""生草机 v2.0 主窗口（PySide6）

界面全部由 Qt 布局与原生控件承担，分块/对照列表走 QListView 虚拟化绘制，
因此拖动窗口边框、滚动与结果流式更新都不会再触发整棵控件树重排。
"""
from __future__ import annotations

import copy
import json
import os
import queue
import shutil
import threading
import time

from PySide6.QtCore import Qt, QTimer
from PySide6.QtGui import QGuiApplication, QKeySequence, QShortcut
from PySide6.QtWidgets import (QApplication, QFileDialog, QFrame, QInputDialog,
                               QMainWindow, QScrollArea, QVBoxLayout, QWidget)

from engine import (DEFAULT_SPLIT_PUNCTS, _get_model, _preprocess,
                    _split_by_threshold, classify_translate_error, grass_translate)
from languages import DEFAULT_PIVOT_LANGS, resolve
from validators import (atomic_write_text, clamp_rounds, dump_history,
                        escape_spreadsheet_cell, next_history_id,
                        normalize_history, read_text_file, sanitize_config_name)
from version import __version__

from . import theme
from .dialogs import (DeleteConfigDialog, ExcludeLangDialog, HistoryDialog,
                      LangSelectDialog, PresetDialog, SplitPunctDialog,
                      StepDetailDialog)
from .panes import (ControlBar, InputPane, LangsPane, ParamsPane, ProgressCard,
                    ResultPane, SplitPane)
from .paths import app_dir
from .theme import px
from .widgets import Toast

RESERVED_MENU_ITEMS = ("配置", "保存当前配置...", "删除配置...")
RANDOM_MODES = {"固定": "off", "低强度": "low", "高强度": "high"}


class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self._init_state()
        self._build_ui()
        self._connect_signals()
        self._setup_shortcuts()
        self._load_history()
        self._refresh_config_menu()
        self._set_default_langs(10)
        self._load_model_async()

    # ================= 状态 =================
    def _init_state(self) -> None:
        self._segments: list[str] = []
        self._seg_states: dict[int, str] = {}
        self._seg_steps: dict[int, list] = {}
        self._seg_results: dict[int, str] = {}
        self._running = False
        self._model_ready = False
        self._model_exc: BaseException | None = None
        self._raw_text = ""
        self._input_view = "原文"
        self._split_puncts = DEFAULT_SPLIT_PUNCTS
        self._langs: list[str] = []
        self._excluded_langs: list[str] = ["英语"]
        self._result_view = "结果"
        self._compare_source = "原文"
        self._scale = theme.SCALE
        self._start_time = 0.0
        self._msg_queue: queue.Queue | None = None
        self._STOP_EVENT = threading.Event()
        self._final_lang = "中文"

        # 历史记录（文件格式与 v1.x 兼容）
        self._history: list[dict] = []
        self._history_limit = 20
        self._history_next_id = 1
        self._history_path = os.path.join(app_dir(), "history.json")

        # 配置
        self._config_dir = os.path.join(app_dir(), "configs")
        self._config_current = "配置"

    # ================= 界面 =================
    def _build_ui(self) -> None:
        self._set_title()
        self.resize(px(980), px(940))
        self.setMinimumSize(px(720), px(560))

        page = QWidget()
        page.setObjectName("page")
        layout = QVBoxLayout(page)
        layout.setContentsMargins(px(14), px(14), px(14), px(14))
        layout.setSpacing(px(8))

        self._input_pane = InputPane()
        self._params_pane = ParamsPane()
        self._langs_pane = LangsPane()
        self._split_pane = SplitPane()
        self._control = ControlBar()
        self._progress = ProgressCard()
        self._result_pane = ResultPane()
        self._result_pane.setMinimumHeight(px(200))

        for widget in (self._input_pane, self._params_pane, self._langs_pane,
                       self._split_pane, self._control, self._progress):
            layout.addWidget(widget)
        layout.addWidget(self._result_pane, 1)

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.NoFrame)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        scroll.setWidget(page)
        self.setCentralWidget(scroll)
        self._page = page
        self._page_scroll = scroll

        self._toast = Toast(page)

    def _connect_signals(self) -> None:
        self._input_pane.textChanged.connect(self._on_input_edit)
        self._input_pane.viewModeChanged.connect(self._on_view_mode)
        self._input_pane.fileDropped.connect(self._set_input_text_from_file)
        self._input_pane.loadClicked.connect(self._load_file)
        self._input_pane.clipboardClicked.connect(self._paste_from_clipboard)

        self._params_pane.roundsChanged.connect(self._on_rounds_change)
        self._params_pane.thresholdChanged.connect(lambda _n: self._on_input_change())
        self._params_pane.finalLangClicked.connect(self._open_final_lang_picker)
        self._params_pane.randomModeChanged.connect(self._on_random_mode_change)
        self._params_pane.excludeClicked.connect(self._open_exclude_dialog)

        self._langs_pane.langClicked.connect(self._open_lang_picker)
        self._langs_pane.presetClicked.connect(self._open_preset)
        self._langs_pane.exportClicked.connect(self._export_config)
        self._langs_pane.importClicked.connect(self._import_config)
        self._langs_pane.configAction.connect(self._on_config_action)

        self._split_pane.segClicked.connect(self._show_seg_detail)
        self._split_pane.punctClicked.connect(self._open_split_punct_dialog)
        self._split_pane.view.zoomRequested.connect(self._on_zoom_wheel)
        self._result_pane.compare_view.zoomRequested.connect(self._on_zoom_wheel)

        self._control.startClicked.connect(self._toggle)
        self._result_pane.viewChanged.connect(self._on_result_view_change)
        self._result_pane.compareSourceChanged.connect(self._on_compare_source_change)
        self._result_pane.historyClicked.connect(self._open_history_dialog)
        self._result_pane.copyClicked.connect(self._copy_result)
        self._result_pane.saveClicked.connect(self._save_result)

        self._input_debounce = QTimer(self)
        self._input_debounce.setSingleShot(True)
        self._input_debounce.setInterval(150)
        self._input_debounce.timeout.connect(self._on_input_change)

        self._poll_timer = QTimer(self)
        self._poll_timer.setInterval(60)
        self._poll_timer.timeout.connect(self._poll_queue)

    def _setup_shortcuts(self) -> None:
        QShortcut(QKeySequence("Ctrl+Return"), self, activated=self._toggle)
        QShortcut(QKeySequence("Ctrl+S"), self, activated=self._save_result)
        QShortcut(QKeySequence("Ctrl+Shift+V"), self, activated=self._paste_from_clipboard)
        QShortcut(QKeySequence("Ctrl+H"), self, activated=self._open_history_dialog)
        QShortcut(QKeySequence("Esc"), self, activated=self._on_escape)
        QShortcut(QKeySequence("Ctrl++"), self, activated=lambda: self._set_scale(self._scale + 0.1))
        QShortcut(QKeySequence("Ctrl+="), self, activated=lambda: self._set_scale(self._scale + 0.1))
        QShortcut(QKeySequence("Ctrl+-"), self, activated=lambda: self._set_scale(self._scale - 0.1))
        QShortcut(QKeySequence("Ctrl+0"), self, activated=lambda: self._set_scale(1.0))

    def _set_title(self, suffix: str = "") -> None:
        base = f"生草机 v{__version__}"
        self.setWindowTitle(f"{base} — {suffix}" if suffix else base)

    def _show_toast(self, message: str, kind: str = "success") -> None:
        self._toast.show_message(message, kind)

    # ================= 输入 =================
    def _on_input_edit(self) -> None:
        if self._running or self._input_pane.view_mode() != "原文":
            return
        self._raw_text = self._input_pane.text()
        self._input_debounce.start()

    def _on_view_mode(self, value: str) -> None:
        current = self._input_pane.text()
        if value == "去空格":
            if self._input_view == "原文":
                self._raw_text = current
            clean = _preprocess(current)
            self._input_pane.set_text(clean)
            self._input_view = value
        else:
            self._input_pane.set_text(self._raw_text)
            self._input_view = value
        self._on_input_change()

    def _load_file(self) -> None:
        path, _ = QFileDialog.getOpenFileName(
            self, "选择文本文件", "", "文本文件 (*.txt);;所有文件 (*)")
        if path:
            self._set_input_text_from_file(path)

    def _paste_from_clipboard(self) -> None:
        if self._running:
            return
        text = QGuiApplication.clipboard().text().strip()
        if not text:
            self._show_toast("剪贴板为空或不可读", "warning")
            return
        self._raw_text = text
        self._input_pane.set_view_mode("原文")
        self._input_view = "原文"
        self._input_pane.set_text(text)
        self._on_input_change()
        self._show_toast(f"已读入剪贴板（{len(text)} 字符）")

    def _set_input_text_from_file(self, path: str) -> None:
        try:
            text = read_text_file(path)
        except Exception as exc:
            self._show_toast(f"读取失败: {exc}", "error")
            return
        if not text.strip():
            self._show_toast("文件内容为空", "warning")
            return
        self._raw_text = text
        self._input_pane.set_view_mode("原文")
        self._input_view = "原文"
        self._input_pane.set_text(text)
        self._on_input_change()
        self._show_toast(f"已读取 {os.path.basename(path)}（{len(text)} 字符）")

    def _on_input_change(self) -> None:
        if self._running:
            return
        clean = _preprocess(self._raw_text)
        self._input_pane.set_char_count(len(clean))
        threshold = self._params_pane.threshold() or 20
        self._segments = _split_by_threshold(clean, threshold, self._split_puncts)
        self._seg_states = {i: "waiting" for i in range(len(self._segments))}
        self._split_pane.set_segments(self._segments)
        self._split_pane.update_info()
        self._progress.set_counter(self._split_pane.counter())

    def _show_seg_detail(self, idx: int) -> None:
        steps = self._seg_steps.get(idx, [])
        if not steps:
            self._show_toast("该段还没有翻译过程", "warning")
            return
        StepDetailDialog(self, idx, steps, self._final_lang)

    # ================= 参数 / 语言 =================
    def _set_default_langs(self, n: int) -> None:
        self._params_pane.set_rounds(n)
        self._on_rounds_change(n)

    def _on_rounds_change(self, n: int) -> None:
        if self._running:
            return
        n = max(1, int(n))
        self._langs = [DEFAULT_PIVOT_LANGS[i % len(DEFAULT_PIVOT_LANGS)] for i in range(n)]
        self._langs_pane.set_langs(self._langs)
        self._update_chain_label()
        self._on_input_change()

    def _on_random_mode_change(self, mode: str) -> None:
        fixed = (mode == "固定")
        self._langs_pane.set_state(not self._running, fixed_mode=fixed)
        self._params_pane.set_exclude_enabled((not self._running) and not fixed)
        if fixed:
            self._update_chain_label()
        else:
            self._update_random_chain_label()

    def _update_chain_label(self) -> None:
        if self._params_pane.random_mode() != "固定":
            self._update_random_chain_label()
            return
        final = self._params_pane.final_lang()
        self._final_lang = final
        self._langs = self._langs_pane.langs()
        self._langs_pane.set_chain("中文 → " + " → ".join(self._langs) + " → " + final)

    def _update_random_chain_label(self) -> None:
        mode = self._params_pane.random_mode()
        desc = "低强度: 大语种随机" if mode == "低强度" else "高强度: 全语种随机"
        excluded = self._excluded_langs
        ex_str = f"，排除{'+'.join(excluded)}" if excluded else ""
        self._langs_pane.set_chain(
            f"随机 × {self._params_pane.rounds()} 轮 ({desc}{ex_str})")

    def _open_lang_picker(self, idx: int) -> None:
        disabled = set()
        langs = self._langs_pane.langs()
        if idx > 0:
            disabled.add(langs[idx - 1])
        if idx + 1 < len(langs):
            disabled.add(langs[idx + 1])
        dialog = LangSelectDialog(self, disabled_langs=disabled)
        if dialog.exec():
            lang = dialog.selected
            if lang:
                self._langs_pane.set_lang_text(idx, lang)
                self._update_chain_label()
                self._on_input_change()

    def _open_final_lang_picker(self) -> None:
        dialog = LangSelectDialog(self)
        if dialog.exec() and dialog.selected:
            self._params_pane.set_final_lang(dialog.selected)
            self._update_chain_label()
            self._on_input_change()

    def _open_preset(self) -> None:
        dialog = PresetDialog(self, len(self._langs_pane.langs()))
        if dialog.exec() and dialog.result_langs:
            self._langs_pane.set_langs(dialog.result_langs)
            self._update_chain_label()
            self._on_input_change()

    def _open_exclude_dialog(self) -> None:
        dialog = ExcludeLangDialog(self, self._excluded_langs)
        if dialog.exec():
            self._excluded_langs = dialog.excluded
            self._update_random_chain_label()

    # ================= 切分标点 =================
    def _open_split_punct_dialog(self) -> None:
        dialog = SplitPunctDialog(self, self._split_puncts)
        if dialog.exec():
            self._apply_split_puncts(dialog.puncts)

    def _apply_split_puncts(self, puncts: str) -> None:
        self._split_puncts = puncts
        self._on_input_change()
        if puncts:
            self._show_toast(f"切分符已更新（{len(puncts)} 个字符）")
        else:
            self._show_toast("已禁用标点切分（仅按段字数硬切）", "warning")

    # ================= 配置 =================
    def _list_config_names(self) -> list[str]:
        try:
            return [os.path.splitext(f)[0] for f in os.listdir(self._config_dir)
                    if f.endswith(".json")]
        except OSError:
            return []

    def _config_path(self, name: str) -> str | None:
        safe = sanitize_config_name(name)
        if safe is None:
            return None
        return os.path.join(self._config_dir, f"{safe}.json")

    def _refresh_config_menu(self) -> None:
        names = list(RESERVED_MENU_ITEMS) + [n for n in self._list_config_names()
                                             if n not in RESERVED_MENU_ITEMS]
        self._langs_pane.set_config_names(names, self._config_current)

    def _on_config_action(self, action: str) -> None:
        if action == "配置":
            return
        if action == "保存当前配置...":
            self._save_config()
            self._refresh_config_menu()
            return
        if action == "删除配置...":
            self._delete_config()
            return
        self._load_config(action)

    def _normalize_config(self, data) -> tuple | None:
        if not isinstance(data, dict):
            return None
        raw_langs = data.get("langs")
        if not isinstance(raw_langs, list):
            return None
        langs = [lang for lang in raw_langs if isinstance(lang, str) and resolve(lang) is not None]
        final = data.get("final", "中文")
        if not isinstance(final, str) or resolve(final) is None:
            final = "中文"
        rounds = clamp_rounds(data.get("rounds"), 10)
        split = data.get("split_puncts")
        if not isinstance(split, str):
            split = None
        return langs, final, rounds, split

    def _apply_config_data(self, data) -> bool:
        normalized = self._normalize_config(data)
        if normalized is None:
            return False
        langs, final, rounds, split = normalized
        self._params_pane.set_rounds(rounds)
        self._on_rounds_change(rounds)
        for i, lang in enumerate(langs):
            if i < len(self._langs_pane.langs()):
                self._langs_pane.set_lang_text(i, lang)
        self._params_pane.set_final_lang(final)
        self._final_lang = final
        if split is not None:
            self._split_puncts = split
        self._update_chain_label()
        self._on_input_change()
        return True

    def _save_config(self) -> None:
        raw, ok = QInputDialog.getText(self, "保存配置", "配置名称:")
        if not ok or not raw.strip():
            return
        name = sanitize_config_name(raw)
        if name is None:
            self._show_toast("配置名非法：不能包含路径分隔符或控制字符，且不超过 40 个字符", "warning")
            return
        path = self._config_path(name)
        data = {"langs": self._langs_pane.langs(), "final": self._params_pane.final_lang(),
                "rounds": self._params_pane.rounds(), "split_puncts": self._split_puncts}
        try:
            os.makedirs(self._config_dir, exist_ok=True)
            atomic_write_text(path, json.dumps(data, ensure_ascii=False, indent=2))
        except Exception as exc:
            self._show_toast(f"保存失败: {exc}", "error")
            return
        self._config_current = name
        self._show_toast(f"配置「{name}」已保存")

    def _delete_config(self) -> None:
        configs = self._list_config_names()
        if not configs:
            self._show_toast("没有已保存的配置", "warning")
            return
        dialog = DeleteConfigDialog(self, configs)
        if dialog.exec():
            self._do_delete_configs(dialog.selected)

    def _do_delete_configs(self, names: list[str]) -> None:
        deleted = 0
        for name in names:
            path = self._config_path(name)
            if path and os.path.isfile(path):
                try:
                    os.remove(path)
                    deleted += 1
                except OSError:
                    pass
        self._config_current = "配置"
        self._refresh_config_menu()
        self._show_toast(f"已删除 {deleted} 个配置")

    def _load_config(self, name: str) -> None:
        path = self._config_path(name)
        if not path or not os.path.exists(path):
            self._show_toast(f"配置「{name}」不存在", "error")
            return
        try:
            with open(path, "r", encoding="utf-8") as f:
                data = json.load(f)
        except Exception as exc:
            self._show_toast(f"读取失败: {exc}", "error")
            return
        if not self._apply_config_data(data):
            self._show_toast(f"配置「{name}」格式无效", "error")
            return
        self._config_current = name
        self._langs_pane.set_config_current(name)
        self._show_toast(f"已加载配置「{name}」")

    def _export_config(self) -> None:
        configs = self._list_config_names()
        if not configs:
            self._show_toast("没有已保存的配置可导出", "warning")
            return
        raw, ok = QInputDialog.getText(
            self, "导出配置", f"可选配置: {', '.join(configs)}\n输入要导出的配置名:")
        if not ok or not raw.strip():
            return
        name = sanitize_config_name(raw)
        src = self._config_path(name) if name else None
        if not src or not os.path.exists(src):
            self._show_toast(f"配置「{raw.strip()}」不存在", "error")
            return
        dst, _ = QFileDialog.getSaveFileName(
            self, "导出配置", f"{name}.json", "JSON 文件 (*.json)")
        if not dst:
            return
        try:
            shutil.copy2(src, dst)
        except Exception as exc:
            self._show_toast(f"导出失败: {exc}", "error")
            return
        self._show_toast(f"已导出到 {os.path.basename(dst)}")

    def _import_config(self) -> None:
        src, _ = QFileDialog.getOpenFileName(self, "导入配置", "", "JSON 文件 (*.json)")
        if not src:
            return
        try:
            with open(src, "r", encoding="utf-8") as f:
                data = json.load(f)
        except Exception as exc:
            self._show_toast(f"读取失败: {exc}", "error")
            return
        if self._normalize_config(data) is None:
            self._show_toast("无效的配置文件（缺少 langs 字段或结构错误）", "error")
            return
        name = sanitize_config_name(os.path.splitext(os.path.basename(src))[0])
        if name is None:
            self._show_toast("配置文件名不可用，请重命名后重试", "error")
            return
        try:
            os.makedirs(self._config_dir, exist_ok=True)
            atomic_write_text(os.path.join(self._config_dir, f"{name}.json"),
                              json.dumps(data, ensure_ascii=False, indent=2))
        except Exception as exc:
            self._show_toast(f"导入失败: {exc}", "error")
            return
        self._config_current = name
        self._refresh_config_menu()
        self._langs_pane.set_config_current(name)
        if not self._apply_config_data(data):
            self._show_toast("已保存配置，但内容无法应用", "warning")
            return
        self._show_toast(f"已导入并应用配置「{name}」")

    # ================= 历史 =================
    def _load_history(self) -> None:
        self._history = []
        try:
            if os.path.exists(self._history_path):
                with open(self._history_path, "r", encoding="utf-8") as f:
                    data = json.load(f)
                self._history = normalize_history(data, self._history_limit)
        except Exception:
            self._history = []
        finally:
            self._history_next_id = next_history_id(self._history)
            self._refresh_compare_sources()

    def _save_history(self) -> None:
        try:
            atomic_write_text(self._history_path, dump_history(self._history))
        except Exception:
            pass

    def _history_label(self, rec: dict) -> str:
        mark = " ⏹" if rec.get("stopped") else ""
        return f"#{rec['id']} {rec['time']}{mark}"

    def _refresh_compare_sources(self) -> None:
        values = ["原文"] + [self._history_label(r) for r in reversed(self._history)]
        self._result_pane.set_compare_sources(values)
        if self._compare_source not in values:
            self._compare_source = "原文"
            self._result_pane.set_compare_source("原文")

    def _add_history_entry(self, stopped: bool = False, elapsed_str: str = "") -> None:
        if not self._seg_results:
            return
        record = {
            "id": self._history_next_id,
            "date": time.strftime("%m-%d"),
            "time": time.strftime("%H:%M:%S"),
            "input": self._raw_text,
            "result": self._result_pane.text(),
            "segments": list(self._segments),
            "seg_results": dict(self._seg_results),
            "seg_steps": copy.deepcopy(self._seg_steps),
            "params": {
                "rounds": self._params_pane.rounds(),
                "mode": self._params_pane.random_mode(),
                "langs": self._langs_pane.langs(),
                "final": self._params_pane.final_lang(),
                "threshold": self._params_pane.threshold(),
                "split_puncts": self._split_puncts,
            },
            "stopped": stopped,
            "elapsed": elapsed_str,
        }
        self._history_next_id += 1
        self._history.append(record)
        while len(self._history) > self._history_limit:
            self._history.pop(0)
        self._save_history()
        self._refresh_compare_sources()
        if self._result_view == "对照":
            self._render_compare_view()

    def _open_history_dialog(self) -> None:
        if not self._history:
            self._show_toast("暂无历史记录", "warning")
            return
        dialog = HistoryDialog(self, self._history)
        dialog.exec()
        action, rec_id = dialog.action, dialog.target_id
        if action == "compare" and rec_id is not None:
            self._history_compare(rec_id)
        elif action == "delete" and rec_id is not None:
            self._history_delete(rec_id)
        elif action == "clear":
            self._history_clear()

    def _history_compare(self, rec_id: int) -> None:
        rec = next((r for r in self._history if r["id"] == rec_id), None)
        if rec is None:
            self._show_toast("记录不存在", "warning")
            return
        label = self._history_label(rec)
        self._compare_source = label
        self._result_pane.set_compare_source(label)
        self._result_pane.set_view_mode("对照")
        self._on_result_view_change("对照")

    def _history_delete(self, rec_id: int) -> None:
        self._history[:] = [r for r in self._history if r["id"] != rec_id]
        self._save_history()
        self._refresh_compare_sources()
        if self._result_view == "对照":
            self._render_compare_view()

    def _history_clear(self) -> None:
        self._history.clear()
        self._save_history()
        self._refresh_compare_sources()
        if self._result_view == "对照":
            self._render_compare_view()
        self._show_toast("历史记录已清空")

    # ================= 结果视图 =================
    def _on_result_view_change(self, value: str) -> None:
        self._result_view = value
        if value == "对照":
            self._render_compare_view()
        # 结果区在窗口较矮时可能位于折叠线以下，切换视图后主动带过去
        QTimer.singleShot(0, self._scroll_to_result)

    def _scroll_to_result(self) -> None:
        self._page_scroll.ensureWidgetVisible(self._result_pane, 0, px(20))

    def _on_compare_source_change(self, value: str) -> None:
        self._compare_source = value
        self._render_compare_view()

    def _render_compare_view(self) -> None:
        right_items = [self._seg_results.get(i, "") for i in range(len(self._segments))]
        left_title, left_items = "原文", list(self._segments)
        if self._compare_source != "原文":
            rec = next((r for r in self._history
                        if self._history_label(r) == self._compare_source), None)
            if rec is not None:
                left_title = self._compare_source
                left_items = [rec["seg_results"].get(i, "")
                              for i in range(len(rec["segments"]))]
        self._result_pane.set_compare_titles(left_title, "当前结果")
        self._result_pane.set_compare_data(left_items, right_items)

    def _copy_result(self) -> None:
        text = self._result_pane.text()
        if text:
            QGuiApplication.clipboard().setText(text)
            self._show_toast("已复制到剪贴板")

    def _save_result(self) -> None:
        text = self._result_pane.text()
        if not text:
            return
        path, _ = QFileDialog.getSaveFileName(
            self, "保存结果", "output.txt", "文本文件 (*.txt);;Excel 文件 (*.xlsx)")
        if not path:
            return
        try:
            if path.endswith(".xlsx"):
                self._save_result_xlsx(path)
            else:
                atomic_write_text(path, text)
            self._show_toast(f"已保存到 {os.path.basename(path)}")
        except ImportError:
            self._show_toast("需要 openpyxl: pip install openpyxl", "error")
        except Exception as exc:
            self._show_toast(f"保存失败: {exc}", "error")

    def _save_result_xlsx(self, path: str) -> None:
        import openpyxl
        wb = openpyxl.Workbook()
        ws = wb.active
        ws.title = "生草结果"
        ws.append(["段号", "原文", "结果"])
        for i, seg in enumerate(self._segments):
            ws.append([i + 1, escape_spreadsheet_cell(seg),
                       escape_spreadsheet_cell(self._seg_results.get(i, ""))])
        detail = wb.create_sheet("翻译过程")
        detail.append(["段号", "步骤", "源语言", "目标语言", "翻译结果"])
        for si in sorted(self._seg_steps.keys()):
            for step_i, (src, tgt, txt) in enumerate(self._seg_steps[si]):
                detail.append([si + 1, step_i + 1, src, tgt, escape_spreadsheet_cell(txt)])
        for sheet in (ws, detail):
            for col in sheet.columns:
                sheet.column_dimensions[col[0].column_letter].width = 40
        wb.save(path)

    # ================= 模型加载 =================
    def _load_model_async(self) -> None:
        if os.environ.get("GRASS_SKIP_MODEL_LOAD") == "1":
            # 仅供界面冒烟测试：跳过真实加载（模型目录通常不存在于 CI）
            self._model_ready = True
            self._control.set_start("▶ 开始翻译", True)
            self._control.set_status("✓ 就绪", "success")
            self._set_title()
            return
        self._control.set_status("⟳ 加载模型中...", "info")
        self._control.set_start("⟳ 模型加载中...", False)
        self._set_title("加载模型中...")
        self._model_exc = None

        def worker():
            try:
                _get_model()
            except Exception as exc:  # noqa: BLE001 - 具体分类交给界面
                self._model_exc = exc
                import traceback
                traceback.print_exc()

        thread = threading.Thread(target=worker, daemon=True)
        thread.start()

        def check():
            if thread.is_alive():
                return
            timer.stop()
            if self._model_exc is not None:
                friendly = classify_translate_error(self._model_exc)
                self._control.set_status(f"✗ {friendly}", "error")
                self._control.set_start("✗ 模型加载失败", False)
                self._set_title("模型加载失败")
            else:
                self._model_ready = True
                self._control.set_start("▶ 开始翻译", True)
                self._control.set_status("✓ 就绪", "success")
                self._set_title()
                self._on_input_change()
                if self._history:
                    self._show_toast(f"已加载 {len(self._history)} 条历史记录", "info")

        timer = QTimer(self)
        timer.setInterval(200)
        timer.timeout.connect(check)
        timer.start()
        self._model_check_timer = timer

    # ================= 翻译流程 =================
    def _toggle(self) -> None:
        if not self._model_ready:
            self._show_toast("模型加载中，请稍候...", "info")
            return
        if self._running:
            self._stop()
        else:
            self._start()

    def _on_escape(self) -> None:
        if self._running:
            self._stop()

    def _start(self) -> None:
        if self._running:
            return
        if not self._raw_text.strip():
            self._control.set_status("⚠ 请输入文本", "warning")
            return
        # 输入框有 150ms 去抖，开始时强制按最新文本重新分段
        self._on_input_change()

        self._poll_timer.stop()
        self._running = True
        self._start_time = time.time()
        self._STOP_EVENT.clear()
        self._msg_queue = queue.Queue()
        self._seg_steps = {}
        self._seg_results = {}
        self._seg_states = {i: "waiting" for i in range(len(self._segments))}

        self._set_params_enabled(False)
        self._control.set_start("■ 停止翻译", True, danger=True)
        self._result_pane.clear_text()
        self._split_pane.model.clear_results()
        self._split_pane.update_info()
        self._progress.reset()
        self._progress.set_counter(f"0 / {len(self._segments)}")
        self._progress.set_step("")
        self._control.set_status("● 翻译中...", "accent")
        self._set_title("翻译中...")

        rounds = self._params_pane.rounds()
        self._final_lang = self._params_pane.final_lang()
        pivot_langs = self._langs_pane.langs()
        threshold = self._params_pane.threshold()
        mode = RANDOM_MODES.get(self._params_pane.random_mode(), "off")
        excluded = self._excluded_langs if mode != "off" else []

        thread = threading.Thread(
            target=self._run_translate,
            args=(self._raw_text, rounds, pivot_langs, threshold, mode, excluded,
                  self._split_puncts),
            daemon=True)
        thread.start()
        self._poll_timer.start()

    def _run_translate(self, text: str, rounds: int, pivot_langs: list[str],
                       threshold: int, random_mode: str, excluded: list[str],
                       split_puncts: str) -> None:
        q = self._msg_queue
        if q is None:
            return
        try:
            for msg in grass_translate(
                    text, rounds, pivot_langs, self._final_lang, threshold,
                    random_mode=random_mode, excluded_langs=excluded,
                    split_puncts=split_puncts, stop_event=self._STOP_EVENT):
                if self._STOP_EVENT.is_set():
                    q.put(("aborted",))
                    return
                q.put(msg)
        except Exception as exc:  # noqa: BLE001
            q.put(("error", classify_translate_error(exc)))

    def _stop(self) -> None:
        self._STOP_EVENT.set()
        self._running = False
        self._poll_timer.stop()
        self._set_params_enabled(True)
        self._control.set_start("▶ 开始翻译", True)
        self._control.set_status("已停止", "secondary")
        self._set_title()

    def _poll_queue(self) -> None:
        if not self._running or self._msg_queue is None:
            return
        try:
            while True:
                msg = self._msg_queue.get_nowait()
                self._handle_msg(msg)
                if not self._running:
                    return
        except queue.Empty:
            pass

    def _handle_msg(self, msg: tuple) -> None:
        kind = msg[0]
        if kind == "step":
            _, si, step_i, src_lang, tgt_lang, current = msg
            total = self._params_pane.rounds()
            self._progress.set_step(
                f"段{si + 1} · {src_lang}→{tgt_lang} ({step_i + 1}/{total})")
            self._seg_steps.setdefault(si, []).append((src_lang, tgt_lang, current))
            seg_total = len(self._segments)
            if seg_total:
                self._progress.set_progress(
                    (si + (step_i + 1) / (total + 1)) / seg_total)
            self._update_seg_state(si, "translating")
            self._auto_follow_seg(si)
        elif kind == "segment":
            _, si, src_lang, tgt_lang, result = msg
            self._seg_steps.setdefault(si, []).append((src_lang, tgt_lang, result))
            self._seg_results[si] = result
            self._split_pane.update_result(si, result)
            self._result_pane.append_text(result)
            self._update_seg_state(si, "done")
            if self._seg_results and len(self._seg_results) == 1:
                # 第一段结果出来时，把结果区带入视野（不打断后续操作）
                self._scroll_to_result()
            if self._result_view == "对照":
                self._result_pane.update_compare_right(si, result)
            if self._segments:
                self._progress.set_progress((si + 1) / len(self._segments))
            self._progress.set_counter(self._split_pane.counter())
        elif kind == "done":
            self._running = False
            self._poll_timer.stop()
            self._set_params_enabled(True)
            self._control.set_start("▶ 开始翻译", True)
            elapsed = time.time() - self._start_time if self._start_time else 0
            time_str = f"{elapsed / 60:.1f}分钟" if elapsed >= 60 else f"{elapsed:.1f}秒"
            self._control.set_status(f"✓ 翻译完成 ({time_str})", "success")
            self._progress.set_step("")
            self._progress.set_progress(1.0, animate=False)
            self._set_title("翻译完成")
            text = self._result_pane.text()
            if text and self._control.auto_copy():
                QGuiApplication.clipboard().setText(text)
                self._show_toast(f"翻译完成 ({time_str})，结果已复制到剪贴板")
            else:
                self._show_toast(f"翻译完成 ({time_str})")
            self._add_history_entry(stopped=False, elapsed_str=time_str)
        elif kind == "aborted":
            self._running = False
            self._poll_timer.stop()
            self._set_params_enabled(True)
            self._control.set_start("▶ 开始翻译", True)
            self._control.set_status("⏹ 已停止", "secondary")
            self._set_title()
            if self._seg_results:
                self._add_history_entry(stopped=True)
        elif kind == "error":
            self._running = False
            self._poll_timer.stop()
            self._set_params_enabled(True)
            self._control.set_start("▶ 开始翻译", True)
            self._control.set_status(f"✗ 错误: {msg[1]}", "error")
            self._set_title("错误")

    def _update_seg_state(self, si: int, state: str) -> None:
        if not (0 <= si < len(self._segments)):
            return
        self._seg_states[si] = state
        self._split_pane.model.update_state(si, state)
        self._progress.set_counter(self._split_pane.counter())

    def _auto_follow_seg(self, si: int) -> None:
        if self._split_pane.auto_follow():
            self._split_pane.follow(si)

    def _set_params_enabled(self, enabled: bool) -> None:
        fixed = self._params_pane.random_mode() == "固定"
        self._input_pane.set_enabled_state(enabled)
        self._params_pane.set_enabled_state(enabled, fixed_mode=fixed)
        self._langs_pane.set_state(enabled, fixed_mode=fixed)
        self._split_pane.set_state(enabled)
        self._control.set_auto_copy_enabled(enabled)
        self._result_pane.set_state(enabled)

    # ================= 缩放 =================
    def _on_zoom_wheel(self, delta: int) -> None:
        if delta == 0:
            return
        self._set_scale(self._scale + (0.1 if delta > 0 else -0.1))

    def _set_scale(self, value: float) -> None:
        value = round(max(theme.SCALE_MIN, min(theme.SCALE_MAX, value)), 2)
        if abs(value - self._scale) < 0.01:
            return
        self._scale = value
        theme.apply_theme(QApplication.instance(), value)
        self._split_pane.refresh_fonts()
        self._result_pane.refresh_fonts()
        self._show_toast(f"字号 {int(value * 100)}%", "info")

    # ================= 关闭 =================
    def closeEvent(self, event) -> None:
        try:
            self._STOP_EVENT.set()
            self._poll_timer.stop()
            self._input_debounce.stop()
            self._save_history()
        finally:
            event.accept()
