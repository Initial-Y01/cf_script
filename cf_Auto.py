import threading
import time
import os
import cv2
import numpy as np
import pyautogui
import tkinter as tk
from tkinter import filedialog, messagebox, ttk
import json

# Windows 专用库
try:
    import win32api, win32con
except ImportError:
    win32api = None

# 全局热键库优先使用 pynput
try:
    from pynput import keyboard as kb
except ImportError:
    kb = None

TEMPLATE_DIR = 'templates'

class CFHackerGUI(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title("CF挂机助手")
        self.geometry("700x550")
        self.templates = {}
        self.running = False
        self.start_hotkey = tk.StringVar(value="<f6>")
        self.stop_hotkey = tk.StringVar(value="<f7>")
        self.worker_thread = None
        self.hotkey_listener = None
        self.is_topmost = tk.BooleanVar(value=False)

        if not os.path.exists(TEMPLATE_DIR):
            os.makedirs(TEMPLATE_DIR)

        self._build_ui()
        self._load_templates()
        self._start_hotkey_listener()

    def _build_ui(self):
        frame = ttk.Frame(self)
        frame.pack(fill=tk.X, padx=5, pady=5)

        ttk.Button(frame, text="添加模板", command=self.add_template).pack(side=tk.LEFT, padx=5)
        ttk.Button(frame, text="移除模板", command=self.remove_template).pack(side=tk.LEFT)
        ttk.Button(frame, text="刷新模板", command=self._load_templates).pack(side=tk.LEFT, padx=5)
        ttk.Checkbutton(frame, text="置顶窗口", variable=self.is_topmost, command=self.toggle_topmost).pack(side=tk.LEFT, padx=5)

        hot_frame = ttk.Frame(self)
        hot_frame.pack(fill=tk.X, padx=5, pady=5)
        ttk.Label(hot_frame, text="开始热键:").pack(side=tk.LEFT)
        ttk.Entry(hot_frame, textvariable=self.start_hotkey, width=15).pack(side=tk.LEFT, padx=5)
        ttk.Label(hot_frame, text="停止热键:").pack(side=tk.LEFT)
        ttk.Entry(hot_frame, textvariable=self.stop_hotkey, width=15).pack(side=tk.LEFT, padx=5)

        btn_frame = ttk.Frame(self)
        btn_frame.pack(fill=tk.X, padx=5, pady=5)
        ttk.Button(btn_frame, text="开始挂机", command=self.start).pack(side=tk.LEFT, padx=5)
        ttk.Button(btn_frame, text="停止挂机", command=self.stop).pack(side=tk.LEFT)

        self.listbox = tk.Listbox(self, height=6)
        self.listbox.pack(fill=tk.BOTH, padx=5, pady=5)

        self.log = tk.Text(self, height=10)
        self.log.pack(fill=tk.BOTH, padx=5, pady=5)
        self.log.insert(tk.END, "日志信息...\n")
        self.log.configure(state=tk.DISABLED)

    def toggle_topmost(self):
        self.attributes('-topmost', self.is_topmost.get())

    def log_message(self, msg):
        self.log.configure(state=tk.NORMAL)
        self.log.insert(tk.END, f"{time.strftime('%H:%M:%S')} - {msg}\n")
        self.log.configure(state=tk.DISABLED)
        self.log.see(tk.END)

    def _load_templates(self):
        self.templates.clear()
        self.listbox.delete(0, tk.END)
        for filename in os.listdir(TEMPLATE_DIR):
            path = os.path.join(TEMPLATE_DIR, filename)
            if os.path.isfile(path) and path.lower().endswith(('.png','.jpg','.bmp')):
                tpl = cv2.imread(path, cv2.IMREAD_GRAYSCALE)
                if tpl is not None:
                    self.templates[path] = tpl
                    self.listbox.insert(tk.END, os.path.basename(path))

    def add_template(self):
        path = filedialog.askopenfilename(title='选择模板', filetypes=[('图片文件','*.png;*.jpg;*.bmp')])
        if not path:
            return
        tpl = cv2.imread(path, cv2.IMREAD_GRAYSCALE)
        if tpl is None:
            messagebox.showerror('错误','无法读取图像')
            return
        dst_path = os.path.join(TEMPLATE_DIR, os.path.basename(path))
        if not os.path.exists(dst_path):
            cv2.imwrite(dst_path, tpl)
        self._load_templates()
        self.log_message(f"添加模板: {os.path.basename(path)}")

    def remove_template(self):
        sel = self.listbox.curselection()
        if not sel:
            return
        name = self.listbox.get(sel[0])
        path = os.path.join(TEMPLATE_DIR, name)
        if os.path.exists(path):
            os.remove(path)
        self._load_templates()
        self.log_message(f"移除模板: {name}")

    def _start_hotkey_listener(self):
        if kb:
            hk = {self.start_hotkey.get(): self.start, self.stop_hotkey.get(): self.stop}
            self.hotkey_listener = kb.GlobalHotKeys(hk)
            self.hotkey_listener.start()
            self.log_message(f"注册全局热键 via pynput: {hk}")
        else:
            self.log_message('未安装 pynput，热键不可用')

    def click_at(self, x, y):
        if win32api:
            try:
                win32api.SetCursorPos((int(x), int(y)))
                time.sleep(0.05)
                win32api.mouse_event(win32con.MOUSEEVENTF_LEFTDOWN,0,0,0,0)
                time.sleep(0.05)
                win32api.mouse_event(win32con.MOUSEEVENTF_LEFTUP,0,0,0,0)
                return
            except Exception as e:
                self.log_message(f"win32 点击失败，回退到 pyautogui: {e}")
        pyautogui.moveTo(x, y)
        time.sleep(0.1)
        pyautogui.click()

    def start(self):
        if self.running:
            return
        if not self.templates:
            messagebox.showwarning('警告','请先添加模板')
            return
        self.running = True
        self.worker_thread = threading.Thread(target=self._loop, daemon=True)
        self.worker_thread.start()
        self.log_message('挂机开始')

    def stop(self):
        if not self.running:
            return
        self.running = False
        if self.worker_thread:
            self.worker_thread.join(timeout=2)
        self.log_message('挂机停止')

    def _loop(self):
        while self.running:
            screenshot = pyautogui.screenshot()
            screen = cv2.cvtColor(np.array(screenshot), cv2.COLOR_RGB2GRAY)
            for path, tpl in self.templates.items():
                res = cv2.matchTemplate(screen, tpl, cv2.TM_CCOEFF_NORMED)
                _, max_val, _, max_loc = cv2.minMaxLoc(res)
                if max_val >= 0.8:
                    th, tw = tpl.shape
                    x = max_loc[0] + tw // 2
                    y = max_loc[1] + th // 2
                    self.click_at(x, y)
                    self.log_message(f"点击 {os.path.basename(path)} @({x},{y}) conf={max_val:.2f}")
                    time.sleep(0.5)
            time.sleep(1.0)

if __name__ == '__main__':
    app = CFHackerGUI()
    app.mainloop()
