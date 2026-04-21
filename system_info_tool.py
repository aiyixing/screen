#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
系统信息工具 - 显示鼠标坐标、窗口信息、像素颜色、截屏功能
"""

import sys
import time
import threading
import tkinter as tk
from tkinter import ttk
from datetime import datetime

try:
    import win32api
    import win32gui
    import win32con
    HAS_WIN32 = True
except ImportError:
    HAS_WIN32 = False
    print("警告: 未安装 pywin32，请运行: pip install pywin32")

try:
    from PIL import Image, ImageGrab, ImageTk
    HAS_PIL = True
except ImportError:
    HAS_PIL = False
    print("警告: 未安装 Pillow，请运行: pip install Pillow")

try:
    import pyperclip
    HAS_PYPERCLIP = True
except ImportError:
    HAS_PYPERCLIP = False
    print("警告: 未安装 pyperclip，请运行: pip install pyperclip")


class SystemInfoTool:
    def __init__(self):
        self.root = tk.Tk()
        self.root.title("系统信息工具")
        self.root.geometry("400x350")
        self.root.resizable(False, False)
        self.root.attributes("-topmost", True)
        
        self.running = True
        self.current_screenshot = None
        
        self._setup_ui()
        self._start_update_thread()
        
    def _setup_ui(self):
        main_frame = ttk.Frame(self.root, padding="10")
        main_frame.pack(fill=tk.BOTH, expand=True)
        
        info_frame = ttk.LabelFrame(main_frame, text="系统信息", padding="10")
        info_frame.pack(fill=tk.X, pady=5)
        
        ttk.Label(info_frame, text="鼠标绝对坐标:", font=("Arial", 10, "bold")).grid(row=0, column=0, sticky=tk.W)
        self.lbl_mouse_abs = ttk.Label(info_frame, text="X: 0, Y: 0", foreground="blue")
        self.lbl_mouse_abs.grid(row=0, column=1, sticky=tk.W, padx=5)
        
        ttk.Label(info_frame, text="鼠标相对坐标:", font=("Arial", 10, "bold")).grid(row=1, column=0, sticky=tk.W)
        self.lbl_mouse_rel = ttk.Label(info_frame, text="X: 0, Y: 0", foreground="green")
        self.lbl_mouse_rel.grid(row=1, column=1, sticky=tk.W, padx=5)
        
        ttk.Label(info_frame, text="活动窗口尺寸:", font=("Arial", 10, "bold")).grid(row=2, column=0, sticky=tk.W)
        self.lbl_window_size = ttk.Label(info_frame, text="宽: 0, 高: 0", foreground="purple")
        self.lbl_window_size.grid(row=2, column=1, sticky=tk.W, padx=5)
        
        ttk.Label(info_frame, text="活动窗口标题:", font=("Arial", 10, "bold")).grid(row=3, column=0, sticky=tk.W)
        self.lbl_window_title = ttk.Label(info_frame, text="无", foreground="orange", width=25)
        self.lbl_window_title.grid(row=3, column=1, sticky=tk.W, padx=5)
        
        color_frame = ttk.LabelFrame(main_frame, text="像素颜色信息", padding="10")
        color_frame.pack(fill=tk.X, pady=5)
        
        ttk.Label(color_frame, text="像素颜色(RGB):", font=("Arial", 10, "bold")).grid(row=0, column=0, sticky=tk.W)
        self.lbl_pixel_color = ttk.Label(color_frame, text="R: 0, G: 0, B: 0", foreground="red")
        self.lbl_pixel_color.grid(row=0, column=1, sticky=tk.W, padx=5)
        
        ttk.Label(color_frame, text="十六进制:", font=("Arial", 10, "bold")).grid(row=1, column=0, sticky=tk.W)
        self.lbl_hex_color = ttk.Label(color_frame, text="#000000", foreground="darkred")
        self.lbl_hex_color.grid(row=1, column=1, sticky=tk.W, padx=5)
        
        self.color_preview = tk.Canvas(color_frame, width=50, height=50, bg="white", relief=tk.SUNKEN)
        self.color_preview.grid(row=0, column=2, rowspan=2, padx=10)
        
        button_frame = ttk.Frame(main_frame)
        button_frame.pack(fill=tk.X, pady=10)
        
        self.btn_screenshot = ttk.Button(button_frame, text="截屏并复制到剪贴板", command=self._take_screenshot)
        self.btn_screenshot.pack(side=tk.LEFT, padx=5)
        
        self.btn_copy_color = ttk.Button(button_frame, text="复制颜色值", command=self._copy_color)
        self.btn_copy_color.pack(side=tk.LEFT, padx=5)
        
        self.status_var = tk.StringVar(value="就绪")
        status_bar = ttk.Label(self.root, textvariable=self.status_var, relief=tk.SUNKEN, anchor=tk.W)
        status_bar.pack(side=tk.BOTTOM, fill=tk.X)
        
    def _get_mouse_position(self):
        if not HAS_WIN32:
            return (0, 0)
        try:
            x, y = win32api.GetCursorPos()
            return (x, y)
        except:
            return (0, 0)
    
    def _get_active_window(self):
        if not HAS_WIN32:
            return (None, 0, 0, 0, 0)
        try:
            hwnd = win32gui.GetForegroundWindow()
            if hwnd == 0:
                return (None, 0, 0, 0, 0)
            
            rect = win32gui.GetWindowRect(hwnd)
            left, top, right, bottom = rect
            width = right - left
            height = bottom - top
            
            try:
                title = win32gui.GetWindowText(hwnd)
            except:
                title = "未知"
            
            return (hwnd, left, top, width, height, title)
        except:
            return (None, 0, 0, 0, 0, "")
    
    def _get_pixel_color(self, x, y):
        if not HAS_WIN32 or not HAS_PIL:
            return (0, 0, 0)
        try:
            screenshot = ImageGrab.grab(bbox=(x, y, x + 1, y + 1))
            if screenshot:
                rgb = screenshot.getpixel((0, 0))
                screenshot.close()
                return rgb
            return (0, 0, 0)
        except:
            return (0, 0, 0)
    
    def _update_info(self):
        while self.running:
            try:
                mouse_x, mouse_y = self._get_mouse_position()
                window_info = self._get_active_window()
                
                hwnd, win_left, win_top, win_width, win_height, win_title = window_info
                
                rel_x = mouse_x - win_left
                rel_y = mouse_y - win_top
                
                if rel_x < 0 or rel_x >= win_width or rel_y < 0 or rel_y >= win_height:
                    rel_x = 0
                    rel_y = 0
                
                pixel_color = self._get_pixel_color(mouse_x, mouse_y)
                r, g, b = pixel_color
                hex_color = f"#{r:02X}{g:02X}{b:02X}"
                
                self.root.after(0, lambda: self._update_ui(
                    mouse_x, mouse_y,
                    rel_x, rel_y,
                    win_width, win_height,
                    win_title,
                    r, g, b, hex_color
                ))
                
                time.sleep(0.05)
            except:
                time.sleep(0.1)
    
    def _update_ui(self, mx, my, rx, ry, ww, wh, wt, r, g, b, hc):
        try:
            self.lbl_mouse_abs.config(text=f"X: {mx}, Y: {my}")
            self.lbl_mouse_rel.config(text=f"X: {rx}, Y: {ry}")
            self.lbl_window_size.config(text=f"宽: {ww}, 高: {wh}")
            self.lbl_window_title.config(text=wt if wt else "无标题")
            self.lbl_pixel_color.config(text=f"R: {r}, G: {g}, B: {b}")
            self.lbl_hex_color.config(text=hc)
            self.color_preview.config(bg=hc)
        except:
            pass
    
    def _take_screenshot(self):
        if not HAS_PIL:
            self._update_status("错误: 未安装 Pillow 库")
            return
        
        try:
            self._update_status("正在截屏...")
            screenshot = ImageGrab.grab()
            
            if screenshot:
                if HAS_PYPERCLIP:
                    try:
                        import io
                        output = io.BytesIO()
                        screenshot.save(output, format='BMP')
                        data = output.getvalue()
                        output.close()
                        
                        try:
                            from ctypes import windll
                            CF_DIB = 8
                            GHND = 0x02
                            
                            windll.kernel32.GlobalAlloc.restype = ctypes.c_void_p
                            windll.kernel32.GlobalLock.restype = ctypes.c_void_p
                            
                            hMem = windll.kernel32.GlobalAlloc(GHND, len(data))
                            pMem = windll.kernel32.GlobalLock(hMem)
                            
                            import ctypes
                            ctypes.windll.kernel32.RtlMoveMemory(pMem, data, len(data))
                            windll.kernel32.GlobalUnlock(hMem)
                            
                            windll.user32.OpenClipboard(0)
                            windll.user32.EmptyClipboard()
                            windll.user32.SetClipboardData(CF_DIB, hMem)
                            windll.user32.CloseClipboard()
                            
                            self._update_status("截屏已复制到剪贴板")
                        except Exception as e:
                            self._update_status(f"剪贴板操作失败: {e}")
                    except:
                        self._update_status("截屏成功，但剪贴板操作需要额外支持")
                else:
                    self._update_status("截屏成功，如需复制到剪贴板请安装 pyperclip")
                
                self.current_screenshot = screenshot
            else:
                self._update_status("截屏失败")
        except Exception as e:
            self._update_status(f"截屏错误: {e}")
    
    def _copy_color(self):
        if not HAS_PYPERCLIP:
            self._update_status("错误: 未安装 pyperclip 库")
            return
        
        try:
            hex_color = self.lbl_hex_color.cget("text")
            pyperclip.copy(hex_color)
            self._update_status(f"颜色值 {hex_color} 已复制到剪贴板")
        except Exception as e:
            self._update_status(f"复制失败: {e}")
    
    def _update_status(self, message):
        self.status_var.set(f"{datetime.now().strftime('%H:%M:%S')} - {message}")
    
    def _start_update_thread(self):
        update_thread = threading.Thread(target=self._update_info, daemon=True)
        update_thread.start()
    
    def run(self):
        self.root.protocol("WM_DELETE_WINDOW", self._on_close)
        self.root.mainloop()
    
    def _on_close(self):
        self.running = False
        self.root.destroy()


def print_help():
    help_text = """
系统信息工具 v1.0

功能说明:
  1. 显示鼠标绝对坐标 (屏幕坐标系)
  2. 显示鼠标在活动窗口中的相对坐标
  3. 显示当前活动窗口的宽度和高度
  4. 显示鼠标位置的像素颜色 (RGB 和 十六进制)
  5. 截屏功能 (可复制到剪贴板)

使用方法:
  python system_info_tool.py
  或直接运行打包后的可执行文件

快捷键:
  无 (通过GUI按钮操作)

依赖库:
  - pywin32: Windows API 调用
  - Pillow: 图像处理和截屏
  - pyperclip: 剪贴板操作

安装依赖:
  pip install pywin32 Pillow pyperclip

打包为独立程序:
  pip install pyinstaller
  pyinstaller --onefile --windowed system_info_tool.py
    """
    print(help_text)


def main():
    if len(sys.argv) > 1:
        if sys.argv[1] in ['-h', '--help', 'help']:
            print_help()
            return
    
    if not HAS_WIN32:
        print("错误: 缺少 pywin32 库，请运行: pip install pywin32")
        print("程序将退出...")
        time.sleep(3)
        return
    
    if not HAS_PIL:
        print("警告: 缺少 Pillow 库，部分功能可能无法使用")
        print("建议运行: pip install Pillow")
    
    print("启动系统信息工具...")
    print("提示: 窗口将始终保持在最上层")
    
    app = SystemInfoTool()
    app.run()


if __name__ == "__main__":
    main()
