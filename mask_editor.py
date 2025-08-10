import tkinter as tk
from tkinter import ttk, filedialog, messagebox
from PIL import Image, ImageTk, ImageOps, ImageDraw
import numpy as np
import cv2
from datetime import datetime
import platform
import asyncio

# ---------------------------- 
# 配置与常量
# ---------------------------- 
DEFAULT_RESOLUTION = (640, 480)  # 默认 VGA 分辨率
DEFAULT_LAB = (0, 200, 100, 150, 100, 150)  # Lmin,Lmax,Amin,Amax,Bmin,Bmax
DEFAULT_GRAY_BIN = (0, 128)  # min,max for gray bin
DEFAULT_AUTO_MASK_GRAY_THRESHOLD = None  # Default auto-mask gray threshold (min, max), None means not set
DEFAULT_AUTO_MASK_LAB_THRESHOLD = None   # Default auto-mask LAB threshold, None means not set
DEFAULT_PLAYBACK_INTERVAL = 3000  # Default playback interval in milliseconds (3 seconds)

# ---------------------------- 
# 工具函数
# ---------------------------- 
def pil_to_cv(img_pil):
    return cv2.cvtColor(np.array(img_pil), cv2.COLOR_RGB2BGR)

def cv_to_pil(img_cv):
    return Image.fromarray(cv2.cvtColor(img_cv, cv2.COLOR_BGR2RGB))

def ensure_binary_np(arr, thresh=128):
    return np.where(arr > thresh, 255, 0).astype(np.uint8)

def composite_layers(layers, target_size, mode="L", apply_alpha=False):
    """Create a composite image from visible layers with optional alpha blending."""
    if not layers:
        return Image.new(mode, target_size, 255)
    composite = Image.new(mode, target_size, 255)
    for layer in layers:
        if layer["visible"] and layer["image"] and not layer["hidden"]:
            img = layer["image"].copy()
            if img.size != target_size:
                img = img.resize(target_size, Image.Resampling.LANCZOS)
            if composite.mode == "RGB" and img.mode != "RGB":
                img = img.convert("RGB")
            elif composite.mode == "L" and img.mode != "L":
                img = img.convert("L")
            if apply_alpha and layer.get("alpha", 1.0) < 1.0:
                background = composite.copy()
                foreground = img
                alpha = layer["alpha"]
                composite = Image.blend(background, foreground, alpha)
            else:
                composite.paste(img, (0, 0), img if img.mode == "RGBA" else None)
    return composite

# ---------------------------- 
# 主类
# ---------------------------- 
class MaskEditorApp:
    def __init__(self, root):
        self.root = root
        self.root.title("二值掩码图编辑器")
        self.root.geometry("1100x700")
        style = ttk.Style(root)
        style.theme_use("clam")

        # 状态
        self.target_resolution = DEFAULT_RESOLUTION  # 默认 VGA 分辨率
        self.custom_resolution = None  # 自定义分辨率，优先级高于默认
        self.layers = [{"name": "Layer 1", "image": Image.new("L", self.target_resolution, 255), "visible": True, "applied": False, "alpha": 1.0, "hidden": False}]
        self.current_layer_index = 0
        self.original_image = None
        self.tk_img = None
        self.canvas_image_id = None
        self.border_id = None
        self.merge_factor = 1
        self.selected_region = None
        self.copied_region = None
        self.threshold_lab = DEFAULT_LAB
        self.threshold_gray = DEFAULT_GRAY_BIN
        self.auto_mask_gray_threshold = DEFAULT_AUTO_MASK_GRAY_THRESHOLD
        self.auto_mask_lab_threshold = DEFAULT_AUTO_MASK_LAB_THRESHOLD
        self.brush_size = 5
        self.playback_interval = DEFAULT_PLAYBACK_INTERVAL

        # view transform state
        self.scale = 1.0
        self.offset_x = 0
        self.offset_y = 0
        self.pan_start = None
        self.show_axis = False

        # editing
        self.tool = "paint"
        self.drag_start = None
        self.show_preview = tk.BooleanVar(value=True)

        # history
        self.undo_stack = []
        self.redo_stack = []

        # UI 状态
        self.show_layer_panel_var = tk.BooleanVar(value=True)
        self.layer_panel = None
        self.sorting_mode = False
        self.sort_order = []
        self.layer_panel_moving = False
        self.layer_panel_start_x = 0
        self.layer_panel_start_y = 0

        # Playback state
        self.is_playing = False
        self.playback_task = None
        self.playback_index = 2
        self.original_layers = []

        # UI 布局
        self._build_ui()

        # 初始显示
        self.root.after(100, self.redraw_canvas)

        # 绑定键
        self.root.bind("<Control-z>", lambda e: self.undo())
        self.root.bind("<Control-y>", lambda e: self.redo())
        self.root.bind("z", lambda e: self.undo())
        self.root.bind("y", lambda e: self.redo())

    def _build_ui(self):
        main = ttk.Frame(self.root, padding=8)
        main.pack(fill=tk.BOTH, expand=True)

        # 上方菜单栏
        menubar = tk.Menu(self.root)
        self.root.config(menu=menubar)

        # 文件菜单
        file_menu = tk.Menu(menubar, tearoff=0)
        menubar.add_cascade(label="文件", menu=file_menu)
        file_menu.add_command(label="生成白板", command=self.generate_white)
        file_menu.add_command(label="导入图片", command=self.import_image_dialog)
        file_menu.add_command(label="自动掩码", command=self.auto_mask)
        file_menu.add_command(label="掩码反转", command=self.mask_invert)
        file_menu.add_separator()
        file_menu.add_command(label="保存掩码", command=self.save_mask)
        file_menu.add_command(label="快速保存", command=self.quick_save)

        # 导入模式子菜单
        import_menu = tk.Menu(file_menu, tearoff=0)
        file_menu.add_cascade(label="导入处理", menu=import_menu)
        self.import_mode_var = tk.StringVar(value="灰度化")
        import_menu.add_radiobutton(label="灰度化", variable=self.import_mode_var, value="灰度化")
        import_menu.add_radiobutton(label="二值化", variable=self.import_mode_var, value="二值化")
        import_menu.add_radiobutton(label="彩色化", variable=self.import_mode_var, value="彩色化")

        # 编辑菜单
        edit_menu = tk.Menu(menubar, tearoff=0)
        menubar.add_cascade(label="编辑", menu=edit_menu)
        edit_menu.add_command(label="撤销 (Z)", command=self.undo)
        edit_menu.add_command(label="重做 (Y)", command=self.redo)
        edit_menu.add_command(label="重置", command=self.reset)
        edit_menu.add_command(label="选择区域", command=lambda: self.set_tool("select"))
        edit_menu.add_command(label="复制", command=self.copy_region)
        edit_menu.add_command(label="粘贴", command=self.paste_region)
        edit_menu.add_command(label="删除选定区域", command=self.delete_region)

        # 工具菜单
        tools_menu = tk.Menu(menubar, tearoff=0)
        menubar.add_cascade(label="工具", menu=tools_menu)
        tools_menu.add_command(label="画黑（矩形）", command=lambda: self.set_tool("paint"))
        tools_menu.add_command(label="擦除（矩形）", command=lambda: self.set_tool("erase"))
        tools_menu.add_command(label="画笔（自由）", command=lambda: self.set_tool("brush"))

        # 图层菜单
        layer_menu = tk.Menu(menubar, tearoff=0)
        menubar.add_cascade(label="图层", menu=layer_menu)
        layer_menu.add_command(label="新建图层", command=self.new_layer)
        layer_menu.add_command(label="排序图层", command=self.open_sorting_window)

        # 设置菜单
        settings_menu = tk.Menu(menubar, tearoff=0)
        menubar.add_cascade(label="设置", menu=settings_menu)
        settings_menu.add_command(label="设置分辨率", command=self._open_resolution_window)
        settings_menu.add_command(label="设置画笔大小", command=self._open_brush_size_window)
        settings_menu.add_command(label="设置像素合并因子", command=self._open_merge_factor_window)
        settings_menu.add_command(label="设置阈值", command=self._open_threshold_window)
        settings_menu.add_command(label="设置自动掩码阈值", command=self._open_auto_mask_threshold_window)
        settings_menu.add_command(label="设置播放间隔", command=self._open_playback_interval_window)
        settings_menu.add_checkbutton(label="设置预览画面", variable=self.show_preview, command=self.redraw_canvas)

        # 视图菜单
        view_menu = tk.Menu(menubar, tearoff=0)
        menubar.add_cascade(label="视图", menu=view_menu)
        self.grid_var = tk.BooleanVar(value=False)
        view_menu.add_checkbutton(label="显示像素网格", variable=self.grid_var, command=self.redraw_canvas)
        view_menu.add_checkbutton(label="显示图层栏", variable=self.show_layer_panel_var, command=self.toggle_layer_panel)
        self.axis_var = tk.BooleanVar(value=False)
        view_menu.add_checkbutton(label="显示坐标轴", variable=self.axis_var, command=self.toggle_axis)

        # 帮助菜单
        help_menu = tk.Menu(menubar, tearoff=0)
        menubar.add_cascade(label="帮助", menu=help_menu)
        help_menu.add_command(label="使用说明", command=self._show_help)

        # 主布局
        self.content_pane = ttk.PanedWindow(main, orient=tk.HORIZONTAL)
        self.content_pane.pack(fill=tk.BOTH, expand=True)

        # 画布区
        canvas_frame = ttk.Frame(self.content_pane)
        self.content_pane.add(canvas_frame, weight=3)
        self.canvas_bg = tk.Canvas(canvas_frame, bg="#bdbdbd")
        self.canvas_bg.pack(fill=tk.BOTH, expand=True)
        self.canvas = tk.Canvas(self.canvas_bg, bg="#999999", highlightthickness=0)
        self.canvas_id_window = self.canvas_bg.create_window(10, 10, anchor="nw", window=self.canvas)

        # 图层面板
        self.layer_panel_frame = ttk.Frame(self.content_pane)
        self.layer_panel_frame.pack_propagate(False)
        self._build_layer_panel()
        self.toggle_layer_panel()

        # 绑定事件
        self.canvas.bind("<ButtonPress-1>", self.on_left_down)
        self.canvas.bind("<B1-Motion>", self.on_left_drag)
        self.canvas.bind("<ButtonRelease-1>", self.on_left_up)
        self.canvas.bind("<ButtonPress-2>", self.on_middle_down)
        self.canvas.bind("<B2-Motion>", self.on_middle_drag)
        self.canvas.bind("<ButtonRelease-2>", self.on_middle_up)
        self.canvas.bind("<MouseWheel>", self.on_mousewheel)
        self.canvas.bind("<Button-4>", self.on_mousewheel)
        self.canvas.bind("<Button-5>", self.on_mousewheel)
        self.canvas_bg.bind("<Configure>", lambda e: self.redraw_canvas())
        
        # 拖拽图层栏
        self.layer_panel_frame.bind("<ButtonPress-1>", self.start_move_layer_panel)
        self.layer_panel_frame.bind("<B1-Motion>", self.move_layer_panel)
        self.layer_panel_frame.bind("<ButtonRelease-1>", self.stop_move_layer_panel)

        # 状态栏
        self.status_var = tk.StringVar(value="准备中")
        status = ttk.Label(self.root, textvariable=self.status_var, relief=tk.SUNKEN, anchor="w")
        status.pack(side=tk.BOTTOM, fill=tk.X)

        self.show_placeholder()

    def _build_layer_panel(self):
        self.layer_panel = ttk.Frame(self.layer_panel_frame, padding=5)
        self.layer_panel.pack(fill=tk.BOTH, expand=True)

        # 图层列表
        ttk.Label(self.layer_panel, text="图层").pack(anchor="w")
        self.layer_listbox = tk.Listbox(self.layer_panel, height=10)
        self.layer_listbox.pack(side=tk.TOP, fill=tk.BOTH, expand=True, padx=5)
        self.layer_listbox.bind("<Double-1>", self.on_layer_select)
        self.layer_listbox.bind("<Button-1>", self.on_layer_select)
        self.layer_listbox.bind("<Button-3>", self._show_layer_context_menu)

        # 按钮
        btn_frame = ttk.Frame(self.layer_panel)
        btn_frame.pack(fill=tk.X, pady=5)
        ttk.Button(btn_frame, text="隐藏", command=self.toggle_layer_visibility).pack(side=tk.LEFT, padx=5)
        ttk.Button(btn_frame, text="删除", command=self.delete_layer).pack(side=tk.LEFT, padx=5)
        self.play_button = ttk.Button(btn_frame, text="播放", command=self.toggle_playback)
        self.play_button.pack(side=tk.LEFT, padx=5)

        self.update_layer_listbox()

    def _show_layer_context_menu(self, event):
        """Show context menu for layer listbox on right-click."""
        index = self.layer_listbox.nearest(event.y)
        if index >= 0:
            self.layer_listbox.select_clear(0, tk.END)
            self.layer_listbox.select_set(index)
            self.current_layer_index = index
            menu = tk.Menu(self.root, tearoff=0)
            menu.add_command(label="重命名", command=self._rename_layer)
            menu.post(event.x_root, event.y_root)

    def _rename_layer(self):
        """Rename the selected layer."""
        if not self.layers or self.current_layer_index < 0 or self.current_layer_index >= len(self.layers):
            messagebox.showerror("错误", "请选择一个图层")
            return
        window = tk.Toplevel(self.root)
        window.title("重命名图层")
        window.geometry("300x150")
        window.resizable(False, False)
        frame = ttk.Frame(window, padding=10)
        frame.pack(fill=tk.BOTH, expand=True)
        ttk.Label(frame, text="新图层名称：").pack(anchor="w", pady=(0, 2))
        name_entry = ttk.Entry(frame)
        name_entry.insert(0, self.layers[self.current_layer_index]["name"])
        name_entry.pack(fill=tk.X, pady=2)
        btn_frame = ttk.Frame(frame)
        btn_frame.pack(fill=tk.X, pady=10)
        def apply():
            new_name = name_entry.get().strip()
            if not new_name:
                messagebox.showerror("错误", "图层名称不能为空")
                return
            if new_name in [layer["name"] for layer in self.layers if layer != self.layers[self.current_layer_index]]:
                messagebox.showerror("错误", "图层名称已存在")
                return
            old_name = self.layers[self.current_layer_index]["name"]
            if old_name in self.sort_order:
                self.sort_order[self.sort_order.index(old_name)] = new_name
            self.layers[self.current_layer_index]["name"] = new_name
            self.push_history()
            self.update_layer_listbox()
            self.status_var.set(f"已重命名图层为：{new_name}")
            window.destroy()
        ttk.Button(btn_frame, text="应用", command=apply).pack(side=tk.LEFT, padx=5)
        ttk.Button(btn_frame, text="取消", command=window.destroy).pack(side=tk.RIGHT, padx=5)

    def _open_resolution_window(self):
        window = tk.Toplevel(self.root)
        window.title("设置分辨率")
        window.geometry("300x150")
        window.resizable(False, False)
        frame = ttk.Frame(window, padding=10)
        frame.pack(fill=tk.BOTH, expand=True)
        ttk.Label(frame, text="分辨率（宽×高）：").pack(anchor="w", pady=(0, 2))
        resolution_entry = ttk.Entry(frame)
        resolution_entry.insert(0, f"{self.target_resolution[0]}×{self.target_resolution[1]}" if self.custom_resolution is None else f"{self.custom_resolution[0]}×{self.custom_resolution[1]}")
        resolution_entry.pack(fill=tk.X, pady=2)
        btn_frame = ttk.Frame(frame)
        btn_frame.pack(fill=tk.X, pady=10)
        ttk.Button(btn_frame, text="应用", command=lambda: apply()).pack(side=tk.LEFT, padx=5)
        ttk.Button(btn_frame, text="取消", command=window.destroy).pack(side=tk.RIGHT, padx=5)
        def apply():
            try:
                res_text = resolution_entry.get().strip()
                if not res_text:
                    raise ValueError("请输入分辨率")
                parts = res_text.replace("×", "x").split("x")
                if len(parts) != 2:
                    raise ValueError("格式错误，请输入 宽×高")
                width, height = map(int, parts)
                if width <= 0 or height <= 0:
                    raise ValueError("分辨率必须为正整数")
                self.custom_resolution = (width, height)
                self.target_resolution = self.custom_resolution
                # 更新所有图层大小
                for layer in self.layers:
                    if layer["image"]:
                        layer["image"] = layer["image"].resize(self.target_resolution, Image.Resampling.LANCZOS)
                self.reset_view()
                self.canvas.config(width=width, height=height)
                self.redraw_canvas()
                self.status_var.set(f"已设置分辨率：{width}×{height}")
                window.destroy()
            except Exception as e:
                messagebox.showerror("错误", f"无效输入：{e}")

    def _open_auto_mask_threshold_window(self):
        window = tk.Toplevel(self.root)
        window.title("设置自动掩码阈值")
        window.geometry("400x300")
        window.resizable(False, False)
        frame = ttk.Frame(window, padding=10)
        frame.pack(fill=tk.BOTH, expand=True)

        # 灰度阈值
        ttk.Label(frame, text="灰度阈值区间 (min,max)：").pack(anchor="w", pady=(0, 2))
        gray_entry = ttk.Entry(frame)
        gray_entry.insert(0, ",".join(map(str, self.auto_mask_gray_threshold)) if self.auto_mask_gray_threshold else "")
        gray_entry.pack(fill=tk.X, pady=(2, 10))

        # LAB 阈值
        ttk.Label(frame, text="彩色（LAB）阈值 (Lmin,Lmax,Amin,Amax,Bmin,Bmax)：").pack(anchor="w", pady=(0, 2))
        lab_entry = ttk.Entry(frame)
        lab_entry.insert(0, ",".join(map(str, self.auto_mask_lab_threshold)) if self.auto_mask_lab_threshold else "")
        lab_entry.pack(fill=tk.X, pady=2)

        # 按钮
        btn_frame = ttk.Frame(frame)
        btn_frame.pack(fill=tk.X, pady=10)
        ttk.Button(btn_frame, text="应用", command=lambda: apply()).pack(side=tk.LEFT, padx=5)
        ttk.Button(btn_frame, text="取消", command=window.destroy).pack(side=tk.RIGHT, padx=5)

        def apply():
            try:
                # 灰度阈值
                gray_text = gray_entry.get().strip()
                gray_vals = None
                if gray_text:
                    parts = [p.strip() for p in gray_text.replace("，", ",").split(",") if p.strip()]
                    if len(parts) != 2:
                        raise ValueError("灰度阈值请输入两个值（min,max）")
                    min_val, max_val = map(int, parts)
                    if not (0 <= min_val <= max_val <= 255):
                        raise ValueError("灰度阈值必须在0-255之间，且min <= max")
                    gray_vals = (min_val, max_val)

                # LAB 阈值
                lab_text = lab_entry.get().strip()
                lab_vals = None
                if lab_text:
                    parts = [p.strip() for p in lab_text.replace("，", ",").split(",") if p.strip()]
                    if len(parts) != 6:
                        raise ValueError("LAB 阈值请输入六个值（Lmin,Lmax,Amin,Amax,Bmin,Bmax）")
                    lab_vals = list(map(int, parts))
                    Lmin, Lmax, Amin, Amax, Bmin, Bmax = lab_vals
                    if not (0 <= Lmin <= Lmax <= 255 and -128 <= Amin <= Amax <= 127 and -128 <= Bmin <= Bmax <= 127):
                        raise ValueError("LAB 阈值范围无效：L in [0,255], A/B in [-128,127]")
                    lab_vals = (Lmin, Lmax, Amin, Amax, Bmin, Bmax)  # 按新顺序存储

                self.auto_mask_gray_threshold = gray_vals
                self.auto_mask_lab_threshold = lab_vals
                self.status_var.set(f"已设置自动掩码阈值：灰度={gray_vals}, LAB={lab_vals}")
                window.destroy()
            except Exception as e:
                messagebox.showerror("错误", f"无效输入：{e}")

    def _open_playback_interval_window(self):
        window = tk.Toplevel(self.root)
        window.title("设置播放间隔")
        window.geometry("300x150")
        window.resizable(False, False)
        frame = ttk.Frame(window, padding=10)
        frame.pack(fill=tk.BOTH, expand=True)
        ttk.Label(frame, text="播放间隔（秒）：").pack(anchor="w", pady=(0, 2))
        interval_entry = ttk.Entry(frame)
        interval_entry.insert(0, str(self.playback_interval / 1000.0))
        interval_entry.pack(fill=tk.X, pady=2)
        btn_frame = ttk.Frame(frame)
        btn_frame.pack(fill=tk.X, pady=10)
        ttk.Button(btn_frame, text="应用", command=lambda: apply()).pack(side=tk.LEFT, padx=5)
        ttk.Button(btn_frame, text="取消", command=window.destroy).pack(side=tk.RIGHT, padx=5)
        def apply():
            try:
                interval = float(interval_entry.get())
                if interval <= 0:
                    raise ValueError("播放间隔必须为正数")
                self.playback_interval = int(interval * 1000)
                self.status_var.set(f"已设置播放间隔：{interval}秒")
                window.destroy()
            except Exception as e:
                messagebox.showerror("错误", f"无效输入：{e}")

    def toggle_playback(self):
        if self.is_playing:
            self.is_playing = False
            if self.playback_task is not None:
                self.root.after_cancel(self.playback_task)
                self.playback_task = None
            self.layers = self.original_layers.copy()
            self.original_layers = []
            for layer in self.layers:
                layer["alpha"] = 1.0
                layer["hidden"] = False
            self.play_button.configure(text="播放")
            self.update_layer_listbox()
            self.redraw_canvas()
            self.status_var.set("播放已停止，恢复原始图层顺序")
        else:
            if len(self.layers) <= 2:
                messagebox.showerror("错误", "至少需要三个图层以播放")
                return
            self.is_playing = True
            self.playback_index = 2
            self.play_button.configure(text="停止")
            self.original_layers = [
                {
                    "name": layer["name"],
                    "image": layer["image"].copy() if layer["image"] else None,
                    "visible": layer["visible"],
                    "applied": layer["applied"],
                    "alpha": layer["alpha"],
                    "hidden": layer["hidden"]
                } for layer in self.layers
            ]
            second_from_bottom_index = len(self.layers) - 2
            for i in range(len(self.layers)):
                if i == second_from_bottom_index:
                    self.layers[i]["alpha"] = 1.0
                    self.layers[i]["hidden"] = False
                else:
                    self.layers[i]["alpha"] = 0.0
                    self.layers[i]["hidden"] = True
            self.update_layer_listbox()
            self.redraw_canvas()
            self.status_var.set(f"显示图层：{self.layers[second_from_bottom_index]['name']} (置顶到倒数第二位)")
            self.playback_task = self.root.after(self.playback_interval, self._playback_step)

    def _playback_step(self):
        if not self.is_playing:
            self.layers = self.original_layers.copy()
            self.original_layers = []
            for layer in self.layers:
                layer["alpha"] = 1.0
                layer["hidden"] = False
            self.play_button.configure(text="播放")
            self.update_layer_listbox()
            self.redraw_canvas()
            self.status_var.set("播放已停止，恢复原始图层顺序")
            return
        second_from_bottom_index = len(self.layers) - 2
        if self.playback_index == 2:
            self.playback_index += 1
            self.playback_task = self.root.after(self.playback_interval, self._playback_step)
            return
        elif self.playback_index <= len(self.layers):
            current_index = len(self.layers) - self.playback_index
            if current_index >= 0:
                self.layers[current_index], self.layers[second_from_bottom_index] = (
                    self.layers[second_from_bottom_index],
                    self.layers[current_index]
                )
                for i in range(len(self.layers)):
                    if i == second_from_bottom_index:
                        self.layers[i]["alpha"] = 1.0
                        self.layers[i]["hidden"] = False
                    else:
                        self.layers[i]["alpha"] = 0.0
                        self.layers[i]["hidden"] = True
                self.update_layer_listbox()
                self.redraw_canvas()
                self.status_var.set(f"显示图层：{self.layers[second_from_bottom_index]['name']} (置顶到倒数第二位)")
                self.playback_index += 1
                self.playback_task = self.root.after(self.playback_interval, self._playback_step)
            else:
                self.layers[0], self.layers[second_from_bottom_index] = (
                    self.layers[second_from_bottom_index],
                    self.layers[0]
                )
                for i in range(len(self.layers)):
                    if i == second_from_bottom_index:
                        self.layers[i]["alpha"] = 1.0
                        self.layers[i]["hidden"] = False
                    else:
                        self.layers[i]["alpha"] = 0.0
                        self.layers[i]["hidden"] = True
                self.update_layer_listbox()
                self.redraw_canvas()
                self.status_var.set(f"显示图层：{self.layers[second_from_bottom_index]['name']} (置顶到倒数第二位)")
                self.is_playing = False
                self.playback_task = None
                self.layers = self.original_layers.copy()
                self.original_layers = []
                for layer in self.layers:
                    layer["alpha"] = 1.0
                    layer["hidden"] = False
                self.play_button.configure(text="播放")
                self.update_layer_listbox()
                self.redraw_canvas()
                self.status_var.set("播放完成，恢复原始图层顺序")
        else:
            self.is_playing = False
            self.playback_task = None
            self.layers = self.original_layers.copy()
            self.original_layers = []
            for layer in self.layers:
                layer["alpha"] = 1.0
                layer["hidden"] = False
            self.play_button.configure(text="播放")
            self.update_layer_listbox()
            self.redraw_canvas()
            self.status_var.set("播放完成，恢复原始图层顺序")

    def auto_mask(self):
        if len(self.layers) < 2:
            messagebox.showerror("错误", "需要至少两个图层以执行自动掩码")
            return
        bottom_layer = self.layers[-1]
        if not bottom_layer["image"]:
            messagebox.showerror("错误", "底图层没有图像")
            return

        gray_intersection = None
        lab_intersection = None

        # 处理灰度图，仅当灰度阈值非空时
        if self.auto_mask_gray_threshold is not None:
            for layer in self.layers[:-1]:
                if layer["image"] and layer["visible"] and layer["image"].mode == "L":
                    img = layer["image"]
                    if img.size != self.target_resolution:
                        img = img.resize(self.target_resolution, Image.Resampling.LANCZOS)
                    arr = np.array(img)
                    min_thresh, max_thresh = self.auto_mask_gray_threshold
                    binary = (arr >= min_thresh) & (arr <= max_thresh).astype(np.uint8)
                    if gray_intersection is None:
                        gray_intersection = binary
                    else:
                        gray_intersection = np.logical_and(gray_intersection, binary).astype(np.uint8)

        # 处理彩色图，仅当 LAB 阈值非空时
        if self.auto_mask_lab_threshold is not None:
            for layer in self.layers[:-1]:
                if layer["image"] and layer["visible"] and layer["image"].mode == "RGB":
                    img = layer["image"]
                    if img.size != self.target_resolution:
                        img = img.resize(self.target_resolution, Image.Resampling.LANCZOS)
                    img_cv = pil_to_cv(img)
                    img_lab = cv2.cvtColor(img_cv, cv2.COLOR_BGR2LAB)
                    Lmin, Lmax, Amin, Amax, Bmin, Bmax = self.auto_mask_lab_threshold
                    lower = np.array([Lmin, Amin, Bmin], dtype=np.uint8)
                    upper = np.array([Lmax, Amax, Bmax], dtype=np.uint8)
                    mask = cv2.inRange(img_lab, lower, upper)
                    binary = (mask == 255).astype(np.uint8)
                    if lab_intersection is None:
                        lab_intersection = binary
                    else:
                        lab_intersection = np.logical_and(lab_intersection, binary).astype(np.uint8)

        # 处理二值化图，仅当灰度阈值和 LAB 阈值均为空时
        if self.auto_mask_gray_threshold is None and self.auto_mask_lab_threshold is None:
            for layer in self.layers[:-1]:
                if layer["image"] and layer["visible"] and layer["image"].mode == "L":
                    img = layer["image"]
                    if img.size != self.target_resolution:
                        img = img.resize(self.target_resolution, Image.Resampling.LANCZOS)
                    arr = np.array(img)
                    binary = (arr == 255).astype(np.uint8)
                    if gray_intersection is None:
                        gray_intersection = binary
                    else:
                        gray_intersection = np.logical_and(gray_intersection, binary).astype(np.uint8)

        # 合并交集
        final_intersection = None
        if gray_intersection is not None and lab_intersection is not None:
            final_intersection = np.logical_and(gray_intersection, lab_intersection).astype(np.uint8)
        elif gray_intersection is not None:
            final_intersection = gray_intersection
        elif lab_intersection is not None:
            final_intersection = lab_intersection
        else:
            messagebox.showerror("错误", "没有可用的图层用于计算交集")
            return

        # 应用交集到倒数第一个图层
        final_intersection = final_intersection * 255
        bottom_arr = np.array(bottom_layer["image"].convert("L") if bottom_layer["image"].mode != "L" else bottom_layer["image"])
        bottom_arr[final_intersection == 255] = 0
        bottom_layer["image"] = Image.fromarray(bottom_arr, mode="L")
        self.push_history()
        self.redraw_canvas()
        status_msg = "已应用自动掩码到倒数第一个图层"
        if self.auto_mask_gray_threshold:
            status_msg += f"（灰度阈值：{self.auto_mask_gray_threshold}）"
        if self.auto_mask_lab_threshold:
            status_msg += f"（LAB阈值：{self.auto_mask_lab_threshold}）"
        if not self.auto_mask_gray_threshold and not self.auto_mask_lab_threshold:
            status_msg += "（黑白图像白色像素交集）"
        self.status_var.set(status_msg)

    def mask_invert(self):
        if not self.layers or not self.layers[self.current_layer_index]["image"]:
            messagebox.showerror("错误", "当前图层没有图像")
            return
        layer = self.layers[self.current_layer_index]
        img = layer["image"]
        arr = np.array(img.convert("L") if img.mode != "L" else img)
        inverted = arr.copy()
        inverted[arr == 0] = 255
        inverted[arr == 255] = 0
        layer["image"] = Image.fromarray(inverted, mode="L")
        self.push_history()
        self.redraw_canvas()
        self.status_var.set(f"已反转图层 {layer['name']} 的掩码")

    def toggle_layer_panel(self):
        if self.show_layer_panel_var.get():
            if self.layer_panel_frame not in self.content_pane.panes():
                self.content_pane.add(self.layer_panel_frame, weight=1)
        else:
            if self.layer_panel_frame in self.content_pane.panes():
                self.content_pane.remove(self.layer_panel_frame)
                self.layer_panel_frame.pack_forget()

    def toggle_axis(self):
        self.show_axis = self.axis_var.get()
        self.redraw_canvas()

    def open_sorting_window(self):
        if not self.layers:
            messagebox.showerror("错误", "没有图层可排序")
            return
        sort_window = tk.Toplevel(self.root)
        sort_window.title("图层排序")
        sort_window.geometry("400x300")
        sort_window.resizable(False, False)
        frame = ttk.Frame(sort_window, padding=10)
        frame.pack(fill=tk.BOTH, expand=True)
        ttk.Label(frame, text="排序顺序").pack(anchor="w")
        sort_listbox = tk.Listbox(frame, height=10, width=15)
        sort_listbox.pack(side=tk.LEFT, fill=tk.Y, padx=5)
        for name in self.sort_order:
            sort_listbox.insert(tk.END, name)
        ttk.Label(frame, text="所有图层").pack(anchor="w")
        all_listbox = tk.Listbox(frame, height=10)
        all_listbox.pack(side=tk.LEFT, fill=tk.BOTH, expand=True, padx=5)
        for layer in self.layers:
            if layer["name"] not in self.sort_order:
                all_listbox.insert(tk.END, layer["name"])
        btn_frame = ttk.Frame(frame)
        btn_frame.pack(fill=tk.X, pady=10)
        ttk.Button(btn_frame, text="应用排列", command=lambda: self.apply_sorting(sort_listbox, all_listbox, sort_window)).pack(side=tk.LEFT, padx=5)
        ttk.Button(btn_frame, text="取消", command=sort_window.destroy).pack(side=tk.RIGHT, padx=5)
        all_listbox.bind("<Double-1>", lambda e: self.add_to_sort(e, all_listbox, sort_listbox))
        sort_listbox.bind("<Button-1>", lambda e: self.remove_from_sort(e, sort_listbox, all_listbox))

    def add_to_sort(self, event, all_listbox, sort_listbox):
        index = all_listbox.nearest(event.y)
        if 0 <= index < all_listbox.size():
            layer_name = all_listbox.get(index)
            if layer_name not in self.sort_order:
                self.sort_order.append(layer_name)
                sort_listbox.insert(tk.END, layer_name)
                all_listbox.delete(index)
                self.status_var.set(f"已添加 {layer_name} 到排序")

    def remove_from_sort(self, event, sort_listbox, all_listbox):
        index = sort_listbox.nearest(event.y)
        if 0 <= index < sort_listbox.size():
            layer_name = sort_listbox.get(index)
            self.sort_order.pop(index)
            all_listbox.insert(tk.END, layer_name)
            sort_listbox.delete(index)
            self.status_var.set(f"已从排序移除 {layer_name}")

    def apply_sorting(self, sort_listbox, all_listbox, sort_window):
        self.sort_order = list(sort_listbox.get(0, tk.END))
        new_layers = []
        for name in self.sort_order:
            for layer in self.layers:
                if layer["name"] == name:
                    new_layers.append(layer)
                    break
        for layer in self.layers:
            if layer["name"] not in self.sort_order:
                new_layers.append(layer)
        self.layers = new_layers
        self.current_layer_index = min(self.current_layer_index, len(self.layers) - 1)
        self.push_history()
        self.update_layer_listbox()
        self.redraw_canvas()
        self.status_var.set(f"图层已按顺序排序：{', '.join(self.sort_order)}")
        sort_window.destroy()

    def update_layer_listbox(self):
        self.layer_listbox.delete(0, tk.END)
        for i, layer in enumerate(self.layers):
            state = " (已应用)" if layer["applied"] else ""
            hidden_state = " (已隐藏)" if layer["hidden"] else ""
            sort_indicator = " (已排序)" if layer["name"] in self.sort_order else ""
            self.layer_listbox.insert(tk.END, f"{layer['name']}{state}{hidden_state}{sort_indicator}")
        if self.layers:
            self.layer_listbox.select_set(self.current_layer_index)

    def new_layer(self):
        layer_count = len(self.layers) + 1
        new_layer = {
            "name": f"Layer {layer_count}",
            "image": Image.new("L", self.target_resolution, 255),
            "visible": True,
            "applied": False,
            "alpha": 1.0,
            "hidden": False
        }
        self.layers.append(new_layer)
        self.current_layer_index = len(self.layers) - 1
        self.push_history()
        self.update_layer_listbox()
        self.toggle_layer_panel()
        self.redraw_canvas()
        self.status_var.set(f"已创建新图层：{new_layer['name']}")

    def on_layer_select(self, event):
        selection = self.layer_listbox.curselection()
        if selection:
            self.current_layer_index = selection[0]
            self.status_var.set(f"已选择图层：{self.layers[self.current_layer_index]['name']}")

    def delete_layer(self):
        if len(self.layers) <= 1:
            messagebox.showerror("错误", "不能删除最后一个图层")
            return
        if 0 <= self.current_layer_index < len(self.layers):
            layer_name = self.layers[self.current_layer_index]["name"]
            del self.layers[self.current_layer_index]
            self.current_layer_index = min(self.current_layer_index, len(self.layers) - 1)
            self.push_history()
            self.update_layer_listbox()
            self.redraw_canvas()
            self.status_var.set(f"已删除图层：{layer_name}")

    def toggle_layer_visibility(self):
        if not self.layers or self.current_layer_index < 0 or self.current_layer_index >= len(self.layers):
            messagebox.showerror("错误", "请选择一个图层")
            return
        current_layer = self.layers[self.current_layer_index]
        if current_layer["alpha"] == 1.0:
            current_layer["alpha"] = 0.3
            current_layer["hidden"] = True
        else:
            current_layer["alpha"] = 1.0
            current_layer["hidden"] = False
        self.redraw_canvas()
        self.update_layer_listbox()
        self.status_var.set(f"图层 {current_layer['name']} 透明度已{'隐藏' if current_layer['alpha'] < 1.0 else '恢复'}")

    def _open_brush_size_window(self):
        window = tk.Toplevel(self.root)
        window.title("设置画笔大小")
        window.geometry("300x150")
        window.resizable(False, False)
        frame = ttk.Frame(window, padding=10)
        frame.pack(fill=tk.BOTH, expand=True)
        ttk.Label(frame, text="画笔大小（像素）：").pack(anchor="w", pady=(0, 2))
        brush_size_entry = ttk.Entry(frame)
        brush_size_entry.insert(0, str(self.brush_size))
        brush_size_entry.pack(fill=tk.X, pady=2)
        btn_frame = ttk.Frame(frame)
        btn_frame.pack(fill=tk.X, pady=10)
        ttk.Button(btn_frame, text="应用", command=lambda: apply()).pack(side=tk.LEFT, padx=5)
        ttk.Button(btn_frame, text="取消", command=window.destroy).pack(side=tk.RIGHT, padx=5)
        def apply():
            try:
                size = int(brush_size_entry.get())
                if size < 1:
                    raise ValueError("画笔大小必须为正整数")
                self.brush_size = size
                self.status_var.set(f"已设置画笔大小：{size}")
                window.destroy()
            except Exception as e:
                messagebox.showerror("错误", f"无效输入：{e}")

    def _open_merge_factor_window(self):
        window = tk.Toplevel(self.root)
        window.title("设置像素合并因子")
        window.geometry("300x150")
        window.resizable(False, False)
        frame = ttk.Frame(window, padding=10)
        frame.pack(fill=tk.BOTH, expand=True)
        ttk.Label(frame, text="像素合并因子（1=无合并）：").pack(anchor="w", pady=(0, 2))
        merge_factor_entry = ttk.Entry(frame)
        merge_factor_entry.insert(0, str(self.merge_factor))
        merge_factor_entry.pack(fill=tk.X, pady=2)
        btn_frame = ttk.Frame(frame)
        btn_frame.pack(fill=tk.X, pady=10)
        ttk.Button(btn_frame, text="应用", command=lambda: apply()).pack(side=tk.LEFT, padx=5)
        ttk.Button(btn_frame, text="取消", command=window.destroy).pack(side=tk.RIGHT, padx=5)
        def apply():
            try:
                factor = int(merge_factor_entry.get())
                if factor < 1:
                    raise ValueError("合并因子必须为正整数")
                self.merge_factor = factor
                self.redraw_canvas()
                self.status_var.set(f"已设置像素合并因子：{factor}")
                window.destroy()
            except Exception as e:
                messagebox.showerror("错误", f"无效输入：{e}")

    def _open_threshold_window(self):
        window = tk.Toplevel(self.root)
        window.title("设置阈值")
        window.geometry("400x250")
        window.resizable(False, False)
        frame = ttk.Frame(window, padding=10)
        frame.pack(fill=tk.BOTH, expand=True)
        ttk.Label(frame, text="LAB 阈值 (Lmin,Lmax,Amin,Amax,Bmin,Bmax)：").pack(anchor="w")
        lab_entry = ttk.Entry(frame)
        lab_entry.insert(0, ",".join(map(str, self.threshold_lab)))
        lab_entry.pack(fill=tk.X, pady=2)
        ttk.Label(frame, text="灰度阈值 (min,max)：").pack(anchor="w", pady=(10, 2))
        gray_entry = ttk.Entry(frame)
        gray_entry.insert(0, ",".join(map(str, self.threshold_gray)))
        gray_entry.pack(fill=tk.X, pady=2)
        btn_frame = ttk.Frame(frame)
        btn_frame.pack(fill=tk.X, pady=10)
        ttk.Button(btn_frame, text="应用", command=lambda: apply()).pack(side=tk.LEFT, padx=5)
        ttk.Button(btn_frame, text="取消", command=window.destroy).pack(side=tk.RIGHT, padx=5)
        def apply():
            try:
                lab_text = lab_entry.get().strip()
                lab_vals = self._parse_lab_entry(lab_text)
                if lab_vals:
                    self.threshold_lab = lab_vals
                gray_text = gray_entry.get().strip()
                gray_vals = self._parse_gray_entry(gray_text)
                if gray_vals[0] is not None:
                    self.threshold_gray = gray_vals
                self.status_var.set("已设置阈值")
                window.destroy()
            except Exception as e:
                messagebox.showerror("错误", f"无效输入：{e}")

    def _show_help(self):
        messagebox.showinfo("使用说明", "拖拽框选编辑；滚轮缩放；中键拖动平移；网格模式下点击切换像素或拖拽范围编辑；导入可选择灰度化、二值化或彩色化 / 裁剪；图层功能支持新建、选择、删除、隐藏、排序和右键重命名；播放功能先显示倒数第二个图层，等待间隔后从倒数第三个图层开始逐层与倒数第二个图层交换并显示（间隔可设置，默认3秒），仅倒数第二个图层可见，最后一步将第一个图层与倒数第二个图层交换，播放结束后恢复原始顺序；自动掩码根据灰度阈值（若设置）处理灰度图、LAB阈值（若设置，格式：Lmin,Lmax,Amin,Amax,Bmin,Bmax）处理彩色图，或两者均空时查找黑白图像白色像素交集，应用到倒数第一个图层；掩码反转将选定图层的黑白像素互换；设置分辨率可自定义分辨率（格式：宽×高），默认生成 VGA (640x480) 白板。")

    def generate_white(self):
        """Generate a new white canvas with custom or default VGA resolution."""
        self.target_resolution = self.custom_resolution if self.custom_resolution else DEFAULT_RESOLUTION
        w, h = self.target_resolution
        self.layers = [{
            "name": "Layer 1",
            "image": Image.new("L", (w, h), 255),
            "visible": True,
            "applied": False,
            "alpha": 1.0,
            "hidden": False
        }]
        self.current_layer_index = 0
        self.original_image = self.layers[0]["image"].copy()
        self.push_history()
        self.reset_view()
        self.canvas.config(width=w, height=h)
        self.update_layer_listbox()
        self.redraw_canvas()
        self.status_var.set(f"已生成白板 {w}x{h}")

    def import_image_dialog(self):
        path = filedialog.askopenfilename(filetypes=[("图像", "*.png;*.jpg;*.jpeg;*.bmp"), ("所有文件", "*.*")])
        if not path:
            return
        try:
            img = Image.open(path)
        except Exception as e:
            messagebox.showerror("处理错误", f"打开图像失败：{e}")
            return
        mode = self.import_mode_var.get()
        try:
            if mode == "灰度化":
                img = img.convert("L") if img.mode != "L" else img
            elif mode == "二值化":
                if img.mode != "L":
                    Lmin, Lmax, Amin, Amax, Bmin, Bmax = self.threshold_lab
                    img_cv = cv2.cvtColor(np.array(img.convert("RGB")), cv2.COLOR_RGB2LAB)
                    lower = np.array([Lmin, Amin, Bmin], dtype=np.uint8)
                    upper = np.array([Lmax, Amax, Bmax], dtype=np.uint8)
                    mask = cv2.inRange(img_cv, lower, upper)
                    img = Image.fromarray(mask).convert("L")
                else:
                    gmin, gmax = self.threshold_gray
                    arr = np.array(img)
                    mask = np.where((arr >= gmin) & (arr <= gmax), 255, 0).astype(np.uint8)
                    img = Image.fromarray(mask, mode="L")
            else:  # 彩色化
                img = img.convert("RGB") if img.mode != "RGB" else img
            self._open_crop_preview(img)
        except Exception as e:
            messagebox.showerror("处理错误", f"导入处理失败：{e}")

    def _parse_lab_entry(self, text):
        if not text:
            return None
        parts = [p.strip() for p in text.replace("，", ",").split(",") if p.strip() != ""]
        if len(parts) != 6:
            return None
        try:
            Lmin, Lmax, Amin, Amax, Bmin, Bmax = map(int, parts)
            if not (0 <= Lmin <= Lmax <= 255 and -128 <= Amin <= Amax <= 127 and -128 <= Bmin <= Bmax <= 127):
                return None
            return (Lmin, Lmax, Amin, Amax, Bmin, Bmax)
        except:
            return None

    def _parse_gray_entry(self, text):
        if not text:
            return (None, None)
        parts = [p.strip() for p in text.replace("，", ",").split(",") if p.strip() != ""]
        if len(parts) != 2:
            return (None, None)
        try:
            return (int(parts[0]), int(parts[1]))
        except:
            return (None, None)

    def _open_crop_preview(self, img_pil):
        target_w, target_h = self.target_resolution
        preview = tk.Toplevel(self.root)
        preview.title("导入预览与裁剪")
        preview.geometry("900x700")
        preview.resizable(True, True)
        frame = ttk.Frame(preview, padding=8)
        frame.pack(fill=tk.BOTH, expand=True)
        canvas = tk.Canvas(frame, bg="#222222")
        canvas.pack(fill=tk.BOTH, expand=True)
        status_var = tk.StringVar(value="拖动鼠标框选裁剪区域或使用下方按钮")
        ttk.Label(frame, textvariable=status_var).pack(fill=tk.X, pady=4)
        btn_frame = ttk.Frame(frame)
        btn_frame.pack(fill=tk.X, pady=6)
        ttk.Label(btn_frame, text=f"目标分辨率：{target_w} x {target_h}").pack(side=tk.LEFT, padx=5)
        src_w, src_h = img_pil.size
        self._preview_img = img_pil.copy()
        self._preview_tk = None
        self._preview_scale = 1.0
        self._preview_pos = (0, 0)
        def draw_fitted():
            canvas.delete("all")
            cw = max(100, canvas.winfo_width())
            ch = max(100, canvas.winfo_height())
            ratio = min((cw - 20) / src_w, (ch - 20) / src_h, 1.0)
            self._preview_scale = ratio
            disp_w = int(src_w * ratio)
            disp_h = int(src_h * ratio)
            self._preview_img_disp = img_pil.resize((disp_w, disp_h), Image.Resampling.LANCZOS)
            self._preview_tk = ImageTk.PhotoImage(self._preview_img_disp)
            self._preview_pos = ((cw - disp_w) // 2, (ch - disp_h) // 2)
            canvas.create_image(self._preview_pos[0], self._preview_pos[1], anchor="nw", image=self._preview_tk)
            if src_w >= target_w and src_h >= target_h:
                canvas.create_text(10, 10, anchor="nw", text="拖动鼠标框选裁剪区域（放开确认）", fill="white", font=("Arial", 12))
            else:
                canvas.create_text(10, 10, anchor="nw", text="图像小于目标分辨率，可选择放大或居中", fill="white", font=("Arial", 12))
        canvas.bind("<Configure>", lambda e: draw_fitted())
        draw_fitted()
        crop_rect = None
        start = None
        def on_down(e):
            nonlocal start, crop_rect
            if src_w < target_w or src_h < target_h:
                return
            start = (e.x, e.y)
            if crop_rect:
                canvas.delete(crop_rect)
                crop_rect = None
        def on_drag(e):
            nonlocal crop_rect
            if not start:
                return
            x1, y1 = start
            x2, y2 = e.x, e.y
            if crop_rect:
                canvas.delete(crop_rect)
            crop_rect = canvas.create_rectangle(x1, y1, x2, y2, outline="red", width=2)
            px, py = self._preview_pos
            sx1 = int(max(0, (min(x1, x2) - px) / self._preview_scale))
            sy1 = int(max(0, (min(y1, y2) - py) / self._preview_scale))
            sx2 = int(min(src_w, (max(x1, x2) - px) / self._preview_scale))
            sy2 = int(min(src_h, (max(y1, y2) - py) / self._preview_scale))
            status_var.set(f"裁剪区域：{sx2 - sx1} x {sy2 - sy1} (目标：{target_w} x {target_h})")
        def on_up(e):
            nonlocal crop_rect, img_pil
            if not start:
                return
            x1, y1 = start
            x2, y2 = e.x, e.y
            px, py = self._preview_pos
            sx1 = int(max(0, (min(x1, x2) - px) / self._preview_scale))
            sy1 = int(max(0, (min(y1, y2) - py) / self._preview_scale))
            sx2 = int(min(src_w, (max(x1, x2) - px) / self._preview_scale))
            sy2 = int(min(src_h, (max(y1, y2) - py) / self._preview_scale))
            if sx2 <= sx1 or sy2 <= sy1:
                status_var.set("裁剪区域无效，请重新选择")
                return
            cropped = img_pil.crop((sx1, sy1, sx2, sy2))
            if cropped.width != target_w or cropped.height != target_h:
                cropped = cropped.resize((target_w, target_h), Image.Resampling.LANCZOS)
            self._add_image_to_new_layer(cropped)
            preview.destroy()
            self.reset_view()
            self.canvas.config(width=target_w, height=target_h)
            self.redraw_canvas()
            self.status_var.set(f"已裁剪并应用图像：{target_w}x{target_h}")
        canvas.bind("<ButtonPress-1>", on_down)
        canvas.bind("<B1-Motion>", on_drag)
        canvas.bind("<ButtonRelease-1>", on_up)
        def center_and_use():
            if src_w >= target_w and src_h >= target_h:
                messagebox.showinfo("提示", "图像大于或等于目标分辨率，请裁剪")
                return
            new = Image.new(img_pil.mode, (target_w, target_h), 255 if img_pil.mode == "L" else (255, 255, 255))
            ox = (target_w - src_w) // 2
            oy = (target_h - src_h) // 2
            new.paste(img_pil, (ox, oy))
            self._add_image_to_new_layer(new)
            preview.destroy()
            self.reset_view()
            self.canvas.config(width=target_w, height=target_h)
            self.redraw_canvas()
            self.status_var.set(f"已居中并补白：{target_w}x{target_h}")
        def scale_up_to_target():
            if src_w >= target_w and src_h >= target_h:
                messagebox.showinfo("提示", "图像大于或等于目标分辨率，请裁剪")
                return
            new = img_pil.resize((target_w, target_h), Image.Resampling.LANCZOS)
            self._add_image_to_new_layer(new)
            preview.destroy()
            self.reset_view()
            self.canvas.config(width=target_w, height=target_h)
            self.redraw_canvas()
            self.status_var.set(f"已放大到目标分辨率：{target_w}x{target_h}")
        is_small = src_w < target_w or src_h < target_h
        ttk.Button(btn_frame, text="居中并补白（小图）", command=center_and_use, state="normal" if is_small else "disabled").pack(side=tk.LEFT, padx=6)
        ttk.Button(btn_frame, text="放大到目标（小图）", command=scale_up_to_target, state="normal" if is_small else "disabled").pack(side=tk.LEFT, padx=6)
        ttk.Button(btn_frame, text="取消", command=preview.destroy).pack(side=tk.RIGHT, padx=6)

    def _add_image_to_new_layer(self, img):
        layer_count = len(self.layers) + 1
        new_layer = {
            "name": f"Layer {layer_count}",
            "image": img,
            "visible": True,
            "applied": False,
            "alpha": 1.0,
            "hidden": False
        }
        self.layers.append(new_layer)
        self.current_layer_index = len(self.layers) - 1
        self.original_image = img.copy()
        self.push_history()
        self.update_layer_listbox()
        self.toggle_layer_panel()

    def reset_view(self):
        self.scale = 1.0
        self.offset_x = 0
        self.offset_y = 0
        self.pan_start = None
        self.selected_region = None

    def redraw_canvas(self, *_):
        try:
            self.canvas.delete("all")
            if not self.layers or not any(layer["image"] for layer in self.layers):
                self.show_placeholder()
                return
            # 动态选择复合模式：使用最顶层可见图层的模式
            mode = "L"
            for layer in self.layers[::-1]:  # 从上到下检查可见图层
                if layer["image"] and layer["visible"] and not layer["hidden"]:
                    mode = layer["image"].mode
                    break
            composite = composite_layers(self.layers, self.target_resolution, mode, apply_alpha=True)
            img_w, img_h = composite.size
            disp_w = int(img_w * self.scale)
            disp_h = int(img_h * self.scale)
            disp = composite.resize((disp_w, disp_h), Image.Resampling.NEAREST if self.grid_var.get() else Image.Resampling.LANCZOS)
            self.tk_img = ImageTk.PhotoImage(disp)
            cw = self.canvas_bg.winfo_width() or 640
            ch = self.canvas_bg.winfo_height() or 480
            cx = max(10, (cw - disp_w) // 2 + self.offset_x)
            cy = max(10, (ch - disp_h) // 2 + self.offset_y)
            self.canvas.config(width=max(cw, img_w), height=max(ch, img_h))
            self.canvas.create_image(cx, cy, anchor="nw", image=self.tk_img, tags="img")
            self.canvas.create_rectangle(cx - 1, cy - 1, cx + disp_w + 1, cy + disp_h + 1, outline="gray", width=1)
            self.img_render_origin = (cx, cy)
            if self.grid_var.get():
                self._draw_pixel_grid(cx, cy, img_w, img_h)
            if self.show_axis:
                self._draw_axis(cx, cy, img_w, img_h)
            if self.selected_region:
                sx1, sy1, sx2, sy2 = self.selected_region
                dx1 = cx + sx1 * self.scale
                dy1 = cy + sy1 * self.scale
                dx2 = cx + sx2 * self.scale
                dy2 = cy + sy2 * self.scale
                self.canvas.create_rectangle(dx1, dy1, dx2, dy2, outline="blue", width=2, tags="selection")
            self.status_var.set(f"图像: {img_w}x{img_h} 显示: {disp_w}x{disp_h} 缩放: {self.scale:.2f}")
        except Exception as e:
            print(f"redraw_canvas 错误: {e}")
            self.status_var.set(f"渲染错误: {str(e)}")
            self.show_placeholder()

    def _draw_pixel_grid(self, cx, cy, img_w, img_h):
        s = self.scale
        m = self.merge_factor
        if s * m < 4:
            self.canvas.create_text(cx + 8, cy + 12, anchor="nw", text="缩放到更大以显示像素网格", fill="red")
            return
        for i in range(0, img_w, m):
            x = cx + int(i * s)
            self.canvas.create_line(x, cy, x, cy + int(img_h * s), fill="#888", width=1)
        for j in range(0, img_h, m):
            y = cy + int(j * s)
            self.canvas.create_line(cx, y, cx + int(img_w * s), y, fill="#888", width=1)

    def _draw_axis(self, cx, cy, img_w, img_h):
        s = self.scale
        step = 10
        for i in range(0, img_w + 1, step):
            x = cx + int(i * s)
            self.canvas.create_line(x, cy, x, cy + 5, fill="black")
            if i % 50 == 0:
                self.canvas.create_text(x, cy + 10, text=str(i), anchor="n", fill="black")
            elif i % 10 == 0:
                self.canvas.create_text(x, cy + 8, text=str(i), anchor="n", fill="black", font=("Arial", 8))
        for j in range(0, img_h + 1, step):
            y = cy + int(j * s)
            self.canvas.create_line(cx, y, cx + 5, y, fill="black")
            if j % 50 == 0:
                self.canvas.create_text(cx + 10, y, text=str(j), anchor="w", fill="black")
            elif j % 10 == 0:
                self.canvas.create_text(cx + 8, y, text=str(j), anchor="w", fill="black", font=("Arial", 8))

    def set_tool(self, t):
        self.tool = t
        self.status_var.set(f"工具：{'画黑(矩形)' if t == 'paint' else '擦除(矩形)' if t == 'erase' else '画笔' if t == 'brush' else '选择'}")
        if t != "select":
            self.selected_region = None
        self.redraw_canvas()

    def on_left_down(self, event):
        if not self.layers or not self.layers[self.current_layer_index]["image"]:
            return
        if self.tool == "select":
            ix, iy = self._screen_to_image(event.x, event.y)
            if self.selected_region is None:
                self._select_image_region(ix, iy)
                if self.selected_region:
                    self.redraw_canvas()
                    self.status_var.set(f"已选择图像区域：{self.selected_region}")
                    return
            else:
                m = self.merge_factor
                ix = (ix // m) * m
                iy = (iy // m) * m
                sx1, sy1, sx2, sy2 = self.selected_region
                if sx1 <= ix < sx2 and sy1 <= iy < sy2:
                    self.drag_start = (event.x, event.y, sx1, sy1)
                    return
        self.drag_start = (event.x, event.y)
        if self.grid_var.get() and self.tool in ["paint", "erase"]:
            self._toggle_pixel(event, preview=False)
        elif self.tool in ["paint", "erase"]:
            ix, iy = self._screen_to_image(event.x, event.y)
            m = self.merge_factor
            ix = (ix // m) * m
            iy = (iy // m) * m
            self.status_var.set(f"框选起始位置: ({ix}, {iy})")

    def _select_image_region(self, ix, iy):
        if not self.layers or not self.layers[self.current_layer_index]["image"]:
            return
        arr = np.array(self.layers[self.current_layer_index]["image"])
        if self.layers[self.current_layer_index]["image"].mode == "RGB":
            arr = cv2.cvtColor(arr, cv2.COLOR_RGB2GRAY)
        non_white = arr != 255
        if not non_white.any():
            return
        rows, cols = np.where(non_white)
        x1, x2 = cols.min(), cols.max() + 1
        y1, y2 = rows.min(), rows.max() + 1
        if x1 <= ix < x2 and y1 <= iy < y2:
            self.selected_region = (x1, y1, x2, y2)

    def on_left_drag(self, event):
        if not self.layers or not self.layers[self.current_layer_index]["image"] or self.drag_start is None:
            return
        x0, y0 = self.drag_start[:2]
        x1, y1 = event.x, event.y
        if self.tool == "brush":
            self._draw_brush(event)
            return
        elif self.tool == "select" and len(self.drag_start) == 4:
            self._move_selection(event)
            return
        ix0, iy0, ix1, iy1 = self._screen_to_image_rect(x0, y0, x1, y1)
        m = self.merge_factor
        ix0 = (ix0 // m) * m
        iy0 = (iy0 // m) * m
        ix1 = ((ix1 + m - 1) // m) * m
        iy1 = ((iy1 + m - 1) // m) * m
        if self.tool == "select":
            if ix1 > ix0 and iy1 > iy0:
                self.selected_region = (ix0, iy0, ix1, iy1)
            self.redraw_canvas()
            self.status_var.set(f"框选区域: ({ix0}, {iy0}) 到 ({ix1}, {iy1})")
            return
        if self.tool in ["paint", "erase"]:
            arr = np.array(self.layers[self.current_layer_index]["image"])
            color = 0 if self.tool == "paint" else 255
            if self.layers[self.current_layer_index]["image"].mode == "RGB":
                color = (0, 0, 0) if self.tool == "paint" else (255, 255, 255)
                if ix1 > ix0 and iy1 > iy0:
                    arr[iy0:iy1, ix0:ix1, :] = color
            else:
                if ix1 > ix0 and iy1 > iy0:
                    arr[iy0:iy1, ix0:ix1] = color
            self.layers[self.current_layer_index]["image"] = Image.fromarray(arr, mode=self.layers[self.current_layer_index]["image"].mode)
            self.redraw_canvas()
            self.status_var.set(f"框选区域: ({ix0}, {iy0}) 到 ({ix1}, {iy1})")

    def on_left_up(self, event):
        if not self.layers or not self.layers[self.current_layer_index]["image"] or self.drag_start is None:
            return
        x0, y0 = self.drag_start[:2]
        x1, y1 = event.x, event.y
        if self.tool == "brush":
            self.layers[self.current_layer_index]["image"] = self.layers[self.current_layer_index]["image"].copy()
            self.push_history()
            self.redraw_canvas()
            self.status_var.set("已完成自由画笔编辑")
        elif self.tool == "select" and len(self.drag_start) == 4:
            self._finalize_move(event)
        elif self.grid_var.get() and self.tool in ["paint", "erase"]:
            self._toggle_pixel(event, preview=False)
            self.redraw_canvas()
        elif self.tool in ["paint", "erase"]:
            self.push_history()
            self.redraw_canvas()
        self.drag_start = None

    def _toggle_pixel(self, event, preview=False):
        if not self.layers or not self.layers[self.current_layer_index]["image"]:
            return
        ix, iy = self._screen_to_image(event.x, event.y)
        m = self.merge_factor
        ix = (ix // m) * m
        iy = (iy // m) * m
        target = self.layers[self.current_layer_index]["image"]
        arr = np.array(target)
        if target.mode == "RGB":
            current = arr[iy:iy+m, ix:ix+m, 0]
            new_val = (0, 0, 0) if current.mean() > 128 else (255, 255, 255)
            arr[iy:iy+m, ix:ix+m, :] = new_val
        else:
            current = arr[iy:iy+m, ix:ix+m]
            new_val = 0 if current.mean() > 128 else 255
            arr[iy:iy+m, ix:ix+m] = new_val
        self.layers[self.current_layer_index]["image"] = Image.fromarray(arr, mode=target.mode)
        if not preview:
            self.push_history()
            self.redraw_canvas()
            self.status_var.set(f"切换像素 ({ix}, {iy}) 为 {'黑' if new_val == 0 or new_val == (0, 0, 0) else '白'}")

    def _draw_brush(self, event):
        if not self.layers or not self.layers[self.current_layer_index]["image"] or self.drag_start is None:
            return
        try:
            size = int(self.brush_size)
            if size < 1:
                raise ValueError
        except:
            self.brush_size = 5
        ix, iy = self._screen_to_image(event.x, event.y)
        m = self.merge_factor
        ix = (ix // m) * m
        iy = (iy // m) * m
        draw = ImageDraw.Draw(self.layers[self.current_layer_index]["image"])
        r = self.brush_size
        left = max(0, ix - r)
        top = max(0, iy - r)
        right = min(self.layers[self.current_layer_index]["image"].width, ix + r + m)
        bottom = min(self.layers[self.current_layer_index]["image"].height, iy + r + m)
        color = 0 if self.tool == "brush" else 255
        if self.layers[self.current_layer_index]["image"].mode == "RGB":
            color = (0, 0, 0) if self.tool == "brush" else (255, 255, 255)
        draw.ellipse([left, top, right, bottom], fill=color)
        self.redraw_canvas()

    def copy_region(self):
        if not self.layers or not self.layers[self.current_layer_index]["image"] or self.selected_region is None:
            messagebox.showerror("错误", "请先选择一个区域")
            return
        sx1, sy1, sx2, sy2 = self.selected_region
        self.copied_region = self.layers[self.current_layer_index]["image"].crop((sx1, sy1, sx2, sy2))
        self.status_var.set("已复制选定区域")

    def paste_region(self):
        if not self.layers or not self.layers[self.current_layer_index]["image"] or self.copied_region is None:
            messagebox.showerror("错误", "没有复制的区域可粘贴")
            return
        new = self.layers[self.current_layer_index]["image"].copy()
        new.paste(self.copied_region, (0, 0))
        self.layers[self.current_layer_index]["image"] = new
        self.push_history()
        self.redraw_canvas()
        self.status_var.set("已粘贴区域到 (0, 0)")

    def delete_region(self):
        if not self.layers or not self.layers[self.current_layer_index]["image"] or self.selected_region is None:
            messagebox.showerror("错误", "请先选择一个区域")
            return
        sx1, sy1, sx2, sy2 = self.selected_region
        draw = ImageDraw.Draw(self.layers[self.current_layer_index]["image"])
        fill_color = 255 if self.layers[self.current_layer_index]["image"].mode == "L" else (255, 255, 255)
        draw.rectangle((sx1, sy1, sx2, sy2), fill=fill_color)
        self.push_history()
        self.selected_region = None
        self.redraw_canvas()
        self.status_var.set("已删除选定区域")

    def _move_selection(self, event):
        x0, y0, sx0, sy0 = self.drag_start
        dx = int((event.x - x0) / self.scale)
        dy = int((event.y - y0) / self.scale)
        m = self.merge_factor
        dx = (dx // m) * m
        dy = (dy // m) * m
        sx1, sy1, sx2, sy2 = self.selected_region
        new_x1 = max(0, min(self.layers[self.current_layer_index]["image"].width - (sx2 - sx1), sx0 + dx))
        new_y1 = max(0, min(self.layers[self.current_layer_index]["image"].height - (sy2 - sy1), sy0 + dy))
        self.selected_region = (new_x1, new_y1, new_x1 + (sx2 - sx1), new_y1 + (sy2 - sy1))
        self.redraw_canvas()

    def _finalize_move(self, event):
        x0, y0, sx0, sy0 = self.drag_start
        dx = int((event.x - x0) / self.scale)
        dy = int((event.y - y0) / self.scale)
        m = self.merge_factor
        dx = (dx // m) * m
        dy = (dy // m) * m
        sx1, sy1, sx2, sy2 = self.selected_region
        new_x1 = max(0, min(self.layers[self.current_layer_index]["image"].width - (sx2 - sx1), sx0 + dx))
        new_y1 = max(0, min(self.layers[self.current_layer_index]["image"].height - (sy2 - sy1), sy0 + dy))
        self.selected_region = (new_x1, new_y1, new_x1 + (sx2 - sx1), new_y1 + (sy2 - sy1))
        img = self.layers[self.current_layer_index]["image"]
        region = img.crop((sx0, sy0, sx2, sy2))
        fill_color = 255 if img.mode == "L" else (255, 255, 255)
        draw = ImageDraw.Draw(img)
        draw.rectangle((sx0, sy0, sx2, sy2), fill=fill_color)
        img.paste(region, (new_x1, new_y1))
        self.layers[self.current_layer_index]["image"] = img
        self.push_history()
        self.redraw_canvas()
        self.status_var.set(f"已移动选定区域到 ({new_x1}, {new_y1})")
        self.drag_start = None

    def on_middle_down(self, event):
        self.pan_start = (event.x, event.y, self.offset_x, self.offset_y)

    def on_middle_drag(self, event):
        if self.pan_start is None:
            return
        x0, y0, ox, oy = self.pan_start
        self.offset_x = ox + (event.x - x0)
        self.offset_y = oy + (event.y - y0)
        self.redraw_canvas()

    def on_middle_up(self, event):
        self.pan_start = None

    def on_mousewheel(self, event):
        if not self.layers or not self.layers[self.current_layer_index]["image"]:
            return
        delta = event.delta or (-event.num + 4) * 120
        factor = 1.1 if delta > 0 else 0.9
        old_scale = self.scale
        self.scale = max(0.1, min(self.scale * factor, 10.0))
        cx, cy = self._screen_to_image(event.x, event.y)
        self.offset_x = int(self.offset_x * self.scale / old_scale + event.x * (1 - self.scale / old_scale))
        self.offset_y = int(self.offset_y * self.scale / old_scale + event.y * (1 - self.scale / old_scale))
        self.redraw_canvas()

    def _screen_to_image(self, x, y):
        """Convert screen coordinates to image coordinates."""
        if not self.layers or not self.layers[self.current_layer_index]["image"]:
            return 0, 0
        cx, cy = self.img_render_origin
        ix = int((x - cx) / self.scale)
        iy = int((y - cy) / self.scale)
        return ix, iy

    def _screen_to_image_rect(self, x0, y0, x1, y1):
        """Convert screen rectangle coordinates to image rectangle coordinates."""
        if not self.layers or not self.layers[self.current_layer_index]["image"]:
            return 0, 0, 0, 0
        cx, cy = self.img_render_origin
        ix0 = int((min(x0, x1) - cx) / self.scale)
        iy0 = int((min(y0, y1) - cy) / self.scale)
        ix1 = int((max(x0, x1) - cx) / self.scale)
        iy1 = int((max(y0, y1) - cy) / self.scale)
        img_w, img_h = self.layers[self.current_layer_index]["image"].size
        ix0 = max(0, min(ix0, img_w))
        iy0 = max(0, min(iy0, img_h))
        ix1 = max(0, min(ix1, img_w))
        iy1 = max(0, min(iy1, img_h))
        return ix0, iy0, ix1, iy1

    def start_move_layer_panel(self, event):
        self.layer_panel_moving = True
        self.layer_panel_start_x = event.x_root - self.layer_panel_frame.winfo_x()
        self.layer_panel_start_y = event.y_root - self.layer_panel_frame.winfo_y()

    def move_layer_panel(self, event):
        if not self.layer_panel_moving:
            return
        x = event.x_root - self.layer_panel_start_x
        y = event.y_root - self.layer_panel_start_y
        self.layer_panel_frame.place(x=x, y=y)

    def stop_move_layer_panel(self, event):
        self.layer_panel_moving = False

    def show_placeholder(self):
        """Display a placeholder when no image is available."""
        self.canvas.delete("all")
        w, h = self.canvas.winfo_width() or 640, self.canvas.winfo_height() or 480
        self.canvas.config(width=w, height=h)
        self.canvas.create_text(w // 2, h // 2, text="无图像，请导入或生成白板", fill="gray", font=("Arial", 12))

    def save_mask(self):
        """Save the composite mask image."""
        if not self.layers or not any(layer["image"] for layer in self.layers):
            messagebox.showerror("错误", "没有图像可保存")
            return
        composite = composite_layers(self.layers, self.target_resolution, "L")
        path = filedialog.asksaveasfilename(defaultextension=".png", filetypes=[("PNG", "*.png"), ("所有文件", "*.*")])
        if path:
            try:
                composite.save(path)
                self.status_var.set(f"已保存掩码到 {path}")
            except Exception as e:
                messagebox.showerror("错误", f"保存失败：{e}")

    def quick_save(self):
        """Quick save the composite mask with a timestamped filename."""
        if not self.layers or not any(layer["image"] for layer in self.layers):
            messagebox.showerror("错误", "没有图像可保存")
            return
        composite = composite_layers(self.layers, self.target_resolution, "L")
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        filename = f"mask_{timestamp}.png"
        try:
            composite.save(filename)
            self.status_var.set(f"已快速保存掩码到 {filename}")
        except Exception as e:
            messagebox.showerror("错误", f"快速保存失败：{e}")

    def push_history(self):
        """Save current state to undo stack."""
        state = [
            {
                "name": layer["name"],
                "image": layer["image"].copy() if layer["image"] else None,
                "visible": layer["visible"],
                "applied": layer["applied"],
                "alpha": layer["alpha"],
                "hidden": layer["hidden"]
            } for layer in self.layers
        ]
        self.undo_stack.append((state, self.current_layer_index))
        self.redo_stack.clear()
        while len(self.undo_stack) > 50:
            self.undo_stack.pop(0)

    def undo(self):
        """Undo the last action."""
        if not self.undo_stack:
            return
        state, current_layer_index = self.undo_stack.pop()
        self.redo_stack.append((
            [
                {
                    "name": layer["name"],
                    "image": layer["image"].copy() if layer["image"] else None,
                    "visible": layer["visible"],
                    "applied": layer["applied"],
                    "alpha": layer["alpha"],
                    "hidden": layer["hidden"]
                } for layer in self.layers
            ],
            self.current_layer_index
        ))
        self.layers = state
        self.current_layer_index = current_layer_index
        self.update_layer_listbox()
        self.redraw_canvas()
        self.status_var.set("已撤销")

    def redo(self):
        """Redo the last undone action."""
        if not self.redo_stack:
            return
        state, current_layer_index = self.redo_stack.pop()
        self.undo_stack.append((
            [
                {
                    "name": layer["name"],
                    "image": layer["image"].copy() if layer["image"] else None,
                    "visible": layer["visible"],
                    "applied": layer["applied"],
                    "alpha": layer["alpha"],
                    "hidden": layer["hidden"]
                } for layer in self.layers
            ],
            self.current_layer_index
        ))
        self.layers = state
        self.current_layer_index = current_layer_index
        self.update_layer_listbox()
        self.redraw_canvas()
        self.status_var.set("已重做")

    def reset(self):
        """Reset all states to initial."""
        if messagebox.askyesno("确认", "重置将清除所有图层和历史记录，是否继续？"):
            self.target_resolution = self.custom_resolution if self.custom_resolution else DEFAULT_RESOLUTION
            self.layers = [{
                "name": "Layer 1",
                "image": Image.new("L", self.target_resolution, 255),
                "visible": True,
                "applied": False,
                "alpha": 1.0,
                "hidden": False
            }]
            self.current_layer_index = 0
            self.undo_stack.clear()
            self.redo_stack.clear()
            self.sort_order.clear()
            self.original_image = None
            self.copied_region = None
            self.selected_region = None
            self.reset_view()
            self.update_layer_listbox()
            self.redraw_canvas()
            self.status_var.set("已重置编辑器")

if __name__ == "__main__":
    root = tk.Tk()
    app = MaskEditorApp(root)
    if platform.system() == "Emscripten":
        asyncio.ensure_future(asyncio.sleep(0))
    else:
        root.mainloop()