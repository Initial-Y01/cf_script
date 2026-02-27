# -*- coding: utf-8 -*-
import subprocess
import threading
import win32api
import win32con
import time
import os
import sys
import shutil
import cv2
import numpy as np
import pyautogui
import tkinter as tk
from tkinter import filedialog, messagebox, ttk
import ctypes


# 全局热键库优先使用 pynput
try:
    from pynput import keyboard as kb

except ImportError:
    kb = None
    print("警告: 未找到 pynput 库，全局热键功能不可用。")


# 隐藏控制台窗口
def hide_console():
    try:
        # 获取当前控制台窗口
        hwnd = ctypes.windll.kernel32.GetConsoleWindow()
        if hwnd:
            # 隐藏窗口
            ctypes.windll.user32.ShowWindow(hwnd, 0)  # 0 = SW_HIDE
            # 确保窗口不会被激活
            ctypes.windll.user32.SetWindowPos(hwnd, 0, 0, 0, 0, 0, 0x0001)
    except Exception as e:
        print(f"隐藏控制台窗口失败: {e}")


# 检查并提升到管理员权限
def is_admin():
    try:
        return ctypes.windll.shell32.IsUserAnAdmin()
    except:
        return False


# 提升权限
def run_as_admin():
    try:
        # 获取当前程序路径
        current_exe = sys.executable

        # 获取当前工作目录
        current_dir = os.path.dirname(current_exe)

        # 以管理员权限重新启动程序，指定工作目录为EXE所在目录，并隐藏窗口
        ctypes.windll.shell32.ShellExecuteW(None, "runas", current_exe, " ".join(sys.argv), current_dir, 0)  # 使用0隐藏窗口
        return True
    except Exception as e:
        print(f"提升权限失败: {e}")
        return False


# 获取程序运行目录（兼容EXE和Python脚本）
def get_app_dir():
    try:
        if getattr(sys, "frozen", False):
            # 打包成EXE后的情况，返回EXE所在目录
            return os.path.dirname(sys.executable)
        else:
            # Python脚本的情况，返回脚本所在目录
            return os.path.dirname(os.path.abspath(__file__))
    except Exception as e:
        # 兜底方案，使用当前工作目录
        print(f"获取程序目录失败: {e}")
        return os.getcwd()


# 如果不是管理员，重新启动程序提升权限
if not is_admin():
    # 尝试提升权限
    if run_as_admin():
        # 如果提升权限成功，退出当前实例
        sys.exit()
    else:
        # 如果提升权限失败，显示错误信息并退出
        try:
            import tkinter.messagebox

            root = tk.Tk()
            root.withdraw()  # 隐藏主窗口
            tkinter.messagebox.showerror("错误", "需要管理员权限才能运行此程序！")
        except:
            print("需要管理员权限才能运行此程序！")
        sys.exit()

# 设置模板文件夹路径，确保在EXE环境中正确
APP_DIR = get_app_dir()

# 确保工作目录正确
os.chdir(APP_DIR)

# 使用绝对路径定义模板目录
TEMPLATE_DIR = os.path.join(APP_DIR, "templates")

# 确保模板文件夹存在
print(f"当前工作目录: {os.getcwd()}")
print(f"程序目录: {APP_DIR}")
print(f"模板目录: {TEMPLATE_DIR}")

try:
    os.makedirs(TEMPLATE_DIR, exist_ok=True)
    print(f"模板文件夹已准备好")
except Exception as e:
    print(f"创建模板文件夹失败: {e}")


class CFAotuGUI(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title("CF挂机助手，用爱发电，盗卖狗清户口本 修改自Github Initial-Y01 By Muou 2026-02-11")
        self.geometry("1500x1000")
        self.templates = {}
        self.running = False
        self.start_hotkey = tk.StringVar(value="<f11>")
        self.stop_hotkey = tk.StringVar(value="<f12>")
        self.worker_thread = None
        self.hotkey_listener = None
        self.is_topmost = tk.BooleanVar(value=False)
        self.last_action_time = time.time()
        self.idle_threshold = 15 * 60
        self.emergency_enabled = tk.BooleanVar(value=True)
        self.idle_threshold_minutes = tk.StringVar(value="0.3")
        self.log_enabled = tk.BooleanVar(value=True)
        # 倒计时关机功能
        self.shutdown_enabled = tk.BooleanVar(value=False)
        self.shutdown_hours = tk.StringVar(value="0")
        self.shutdown_minutes = tk.StringVar(value="30")
        self.shutdown_timer = None
        self.shutdown_remaining = 0

        # 设置现代主题
        self._setup_theme()

        self._build_ui()
        self._load_templates()
        self._start_hotkey_listener()

    def _build_ui(self):
        # 主容器
        main_frame = ttk.Frame(self, padding=20)
        main_frame.pack(fill=tk.BOTH, expand=True)

        # 标题区域
        title_frame = ttk.Frame(main_frame)
        title_frame.pack(fill=tk.X, pady=(0, 20))
        try:
            ttk.Label(title_frame, text="CF挂机助手", font=("Microsoft YaHei", 18, "bold"), foreground="#1a73e8").pack(side=tk.LEFT)
        except:
            # 如果字体设置失败，使用默认字体
            ttk.Label(title_frame, text="CF挂机助手", foreground="#1a73e8").pack(side=tk.LEFT)

        # 内容区域
        content_frame = ttk.Frame(main_frame)
        content_frame.pack(fill=tk.BOTH, expand=True)

        # 左侧区域
        left_frame = ttk.Frame(content_frame)
        left_frame.pack(side=tk.LEFT, fill=tk.BOTH, expand=True, padx=(0, 10))

        # 模板管理区域
        template_frame = ttk.LabelFrame(left_frame, text="模板管理", padding=15)
        template_frame.pack(fill=tk.BOTH, expand=True, pady=(0, 15))

        template_btn_frame = ttk.Frame(template_frame)
        template_btn_frame.pack(fill=tk.X, pady=(0, 10))
        ttk.Button(template_btn_frame, text="添加模板", command=self.add_template).pack(side=tk.LEFT, padx=5)
        ttk.Button(template_btn_frame, text="移除模板", command=self.remove_template).pack(side=tk.LEFT, padx=5)
        ttk.Button(template_btn_frame, text="刷新模板", command=self._load_templates).pack(side=tk.LEFT, padx=5)
        ttk.Checkbutton(template_btn_frame, text="置顶窗口", variable=self.is_topmost, command=self.toggle_topmost).pack(side=tk.RIGHT)

        # 模板列表
        self.listbox = tk.Listbox(template_frame, height=8, relief="solid", borderwidth=1, bg="white")
        self.listbox.pack(fill=tk.BOTH, expand=True)

        # 右侧区域
        right_frame = ttk.Frame(content_frame)
        right_frame.pack(side=tk.RIGHT, fill=tk.BOTH, expand=True, padx=(10, 0))

        # 热键设置区域
        hotkey_frame = ttk.LabelFrame(right_frame, text="热键设置", padding=15)
        hotkey_frame.pack(fill=tk.X, pady=(0, 15))

        hot_frame = ttk.Frame(hotkey_frame)
        hot_frame.pack(fill=tk.X)
        ttk.Label(hot_frame, text="开始热键:").pack(side=tk.LEFT, padx=(0, 10), anchor=tk.CENTER)
        ttk.Entry(hot_frame, textvariable=self.start_hotkey, width=15).pack(side=tk.LEFT, padx=10)
        ttk.Label(hot_frame, text="停止热键:").pack(side=tk.LEFT, padx=(0, 10), anchor=tk.CENTER)
        ttk.Entry(hot_frame, textvariable=self.stop_hotkey, width=15).pack(side=tk.LEFT, padx=10)

        # 控制按钮区域
        control_frame = ttk.LabelFrame(right_frame, text="控制", padding=15)
        control_frame.pack(fill=tk.X, pady=(0, 15))

        btn_frame = ttk.Frame(control_frame)
        btn_frame.pack(fill=tk.X)
        ttk.Button(btn_frame, text="开始挂机", command=self.start).pack(side=tk.LEFT, padx=5, fill=tk.X, expand=True)
        ttk.Button(btn_frame, text="停止挂机", command=self.stop).pack(side=tk.LEFT, padx=5, fill=tk.X, expand=True)

        # 高级设置区域
        setting_frame = ttk.LabelFrame(right_frame, text="高级设置", padding=15)
        setting_frame.pack(fill=tk.X, pady=(0, 15))

        # 反挂机设置
        emergency_frame = ttk.Frame(setting_frame)
        emergency_frame.pack(fill=tk.X, pady=(0, 10))
        ttk.Checkbutton(emergency_frame, text="启用反挂机检测动作", variable=self.emergency_enabled).pack(side=tk.LEFT, padx=5, anchor=tk.W)
        ttk.Label(emergency_frame, text="空闲阈值(分钟):").pack(side=tk.LEFT, padx=(20, 10), anchor=tk.W)
        ttk.Entry(emergency_frame, textvariable=self.idle_threshold_minutes, width=5).pack(side=tk.LEFT)
        ttk.Checkbutton(emergency_frame, text="启用日志输出", variable=self.log_enabled).pack(side=tk.RIGHT, anchor=tk.W)

        # 倒计时关机功能
        shutdown_frame = ttk.Frame(setting_frame)
        shutdown_frame.pack(fill=tk.X)
        ttk.Checkbutton(shutdown_frame, text="启用倒计时关机", variable=self.shutdown_enabled, command=self.toggle_shutdown).pack(side=tk.LEFT, padx=5, anchor=tk.W)
        ttk.Label(shutdown_frame, text="关机时间(小时:分钟):").pack(side=tk.LEFT, padx=(20, 10), anchor=tk.W)
        ttk.Entry(shutdown_frame, textvariable=self.shutdown_hours, width=3).pack(side=tk.LEFT)
        ttk.Label(shutdown_frame, text=":").pack(side=tk.LEFT, padx=5, anchor=tk.CENTER)
        ttk.Entry(shutdown_frame, textvariable=self.shutdown_minutes, width=3).pack(side=tk.LEFT)
        self.shutdown_label = ttk.Label(shutdown_frame, text="剩余时间: 00:00:00", font=("Microsoft YaHei", 10, "bold"))
        self.shutdown_label.pack(side=tk.RIGHT, anchor=tk.W)

        # 日志区域（底部）
        log_frame = ttk.LabelFrame(main_frame, text="日志", padding=15)
        log_frame.pack(fill=tk.BOTH, expand=True, pady=(20, 0))

        try:
            self.log = tk.Text(log_frame, height=10, relief="solid", borderwidth=1, font=("Microsoft YaHei", 10), bg="white")
        except:
            # 如果字体设置失败，使用默认字体
            self.log = tk.Text(log_frame, height=10, relief="solid", borderwidth=1, bg="white")
        self.log.pack(fill=tk.BOTH, expand=True)
        self.log.insert(tk.END, "日志信息...\n")
        self.log.configure(state=tk.DISABLED)

    def _setup_theme(self):
        """设置现代主题"""
        # 设置窗口图标（如果有的话）
        # 可以在这里添加窗口图标设置

        # 设置窗口背景色
        self.configure(bg="white")

        # 设置字体
        try:
            # 尝试设置字体
            self.option_add("*Font", ("Microsoft YaHei", 11))
        except:
            # 如果失败，使用默认字体
            pass

        # 设置按钮样式
        style = ttk.Style()
        try:
            # 尝试使用现代主题
            style.theme_use("clam")

            # 配置样式
            style.configure("TButton", padding=10, relief="flat", background="#1a73e8", foreground="white", font=("Microsoft YaHei", 11, "normal"), borderwidth=0, borderradius=6)
            style.map("TButton", background=[("active", "#1557b0")], foreground=[("active", "white")])

            # 配置标签样式
            style.configure("TLabel", background="white", foreground="#333333", font=("Microsoft YaHei", 11, "normal"))

            # 配置输入框样式
            style.configure("TEntry", padding=8, relief="solid", borderwidth=1, font=("Microsoft YaHei", 11, "normal"), fieldbackground="white", foreground="#333333", borderradius=4)

            # 配置复选框样式
            style.configure("TCheckbutton", background="white", foreground="#333333", font=("Microsoft YaHei", 11, "normal"))

            # 配置标签框架样式
            try:
                style.configure("TLabelframe", background="white", foreground="#1a73e8", font=("Microsoft YaHei", 11, "bold"))
                style.configure("TLabelframe.Label", background="white", foreground="#1a73e8", font=("Microsoft YaHei", 11, "bold"))
            except:
                pass

            # 配置框架样式
            try:
                style.configure("TFrame", background="white")
            except:
                pass
        except:
            # 如果主题不可用，使用默认主题
            pass

    def toggle_topmost(self):
        self.attributes("-topmost", self.is_topmost.get())

    def log_message(self, msg):
        if not self.log_enabled.get():
            return
        self.after(0, self._update_log, msg)

    def _update_log(self, msg):
        self.log.configure(state=tk.NORMAL)
        self.log.insert(tk.END, f"{time.strftime('%H:%M:%S')} - {msg}\n")
        self.log.configure(state=tk.DISABLED)
        self.log.see(tk.END)

    def _load_templates(self):
        self.templates.clear()
        self.listbox.delete(0, tk.END)

        # 确保模板目录存在
        if not os.path.exists(TEMPLATE_DIR):
            self.log_message(f"模板目录不存在: {TEMPLATE_DIR}")
            try:
                os.makedirs(TEMPLATE_DIR, exist_ok=True)
                self.log_message(f"已创建模板目录: {TEMPLATE_DIR}")
            except Exception as e:
                self.log_message(f"创建模板目录失败: {e}")
                return

        try:
            files = os.listdir(TEMPLATE_DIR)
            self.log_message(f"模板目录文件列表: {files}")

            for filename in files:
                path = os.path.join(TEMPLATE_DIR, filename)
                if os.path.isfile(path):
                    # 检查文件扩展名
                    ext = os.path.splitext(filename)[1].lower()
                    if ext in [".png", ".jpg", ".bmp"]:
                        try:
                            self.log_message(f"尝试加载模板: {path}")
                            # 使用numpy和cv2.imdecode处理中文路径
                            with open(path, "rb") as f:
                                img_data = np.frombuffer(f.read(), np.uint8)
                            tpl = cv2.imdecode(img_data, cv2.IMREAD_GRAYSCALE)
                            if tpl is not None:
                                self.templates[path] = tpl
                                self.listbox.insert(tk.END, filename)
                                self.log_message(f"成功加载模板: {filename}")
                            else:
                                self.log_message(f"无法读取模板: {filename}")
                        except Exception as e:
                            self.log_message(f"加载模板失败 {filename}: {e}")
                    else:
                        self.log_message(f"跳过非图片文件: {filename}")
        except Exception as e:
            self.log_message(f"读取模板目录失败: {e}")

    def add_template(self):
        path = filedialog.askopenfilename(title="选择模板", filetypes=[("图片文件", "*.png;*.jpg;*.bmp")])
        if not path:
            return
        try:
            # 确保模板目录存在
            if not os.path.exists(TEMPLATE_DIR):
                os.makedirs(TEMPLATE_DIR, exist_ok=True)
                self.log_message(f"创建模板目录: {TEMPLATE_DIR}")

            # 读取源文件
            with open(path, "rb") as f:
                tpl_data = np.frombuffer(f.read(), np.uint8)
            tpl = cv2.imdecode(tpl_data, cv2.IMREAD_GRAYSCALE)

            if tpl is None:
                messagebox.showerror("错误", "无法读取图像")
                return

            # 构建目标路径
            filename = os.path.basename(path)
            dst_path = os.path.join(TEMPLATE_DIR, filename)

            self.log_message(f"尝试保存模板到: {dst_path}")

            # 保存模板文件
            if not os.path.exists(dst_path):
                # 使用更可靠的文件复制方式
                shutil.copy2(path, dst_path)
                self.log_message(f"成功保存模板到: {dst_path}")
            else:
                self.log_message(f"模板已存在: {dst_path}")

            # 重新加载模板
            self._load_templates()
            self.log_message(f"添加模板: {filename}")

        except Exception as e:
            self.log_message(f"添加模板失败: {e}")
            messagebox.showerror("错误", f"添加模板失败: {e}")

    def remove_template(self):
        sel = self.listbox.curselection()
        if not sel:
            return
        name = self.listbox.get(sel[0])
        path = os.path.join(TEMPLATE_DIR, name)
        self.log_message(f"尝试移除模板: {path}")
        if os.path.exists(path):
            try:
                os.remove(path)
                self.log_message(f"成功移除模板: {name}")
            except Exception as e:
                self.log_message(f"移除模板失败: {e}")
                messagebox.showerror("错误", f"移除模板失败: {e}")
        else:
            self.log_message(f"模板不存在: {path}")
        self._load_templates()

    def _start_hotkey_listener(self):
        if kb:
            try:
                # 先停止之前的热键监听器
                if self.hotkey_listener:
                    self.hotkey_listener.stop()
                    time.sleep(0.1)

                hk = {self.start_hotkey.get(): self.start, self.stop_hotkey.get(): self.stop}
                self.hotkey_listener = kb.GlobalHotKeys(hk)
                self.hotkey_listener.start()
                # 隐藏热键注册日志
                # self.log_message(f"注册全局热键 via pynput: {hk}")
            except Exception as e:
                self.log_message(f"注册热键失败: {e}")
        else:
            self.log_message("未安装 pynput，热键不可用")

    def click_at(self, x, y):
        try:
            int_x, int_y = int(x), int(y)
            # 使用win32api进行精确的鼠标点击，提高游戏内识别率
            win32api.SetCursorPos((int_x, int_y))
            time.sleep(0.03)  # Delay for cursor to settle
            win32api.mouse_event(win32con.MOUSEEVENTF_LEFTDOWN, 0, 0, 0, 0)
            time.sleep(0.05)  # Delay between down and up events
            win32api.mouse_event(win32con.MOUSEEVENTF_LEFTUP, 0, 0, 0, 0)
            time.sleep(0.03)  # Delay after click to ensure it's processed
        except Exception as e:
            self.log_message(f"点击 @({int_x},{int_y}) 时发生错误: {e}")

    def perform_emergency_action(self):
        """执行反挂机检测动作，模拟真实玩家行为"""
        try:
            if win32api:
                # 检查是否有管理员权限
                is_admin = ctypes.windll.shell32.IsUserAnAdmin() != 0
                if not is_admin:
                    self.log_message("警告: 无管理员权限，反挂机动作可能无法在游戏内生效")

                # 使用win32api模拟更复杂的玩家行为，提高游戏内识别率
                self.log_message("执行高级反挂机动作")

                # 只短按左键，随机次数，不移动鼠标
                click_count = np.random.randint(1, 5)  # 随机点击次数 1-4次
                for _ in range(click_count):
                    # 短按左键，使用不同的参数组合，减少被检测的可能性
                    win32api.mouse_event(win32con.MOUSEEVENTF_LEFTDOWN | win32con.MOUSEEVENTF_ABSOLUTE, 0, 0, np.random.randint(1, 10), np.random.randint(1, 10))
                    # 随机按下时长
                    press_duration = np.random.uniform(0.05, 0.2)  # 随机按下时长 0.05-0.2秒
                    time.sleep(press_duration)
                    win32api.mouse_event(win32con.MOUSEEVENTF_LEFTUP | win32con.MOUSEEVENTF_ABSOLUTE, 0, 0, np.random.randint(1, 10), np.random.randint(1, 10))
                    # 随机间隔
                    interval = np.random.uniform(0.1, 0.5)  # 随机间隔 0.1-0.5秒
                    time.sleep(interval)

                # 模拟按键操作
                # 随机按WASD中的一个键
                keys = [0x57, 0x41, 0x53, 0x44]  # W, A, S, D
                random_key = np.random.choice(keys)
                # 使用不同的参数组合，减少被检测的可能性
                win32api.keybd_event(random_key, win32api.MapVirtualKey(random_key, 0), 0, 0)
                # 随机按键时长
                key_duration = np.random.uniform(0.1, 0.5)  # 随机按键时长 0.1-0.5秒
                time.sleep(key_duration)
                win32api.keybd_event(random_key, win32api.MapVirtualKey(random_key, 0), win32con.KEYEVENTF_KEYUP, 0)

        except Exception as e:
            self.log_message(f"反挂机动作执行失败: {e}")

    def start(self):
        if self.running:
            return
        if not self.templates:
            messagebox.showwarning("警告", "请先添加模板")
            return
        try:
            self.idle_threshold = int(float(self.idle_threshold_minutes.get()) * 60)
        except ValueError:
            self.idle_threshold = 18  # 默认0.3分钟
            self.idle_threshold_minutes.set("0.3")
            self.log_message("无效的空闲阈值，已重置为0.3分钟")

        # 重新注册热键，确保使用最新设置
        self._start_hotkey_listener()

        self.running = True
        self.last_action_time = time.time()
        self.worker_thread = threading.Thread(target=self._loop, daemon=True)
        self.worker_thread.start()
        self.log_message("挂机开始")

    def stop(self):
        if not self.running:
            return
        self.running = False
        if self.worker_thread and self.worker_thread.is_alive():
            self.worker_thread.join(timeout=2)
        self.log_message("挂机停止")

    def toggle_shutdown(self):
        """切换倒计时关机功能"""
        if self.shutdown_enabled.get():
            self.start_shutdown_timer()
        else:
            self.stop_shutdown_timer()

    def start_shutdown_timer(self):
        """启动倒计时关机定时器"""
        try:
            # 停止之前的定时器
            self.stop_shutdown_timer()

            # 获取关机时间
            hours = int(float(self.shutdown_hours.get()))
            minutes = int(float(self.shutdown_minutes.get()))
            self.shutdown_remaining = hours * 3600 + minutes * 60

            # 更新显示
            self.update_shutdown_display()

            # 启动定时器
            self.shutdown_timer = self.after(1000, self.update_shutdown_timer)
            self.log_message(f"启动倒计时关机，将在{hours}小时{minutes}分钟后关机")
        except ValueError:
            self.log_message("无效的关机时间")
            self.shutdown_enabled.set(False)

    def stop_shutdown_timer(self):
        """停止倒计时关机定时器"""
        if self.shutdown_timer:
            self.after_cancel(self.shutdown_timer)
            self.shutdown_timer = None
        self.shutdown_remaining = 0
        self.update_shutdown_display()
        self.log_message("取消倒计时关机")

    def update_shutdown_timer(self):
        """更新倒计时关机定时器"""
        if not self.shutdown_enabled.get():
            return

        self.shutdown_remaining -= 1
        self.update_shutdown_display()

        if self.shutdown_remaining <= 0:
            # 执行关机
            self.log_message("执行关机操作")
            try:
                subprocess.run(["shutdown", "/s", "/t", "0"], check=True)
            except Exception as e:
                self.log_message(f"关机失败: {e}")
            return

        # 继续定时
        self.shutdown_timer = self.after(1000, self.update_shutdown_timer)

    def update_shutdown_display(self):
        """更新倒计时关机显示"""
        hours = self.shutdown_remaining // 3600
        minutes = (self.shutdown_remaining % 3600) // 60
        seconds = self.shutdown_remaining % 60
        self.shutdown_label.config(text=f"剩余时间: {hours:02d}:{minutes:02d}:{seconds:02d}")

    def _loop(self):  # 识别匹配点击
        while self.running:
            try:
                screenshot = pyautogui.screenshot()
                screen = cv2.cvtColor(np.array(screenshot), cv2.COLOR_RGB2GRAY)
                found_in_cycle = False
                matched_targets = []
                for path, tpl in self.templates.items():
                    # 多尺度模板匹配，支持多种分辨率
                    found = False
                    # 尝试不同的缩放比例
                    for scale in [0.5, 0.75, 1.0, 1.25, 1.5]:
                        if not self.running:
                            break
                        # 缩放模板
                        resized_tpl = cv2.resize(tpl, (0, 0), fx=scale, fy=scale)
                        # 确保缩放后的模板大小小于屏幕大小
                        if resized_tpl.shape[0] > screen.shape[0] or resized_tpl.shape[1] > screen.shape[1]:
                            continue
                        # 模板匹配
                        res = cv2.matchTemplate(screen, resized_tpl, cv2.TM_CCOEFF_NORMED)
                        _, max_val, _, max_loc = cv2.minMaxLoc(res)
                        if max_val >= 0.8:
                            th, tw = resized_tpl.shape
                            x = max_loc[0] + tw / 2
                            y = max_loc[1] + th / 2
                            matched_targets.append((path, x, y, max_val))
                            found = True
                            break
                    if found:
                        continue

                # 实现列表循环点击，避免遮挡
                # 按照y坐标排序，从上到下点击，避免下方模板被上方模板遮挡
                matched_targets.sort(key=lambda item: item[2])  # 按y坐标排序

                for path, x, y, conf in matched_targets:
                    if not self.running:
                        break
                    self.log_message(f"点击 {os.path.basename(path)} @({int(x)},{int(y)}) conf={conf:.2f}")
                    self.click_at(x, y)
                    self.last_action_time = time.time()
                    # 随机间隔，避免机械点击
                    click_interval = np.random.uniform(0.3, 0.8)  # 随机间隔 0.3-0.8秒
                    time.sleep(click_interval)
                    found_in_cycle = True

                if not self.running:
                    break

                if not found_in_cycle and self.emergency_enabled.get():  # 反挂机检测
                    if time.time() - self.last_action_time > self.idle_threshold:
                        self.perform_emergency_action()
                        self.last_action_time = time.time()
                        self.log_message("长时间未检测到模板，触发反挂机检测动作")
                time.sleep(1.0)

            except Exception as e:
                self.log_message(f"循环中发生错误: {e}")
                # 发生错误时也更新最后操作时间，避免频繁触发反挂机动作
                self.last_action_time = time.time()
                time.sleep(5)


if __name__ == "__main__":
    # 简化启动流程，确保EXE环境稳定
    try:
        print("程序开始启动...")

        # 确保工作目录正确
        app_dir = get_app_dir()
        print(f"程序目录: {app_dir}")
        os.chdir(app_dir)
        print(f"当前工作目录: {os.getcwd()}")

        # 确保模板文件夹存在
        print(f"模板目录: {TEMPLATE_DIR}")
        os.makedirs(TEMPLATE_DIR, exist_ok=True)
        print("模板目录已准备好")

        # 隐藏控制台窗口
        hide_console()

        # 启动GUI
        print("准备启动GUI...")
        app = CFAotuGUI()
        print("GUI启动成功")
        app.mainloop()
    except Exception as e:
        # 显示错误信息
        print(f"程序启动失败: {e}")
        try:
            # 记录错误到文件
            with open(os.path.join(APP_DIR, "error.log"), "a", encoding="utf-8") as f:
                f.write(f"{time.strftime('%Y-%m-%d %H:%M:%S')} - 程序启动失败: {e}\n")
        except:
            pass
        sys.exit(1)
