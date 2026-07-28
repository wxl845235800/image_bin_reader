import tkinter as tk
from tkinter import ttk, filedialog, messagebox
import os
import numpy as np
from PIL import Image, ImageTk

# Try to import tkinterdnd2 for drag-and-drop support
try:
    from tkinterdnd2 import DND_FILES, TkinterDnD
    HAS_DND = True
except ImportError:
    HAS_DND = False

# BIN 格式: 纯 RGB planar 数据，无任何头部
#   RRR...GGG...BBB... (所有 R 通道像素，然后所有 G，然后所有 B)
#   存储格式: 可选择 uint8 或 float32（与数值范围无关）

# ---- 图像处理函数 ----

RESIZE_STRETCH = 'stretch'
RESIZE_CROP = 'crop'

def resize_and_crop_image(img, target_w, target_h, mode):
    if target_w <= 0 or target_h <= 0:
        return img
    if mode == RESIZE_STRETCH:
        return img.resize((target_w, target_h), Image.LANCZOS)
    elif mode == RESIZE_CROP:
        src_w, src_h = img.size
        scale = max(target_w / src_w, target_h / src_h)
        new_w = int(round(src_w * scale))
        new_h = int(round(src_h * scale))
        img_resized = img.resize((new_w, new_h), Image.LANCZOS)
        left = (new_w - target_w) // 2
        top = (new_h - target_h) // 2
        return img_resized.crop((left, top, left + target_w, top + target_h))
    return img


def rgb_to_planar(img_array):
    """HWC (H,W,3) -> CHW planar (3,H,W) -> RRR...GGG...BBB..."""
    planar = np.transpose(img_array, (2, 0, 1))
    return planar.flatten()


def planar_to_rgb(flat_data, height, width):
    """RRR...GGG...BBB... -> HWC (H,W,3)"""
    channels = 3
    planar = flat_data.reshape((channels, height, width))
    return np.transpose(planar, (1, 2, 0))


def process_image_for_bin(image, crop_w, crop_h, crop_mode, export_float32, normalize=False):
    """预处理图片并返回 RGB planar 像素数据 (无头)
    
    Args:
        export_float32: True=存为float32, False=存为uint8
        normalize: True=除以255归一化到0~1, False=保持原始值
    """
    img = image
    if img.mode != 'RGB':
        img = img.convert('RGB')
    if crop_w > 0 and crop_h > 0:
        img = resize_and_crop_image(img, crop_w, crop_h, crop_mode)
    width, height = img.size
    img_array = np.array(img, dtype=np.uint8)
    planar_data = rgb_to_planar(img_array)
    
    if normalize:
        # 归一化到 0~1，然后根据格式选择存储方式
        normalized = planar_data.astype(np.float32) / 255.0
        if export_float32:
            out_bytes = normalized.tobytes()
        else:
            # 如果要归一化但存为uint8，需要乘以255转回（虽然不合理，但支持用户选择）
            out_arr = (normalized * 255).astype(np.uint8)
            out_bytes = out_arr.tobytes()
    else:
        # 保持原始值 0-255
        if export_float32:
            out_arr = planar_data.astype(np.float32)
            out_bytes = out_arr.tobytes()
        else:
            out_bytes = planar_data.tobytes()
    
    return out_bytes, width, height


def image_to_bin(image_path, bin_path, crop_w=0, crop_h=0, crop_mode=RESIZE_STRETCH, export_float32=False, normalize=False):
    """图片 → 纯 BIN (RGB planar，无头部)
    
    Args:
        export_float32: 存储格式，True=float32, False=uint8
        normalize: 是否归一化到0~1
    
    Returns:
        (width, height, data_size, is_float32)
    """
    img = Image.open(image_path)
    out_bytes, width, height = process_image_for_bin(img, crop_w, crop_h, crop_mode, export_float32, normalize)
    with open(bin_path, 'wb') as f:
        f.write(out_bytes)
    return width, height, len(out_bytes), export_float32


def raw_bin_to_image(bin_path, width, height, is_float32, output_path=None, scale_factor=255.0):
    """纯 BIN (RGB planar 数据，无头部) → 图片
    
    Args:
        bin_path: 输入 bin 路径
        width: 图像宽度（像素）
        height: 图像高度（像素）
        is_float32: True=float32存储, False=uint8存储
        output_path: 输出图片路径 (None 则不保存)
        scale_factor: float32 数据自动放大倍数，默认 255
    Returns:
        (PIL.Image, width, height, is_float32, data_size, stats_dict)
    """
    with open(bin_path, 'rb') as f:
        raw_data = f.read()
    
    data_size = len(raw_data)
    
    if is_float32:
        arr = np.frombuffer(raw_data, dtype=np.float32)
        stats = {
            'min': float(arr.min()),
            'max': float(arr.max()),
            'first_8': arr[:8].tolist()
        }
        # 根据数值范围判断是否需要自动放大：
        # 如果数值整体范围较小（最大值 <= 1），乘以放大倍数转回显示
        if stats['max'] <= 1.0:
            arr_uint8 = np.clip(arr * float(scale_factor), 0.0, 255.0).astype(np.uint8)
            stats['auto_scaled'] = True
            stats['scale_factor'] = float(scale_factor)
        else:
            arr_uint8 = np.clip(arr, 0.0, 255.0).astype(np.uint8)
            stats['auto_scaled'] = False
            stats['scale_factor'] = 1.0
    else:
        arr = np.frombuffer(raw_data, dtype=np.uint8)
        stats = {
            'min': int(arr.min()),
            'max': int(arr.max()),
            'first_8': arr[:8].tolist(),
            'auto_scaled': False,
            'scale_factor': 1.0
        }
        arr_uint8 = arr
    
    img_array = planar_to_rgb(arr_uint8, height, width)
    img = Image.fromarray(img_array, mode='RGB')
    
    if output_path:
        img.save(output_path)
    
    return img, width, height, is_float32, data_size, stats


# ---- 界面类 ----

class ImageBinConverter:
    def __init__(self, root):
        self.root = root
        self.root.title("图像bin显示")
        self.root.geometry("850x600")
        self.root.resizable(True, True)
        self.root.minsize(700, 500)
        self.root.configure(bg='#f0f0f0')
        
        self.input_path = tk.StringVar()
        self.output_path = tk.StringVar()
        self.crop_w_var = tk.StringVar(value="")
        self.crop_h_var = tk.StringVar(value="")
        self.crop_mode_var = tk.StringVar(value=RESIZE_STRETCH)
        self.export_float32_var = tk.BooleanVar(value=False)  # 导出格式：False=uint8, True=float32
        self.normalize_export_var = tk.BooleanVar(value=False)  # 导出归一化：将像素值除以255，变成0~1
        self.output_format_var = tk.StringVar(value='bmp')  # 输出图片格式
        self.status_text = tk.StringVar(value="将图片或 .bin 文件拖入窗口，或点击按钮选择文件")
        self.img_preview = None
        self.current_img = None
        
        # BIN 读取参数
        self.bin_w_var = tk.StringVar(value="")
        self.bin_h_var = tk.StringVar(value="")
        self.bin_float32_var = tk.BooleanVar(value=False)
        self.bin_scale_factor_var = tk.StringVar(value="255")
        self.current_file_path = ""
        self._last_guessed_uint8 = None
        self._last_guessed_float32 = None
        
        self.setup_ui()
        
        if HAS_DND:
            try:
                self.root.drop_target_register(DND_FILES)
                self.root.dnd_bind('<<Drop>>', self.on_drop)
            except Exception as e:
                self.status_text.set(f"拖拽初始化失败: {e}")
        else:
            self.status_text.set("提示: 安装 tkinterdnd2 可启用拖拽功能 (pip install tkinterdnd2)")
    
    def setup_ui(self):
        main_pw = ttk.PanedWindow(self.root, orient=tk.HORIZONTAL)
        main_pw.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)
        
        # ===== 左侧: BIN 数据信息 + 预览（上下可拖动调整） =====
        left_frame = ttk.Frame(main_pw)
        main_pw.add(left_frame, weight=1)
        
        left_pw = ttk.PanedWindow(left_frame, orient=tk.VERTICAL)
        left_pw.pack(fill=tk.BOTH, expand=True)
        
        # BIN 数据信息区（上方，占 1/3）
        info_frame = ttk.LabelFrame(left_pw, text="BIN 数据信息", padding="5")
        left_pw.add(info_frame, weight=1)
        
        # 左右两个子容器
        info_left = ttk.Frame(info_frame)
        info_left.pack(side=tk.LEFT, fill=tk.BOTH, expand=True, padx=(0, 3))
        
        info_right = ttk.Frame(info_frame)
        info_right.pack(side=tk.LEFT, fill=tk.BOTH, expand=True, padx=(3, 0))
        
        # float32 读取统计
        ttk.Label(info_left, text="若以 float32 读取", font=('Microsoft YaHei', 9, 'bold'), foreground='#0066cc').pack(anchor=tk.W)
        self.bin_f32_range = ttk.Label(info_left, text="数据范围: -", font=('Consolas', 9))
        self.bin_f32_range.pack(anchor=tk.W, pady=(2, 0))
        self.bin_f32_first = ttk.Label(info_left, text="前 8 个: -", font=('Consolas', 8), wraplength=200)
        self.bin_f32_first.pack(anchor=tk.W, pady=(2, 0))
        
        # uint8 读取统计
        ttk.Label(info_right, text="若以 uint8 读取", font=('Microsoft YaHei', 9, 'bold'), foreground='#cc6600').pack(anchor=tk.W)
        self.bin_u8_range = ttk.Label(info_right, text="数据范围: -", font=('Consolas', 9))
        self.bin_u8_range.pack(anchor=tk.W, pady=(2, 0))
        self.bin_u8_first = ttk.Label(info_right, text="前 8 个: -", font=('Consolas', 8), wraplength=200)
        self.bin_u8_first.pack(anchor=tk.W, pady=(2, 0))
        
        # 图像预览（下方，占 2/3）
        preview_frame = ttk.LabelFrame(left_pw, text="图像预览", padding="5")
        left_pw.add(preview_frame, weight=2)
        
        # 推测尺寸提示栏（在画面上方，独立显示，不会被覆盖）
        self.hint_label = ttk.Label(
            preview_frame, text="", font=('Microsoft YaHei', 9), foreground='#0066cc',
            wraplength=400, justify=tk.CENTER
        )
        self.hint_label.pack(fill=tk.X, pady=(0, 3))
        
        self.preview_info = ttk.Label(
            preview_frame, text="", font=('Microsoft YaHei', 8), foreground='#666666',
            wraplength=300
        )
        self.preview_info.pack(fill=tk.X, pady=(0, 3))
        
        self.canvas = tk.Canvas(
            preview_frame, bg='#e8e8e8', relief=tk.GROOVE, bd=2, highlightthickness=0
        )
        self.canvas.pack(fill=tk.BOTH, expand=True)
        self.canvas.create_text(
            10, 10, anchor=tk.NW,
            text="暂无预览\n\n拖入图片或 .bin 文件\n即可显示预览",
            font=('Microsoft YaHei', 10), fill='#999999', tags='hint'
        )
        
        # ===== 右侧: 控制 =====
        right_frame = ttk.Frame(main_pw)
        main_pw.add(right_frame, weight=1)
        
        canvas_container = ttk.Frame(right_frame)
        canvas_container.pack(fill=tk.BOTH, expand=True)
        
        scrollbar = ttk.Scrollbar(canvas_container, orient=tk.VERTICAL)
        self.scroll_canvas = tk.Canvas(canvas_container, highlightthickness=0, bd=0)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
        self.scroll_canvas.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        scrollbar.config(command=self.scroll_canvas.yview)
        self.scroll_canvas.config(yscrollcommand=scrollbar.set)
        
        self.scroll_frame = ttk.Frame(self.scroll_canvas)
        self.scroll_window = self.scroll_canvas.create_window(
            (0, 0), window=self.scroll_frame, anchor=tk.NW, width=self.scroll_canvas.winfo_width()
        )
        self.scroll_frame.bind('<Configure>', self._on_frame_configure)
        self.scroll_canvas.bind('<Configure>', self._on_canvas_configure)
        self.scroll_canvas.bind('<Enter>', self._bind_mousewheel)
        self.scroll_canvas.bind('<Leave>', self._unbind_mousewheel)
        
        control_frame = self.scroll_frame
        
        # ---- BIN 读取参数（放在最上方） ----
        bin_frame = ttk.LabelFrame(control_frame, text="BIN 读取参数", padding="5")
        bin_frame.pack(fill=tk.X, pady=(0, 8))
        
        size_row = ttk.Frame(bin_frame)
        size_row.pack(fill=tk.X, pady=(0, 5))
        
        ttk.Label(size_row, text="W:", font=('Microsoft YaHei', 9)).pack(side=tk.LEFT)
        self.bin_w_entry = ttk.Entry(size_row, textvariable=self.bin_w_var, width=6)
        self.bin_w_entry.pack(side=tk.LEFT, padx=(1, 5))
        
        ttk.Label(size_row, text="H:", font=('Microsoft YaHei', 9)).pack(side=tk.LEFT)
        self.bin_h_entry = ttk.Entry(size_row, textvariable=self.bin_h_var, width=6)
        self.bin_h_entry.pack(side=tk.LEFT, padx=(1, 5))
        
        # 回车键绑定：自动计算另一个尺寸并刷新
        self.bin_w_entry.bind('<Return>', self._on_bin_wh_enter)
        self.bin_h_entry.bind('<Return>', self._on_bin_wh_enter)
        # 失去焦点时也尝试自动计算
        self.bin_w_entry.bind('<FocusOut>', self._on_bin_wh_focusout)
        self.bin_h_entry.bind('<FocusOut>', self._on_bin_wh_focusout)
        
        ttk.Button(size_row, text="推测尺寸", command=self._clear_bin_wh).pack(side=tk.RIGHT, padx=(5, 0))
        ttk.Label(size_row, text="清除已填尺寸并重新推测", font=('Microsoft YaHei', 8), foreground='#888888').pack(side=tk.RIGHT)
        
        type_row = ttk.Frame(bin_frame)
        type_row.pack(fill=tk.X, pady=(0, 3))
        
        self.bin_float32_rb = ttk.Radiobutton(
            type_row, text="以 float32 形式读取", variable=self.bin_float32_var, value=True,
            command=self._on_bin_type_changed
        )
        self.bin_float32_rb.pack(side=tk.LEFT, padx=(0, 8))
        
        self.bin_uint8_rb = ttk.Radiobutton(
            type_row, text="以 uint8 形式读取", variable=self.bin_float32_var, value=False,
            command=self._on_bin_type_changed
        )
        self.bin_uint8_rb.pack(side=tk.LEFT)
        
        # 放大倍数（float32 自动放大用）
        scale_row = ttk.Frame(bin_frame)
        scale_row.pack(fill=tk.X, pady=(0, 3))
        ttk.Label(scale_row, text="放大倍数:", font=('Microsoft YaHei', 9)).pack(side=tk.LEFT)
        self.bin_scale_entry = ttk.Entry(scale_row, textvariable=self.bin_scale_factor_var, width=8)
        self.bin_scale_entry.pack(side=tk.LEFT, padx=(1, 5))
        ttk.Label(scale_row, text="(float32 范围<1时自动 × 倍数，0~1023)", font=('Microsoft YaHei', 8), foreground='#888888').pack(side=tk.LEFT)
        
        # ---- 拖放区域 ----
        drop_frame = ttk.LabelFrame(control_frame, text="拖放区域", padding="5")
        drop_frame.pack(fill=tk.X, pady=(0, 8))
        self.drop_label = tk.Label(
            drop_frame,
            text="📁 将图片或 .bin 文件\n拖入窗口任意位置即可加载",
            font=('Microsoft YaHei', 10), bg='#e8e8e8', relief=tk.GROOVE, bd=2,
            padx=10, pady=10, cursor='hand2', justify=tk.CENTER
        )
        self.drop_label.pack(fill=tk.X, padx=3, pady=3)
        self.drop_label.bind('<Button-1>', lambda e: self.browse_input())
        self.drop_label.bind('<Enter>', lambda e: self.drop_label.config(bg='#d0d0d0'))
        self.drop_label.bind('<Leave>', lambda e: self.drop_label.config(bg='#e8e8e8'))
        
        # ---- 转换按钮（放在拖放区域下方） ----
        self.convert_btn = tk.Button(
            control_frame, text="▶ 开始转换",
            font=('Microsoft YaHei', 10, 'bold'), bg='#4CAF50', fg='white',
            padx=15, pady=4, cursor='hand2', command=self.convert
        )
        self.convert_btn.pack(pady=(0, 8))
        
        # ---- 文件选择 ----
        io_frame = ttk.LabelFrame(control_frame, text="文件选择", padding="5")
        io_frame.pack(fill=tk.X, pady=(0, 8))
        ttk.Label(io_frame, text="输入:", font=('Microsoft YaHei', 9)).grid(row=0, column=0, sticky=tk.W, padx=(0, 3), pady=2)
        ttk.Entry(io_frame, textvariable=self.input_path).grid(row=0, column=1, sticky=tk.EW, padx=(0, 3), pady=2)
        ttk.Button(io_frame, text="浏览", command=self.browse_input).grid(row=0, column=2, pady=2)
        ttk.Label(io_frame, text="输出:", font=('Microsoft YaHei', 9)).grid(row=1, column=0, sticky=tk.W, padx=(0, 3), pady=2)
        self.output_entry = ttk.Entry(io_frame, textvariable=self.output_path)
        self.output_entry.grid(row=1, column=1, sticky=tk.EW, padx=(0, 3), pady=2)
        
        fmt_combo = ttk.Combobox(io_frame, textvariable=self.output_format_var, values=['bmp', 'jpg', 'png', 'tiff'], width=6, state='readonly')
        fmt_combo.grid(row=1, column=2, pady=2)
        fmt_combo.bind('<<ComboboxSelected>>', self._on_output_format_changed)
        
        io_frame.columnconfigure(1, weight=1)
        
        # ---- 导出 BIN 参数设定（合并裁剪/缩放/格式） ----
        export_frame = ttk.LabelFrame(control_frame, text="导出 BIN 参数设定", padding="5")
        export_frame.pack(fill=tk.X, pady=(0, 8))
        
        # 尺寸行
        size_row = ttk.Frame(export_frame)
        size_row.pack(fill=tk.X, pady=(0, 5))
        
        ttk.Label(size_row, text="目标  W:", font=('Microsoft YaHei', 9)).pack(side=tk.LEFT)
        self.crop_w_entry = ttk.Entry(size_row, textvariable=self.crop_w_var, width=6)
        self.crop_w_entry.pack(side=tk.LEFT, padx=(1, 5))
        
        ttk.Label(size_row, text="H:", font=('Microsoft YaHei', 9)).pack(side=tk.LEFT)
        self.crop_h_entry = ttk.Entry(size_row, textvariable=self.crop_h_var, width=6)
        self.crop_h_entry.pack(side=tk.LEFT, padx=(1, 5))
        
        ttk.Label(size_row, text="像素", font=('Microsoft YaHei', 8), foreground='#888888').pack(side=tk.LEFT)
        ttk.Button(size_row, text="原图", command=self._fill_from_source).pack(side=tk.RIGHT)
        
        # 模式行
        mode_row = ttk.Frame(export_frame)
        mode_row.pack(fill=tk.X, pady=(0, 5))
        
        self.crop_stretch_rb = ttk.Radiobutton(
            mode_row, text="拉伸", variable=self.crop_mode_var, value=RESIZE_STRETCH
        )
        self.crop_stretch_rb.pack(side=tk.LEFT, padx=(0, 5))
        
        self.crop_center_rb = ttk.Radiobutton(
            mode_row, text="裁剪", variable=self.crop_mode_var, value=RESIZE_CROP
        )
        self.crop_center_rb.pack(side=tk.LEFT)
        
        # 存储格式行
        fmt_row = ttk.Frame(export_frame)
        fmt_row.pack(fill=tk.X, pady=(0, 3))
        
        self.export_uint8_rb = ttk.Radiobutton(
            fmt_row, text="以 uint8 形式存 bin", variable=self.export_float32_var, value=False
        )
        self.export_uint8_rb.pack(side=tk.LEFT, padx=(0, 8))
        
        self.export_float32_rb = ttk.Radiobutton(
            fmt_row, text="以 float32 形式存 bin", variable=self.export_float32_var, value=True
        )
        self.export_float32_rb.pack(side=tk.LEFT)
        
        # 归一化选项
        self.normalize_cb = ttk.Checkbutton(
            export_frame, text="归一化 (将像素值除以255，存为 0.0~1.0)",
            variable=self.normalize_export_var
        )
        self.normalize_cb.pack(anchor=tk.W, pady=(2, 0))
        
        ttk.Label(export_frame, text="留空尺寸则不缩放/裁剪", font=('Microsoft YaHei', 8), foreground='#999999').pack(anchor=tk.W, pady=(0, 0))
        
        # ---- 状态 ----
        status_frame = ttk.Frame(control_frame)
        status_frame.pack(fill=tk.X)
        self.status_label = ttk.Label(
            status_frame, textvariable=self.status_text,
            font=('Microsoft YaHei', 8), foreground='#555555', wraplength=350, justify=tk.LEFT
        )
        self.status_label.pack(fill=tk.X)
    
    # ---- 辅助方法 ----
    
    def _on_frame_configure(self, event):
        self.scroll_canvas.configure(scrollregion=self.scroll_canvas.bbox("all"))
    
    def _on_canvas_configure(self, event):
        self.scroll_canvas.itemconfig(self.scroll_window, width=event.width)
    
    def _bind_mousewheel(self, event):
        self.scroll_canvas.bind_all('<MouseWheel>', self._on_mousewheel)
    
    def _unbind_mousewheel(self, event):
        self.scroll_canvas.unbind_all('<MouseWheel>')
    
    def _on_mousewheel(self, event):
        self.scroll_canvas.yview_scroll(int(-1 * (event.delta / 120)), "units")
    
    def _fill_from_source(self):
        if self.current_img is not None:
            w, h = self.current_img.size
            self.crop_w_var.set(str(w))
            self.crop_h_var.set(str(h))
            self.status_text.set(f"已填入原图尺寸: {w}×{h}")
    
    def _fill_bin_size_from_preview(self):
        if self.current_img is not None:
            w, h = self.current_img.size
            self.bin_w_var.set(str(w))
            self.bin_h_var.set(str(h))
            self.status_text.set(f"已填入尺寸: {w}×{h}")
    
    def _on_bin_wh_enter(self, event):
        self._auto_fill_other_dimension(refresh=True)
    
    def _on_bin_wh_focusout(self, event):
        self._auto_fill_other_dimension(refresh=True)
    
    def _auto_fill_other_dimension(self, refresh=False):
        """当 W 或 H 中只有一个被填入时，根据文件大小自动计算另一个"""
        if not self.current_file_path or not os.path.isfile(self.current_file_path):
            return
        ext = os.path.splitext(self.current_file_path)[1].lower()
        if ext != '.bin':
            return
        
        w_str = self.bin_w_var.get().strip()
        h_str = self.bin_h_var.get().strip()
        
        # 如果两个都没填，不自动计算
        if not w_str and not h_str:
            return
        
        try:
            file_size = os.path.getsize(self.current_file_path)
            is_float32 = self.bin_float32_var.get()
            bytes_per_pixel = 12 if is_float32 else 3
            
            # 判断当前焦点在哪个输入框，优先根据当前输入框计算另一个
            focused = self.root.focus_get()
            focused_is_w = (focused == self.bin_w_entry)
            focused_is_h = (focused == self.bin_h_entry)
            
            if focused_is_w and w_str:
                # 当前在 W 输入框，根据 W 计算 H
                w = int(w_str)
                if w > 0:
                    h = file_size / (w * bytes_per_pixel)
                    if h > 0:
                        self.bin_h_var.set(str(int(round(h))))
            elif focused_is_h and h_str:
                # 当前在 H 输入框，根据 H 计算 W
                h = int(h_str)
                if h > 0:
                    w = file_size / (h * bytes_per_pixel)
                    if w > 0:
                        self.bin_w_var.set(str(int(round(w))))
            else:
                # 没有明确焦点时，只填空的那个
                if w_str and not h_str:
                    w = int(w_str)
                    if w > 0:
                        h = file_size / (w * bytes_per_pixel)
                        if h > 0:
                            self.bin_h_var.set(str(int(round(h))))
                elif h_str and not w_str:
                    h = int(h_str)
                    if h > 0:
                        w = file_size / (h * bytes_per_pixel)
                        if w > 0:
                            self.bin_w_var.set(str(int(round(w))))
        except ValueError:
            pass
        
        if refresh:
            self._refresh_preview_only()
    
    def _get_bin_scale_factor(self):
        try:
            val = float(self.bin_scale_factor_var.get())
            if val < 0:
                return 0.0
            if val > 1023:
                return 1023.0
            return val
        except ValueError:
            return 255.0
    
    def _refresh_preview_only(self):
        """仅刷新预览，不重新填入推测尺寸"""
        if not self.current_file_path or not os.path.isfile(self.current_file_path):
            return
        ext = os.path.splitext(self.current_file_path)[1].lower()
        if ext != '.bin':
            return
        
        w_str = self.bin_w_var.get().strip()
        h_str = self.bin_h_var.get().strip()
        
        if not w_str or not h_str:
            return
        
        try:
            w = int(w_str)
            h = int(h_str)
            if w <= 0 or h <= 0:
                return
            
            is_float32 = self.bin_float32_var.get()
            scale_factor = self._get_bin_scale_factor()
            img, width, height, is_f, data_size, stats = raw_bin_to_image(
                self.current_file_path, w, h, is_float32, scale_factor=scale_factor
            )
            self.current_img = img
            
            dtype_str = 'float32' if is_f else 'uint8'
            total_pixels = w * h * 3
            expected_uint8 = total_pixels
            expected_f32 = total_pixels * 4
            expected_str = f" (期望: uint8≈{expected_uint8}B, f32≈{expected_f32}B)"
            scale_notice = ""
            if is_f and stats.get('auto_scaled', False):
                sf = stats.get('scale_factor', 255.0)
                scale_notice = f" | ⚠ 数值范围<1，已 ×{sf:.0f} 显示"
            
            self.preview_info.config(
                text=f"尺寸: {w}×{h} | 数据: {dtype_str} | 大小: {data_size:,} 字节{expected_str}{scale_notice}"
            )
            self._show_image_on_canvas(img)
        except Exception as e:
            self.preview_info.config(text=f"预览失败: {str(e)}")
    
    def _clear_bin_wh(self):
        """一键清除已填入的 W/H，并根据当前读取模式填入推测尺寸"""
        self.bin_w_var.set("")
        self.bin_h_var.set("")
        if self.current_file_path and os.path.isfile(self.current_file_path):
            ext = os.path.splitext(self.current_file_path)[1].lower()
            if ext == '.bin':
                self.update_preview(self.current_file_path)
    
    def _on_bin_type_changed(self):
        """BIN 读取类型切换时刷新预览，但不覆盖用户已手动填入的 W/H"""
        if self.current_file_path and os.path.isfile(self.current_file_path):
            ext = os.path.splitext(self.current_file_path)[1].lower()
            if ext == '.bin':
                # 只有当 W/H 为空时，才填入对应模式的推测尺寸
                w_str = self.bin_w_var.get().strip()
                h_str = self.bin_h_var.get().strip()
                if not w_str and not h_str:
                    if self.bin_float32_var.get():
                        if self._last_guessed_float32:
                            self.bin_w_var.set(str(self._last_guessed_float32[0]))
                            self.bin_h_var.set(str(self._last_guessed_float32[1]))
                    else:
                        if self._last_guessed_uint8:
                            self.bin_w_var.set(str(self._last_guessed_uint8[0]))
                            self.bin_h_var.set(str(self._last_guessed_uint8[1]))
                self.update_preview(self.current_file_path)
    
    def browse_input(self):
        file_path = filedialog.askopenfilename(
            title="选择输入文件",
            filetypes=[
                ("所有支持的文件", "*.jpg *.jpeg *.png *.bmp *.gif *.tiff *.tif *.bin"),
                ("图片文件", "*.jpg *.jpeg *.png *.bmp *.gif *.tiff *.tif"),
                ("二进制文件 (*.bin)", "*.bin"),
                ("所有文件", "*.*")
            ]
        )
        if file_path:
            self._load_file(file_path)
    
    def browse_output(self):
        file_path = filedialog.asksaveasfilename(
            title="选择输出文件保存位置",
            defaultextension=".bin",
            filetypes=[
                ("二进制文件 (*.bin)", "*.bin"),
                ("图片文件 (*.jpg, *.png)", "*.jpg *.png"),
                ("所有文件", "*.*")
            ]
        )
        if file_path:
            self.output_path.set(file_path)
    
    def auto_set_output(self, input_path):
        base, ext = os.path.splitext(input_path)
        ext = ext.lower()
        if ext in ('.jpg', '.jpeg', '.png', '.bmp', '.gif', '.tiff', '.tif'):
            self.output_path.set(base + '.bin')
        elif ext == '.bin':
            self.output_path.set(base + '_还原.' + self.output_format_var.get())
    
    def _on_output_format_changed(self, event=None):
        input_path = self.input_path.get().strip()
        if input_path and os.path.splitext(input_path)[1].lower() == '.bin':
            base, _ = os.path.splitext(self.output_path.get())
            if base:
                self.output_path.set(base + '.' + self.output_format_var.get())
    
    def on_drop(self, event):
        raw = event.data
        if not raw:
            return
        first_file = None
        raw = raw.strip()
        if raw.startswith('file://') or raw.startswith('file:'):
            import urllib.parse
            for line in raw.split():
                line = line.strip()
                if line.startswith('file://'):
                    try:
                        path = urllib.parse.unquote(line[7:])
                        if path.startswith('/') and len(path) > 2 and path[2] == ':':
                            path = path[1:]
                        if os.path.isfile(path):
                            first_file = path
                            break
                    except:
                        pass
            if first_file:
                self._load_file(first_file)
                return
        files = []
        i = 0
        while i < len(raw):
            if raw[i] == '{':
                j = raw.find('}', i)
                if j != -1:
                    files.append(raw[i+1:j])
                    i = j + 1
                else:
                    i += 1
            elif raw[i] in (' ', '\r', '\n', '\t'):
                i += 1
            else:
                j = i
                while j < len(raw) and raw[j] not in (' ', '\r', '\n', '\t'):
                    j += 1
                files.append(raw[i:j])
                i = j
        for f in files:
            f = f.strip('"\'')
            if f and os.path.isfile(f):
                first_file = f
                break
        if first_file:
            self._load_file(first_file)
    
    def _load_file(self, file_path):
        self.input_path.set(file_path)
        self.current_file_path = file_path
        self.auto_set_output(file_path)
        self.status_text.set(f"已加载文件: {os.path.basename(file_path)}")
        self.update_preview(file_path)
    
    def _guess_bin_dimensions(self, file_size, is_float32):
        bytes_per_pixel = 12 if is_float32 else 3
        total_pixels = file_size / bytes_per_pixel
        
        # 1. 优先尝试精确方形：total_pixels 必须能被 3 整除且开方为整数
        # 因为 RGB 有 3 个通道，总像素数 = w * h，方形时 w = h = sqrt(total_pixels)
        import math
        sqrt_pixels = int(math.isqrt(int(total_pixels)))
        if sqrt_pixels > 0 and sqrt_pixels * sqrt_pixels == int(total_pixels):
            # 精确方形
            return (sqrt_pixels, sqrt_pixels)
        
        # 2. 如果 total_pixels 不是完全平方数，找最接近的整数方形
        # 例如 total_pixels = 792100 (890*890) 就是精确方形
        # 如果 total_pixels = 792000，则找最近的 890*889 或类似
        sqrt_pixels = int(round(total_pixels ** 0.5))
        if sqrt_pixels > 0:
            # 尝试 w=h=sqrt_pixels 和 w=h=sqrt_pixels-1
            for side in [sqrt_pixels, sqrt_pixels - 1, sqrt_pixels + 1]:
                if side <= 0:
                    continue
                expected_pixels = side * side
                diff = abs(expected_pixels - total_pixels)
                if diff / total_pixels < 0.05:
                    return (side, side)
        
        # 3. 方形不满足时，尝试 16:9
        # w/h = 16/9 => w = 16k, h = 9k, total = 144 k^2
        k = int(round((total_pixels / 144) ** 0.5))
        for k_candidate in [k, k - 1, k + 1]:
            if k_candidate <= 0:
                continue
            w = 16 * k_candidate
            h = 9 * k_candidate
            expected_pixels = w * h
            diff = abs(expected_pixels - total_pixels)
            if diff / total_pixels < 0.02:
                return (w, h)
        
        # 4. 尝试其他常见分辨率
        candidates = [
            (640, 480), (800, 600), (1024, 768), (1280, 1024), (720, 480),
            (1920, 1080), (1280, 720), (854, 480), (640, 360), (320, 180),
            (256, 256), (512, 512), (1024, 1024), (128, 128), (384, 384), (768, 768),
        ]
        
        best_match = None
        best_diff = float('inf')
        
        for w, h in candidates:
            expected_pixels = w * h
            diff = abs(expected_pixels - total_pixels)
            if diff < best_diff:
                best_diff = diff
                best_match = (w, h)
        
        if best_match and best_diff / total_pixels < 0.05:
            return best_match
        
        # 5. 最后的回退：按 1:1 比例计算
        w_guess = int(round(total_pixels ** 0.5))
        h_guess = int(round(total_pixels / w_guess)) if w_guess > 0 else 0
        return (w_guess, h_guess)
    
    def update_preview(self, file_path):
        self.canvas.delete('preview_img')
        self.canvas.delete('hint')
        
        try:
            ext = os.path.splitext(file_path)[1].lower()
            
            if ext == '.bin':
                file_size = os.path.getsize(file_path)
                
                with open(file_path, 'rb') as f:
                    raw_data = f.read()
                
                arr_f32 = np.frombuffer(raw_data, dtype=np.float32)
                stats_float32 = {
                    'min': float(arr_f32.min()),
                    'max': float(arr_f32.max()),
                    'first_8': arr_f32[:8].tolist()
                }
                
                arr_u8 = np.frombuffer(raw_data, dtype=np.uint8)
                stats_uint8 = {
                    'min': int(arr_u8.min()),
                    'max': int(arr_u8.max()),
                    'first_8': arr_u8[:8].tolist()
                }
                
                self._update_bin_info(stats_float32, stats_uint8)
                
                is_float32 = self.bin_float32_var.get()
                guessed_u8 = self._guess_bin_dimensions(file_size, False)
                guessed_f32 = self._guess_bin_dimensions(file_size, True)
                self._last_guessed_uint8 = guessed_u8
                self._last_guessed_float32 = guessed_f32
                guessed = guessed_f32 if is_float32 else guessed_u8
                
                # 显示推测尺寸作为参考
                if guessed:
                    size_info = f"uint8:{guessed_u8[0]}×{guessed_u8[1]}" if guessed_u8 else "uint8:?"
                    if guessed_f32:
                        size_info += f" | float32:{guessed_f32[0]}×{guessed_f32[1]}"
                    self.preview_info.config(
                        text=f"文件大小: {file_size:,} 字节 | 已推测尺寸: {size_info} (可修改)"
                    )
                    self.hint_label.config(
                        text=f"已推测尺寸: uint8: {guessed_u8[0]}×{guessed_u8[1]}  |  float32: {guessed_f32[0]}×{guessed_f32[1]}"
                    )
                else:
                    self.hint_label.config(text="")
                    self.preview_info.config(
                        text=f"文件大小: {file_size:,} 字节 | 请填写 W 和 H"
                    )
                
                # 检查是否已有 W/H（用户手动输入或之前的推测）
                w_str = self.bin_w_var.get().strip()
                h_str = self.bin_h_var.get().strip()
                
                if w_str and h_str:
                    # 使用当前 W/H（可能是用户手动修改的）
                    w = int(w_str)
                    h = int(h_str)
                    scale_factor = self._get_bin_scale_factor()
                    img, w, h, is_f, data_size, stats = raw_bin_to_image(
                        file_path, w, h, is_float32, scale_factor=scale_factor
                    )
                    self.current_img = img
                    dtype_str = 'float32' if is_f else 'uint8'
                    total_pixels = w * h * 3
                    expected_uint8 = total_pixels
                    expected_f32 = total_pixels * 4
                    expected_str = f" (期望: uint8≈{expected_uint8}B, f32≈{expected_f32}B)"
                    scale_notice = ""
                    if is_f and stats.get('auto_scaled', False):
                        sf = stats.get('scale_factor', 255.0)
                        scale_notice = f" | ⚠ 数值范围<1，已 ×{sf:.0f} 显示"
                    self.preview_info.config(
                        text=f"尺寸: {w}×{h} | 数据: {dtype_str} | 大小: {data_size:,} 字节{expected_str}{scale_notice}"
                    )
                    self._show_image_on_canvas(img)
                else:
                    # W/H 为空，填入推测值
                    if guessed:
                        self.bin_w_var.set(str(guessed[0]))
                        self.bin_h_var.set(str(guessed[1]))
                        w = guessed[0]
                        h = guessed[1]
                        scale_factor = self._get_bin_scale_factor()
                        img, w, h, is_f, data_size, stats = raw_bin_to_image(
                            file_path, w, h, is_float32, scale_factor=scale_factor
                        )
                        self.current_img = img
                        dtype_str = 'float32' if is_f else 'uint8'
                        total_pixels = w * h * 3
                        expected_uint8 = total_pixels
                        expected_f32 = total_pixels * 4
                        expected_str = f" (期望: uint8≈{expected_uint8}B, f32≈{expected_f32}B)"
                        scale_notice = ""
                        if is_f and stats.get('auto_scaled', False):
                            sf = stats.get('scale_factor', 255.0)
                            scale_notice = f" | ⚠ 数值范围<1，已 ×{sf:.0f} 显示"
                        self.preview_info.config(
                            text=f"尺寸: {w}×{h} | 数据: {dtype_str} | 大小: {data_size:,} 字节{expected_str}{scale_notice}"
                        )
                        self._show_image_on_canvas(img)
                    else:
                        self.current_img = None
                        self.canvas.create_text(
                            10, 10, anchor=tk.NW,
                            text="请填写 W 和 H\n以预览图像",
                            font=('Microsoft YaHei', 10), fill='#cc6600', tags='hint'
                        )
            else:
                img = Image.open(file_path)
                self.current_img = img
                w, h = img.size
                self.bin_w_var.set(str(w))
                self.bin_h_var.set(str(h))
                self.hint_label.config(text="")
                self.preview_info.config(text=f"尺寸: {w}×{h} | 模式: {img.mode}")
                self._clear_bin_info()
                self._show_image_on_canvas(img)
            
        except Exception as e:
            self.canvas.create_text(
                10, 10, anchor=tk.NW,
                text=f"预览失败: {str(e)}", font=('Microsoft YaHei', 9), fill='#cc0000', tags='hint'
            )
            self.preview_info.config(text="预览失败")
            # 对于 BIN 文件，保留已显示的统计数据，不清除
            if ext != '.bin':
                self._clear_bin_info()
    
    def _update_bin_info(self, stats_float32, stats_uint8):
        # float32 统计
        f32_range = f"{stats_float32['min']:.6f} ~ {stats_float32['max']:.6f}"
        f32_first8 = ', '.join([f"{v:.6f}" for v in stats_float32['first_8']])
        
        # uint8 统计
        u8_range = f"{stats_uint8['min']} ~ {stats_uint8['max']}"
        u8_first8 = ', '.join([str(v) for v in stats_uint8['first_8']])
        
        self.bin_f32_range.config(text=f"数据范围: {f32_range}")
        self.bin_f32_first.config(text=f"前 8 个: [{f32_first8}]")
        self.bin_u8_range.config(text=f"数据范围: {u8_range}")
        self.bin_u8_first.config(text=f"前 8 个: [{u8_first8}]")
    
    def _clear_bin_info(self):
        self.bin_f32_range.config(text="数据范围: -")
        self.bin_f32_first.config(text="前 8 个: -")
        self.bin_u8_range.config(text="数据范围: -")
        self.bin_u8_first.config(text="前 8 个: -")
    
    def _show_image_on_canvas(self, img):
        self.canvas.update_idletasks()
        cw = self.canvas.winfo_width()
        ch = self.canvas.winfo_height()
        if cw < 50 or ch < 50:
            self.root.after(100, lambda: self._show_image_on_canvas(img))
            return
        margin = 10
        avail_w = cw - margin * 2
        avail_h = ch - margin * 2
        iw, ih = img.size
        scale = min(avail_w / iw, avail_h / ih)
        if scale > 1.0:
            scale = 1.0
        new_w = int(iw * scale)
        new_h = int(ih * scale)
        if new_w < 1 or new_h < 1:
            new_w, new_h = 1, 1
        img_resized = img.resize((new_w, new_h), Image.LANCZOS)
        self.img_preview = ImageTk.PhotoImage(img_resized)
        x = (cw - new_w) // 2
        y = (ch - new_h) // 2
        self.canvas.create_image(x, y, anchor=tk.NW, image=self.img_preview, tags='preview_img')
        self.canvas.create_rectangle(x, y, x + new_w, y + new_h, outline='#cccccc', width=1, tags='preview_img')
    
    def _get_crop_params(self):
        w_str = self.crop_w_var.get().strip()
        h_str = self.crop_h_var.get().strip()
        if not w_str or not h_str:
            return None
        try:
            crop_w = int(w_str)
            crop_h = int(h_str)
            if crop_w <= 0 or crop_h <= 0:
                return None
            return (crop_w, crop_h, self.crop_mode_var.get())
        except ValueError:
            return None
    
    def convert(self):
        input_path = self.input_path.get().strip()
        output_path = self.output_path.get().strip()
        
        if not input_path:
            messagebox.showerror("错误", "请先选择输入文件")
            return
        if not output_path:
            messagebox.showerror("错误", "请设置输出文件路径")
            return
        if not os.path.isfile(input_path):
            messagebox.showerror("错误", f"输入文件不存在:\n{input_path}")
            return
        
        try:
            ext = os.path.splitext(input_path)[1].lower()
            crop_params = self._get_crop_params()
            export_float32 = self.export_float32_var.get()
            
            if ext == '.bin':
                w_str = self.bin_w_var.get().strip()
                h_str = self.bin_h_var.get().strip()
                if not w_str or not h_str:
                    messagebox.showerror("错误", "请填写「BIN 读取参数」中的宽度 W 和高度 H")
                    return
                w = int(w_str)
                h = int(h_str)
                is_float32 = self.bin_float32_var.get()
                scale_factor = self._get_bin_scale_factor()
                
                img, width, height, is_f, data_size, stats = raw_bin_to_image(
                    input_path, w, h, is_float32, output_path, scale_factor=scale_factor
                )
                dtype_str = 'float32' if is_f else 'uint8'
                self.status_text.set(
                    f"✅ 转换成功！BIN → 图片\n"
                    f"尺寸: {width}×{height}  数据: {dtype_str}\n"
                    f"输出: {os.path.basename(output_path)}"
                )
                self._show_image_on_canvas(img)
                self.current_img = img
                self.hint_label.config(text="")
                self.preview_info.config(text=f"尺寸: {width}×{height} | 数据: {dtype_str} | 大小: {data_size:,} 字节")
                
                with open(input_path, 'rb') as f:
                    raw_data = f.read()
                arr_f32 = np.frombuffer(raw_data, dtype=np.float32)
                stats_float32 = {'min': float(arr_f32.min()), 'max': float(arr_f32.max()), 'first_8': arr_f32[:8].tolist()}
                arr_u8 = np.frombuffer(raw_data, dtype=np.uint8)
                stats_uint8 = {'min': int(arr_u8.min()), 'max': int(arr_u8.max()), 'first_8': arr_u8[:8].tolist()}
                # 在统计数据中补充放大倍数信息
                sf = self._get_bin_scale_factor()
                if is_float32 and stats.get('auto_scaled', False):
                    stats_float32['scale_factor'] = sf
                self._update_bin_info(stats_float32, stats_uint8)
                
                messagebox.showinfo("转换成功", f"BIN 文件已还原为图片！\n\n尺寸: {width}×{height}\n数据类型: {dtype_str}\n输出: {output_path}")
            else:
                if crop_params:
                    crop_w, crop_h, crop_mode = crop_params
                    mode_name = "直接拉伸" if crop_mode == RESIZE_STRETCH else "中心裁剪"
                    
                    width, height, data_size, is_f = image_to_bin(
                        input_path, output_path, crop_w=crop_w, crop_h=crop_h, 
                        crop_mode=crop_mode, export_float32=export_float32,
                        normalize=self.normalize_export_var.get()
                    )
                    fmt_str = 'float32' if export_float32 else 'uint8'
                    
                    img = Image.open(input_path)
                    processed = resize_and_crop_image(img, crop_w, crop_h, crop_mode)
                    self._show_image_on_canvas(processed)
                    self.current_img = processed
                    self.hint_label.config(text="")
                    
                    self.bin_w_var.set(str(width))
                    self.bin_h_var.set(str(height))
                    
                    self.preview_info.config(text=f"处理后: {processed.size[0]}×{processed.size[1]} | RGB")
                    self.status_text.set(
                        f"✅ 转换成功！图片 → BIN [{mode_name}]\n"
                        f"原始: {img.size[0]}×{img.size[1]} → BIN: {width}×{height}\n"
                        f"存储格式: {fmt_str}\n"
                        f"输出: {os.path.basename(output_path)}"
                    )
                    messagebox.showinfo(
                        "转换成功",
                        f"图片已转换为 BIN 文件！\n\n"
                        f"原始尺寸: {img.size[0]}×{img.size[1]}\n"
                        f"目标尺寸: {crop_w}×{crop_h}\n"
                        f"存储格式: {fmt_str}\n"
                        f"输出: {output_path}"
                    )
                else:
                    width, height, data_size, is_f = image_to_bin(
                        input_path, output_path, export_float32=export_float32,
                        normalize=self.normalize_export_var.get()
                    )
                    fmt_str = 'float32' if export_float32 else 'uint8'
                    
                    self.bin_w_var.set(str(width))
                    self.bin_h_var.set(str(height))
                    
                    self.status_text.set(
                        f"✅ 转换成功！图片 → BIN\n"
                        f"尺寸: {width}×{height}  存储格式: {fmt_str}\n"
                        f"数据大小: {data_size:,} 字节\n"
                        f"输出: {os.path.basename(output_path)}"
                    )
                    messagebox.showinfo(
                        "转换成功",
                        f"图片已转换为 BIN 文件！\n\n"
                        f"尺寸: {width}×{height}\n"
                        f"存储格式: {fmt_str}\n"
                        f"输出: {output_path}"
                    )
        except Exception as e:
            self.status_text.set(f"❌ 转换失败: {str(e)}")
            messagebox.showerror("转换失败", f"发生错误:\n{str(e)}")


def main():
    if HAS_DND:
        root = TkinterDnD.Tk()
    else:
        root = tk.Tk()
    app = ImageBinConverter(root)
    root.mainloop()


if __name__ == '__main__':
    main()