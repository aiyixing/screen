#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
系统信息工具 v4.0
- 显示鼠标坐标、窗口信息、像素颜色
- 三种截屏模式：全屏、窗口、区域
- 截图后可编辑标注
- 热键配置
- 颜色历史
"""

import sys
import os
import json
import time
import threading
import tkinter as tk
from tkinter import ttk, messagebox, simpledialog, colorchooser
from datetime import datetime
from collections import deque
from copy import deepcopy

try:
    import win32api
    import win32gui
    import win32con
    HAS_WIN32 = True
except ImportError:
    HAS_WIN32 = False
    print("警告: 未安装 pywin32，请运行: pip install pywin32")

try:
    from PIL import Image, ImageGrab, ImageTk, ImageDraw, ImageFont
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

try:
    from pynput import keyboard
    HAS_PYNPUT = True
except ImportError:
    HAS_PYNPUT = False
    print("警告: 未安装 pynput，请运行: pip install pynput")


CONFIG_FILE = "config.json"

DEFAULT_HOTKEYS = {
    "screenshot_full": "<ctrl>+<f1>",
    "screenshot_window": "<ctrl>+<f2>",
    "screenshot_area": "<ctrl>+<f3>",
    "record_color": "<ctrl>+<f4>",
    "copy_rgb": "<ctrl>+<f5>",
    "copy_hex": "<ctrl>+<f6>",
    "toggle_window": "<ctrl>+<f7>",
    "copy_history_1": "<ctrl>+1",
    "copy_history_2": "<ctrl>+2",
    "copy_history_3": "<ctrl>+3",
    "copy_history_4": "<ctrl>+4",
    "copy_history_5": "<ctrl>+5",
    "copy_history_6": "<ctrl>+6",
    "copy_history_7": "<ctrl>+7",
    "copy_history_8": "<ctrl>+8",
    "copy_history_9": "<ctrl>+9",
    "copy_history_10": "<ctrl>+0",
}

HOTKEY_DESCRIPTIONS = {
    "screenshot_full": "全屏截屏",
    "screenshot_window": "窗口截屏",
    "screenshot_area": "区域截屏",
    "record_color": "记录当前颜色",
    "copy_rgb": "复制当前RGB",
    "copy_hex": "复制当前HEX",
    "toggle_window": "显示/隐藏窗口",
    "copy_history_1": "复制历史颜色1",
    "copy_history_2": "复制历史颜色2",
    "copy_history_3": "复制历史颜色3",
    "copy_history_4": "复制历史颜色4",
    "copy_history_5": "复制历史颜色5",
    "copy_history_6": "复制历史颜色6",
    "copy_history_7": "复制历史颜色7",
    "copy_history_8": "复制历史颜色8",
    "copy_history_9": "复制历史颜色9",
    "copy_history_10": "复制历史颜色10",
}


class ColorHistoryItem:
    def __init__(self, r, g, b, x, y):
        self.r = r
        self.g = g
        self.b = b
        self.x = x
        self.y = y
        self.timestamp = datetime.now()
        self.hex_color = f"#{r:02X}{g:02X}{b:02X}"
        self.rgb_str = f"RGB({r}, {g}, {b})"
    
    def get_time_str(self):
        return self.timestamp.strftime("%H:%M:%S")


class HotkeyConfig:
    def __init__(self):
        self.hotkeys = DEFAULT_HOTKEYS.copy()
        self.load()
    
    def load(self):
        if os.path.exists(CONFIG_FILE):
            try:
                with open(CONFIG_FILE, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                    if 'hotkeys' in data:
                        for key, value in data['hotkeys'].items():
                            if key in self.hotkeys:
                                self.hotkeys[key] = value
            except Exception as e:
                print(f"加载配置失败: {e}")
    
    def save(self):
        try:
            with open(CONFIG_FILE, 'w', encoding='utf-8') as f:
                json.dump({'hotkeys': self.hotkeys}, f, indent=2, ensure_ascii=False)
        except Exception as e:
            print(f"保存配置失败: {e}")
    
    def get_hotkey(self, action):
        return self.hotkeys.get(action, DEFAULT_HOTKEYS.get(action, ""))
    
    def set_hotkey(self, action, hotkey):
        self.hotkeys[action] = hotkey.lower()
        self.save()
    
    def reset_to_default(self):
        self.hotkeys = DEFAULT_HOTKEYS.copy()
        self.save()


class RegionSelector:
    def __init__(self, callback):
        self.callback = callback
        self.start_x = 0
        self.start_y = 0
        self.end_x = 0
        self.end_y = 0
        self.selecting = False
        self.screenshot = None
        
    def start_selection(self):
        self.root = tk.Tk()
        self.root.attributes('-fullscreen', True)
        self.root.attributes('-topmost', True)
        self.root.overrideredirect(True)
        self.root.focus_force()
        
        screen_width = self.root.winfo_screenwidth()
        screen_height = self.root.winfo_screenheight()
        
        self.root.geometry(f"{screen_width}x{screen_height}+0+0")
        
        try:
            self.screenshot = ImageGrab.grab()
            self.tk_screenshot = ImageTk.PhotoImage(self.screenshot)
        except:
            self.screenshot = None
        
        self.canvas = tk.Canvas(self.root, width=screen_width, height=screen_height, 
                                highlightthickness=0, cursor="cross")
        self.canvas.pack(fill=tk.BOTH, expand=True)
        
        if self.screenshot:
            self.canvas.create_image(0, 0, anchor=tk.NW, image=self.tk_screenshot)
        
        self.dim_rect = self.canvas.create_rectangle(
            0, 0, screen_width, screen_height,
            fill='black', stipple='gray25', outline=''
        )
        
        self.selection_rect = self.canvas.create_rectangle(
            0, 0, 0, 0,
            outline='#FF0000', width=2
        )
        
        self.info_bg = self.canvas.create_rectangle(
            0, 0, 200, 35,
            fill='#FFFFCC', outline='#999999', tags='info'
        )
        self.info_text = self.canvas.create_text(
            10, 17, anchor=tk.W,
            text="拖动鼠标选择区域 | ESC取消 | Enter确认",
            font=("Arial", 10, "bold"), fill='#333333', tags='info'
        )
        
        self.size_bg = None
        self.size_text = None
        
        self.instruction_bg = self.canvas.create_rectangle(
            screen_width//2 - 300, 10, screen_width//2 + 300, 50,
            fill='#E8F4FD', outline='#4A90E2', width=2
        )
        self.instruction_text = self.canvas.create_text(
            screen_width//2, 30,
            text="🖱️ 按住鼠标左键拖动选择区域 | ESC取消 | Enter确认",
            font=("Arial", 14, "bold"), fill='#2C5AA0'
        )
        
        self.canvas.bind('<Button-1>', self.on_mouse_down)
        self.canvas.bind('<B1-Motion>', self.on_mouse_move)
        self.canvas.bind('<ButtonRelease-1>', self.on_mouse_up)
        self.root.bind('<Escape>', self.on_escape)
        self.root.bind('<KeyPress>', self.on_key_press)
        self.root.bind('<Motion>', self.on_mouse_move_always)
        
        self.root.mainloop()
    
    def on_mouse_move_always(self, event):
        if not self.selecting:
            self.canvas.coords(self.info_bg, event.x + 20, event.y + 20, 
                              event.x + 220, event.y + 55)
            self.canvas.coords(self.info_text, event.x + 30, event.y + 37)
            self.canvas.tag_raise('info')
    
    def on_mouse_down(self, event):
        self.selecting = True
        self.start_x = event.x
        self.start_y = event.y
        self.end_x = event.x
        self.end_y = event.y
        
        self._update_selection()
        
        if self.size_text is None:
            self.size_bg = self.canvas.create_rectangle(
                0, 0, 100, 25,
                fill='white', outline='#666666', width=1, tags='size_info'
            )
            self.size_text = self.canvas.create_text(
                0, 0, anchor=tk.CENTER,
                text="0 x 0",
                font=("Consolas", 10, "bold"), fill='#FF0000', tags='size_info'
            )
    
    def on_mouse_move(self, event):
        if not self.selecting:
            return
            
        self.end_x = event.x
        self.end_y = event.y
        
        self._update_selection()
    
    def _update_selection(self):
        x1 = min(self.start_x, self.end_x)
        y1 = min(self.start_y, self.end_y)
        x2 = max(self.start_x, self.end_x)
        y2 = max(self.start_y, self.end_y)
        
        screen_width = self.root.winfo_screenwidth()
        screen_height = self.root.winfo_screenheight()
        
        self.canvas.coords(self.selection_rect, x1, y1, x2, y2)
        
        self.canvas.coords(self.dim_rect, 0, 0, screen_width, screen_height)
        self.canvas.create_rectangle(
            x1, y1, x2, y2,
            fill='', outline='', tags='clear'
        )
        self.canvas.tag_raise(self.selection_rect)
        
        width = x2 - x1
        height = y2 - y1
        
        if self.size_text:
            center_x = (x1 + x2) // 2
            center_y = (y1 + y2) // 2
            
            self.canvas.coords(self.size_bg, center_x - 45, center_y - 12, 
                              center_x + 45, center_y + 12)
            self.canvas.coords(self.size_text, center_x, center_y)
            self.canvas.itemconfig(self.size_text, text=f"{width} x {height}")
            self.canvas.tag_raise('size_info')
        
        if self.selecting:
            mid_x = max(x1, 100)
            mid_y = max(y1 - 30, 10)
            self.canvas.coords(self.info_bg, mid_x - 100, mid_y, mid_x + 100, mid_y + 35)
            self.canvas.coords(self.info_text, mid_x - 90, mid_y + 17)
            self.canvas.itemconfig(self.info_text, 
                text=f"起点:({self.start_x},{self.start_y}) 当前:({self.end_x},{self.end_y})")
            self.canvas.tag_raise('info')
    
    def on_mouse_up(self, event):
        self.selecting = False
        self._finish_selection()
    
    def on_key_press(self, event):
        if event.keysym == 'Return':
            self._finish_selection()
    
    def on_escape(self, event):
        self.selecting = False
        self.root.destroy()
        if self.callback:
            self.callback(None)
    
    def _finish_selection(self):
        x1 = min(self.start_x, self.end_x)
        y1 = min(self.start_y, self.end_y)
        x2 = max(self.start_x, self.end_x)
        y2 = max(self.start_y, self.end_y)
        
        if x2 - x1 > 5 and y2 - y1 > 5:
            region = (x1, y1, x2, y2)
            self.root.destroy()
            if self.callback:
                self.callback(region)
        else:
            self.root.destroy()
            if self.callback:
                self.callback(None)


class ScreenshotEditor:
    TOOLS = ['select', 'rect', 'ellipse', 'line', 'arrow', 'pen', 'text']
    TOOL_NAMES = {
        'select': '选择',
        'rect': '矩形',
        'ellipse': '椭圆',
        'line': '直线',
        'arrow': '箭头',
        'pen': '画笔',
        'text': '文字'
    }
    
    def __init__(self, image, callback=None):
        self.original_image = image.copy()
        self.current_image = image.copy()
        self.callback = callback
        self.result = None
        
        self.current_tool = 'rect'
        self.current_color = '#FF0000'
        self.line_width = 3
        self.font_size = 24
        
        self.history = []
        self.history_index = -1
        self.max_history = 50
        
        self.drawing = False
        self.start_x = 0
        self.start_y = 0
        self.last_x = 0
        self.last_y = 0
        self.temp_item = None
        self.pen_points = []
        
        self._setup_ui()
        self._save_state()
        
    def _setup_ui(self):
        self.root = tk.Toplevel()
        self.root.title("截图编辑器 (100%显示)")
        self.root.attributes('-topmost', True)
        self.root.protocol("WM_DELETE_WINDOW", self._on_cancel)
        
        screen_width = self.root.winfo_screenwidth()
        screen_height = self.root.winfo_screenheight()
        img_width, img_height = self.original_image.size
        
        window_width = min(img_width + 60, screen_width - 100)
        window_height = min(img_height + 140, screen_height - 100)
        
        self.root.geometry(f"{window_width}x{window_height}")
        
        self.scale = 1.0
        
        toolbar_frame = ttk.Frame(self.root)
        toolbar_frame.pack(fill=tk.X, pady=5)
        
        ttk.Button(toolbar_frame, text="↶ 撤销", command=self._undo, width=6).pack(side=tk.LEFT, padx=2)
        ttk.Button(toolbar_frame, text="↷ 重做", command=self._redo, width=6).pack(side=tk.LEFT, padx=2)
        
        ttk.Separator(toolbar_frame, orient=tk.VERTICAL).pack(side=tk.LEFT, fill=tk.Y, padx=10)
        
        self.tool_var = tk.StringVar(value=self.current_tool)
        for tool in self.TOOLS:
            btn = ttk.Radiobutton(toolbar_frame, text=self.TOOL_NAMES[tool], 
                                   variable=self.tool_var, value=tool,
                                   command=self._on_tool_change)
            btn.pack(side=tk.LEFT, padx=2)
        
        ttk.Separator(toolbar_frame, orient=tk.VERTICAL).pack(side=tk.LEFT, fill=tk.Y, padx=10)
        
        ttk.Label(toolbar_frame, text="颜色:").pack(side=tk.LEFT, padx=2)
        self.color_btn = tk.Button(toolbar_frame, bg=self.current_color, width=3, 
                                    command=self._choose_color)
        self.color_btn.pack(side=tk.LEFT, padx=2)
        
        ttk.Label(toolbar_frame, text="线宽:").pack(side=tk.LEFT, padx=2)
        self.line_width_var = tk.StringVar(value=str(self.line_width))
        line_width_combo = ttk.Combobox(toolbar_frame, textvariable=self.line_width_var, 
                                          values=['1', '2', '3', '4', '5', '8', '10'], 
                                          width=3, state='readonly')
        line_width_combo.pack(side=tk.LEFT, padx=2)
        line_width_combo.bind('<<ComboboxSelected>>', self._on_line_width_change)
        
        ttk.Label(toolbar_frame, text="字号:").pack(side=tk.LEFT, padx=2)
        self.font_size_var = tk.StringVar(value=str(self.font_size))
        font_size_combo = ttk.Combobox(toolbar_frame, textvariable=self.font_size_var, 
                                         values=['12', '16', '20', '24', '28', '32', '40'], 
                                         width=3, state='readonly')
        font_size_combo.pack(side=tk.LEFT, padx=2)
        font_size_combo.bind('<<ComboboxSelected>>', self._on_font_size_change)
        
        ttk.Separator(toolbar_frame, orient=tk.VERTICAL).pack(side=tk.LEFT, fill=tk.Y, padx=10)
        
        ttk.Button(toolbar_frame, text="✗ 取消", command=self._on_cancel).pack(side=tk.RIGHT, padx=5)
        ttk.Button(toolbar_frame, text="✓ 确定", command=self._on_confirm).pack(side=tk.RIGHT, padx=5)
        
        canvas_frame = ttk.Frame(self.root)
        canvas_frame.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)
        
        h_scrollbar = ttk.Scrollbar(canvas_frame, orient=tk.HORIZONTAL)
        h_scrollbar.pack(side=tk.BOTTOM, fill=tk.X)
        v_scrollbar = ttk.Scrollbar(canvas_frame, orient=tk.VERTICAL)
        v_scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
        
        img_width, img_height = self.current_image.size
        self.canvas = tk.Canvas(canvas_frame, bg='gray', cursor='cross',
                                scrollregion=(0, 0, img_width, img_height),
                                xscrollcommand=h_scrollbar.set,
                                yscrollcommand=v_scrollbar.set)
        self.canvas.pack(fill=tk.BOTH, expand=True)
        
        h_scrollbar.config(command=self.canvas.xview)
        v_scrollbar.config(command=self.canvas.yview)
        
        self.offset_x = 0
        self.offset_y = 0
        self.display_width = img_width
        self.display_height = img_height
        
        self._update_canvas()
        
        self.canvas.bind('<Button-1>', self._on_mouse_down)
        self.canvas.bind('<B1-Motion>', self._on_mouse_move)
        self.canvas.bind('<ButtonRelease-1>', self._on_mouse_up)
        
        self.root.grab_set()
        self.root.wait_window()
        
    def _update_canvas(self):
        self.canvas.delete('all')
        
        self.tk_image = ImageTk.PhotoImage(self.current_image)
        self.canvas.create_image(0, 0, anchor=tk.NW, image=self.tk_image)
        
    def _on_tool_change(self):
        self.current_tool = self.tool_var.get()
        
    def _choose_color(self):
        color = colorchooser.askcolor(self.current_color, title="选择颜色")
        if color and color[1]:
            self.current_color = color[1]
            self.color_btn.config(bg=self.current_color)
            
    def _on_line_width_change(self, event=None):
        try:
            self.line_width = int(self.line_width_var.get())
        except:
            self.line_width = 3
            
    def _on_font_size_change(self, event=None):
        try:
            self.font_size = int(self.font_size_var.get())
        except:
            self.font_size = 24
            
    def _screen_to_image(self, sx, sy):
        cx = self.canvas.canvasx(sx)
        cy = self.canvas.canvasy(sy)
        ix = int(cx)
        iy = int(cy)
        img_width, img_height = self.current_image.size
        ix = max(0, min(ix, img_width - 1))
        iy = max(0, min(iy, img_height - 1))
        return ix, iy
    
    def _image_to_screen(self, ix, iy):
        return ix, iy
        
    def _on_mouse_down(self, event):
        self.drawing = True
        self.start_x, self.start_y = self._screen_to_image(event.x, event.y)
        self.last_x, self.last_y = self.start_x, self.start_y
        self.pen_points = [(self.start_x, self.start_y)]
        
        if self.current_tool == 'text':
            text = simpledialog.askstring("输入文字", "请输入标注文字:")
            if text:
                self._draw_text(self.start_x, self.start_y, text)
                self.drawing = False
                
    def _on_mouse_move(self, event):
        if not self.drawing:
            return
            
        curr_x, curr_y = self._screen_to_image(event.x, event.y)
        
        if self.temp_item:
            self.canvas.delete(self.temp_item)
            self.temp_item = None
            
        if self.current_tool == 'rect':
            self.temp_item = self.canvas.create_rectangle(
                self.start_x, self.start_y, curr_x, curr_y, outline=self.current_color, 
                width=self.line_width, dash=(5, 5)
            )
        elif self.current_tool == 'ellipse':
            self.temp_item = self.canvas.create_oval(
                self.start_x, self.start_y, curr_x, curr_y, outline=self.current_color, 
                width=self.line_width, dash=(5, 5)
            )
        elif self.current_tool == 'line':
            self.temp_item = self.canvas.create_line(
                self.start_x, self.start_y, curr_x, curr_y, fill=self.current_color, 
                width=self.line_width, dash=(5, 5)
            )
        elif self.current_tool == 'arrow':
            self.temp_item = self.canvas.create_line(
                self.start_x, self.start_y, curr_x, curr_y, fill=self.current_color, 
                width=self.line_width, arrow=tk.LAST, arrowshape=(15, 20, 5)
            )
        elif self.current_tool == 'pen':
            self.pen_points.append((curr_x, curr_y))
            if len(self.pen_points) >= 2:
                self.canvas.create_line(
                    self.last_x, self.last_y, curr_x, curr_y, fill=self.current_color, 
                    width=self.line_width
                )
            self.last_x, self.last_y = curr_x, curr_y
            
    def _on_mouse_up(self, event):
        if not self.drawing:
            return
            
        self.drawing = False
        end_x, end_y = self._screen_to_image(event.x, event.y)
        
        if self.temp_item:
            self.canvas.delete(self.temp_item)
            self.temp_item = None
            
        if self.current_tool in ['rect', 'ellipse', 'line', 'arrow'] and (self.start_x != end_x or self.start_y != end_y):
            self._draw_to_image(self.start_x, self.start_y, end_x, end_y)
            self._save_state()
            self._update_canvas()
        elif self.current_tool == 'pen' and len(self.pen_points) >= 2:
            self._draw_pen_to_image()
            self._save_state()
            self._update_canvas()
            
    def _draw_to_image(self, x1, y1, x2, y2):
        draw = ImageDraw.Draw(self.current_image)
        
        if self.current_tool == 'rect':
            draw.rectangle([x1, y1, x2, y2], outline=self.current_color, width=self.line_width)
        elif self.current_tool == 'ellipse':
            draw.ellipse([x1, y1, x2, y2], outline=self.current_color, width=self.line_width)
        elif self.current_tool == 'line':
            draw.line([x1, y1, x2, y2], fill=self.current_color, width=self.line_width)
        elif self.current_tool == 'arrow':
            draw.line([x1, y1, x2, y2], fill=self.current_color, width=self.line_width)
            self._draw_arrowhead(draw, x1, y1, x2, y2)
            
    def _draw_arrowhead(self, draw, x1, y1, x2, y2):
        import math
        angle = math.atan2(y2 - y1, x2 - x1)
        arrow_length = 15 + self.line_width * 2
        arrow_angle = math.pi / 6
        
        x3 = x2 - arrow_length * math.cos(angle - arrow_angle)
        y3 = y2 - arrow_length * math.sin(angle - arrow_angle)
        x4 = x2 - arrow_length * math.cos(angle + arrow_angle)
        y4 = y2 - arrow_length * math.sin(angle + arrow_angle)
        
        draw.polygon([x2, y2, x3, y3, x4, y4], fill=self.current_color)
        
    def _draw_pen_to_image(self):
        draw = ImageDraw.Draw(self.current_image)
        if len(self.pen_points) >= 2:
            draw.line(self.pen_points, fill=self.current_color, width=self.line_width)
            
    def _draw_text(self, x, y, text):
        draw = ImageDraw.Draw(self.current_image)
        try:
            try:
                font = ImageFont.truetype("msyh.ttc", self.font_size)
            except:
                try:
                    font = ImageFont.truetype("arial.ttf", self.font_size)
                except:
                    font = ImageFont.load_default()
                    
            draw.text((x, y), text, fill=self.current_color, font=font)
            self._save_state()
            self._update_canvas()
        except Exception as e:
            print(f"文字绘制错误: {e}")
            
    def _save_state(self):
        if self.history_index < len(self.history) - 1:
            self.history = self.history[:self.history_index + 1]
            
        self.history.append(self.current_image.copy())
        self.history_index = len(self.history) - 1
        
        if len(self.history) > self.max_history:
            self.history.pop(0)
            self.history_index -= 1
            
    def _undo(self):
        if self.history_index > 0:
            self.history_index -= 1
            self.current_image = self.history[self.history_index].copy()
            self._update_canvas()
            
    def _redo(self):
        if self.history_index < len(self.history) - 1:
            self.history_index += 1
            self.current_image = self.history[self.history_index].copy()
            self._update_canvas()
            
    def _on_cancel(self):
        self.result = None
        self.root.destroy()
        
    def _on_confirm(self):
        self.result = self.current_image
        self.root.destroy()
        
    def get_result(self):
        return self.result


class HotkeyConfigDialog:
    def __init__(self, parent, config, on_save_callback):
        self.parent = parent
        self.config = config
        self.on_save_callback = on_save_callback
        self.editing_action = None
        self.temp_keys = []
        
        self.dialog = tk.Toplevel(parent)
        self.dialog.title("快捷键配置")
        self.dialog.geometry("450x550")
        self.dialog.resizable(False, False)
        self.dialog.transient(parent)
        self.dialog.grab_set()
        
        self._setup_ui()
    
    def _setup_ui(self):
        main_frame = ttk.Frame(self.dialog, padding="10")
        main_frame.pack(fill=tk.BOTH, expand=True)
        
        ttk.Label(main_frame, text="点击热键值进行修改，按 ESC 取消，按 Enter 确认", 
                 font=("Arial", 9, "bold"), foreground="blue").pack(pady=5)
        
        canvas_frame = ttk.Frame(main_frame)
        canvas_frame.pack(fill=tk.BOTH, expand=True)
        
        canvas = tk.Canvas(canvas_frame)
        scrollbar = ttk.Scrollbar(canvas_frame, orient="vertical", command=canvas.yview)
        self.scrollable_frame = ttk.Frame(canvas)
        
        self.scrollable_frame.bind(
            "<Configure>",
            lambda e: canvas.configure(scrollregion=canvas.bbox("all"))
        )
        
        canvas.create_window((0, 0), window=self.scrollable_frame, anchor="nw")
        canvas.configure(yscrollcommand=scrollbar.set)
        
        canvas.pack(side="left", fill="both", expand=True)
        scrollbar.pack(side="right", fill="y")
        
        self.hotkey_entries = {}
        
        for action, description in HOTKEY_DESCRIPTIONS.items():
            frame = ttk.Frame(self.scrollable_frame)
            frame.pack(fill=tk.X, pady=1, padx=5)
            
            ttk.Label(frame, text=description, width=22).pack(side=tk.LEFT)
            
            hotkey = self.config.get_hotkey(action)
            entry = ttk.Entry(frame, width=18, justify='center')
            entry.insert(0, hotkey)
            entry.config(state='readonly')
            entry.pack(side=tk.LEFT, padx=10)
            
            entry.bind('<Button-1>', lambda e, a=action, ent=entry: self._start_edit(a, ent))
            
            self.hotkey_entries[action] = entry
        
        btn_frame = ttk.Frame(main_frame)
        btn_frame.pack(fill=tk.X, pady=10)
        
        ttk.Button(btn_frame, text="恢复默认", command=self._reset_default).pack(side=tk.LEFT, padx=5)
        ttk.Button(btn_frame, text="保存并应用", command=self._save_and_close).pack(side=tk.RIGHT, padx=5)
        ttk.Button(btn_frame, text="取消", command=self.dialog.destroy).pack(side=tk.RIGHT, padx=5)
    
    def _start_edit(self, action, entry):
        if self.editing_action:
            self._cancel_edit()
        
        self.editing_action = action
        self.temp_keys = []
        entry.config(state='normal')
        entry.delete(0, tk.END)
        entry.insert(0, "按下新快捷键...")
        entry.config(state='readonly')
        
        entry.bind('<KeyPress>', lambda e: self._on_key_press(e, action, entry))
        entry.bind('<Escape>', lambda e: self._cancel_edit())
        entry.bind('<Return>', lambda e: self._confirm_edit(action, entry))
    
    def _on_key_press(self, event, action, entry):
        key = event.keysym.lower()
        
        modifiers = []
        if event.state & 0x4:
            modifiers.append('ctrl')
        if event.state & 0x1:
            modifiers.append('shift')
        if event.state & 0x8:
            modifiers.append('alt')
        
        actual_key = key
        if key in ['control_l', 'control_r', 'ctrl_l', 'ctrl_r']:
            actual_key = 'ctrl'
        elif key in ['shift_l', 'shift_r']:
            actual_key = 'shift'
        elif key in ['alt_l', 'alt_r']:
            actual_key = 'alt'
        
        if actual_key not in modifiers:
            hotkey_parts = []
            if 'ctrl' in modifiers:
                hotkey_parts.append('<ctrl>')
            if 'shift' in modifiers:
                hotkey_parts.append('<shift>')
            if 'alt' in modifiers:
                hotkey_parts.append('<alt>')
            hotkey_parts.append(f'<{actual_key}>' if len(actual_key) > 1 else actual_key)
            hotkey_str = '+'.join(hotkey_parts)
            
            display_str = hotkey_str.replace('<', '').replace('>', '')
            entry.config(state='normal')
            entry.delete(0, tk.END)
            entry.insert(0, display_str)
            entry.config(state='readonly')
            
            self.temp_keys = [hotkey_str]
    
    def _cancel_edit(self):
        if self.editing_action:
            entry = self.hotkey_entries.get(self.editing_action)
            if entry:
                hotkey = self.config.get_hotkey(self.editing_action)
                display_str = hotkey.replace('<', '').replace('>', '')
                entry.config(state='normal')
                entry.delete(0, tk.END)
                entry.insert(0, display_str)
                entry.config(state='readonly')
            self.editing_action = None
            self.temp_keys = []
    
    def _confirm_edit(self, action, entry):
        if self.temp_keys:
            hotkey = self.temp_keys[0]
            self.config.set_hotkey(action, hotkey)
            self.editing_action = None
            self.temp_keys = []
    
    def _reset_default(self):
        if messagebox.askyesno("确认", "确定要恢复所有默认快捷键吗？"):
            self.config.reset_to_default()
            for action, entry in self.hotkey_entries.items():
                hotkey = self.config.get_hotkey(action)
                display_str = hotkey.replace('<', '').replace('>', '')
                entry.config(state='normal')
                entry.delete(0, tk.END)
                entry.insert(0, display_str)
                entry.config(state='readonly')
    
    def _save_and_close(self):
        self._cancel_edit()
        self.config.save()
        if self.on_save_callback:
            self.on_save_callback()
        self.dialog.destroy()


class ColorHistoryPanel:
    def __init__(self, parent, color_history):
        self.parent = parent
        self.color_history = color_history
        self.selected_index = None
        self.detail_window = None
        
        self._setup_ui()
        
    def _setup_ui(self):
        self.frame = ttk.LabelFrame(self.parent, text="颜色历史 (点击查看详情)", padding="5")
        self.frame.pack(fill=tk.X, pady=3)
        
        self.rows_frame = ttk.Frame(self.frame)
        self.rows_frame.pack(fill=tk.X)
        
        self.color_buttons = []
        for row in range(2):
            row_frame = ttk.Frame(self.rows_frame)
            row_frame.pack(fill=tk.X)
            
            for col in range(5):
                idx = row * 5 + col
                btn_frame = ttk.Frame(row_frame)
                btn_frame.pack(side=tk.LEFT, padx=3, pady=2)
                
                btn = tk.Canvas(btn_frame, width=28, height=28, bg="#f0f0f0", 
                               relief=tk.RAISED, cursor="hand2")
                btn.pack()
                
                idx_label = ttk.Label(btn_frame, text=f"{idx+1}", font=("Arial", 7))
                idx_label.pack()
                
                btn.bind('<Button-1>', lambda e, i=idx: self._on_color_click(i))
                
                self.color_buttons.append({
                    'canvas': btn,
                    'label': idx_label
                })
    
    def update_display(self, color_history):
        self.color_history = color_history
        for i in range(10):
            btn = self.color_buttons[i]
            if i < len(self.color_history):
                item = self.color_history[i]
                btn['canvas'].config(bg=item.hex_color, relief=tk.RAISED)
            else:
                btn['canvas'].config(bg="#f0f0f0", relief=tk.FLAT)
        
        if self.selected_index is not None and self.selected_index < len(self.color_history):
            self.color_buttons[self.selected_index]['canvas'].config(relief=tk.SUNKEN)
    
    def _on_color_click(self, index):
        if index >= len(self.color_history):
            return
        
        self.selected_index = index
        for i in range(10):
            if i == index:
                self.color_buttons[i]['canvas'].config(relief=tk.SUNKEN)
            elif i < len(self.color_history):
                self.color_buttons[i]['canvas'].config(relief=tk.RAISED)
        
        self._show_detail(index)
    
    def _show_detail(self, index):
        item = self.color_history[index]
        
        if self.detail_window:
            try:
                self.detail_window.destroy()
            except:
                pass
        
        self.detail_window = tk.Toplevel(self.parent)
        self.detail_window.title(f"颜色详情 #{index+1}")
        self.detail_window.geometry("320x200")
        self.detail_window.resizable(False, False)
        self.detail_window.transient(self.parent)
        
        main_frame = ttk.Frame(self.detail_window, padding="15")
        main_frame.pack(fill=tk.BOTH, expand=True)
        
        preview_frame = ttk.Frame(main_frame)
        preview_frame.pack(fill=tk.X, pady=10)
        
        preview = tk.Canvas(preview_frame, width=60, height=60, bg=item.hex_color, 
                           relief=tk.SUNKEN)
        preview.pack(side=tk.LEFT, padx=10)
        
        info_frame = ttk.Frame(preview_frame)
        info_frame.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        
        ttk.Label(info_frame, text=f"RGB: {item.rgb_str}", 
                  font=("Arial", 10, "bold")).pack(anchor=tk.W)
        ttk.Label(info_frame, text=f"十六进制: {item.hex_color}", 
                  font=("Arial", 10)).pack(anchor=tk.W)
        ttk.Label(info_frame, text=f"位置: ({item.x}, {item.y})", 
                  font=("Arial", 10)).pack(anchor=tk.W)
        ttk.Label(info_frame, text=f"时间: {item.get_time_str()}", 
                  font=("Arial", 10)).pack(anchor=tk.W)
        
        btn_frame = ttk.Frame(main_frame)
        btn_frame.pack(fill=tk.X, pady=10)
        
        ttk.Button(btn_frame, text="复制 RGB", 
                  command=lambda: self._copy_rgb(item)).pack(side=tk.LEFT, padx=5)
        ttk.Button(btn_frame, text="复制 十六进制", 
                  command=lambda: self._copy_hex(item)).pack(side=tk.LEFT, padx=5)
        ttk.Button(btn_frame, text="关闭", 
                  command=self.detail_window.destroy).pack(side=tk.RIGHT, padx=5)
    
    def _copy_rgb(self, item):
        if HAS_PYPERCLIP:
            pyperclip.copy(item.rgb_str)
    
    def _copy_hex(self, item):
        if HAS_PYPERCLIP:
            pyperclip.copy(item.hex_color)


class SystemInfoTool:
    def __init__(self):
        self.root = tk.Tk()
        self.root.title("系统信息工具 v4.0")
        self.root.geometry("220x420")
        self.root.resizable(False, False)
        self.root.attributes("-topmost", True)
        
        self.config = HotkeyConfig()
        
        self.running = True
        self.current_screenshot = None
        self.color_history = deque(maxlen=10)
        self.current_r = 0
        self.current_g = 0
        self.current_b = 0
        self.current_hex = "#000000"
        self.current_mouse_x = 0
        self.current_mouse_y = 0
        
        self.hotkey_listener = None
        self.global_hotkeys = None
        self.window_visible = True
        
        self._setup_ui()
        self._setup_hotkeys()
        self._start_update_thread()
        
    def _setup_ui(self):
        main_frame = ttk.Frame(self.root, padding="5")
        main_frame.pack(fill=tk.BOTH, expand=True)
        
        top_frame = ttk.Frame(main_frame)
        top_frame.pack(fill=tk.X, pady=1)
        
        self.screenshot_mode = tk.StringVar(value="window")
        ttk.Radiobutton(top_frame, text="全", variable=self.screenshot_mode, 
                        value="full").pack(side=tk.LEFT, padx=2)
        ttk.Radiobutton(top_frame, text="窗", variable=self.screenshot_mode, 
                        value="window").pack(side=tk.LEFT, padx=2)
        ttk.Radiobutton(top_frame, text="区", variable=self.screenshot_mode, 
                        value="area").pack(side=tk.LEFT, padx=2)
        
        ttk.Button(top_frame, text="热键", command=self._open_hotkey_config, 
                  width=4).pack(side=tk.RIGHT, padx=2)
        ttk.Button(top_frame, text="截屏", command=self._do_screenshot, 
                  width=4).pack(side=tk.RIGHT, padx=2)
        self.hide_btn = ttk.Button(top_frame, text="隐藏", command=self._toggle_window, 
                  width=4)
        self.hide_btn.pack(side=tk.RIGHT, padx=2)
        
        info_frame = ttk.Frame(main_frame)
        info_frame.pack(fill=tk.X, pady=1)
        
        row1 = ttk.Frame(info_frame)
        row1.pack(fill=tk.X, pady=1)
        
        ttk.Label(row1, text="鼠标:", font=("Arial", 8, "bold")).pack(side=tk.LEFT)
        self.lbl_mouse_abs = ttk.Label(row1, text="(0,0)", foreground="blue", font=("Arial", 8))
        self.lbl_mouse_abs.pack(side=tk.LEFT, padx=3)
        self.lbl_mouse_rel = ttk.Label(row1, text="[(0,0)]", foreground="green", font=("Arial", 8))
        self.lbl_mouse_rel.pack(side=tk.LEFT, padx=3)
        
        row2 = ttk.Frame(info_frame)
        row2.pack(fill=tk.X, pady=1)
        
        ttk.Label(row2, text="窗口:", font=("Arial", 8, "bold")).pack(side=tk.LEFT)
        self.lbl_window_size = ttk.Label(row2, text="0x0", foreground="purple", font=("Arial", 8))
        self.lbl_window_size.pack(side=tk.LEFT, padx=3)
        self.lbl_window_title = ttk.Label(row2, text="", foreground="orange", font=("Arial", 7), width=12)
        self.lbl_window_title.pack(side=tk.LEFT, padx=3)
        
        color_frame = ttk.Frame(main_frame)
        color_frame.pack(fill=tk.X, pady=1)
        
        self.color_preview = tk.Canvas(color_frame, width=24, height=24, bg="white", 
                                        relief=tk.SUNKEN)
        self.color_preview.pack(side=tk.LEFT, padx=2)
        
        color_info = ttk.Frame(color_frame)
        color_info.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        
        c_row1 = ttk.Frame(color_info)
        c_row1.pack(fill=tk.X)
        ttk.Label(c_row1, text="RGB:", font=("Arial", 7, "bold")).pack(side=tk.LEFT)
        self.lbl_pixel_color = ttk.Label(c_row1, text="(0,0,0)", foreground="red", font=("Arial", 7))
        self.lbl_pixel_color.pack(side=tk.LEFT, padx=1)
        ttk.Label(c_row1, text="|", font=("Arial", 7)).pack(side=tk.LEFT, padx=1)
        self.lbl_hex_color = ttk.Label(c_row1, text="#000000", foreground="darkred", font=("Arial", 7))
        self.lbl_hex_color.pack(side=tk.LEFT, padx=1)
        
        c_row2 = ttk.Frame(color_info)
        c_row2.pack(fill=tk.X)
        ttk.Label(c_row2, text="Pos:", font=("Arial", 7, "bold")).pack(side=tk.LEFT)
        self.lbl_color_pos = ttk.Label(c_row2, text="(0,0)", foreground="gray", font=("Arial", 7))
        self.lbl_color_pos.pack(side=tk.LEFT, padx=1)
        
        self.color_history_panel = ColorHistoryPanel(main_frame, self.color_history)
        
        self.status_var = tk.StringVar(value="就绪")
        status_bar = ttk.Label(self.root, textvariable=self.status_var, relief=tk.SUNKEN, anchor=tk.W, font=("Arial", 7))
        status_bar.pack(side=tk.BOTTOM, fill=tk.X)
    
    def _update_hotkey_info(self):
        info = (
            f"全屏:{self._format_hotkey(self.config.get_hotkey('screenshot_full'))} | "
            f"窗口:{self._format_hotkey(self.config.get_hotkey('screenshot_window'))} | "
            f"区域:{self._format_hotkey(self.config.get_hotkey('screenshot_area'))}\n"
            f"记录颜色:{self._format_hotkey(self.config.get_hotkey('record_color'))} | "
            f"复制RGB:{self._format_hotkey(self.config.get_hotkey('copy_rgb'))} | "
            f"复制HEX:{self._format_hotkey(self.config.get_hotkey('copy_hex'))}"
        )
        self.hotkey_info_text.set(info)
    
    def _format_hotkey(self, hotkey):
        return hotkey.replace('<', '').replace('>', '').upper()
    
    def _open_hotkey_config(self):
        HotkeyConfigDialog(self.root, self.config, self._on_hotkey_config_changed)
    
    def _on_hotkey_config_changed(self):
        self._update_hotkey_info()
        self._setup_hotkeys()
        self._update_status("热键配置已更新")
    
    def _toggle_window(self):
        self.window_visible = not self.window_visible
        if self.window_visible:
            self.root.deiconify()
            self.hide_btn.config(text="隐藏")
            self._update_status("窗口已显示")
        else:
            self.root.withdraw()
            self._update_status("窗口已隐藏 (按 Ctrl+F7 显示)")
    
    def _parse_hotkey_string(self, hotkey_str):
        hotkey_str = hotkey_str.lower().strip()
        hotkey_str = hotkey_str.replace('<', '').replace('>', '')
        
        parts = hotkey_str.split('+')
        modifiers = set()
        key = None
        
        for part in parts:
            part = part.strip()
            if part in ['ctrl', 'control']:
                modifiers.add('ctrl')
            elif part in ['shift']:
                modifiers.add('shift')
            elif part in ['alt']:
                modifiers.add('alt')
            else:
                key = part
        
        return modifiers, key
    
    def _setup_hotkeys(self):
        if not HAS_PYNPUT:
            self._update_status("警告: 未安装 pynput，热键功能不可用")
            return
        
        if self.hotkey_listener:
            try:
                self.hotkey_listener.stop()
            except:
                pass
        
        self.ctrl_pressed = False
        self.shift_pressed = False
        self.alt_pressed = False
        
        print("="*50)
        print("热键配置:")
        for action in HOTKEY_DESCRIPTIONS:
            hotkey = self.config.get_hotkey(action)
            mods, key = self._parse_hotkey_string(hotkey)
            print(f"  {HOTKEY_DESCRIPTIONS[action]}: {hotkey} -> modifiers={mods}, key={key}")
        print("="*50)
        
        def on_press(key):
            try:
                if key in [keyboard.Key.ctrl_l, keyboard.Key.ctrl_r]:
                    self.ctrl_pressed = True
                    return
                if key in [keyboard.Key.shift_l, keyboard.Key.shift_r]:
                    self.shift_pressed = True
                    return
                if key in [keyboard.Key.alt_l, keyboard.Key.alt_r]:
                    self.alt_pressed = True
                    return
                
                pressed_key = None
                if hasattr(key, 'char') and key.char:
                    pressed_key = key.char.lower()
                elif hasattr(key, 'name'):
                    pressed_key = key.name.lower()
                
                if not pressed_key:
                    return
                
                current_modifiers = set()
                if self.ctrl_pressed:
                    current_modifiers.add('ctrl')
                if self.shift_pressed:
                    current_modifiers.add('shift')
                if self.alt_pressed:
                    current_modifiers.add('alt')
                
                print(f"按键: modifiers={current_modifiers}, key={pressed_key}")
                
                actions = [
                    ("screenshot_full", self._screenshot_full),
                    ("screenshot_window", self._screenshot_window),
                    ("screenshot_area", self._screenshot_area),
                    ("record_color", self._record_color),
                    ("copy_rgb", self._copy_current_rgb),
                    ("copy_hex", self._copy_current_hex),
                    ("toggle_window", self._toggle_window),
                ]
                
                for i in range(1, 11):
                    action_name = f"copy_history_{i}"
                    idx = i - 1
                    def make_callback(idx):
                        return lambda: self._copy_history_rgb(idx)
                    actions.append((action_name, make_callback(idx)))
                
                for action_name, callback in actions:
                    hotkey_str = self.config.get_hotkey(action_name)
                    required_modifiers, required_key = self._parse_hotkey_string(hotkey_str)
                    
                    if current_modifiers == required_modifiers and pressed_key == required_key:
                        print(f"匹配到: {HOTKEY_DESCRIPTIONS[action_name]}")
                        self.root.after(0, callback)
                        return
                    
            except Exception as e:
                print(f"热键处理错误: {e}")
        
        def on_release(key):
            try:
                if key in [keyboard.Key.ctrl_l, keyboard.Key.ctrl_r]:
                    self.ctrl_pressed = False
                elif key in [keyboard.Key.shift_l, keyboard.Key.shift_r]:
                    self.shift_pressed = False
                elif key in [keyboard.Key.alt_l, keyboard.Key.alt_r]:
                    self.alt_pressed = False
            except:
                pass
        
        try:
            self.hotkey_listener = keyboard.Listener(
                on_press=on_press,
                on_release=on_release
            )
            self.hotkey_listener.daemon = True
            self.hotkey_listener.start()
            print("热键监听器已启动")
            self._update_status("热键已就绪")
        except Exception as e:
            print(f"热键监听器启动失败: {e}")
            self._update_status(f"热键启动失败: {e}")
    
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
            return (None, 0, 0, 0, 0, "")
        try:
            hwnd = win32gui.GetForegroundWindow()
            if hwnd == 0:
                return (None, 0, 0, 0, 0, "")
            
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
                self.current_mouse_x = mouse_x
                self.current_mouse_y = mouse_y
                
                window_info = self._get_active_window()
                hwnd, win_left, win_top, win_width, win_height, win_title = window_info
                
                rel_x = mouse_x - win_left
                rel_y = mouse_y - win_top
                
                if rel_x < 0 or rel_x >= win_width or rel_y < 0 or rel_y >= win_height:
                    rel_x = 0
                    rel_y = 0
                
                pixel_color = self._get_pixel_color(mouse_x, mouse_y)
                r, g, b = pixel_color
                self.current_r = r
                self.current_g = g
                self.current_b = b
                self.current_hex = f"#{r:02X}{g:02X}{b:02X}"
                
                self.root.after(0, lambda: self._update_ui(
                    mouse_x, mouse_y,
                    rel_x, rel_y,
                    win_width, win_height,
                    win_title,
                    r, g, b, self.current_hex
                ))
                
                time.sleep(0.05)
            except:
                time.sleep(0.1)
    
    def _update_ui(self, mx, my, rx, ry, ww, wh, wt, r, g, b, hc):
        try:
            self.lbl_mouse_abs.config(text=f"绝对 ({mx},{my})")
            self.lbl_mouse_rel.config(text=f"相对 ({rx},{ry})")
            self.lbl_window_size.config(text=f"尺寸: {ww}x{wh}")
            self.lbl_window_title.config(text=wt[:15] + "..." if len(wt) > 15 else wt if wt else "无")
            self.lbl_pixel_color.config(text=f"({r}, {g}, {b})")
            self.lbl_hex_color.config(text=hc)
            self.lbl_color_pos.config(text=f"({mx}, {my})")
            self.color_preview.config(bg=hc)
        except:
            pass
    
    def _copy_image_to_clipboard(self, image):
        try:
            import io
            import ctypes
            from ctypes import windll
            
            output = io.BytesIO()
            image.save(output, format='BMP')
            data = output.getvalue()
            output.close()
            
            CF_DIB = 8
            GHND = 0x02
            
            windll.kernel32.GlobalAlloc.restype = ctypes.c_void_p
            windll.kernel32.GlobalLock.restype = ctypes.c_void_p
            
            hMem = windll.kernel32.GlobalAlloc(GHND, len(data))
            pMem = windll.kernel32.GlobalLock(hMem)
            
            ctypes.windll.kernel32.RtlMoveMemory(pMem, data, len(data))
            windll.kernel32.GlobalUnlock(hMem)
            
            windll.user32.OpenClipboard(0)
            windll.user32.EmptyClipboard()
            windll.user32.SetClipboardData(CF_DIB, hMem)
            windll.user32.CloseClipboard()
            
            return True
        except Exception as e:
            print(f"剪贴板操作失败: {e}")
            return False
    
    def _do_screenshot(self):
        mode = self.screenshot_mode.get()
        if mode == "full":
            self._screenshot_full()
        elif mode == "window":
            self._screenshot_window()
        elif mode == "area":
            self._screenshot_area()
    
    def _open_editor(self, image):
        if image is None:
            return
            
        editor = ScreenshotEditor(image)
        result = editor.get_result()
        
        if result:
            if self._copy_image_to_clipboard(result):
                self._update_status("[编辑器] 确定 - 已复制到剪贴板")
            else:
                self._update_status("[编辑器] 确定 - 剪贴板操作失败")
        else:
            self._update_status("[编辑器] 取消 - 未复制到剪贴板")
    
    def _screenshot_full(self):
        if not HAS_PIL:
            self._update_status("错误: 未安装 Pillow 库")
            return
        
        try:
            self._update_status("正在全屏截屏...")
            self.root.after(100, lambda: self._do_screenshot_full_async())
        except Exception as e:
            self._update_status(f"[全屏截屏] 错误: {e}")
    
    def _do_screenshot_full_async(self):
        try:
            screenshot = ImageGrab.grab()
            
            if screenshot:
                self.current_screenshot = screenshot
                self._update_status("[全屏截屏] 进入编辑器...")
                self.root.after(100, lambda: self._open_editor(screenshot))
            else:
                self._update_status("[全屏截屏] 失败")
        except Exception as e:
            self._update_status(f"[全屏截屏] 错误: {e}")
    
    def _screenshot_window(self):
        if not HAS_WIN32 or not HAS_PIL:
            self._update_status("错误: 缺少必要的库")
            return
        
        try:
            self._update_status("正在窗口截屏...")
            self.root.after(100, lambda: self._do_screenshot_window_async())
        except Exception as e:
            self._update_status(f"[窗口截屏] 错误: {e}")
    
    def _do_screenshot_window_async(self):
        try:
            window_info = self._get_active_window()
            hwnd, left, top, width, height, title = window_info
            
            if hwnd is None or width <= 0 or height <= 0:
                self._update_status("[窗口截屏] 无法获取活动窗口")
                return
            
            bbox = (left, top, left + width, top + height)
            screenshot = ImageGrab.grab(bbox=bbox)
            
            if screenshot:
                self.current_screenshot = screenshot
                self._update_status(f"[窗口截屏] 进入编辑器: {title[:20] if title else '未知'} ({width}x{height})")
                self.root.after(100, lambda: self._open_editor(screenshot))
            else:
                self._update_status("[窗口截屏] 失败")
        except Exception as e:
            self._update_status(f"[窗口截屏] 错误: {e}")
    
    def _screenshot_area(self):
        if not HAS_PIL:
            self._update_status("错误: 未安装 Pillow 库")
            return
        
        try:
            self._update_status("[区域截屏] 请用鼠标拖动选择区域...")
            
            def on_region_selected(region):
                if region:
                    x1, y1, x2, y2 = region
                    self.root.after(0, lambda: self._capture_region(x1, y1, x2, y2))
                else:
                    self.root.after(0, lambda: self._update_status("[区域截屏] 已取消"))
            
            selector = RegionSelector(on_region_selected)
            selector.start_selection()
            
        except Exception as e:
            self._update_status(f"[区域截屏] 错误: {e}")
    
    def _capture_region(self, x1, y1, x2, y2):
        try:
            bbox = (x1, y1, x2, y2)
            screenshot = ImageGrab.grab(bbox=bbox)
            
            if screenshot:
                width = x2 - x1
                height = y2 - y1
                self.current_screenshot = screenshot
                self._update_status(f"[区域截屏] 进入编辑器: 区域({x1},{y1})-({x2},{y2}) {width}x{height}")
                self.root.after(100, lambda: self._open_editor(screenshot))
            else:
                self._update_status("[区域截屏] 失败")
        except Exception as e:
            self._update_status(f"[区域截屏] 错误: {e}")
    
    def _record_color(self):
        try:
            item = ColorHistoryItem(
                self.current_r, 
                self.current_g, 
                self.current_b,
                self.current_mouse_x,
                self.current_mouse_y
            )
            self.color_history.appendleft(item)
            self.color_history_panel.update_display(self.color_history)
            self._update_status(f"[记录颜色] {item.rgb_str} 位置:({item.x},{item.y})")
        except Exception as e:
            self._update_status(f"[记录颜色] 失败: {e}")
    
    def _copy_current_rgb(self):
        if not HAS_PYPERCLIP:
            self._update_status("错误: 未安装 pyperclip 库")
            return
        
        try:
            rgb_str = f"RGB({self.current_r}, {self.current_g}, {self.current_b})"
            pyperclip.copy(rgb_str)
            self._update_status(f"[复制RGB] {rgb_str}")
        except Exception as e:
            self._update_status(f"[复制RGB] 失败: {e}")
    
    def _copy_current_hex(self):
        if not HAS_PYPERCLIP:
            self._update_status("错误: 未安装 pyperclip 库")
            return
        
        try:
            pyperclip.copy(self.current_hex)
            self._update_status(f"[复制HEX] {self.current_hex}")
        except Exception as e:
            self._update_status(f"[复制HEX] 失败: {e}")
    
    def _copy_history_rgb(self, index):
        if not HAS_PYPERCLIP:
            self._update_status("错误: 未安装 pyperclip 库")
            return
        
        try:
            if 0 <= index < len(self.color_history):
                item = self.color_history[index]
                pyperclip.copy(item.rgb_str)
                self._update_status(f"[复制历史{index+1}] {item.rgb_str}")
            else:
                self._update_status(f"历史记录 {index+1} 为空")
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
        if self.global_hotkeys:
            try:
                self.global_hotkeys.stop()
            except:
                pass
        self.root.destroy()


def print_help():
    help_text = """
系统信息工具 v4.0

功能说明:
  1. 显示鼠标绝对坐标和相对坐标
  2. 显示当前活动窗口的尺寸和标题
  3. 显示鼠标位置的像素颜色 (RGB 和 十六进制)
  4. 三种截屏模式:
     - 全屏截屏: 截取整个屏幕
     - 窗口截屏: 自动匹配当前活动窗口区域
     - 区域截屏: 用鼠标拖动选择任意区域（带半透明遮罩和尺寸提示）
  5. 截图后可编辑标注:
     - 画矩形、椭圆、直线、箭头
     - 自由画笔
     - 文字标注
     - 撤销/重做
     - 确定才复制到剪贴板，取消则不复制
  6. 颜色历史记录 (最多10个，点击色块查看详情)
  7. 可自定义快捷键配置

默认快捷键 (可在配置中修改):
  Ctrl+F1 - 全屏截屏
  Ctrl+F2 - 窗口截屏
  Ctrl+F3 - 区域截屏
  Ctrl+F4 - 记录当前颜色
  Ctrl+F5 - 复制当前RGB
  Ctrl+F6 - 复制当前HEX
  Ctrl+1~Ctrl+9 - 复制历史颜色1~9
  Ctrl+0 - 复制历史颜色10

截图编辑器工具:
  - 矩形: 画矩形框
  - 椭圆: 画椭圆/圆形
  - 直线: 画直线
  - 箭头: 画带箭头的线
  - 画笔: 自由绘制
  - 文字: 添加文字标注

配置文件:
  config.json - 保存快捷键配置

依赖库:
  pywin32, Pillow, pyperclip, pynput

安装依赖:
  pip install pywin32 Pillow pyperclip pynput
    """
    print(help_text)


def main():
    if len(sys.argv) > 1:
        if sys.argv[1] in ['-h', '--help', 'help']:
            print_help()
            return
    
    if not HAS_WIN32:
        print("错误: 缺少 pywin32 库，请运行: pip install pywin32")
        time.sleep(3)
        return
    
    if not HAS_PIL:
        print("警告: 缺少 Pillow 库")
    
    if not HAS_PYNPUT:
        print("警告: 缺少 pynput 库，热键功能不可用")
    
    print("启动系统信息工具 v4.0...")
    
    app = SystemInfoTool()
    app.run()


if __name__ == "__main__":
    main()
