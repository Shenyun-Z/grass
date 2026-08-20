# -*- coding: utf-8 -*-
"""GUI 翻译控制：启动、停止、消息轮询、进度更新"""
import queue
import threading
import time
from engine import grass_translate
from gui_styles import COLORS


class TranslateMixin:
    def _toggle(self):
        if not self._model_ready:
            self._show_toast("模型加载中，请稍候...", "info")
            return
        if self._running:
            self._stop()
        else:
            self._start()

    def _start(self):
        if not self._raw_text.strip():
            self._status_label.configure(text="⚠ 请输入文本", text_color=COLORS["warning"])
            return

        self._running = True
        self._start_time = time.time()
        self._STOP_EVENT.clear()
        self._msg_queue = queue.Queue()
        self._seg_steps = {}
        self._seg_results = {}
        self._set_params_enabled(False)
        self._start_btn.configure(text="■ 停止翻译")
        self._animate_btn_color(self._start_btn, "#aa3333", "#cc4444")
        self._result_box.configure(state="normal")
        self._result_box.delete("1.0", "end")
        self._result_box.configure(state="disabled")
        self._progress_bar.set(0)
        for i in range(len(self._segments)):
            self._seg_states[i] = "waiting"
            self._update_card_state(i, "waiting")
        self._seg_counter.configure(text=f"0 / {len(self._segments)}")
        self._step_label.configure(text="")
        self._status_label.configure(text="● 翻译中...", text_color=COLORS["accent"])
        self.title("生草机 — 翻译中...")

        rounds = self._rounds_var.get()
        pivot_langs = [v.get() for v in self._lang_vars]
        threshold = self._threshold_var.get()
        random_mode = self._random_mode_var.get()
        mode_arg = {"固定": "off", "低强度": "low", "高强度": "high"}.get(random_mode, "off")
        excluded = self._excluded_langs if mode_arg != "off" else []

        t = threading.Thread(
            target=self._run_translate,
            args=(self._raw_text, rounds, pivot_langs, threshold, mode_arg, excluded, self._split_puncts),
            daemon=True)
        t.start()
        self._poll_queue()

    def _run_translate(self, text, rounds, pivot_langs, threshold, random_mode="off",
                       excluded_langs=None, split_puncts=None):
        q = self._msg_queue
        try:
            for msg in grass_translate(
                    text, rounds, pivot_langs, self._FINAL_LANG, threshold,
                    random_mode=random_mode, excluded_langs=excluded_langs or [],
                    split_puncts=split_puncts):
                if self._STOP_EVENT.is_set():
                    q.put(("aborted",))
                    return
                q.put(msg)
        except Exception as e:
            q.put(("error", str(e)))

    def _stop(self):
        self._STOP_EVENT.set()
        self._running = False
        if self._poll_after_id is not None:
            self.after_cancel(self._poll_after_id)
            self._poll_after_id = None
        self._set_params_enabled(True)
        self._start_btn.configure(text="▶ 开始翻译")
        self._animate_btn_color(self._start_btn, COLORS["accent"], COLORS["accent_hover"])
        self._status_label.configure(text=" 已停止", text_color=COLORS["text_secondary"])
        self.title("生草机")

    def _poll_queue(self):
        if not self._running:
            return
        q = self._msg_queue
        try:
            while True:
                msg = q.get_nowait()
                self._handle_msg(msg)
        except queue.Empty:
            pass
        self._poll_after_id = self.after(100, self._poll_queue)

    def _handle_msg(self, msg):
        kind = msg[0]
        if kind == "step":
            _, si, step_i, src_lang, tgt_lang, current = msg
            total = self._rounds_var.get()
            self._step_label.configure(text=f"段{si+1} · {src_lang}→{tgt_lang} ({step_i+1}/{total})")
            if si not in self._seg_steps:
                self._seg_steps[si] = []
            self._seg_steps[si].append((src_lang, tgt_lang, current))
            seg_total = len(self._segments)
            # 每段共 rounds+1 步（中转轮数 + 最后译回），译回步骤也计入进度，避免跳变
            progress = (si + (step_i + 1) / (total + 1)) / seg_total
            self._animate_progress(progress)
            self._update_seg_status(si, "●")
            self._auto_follow_seg(si)
        elif kind == "segment":
            _, si, src_lang, tgt_lang, result = msg
            if si not in self._seg_steps:
                self._seg_steps[si] = []
            self._seg_steps[si].append((src_lang, tgt_lang, result))
            self._seg_results[si] = result
            self._update_seg_status(si, "✓")
            self._result_box.configure(state="normal")
            self._result_box.insert("end", result)
            self._result_box.configure(state="disabled")
            self._result_box.see("end")
            if self._split_view:
                self._split_view.update_result(si, result)
                info, counter = self._split_view.get_info()
                self._split_info.configure(text=info)
                self._seg_counter.configure(text=counter)
            if getattr(self, "_result_view", "结果") == "对照":
                self._render_compare_view()
            self._animate_progress((si + 1) / len(self._segments))
        elif kind == "done":
            self._running = False
            self._set_params_enabled(True)
            self._start_btn.configure(text="▶ 开始翻译")
            self._animate_btn_color(self._start_btn, COLORS["accent"], COLORS["accent_hover"])
            elapsed = time.time() - self._start_time if hasattr(self, "_start_time") else 0
            time_str = f"{elapsed/60:.1f}分钟" if elapsed >= 60 else f"{elapsed:.1f}秒"
            self._status_label.configure(text=f"✓ 翻译完成 ({time_str})", text_color=COLORS["success"])
            self._step_label.configure(text="")
            self._animate_progress(1)
            self.title("生草机 — 翻译完成")
            result_text = self._result_box.get("1.0", "end-1c")
            if result_text and self._auto_copy_var.get():
                self.clipboard_clear()
                self.clipboard_append(result_text)
                self._show_toast(f"翻译完成 ({time_str})，结果已复制到剪贴板")
            else:
                self._show_toast(f"翻译完成 ({time_str})")
            self._add_history_entry(stopped=False, elapsed_str=time_str)
        elif kind == "aborted":
            self._running = False
            self._set_params_enabled(True)
            self._start_btn.configure(text="▶ 开始翻译")
            self._animate_btn_color(self._start_btn, COLORS["accent"], COLORS["accent_hover"])
            self._status_label.configure(text="⏹ 已停止", text_color=COLORS["text_secondary"])
            self.title("生草机")
            if self._seg_results:
                self._add_history_entry(stopped=True)
        elif kind == "error":
            self._running = False
            self._set_params_enabled(True)
            self._start_btn.configure(text="▶ 开始翻译")
            self._animate_btn_color(self._start_btn, COLORS["accent"], COLORS["accent_hover"])
            self._status_label.configure(text=f"✗ 错误: {msg[1]}", text_color=COLORS["error"])
            self.title("生草机 — 错误")

    def _update_card_state(self, si, state):
        if self._split_view:
            self._split_view.update_state(si, state)

    def _update_seg_status(self, si, symbol):
        if si < 0 or si >= len(self._segments):
            return
        if symbol == "●":
            state = "translating"
        elif symbol == "✓":
            state = "done"
        else:
            state = "waiting"
        self._seg_states[si] = state
        self._update_card_state(si, state)
        done = sum(1 for s in self._seg_states.values() if s == "done")
        total = len(self._segments)
        self._seg_counter.configure(text=f"{done} / {total}")

    def _auto_follow_seg(self, si):
        if not self._auto_follow_var.get():
            return
        if self._split_view:
            self._split_view.auto_follow(si)