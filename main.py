import tkinter as tk
from tkinter import ttk, filedialog, messagebox
import numpy as np
from PIL import Image, ImageTk, ImageDraw
import os
from pathlib import Path

class SemanticSegmentationTool:
    def __init__(self, root):
        self.root = root
        self.root.title("語意分割標記系統")
        self.root.geometry("1400x800")
        self.root.configure(bg='#f0f0f0')
        
        # 初始化變數
        self.images = []
        self.current_image_index = -1
        self.current_image = None
        self.current_pil_image = None
        self.mask_visible = True
        self.is_drawing = False
        self.brush_size = 15
        self.opacity = 0.8
        self.scale = 1.0
        self.max_display_size = 800
        self.display_scale = 1.0
        self.original_width = 0
        self.original_height = 0
        
        # 繪圖模式：brush, eraser, fill
        self.draw_mode = tk.StringVar(value="brush")  # brush, eraser, fill
        # 橡皮擦模式（可保留或移除，若保留則與 draw_mode 綁定）
        self.erase_mode = tk.BooleanVar(value=False)
        
        # Undo/Redo 堆疊
        self.undo_stack = []
        self.redo_stack = []
        
        # 畫布和遮罩
        self.display_image = None
        self.mask_array = None
        self.mask_image = None

        self.last_draw_pos = None  # 紀錄筆刷上一次的位置
        
        self.setup_ui()
        self.setup_key_bindings()
        
    def setup_ui(self):
        # 主框架
        main_frame = ttk.Frame(self.root)
        main_frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)

        # 標題
        title_label = ttk.Label(main_frame, text="🎯 語意分割標記系統",
                               font=('Arial', 20, 'bold'))
        title_label.pack(pady=(0, 10))

        # 控制面板
        control_frame = ttk.LabelFrame(main_frame, text="控制面板", padding=10)
        control_frame.pack(fill=tk.X, pady=(0, 10))

        # 檔案選擇
        file_frame = ttk.Frame(control_frame)
        file_frame.pack(fill=tk.X, pady=(0, 10))

        ttk.Button(file_frame, text="📁 選擇TIF圖片檔案",
                  command=self.load_images).pack(side=tk.LEFT, padx=(0, 10))

        # 圖片列表
        self.image_listbox = tk.Listbox(control_frame, height=3)
        self.image_listbox.pack(fill=tk.X, pady=(0, 10))
        self.image_listbox.bind('<<ListboxSelect>>', self.on_image_select)

        # 工作區域
        workspace_frame = ttk.Frame(main_frame)
        workspace_frame.pack(fill=tk.BOTH, expand=True)

        # 畫布區域
        canvas_frame = ttk.LabelFrame(workspace_frame, text="圖片顯示", padding=10)
        canvas_frame.pack(side=tk.LEFT, fill=tk.BOTH, expand=True, padx=(0, 10))

        # 創建帶滾動條的畫布
        canvas_container = ttk.Frame(canvas_frame)
        canvas_container.pack(fill=tk.BOTH, expand=True)

        self.canvas = tk.Canvas(canvas_container, bg='white', cursor='crosshair')

        # 滾動條
        v_scrollbar = ttk.Scrollbar(canvas_container, orient=tk.VERTICAL, command=self.canvas.yview)
        h_scrollbar = ttk.Scrollbar(canvas_container, orient=tk.HORIZONTAL, command=self.canvas.xview)
        self.canvas.configure(yscrollcommand=v_scrollbar.set, xscrollcommand=h_scrollbar.set)

        # 佈局滾動條和畫布
        self.canvas.grid(row=0, column=0, sticky='nsew')
        v_scrollbar.grid(row=0, column=1, sticky='ns')
        h_scrollbar.grid(row=1, column=0, sticky='ew')

        canvas_container.grid_rowconfigure(0, weight=1)
        canvas_container.grid_columnconfigure(0, weight=1)

        # 綁定畫布事件
        self.canvas.bind('<Button-1>', self.start_drawing)
        self.canvas.bind('<B1-Motion>', self.draw)
        self.canvas.bind('<ButtonRelease-1>', self.stop_drawing)
        self.canvas.bind('<MouseWheel>', self.on_mousewheel)
        self.canvas.bind('<Button-3>', self.fill_mask)

        # --------- 工具面板（加上滾動） ---------
        tools_scroll_frame = ttk.Frame(workspace_frame)
        tools_scroll_frame.pack(side=tk.RIGHT, fill=tk.Y)

        tools_canvas = tk.Canvas(tools_scroll_frame, width=300)
        tools_scrollbar = ttk.Scrollbar(tools_scroll_frame, orient=tk.VERTICAL, command=tools_canvas.yview)
        tools_canvas.configure(yscrollcommand=tools_scrollbar.set)

        tools_canvas.pack(side=tk.LEFT, fill=tk.Y, expand=True)
        tools_scrollbar.pack(side=tk.RIGHT, fill=tk.Y)

        tools_inner = ttk.Frame(tools_canvas)
        tools_inner.bind(
            "<Configure>",
            lambda e: tools_canvas.configure(scrollregion=tools_canvas.bbox("all"))
        )
        tools_canvas.create_window((0, 0), window=tools_inner, anchor="nw")

        # 用 tools_inner 取代原本的 tools_frame
        tools_frame = tools_inner
        # --------------------------------------

        # 筆刷控制
        brush_frame = ttk.LabelFrame(tools_frame, text="🖌️ 筆刷工具", padding=10)
        brush_frame.pack(fill=tk.X, pady=(0, 10))

        # 工具選擇 Radiobutton
        ttk.Label(brush_frame, text="工具選擇:").pack(anchor=tk.W)
        ttk.Radiobutton(brush_frame, text="畫筆", variable=self.draw_mode, value="brush").pack(anchor=tk.W)
        ttk.Radiobutton(brush_frame, text="橡皮擦", variable=self.draw_mode, value="eraser").pack(anchor=tk.W)
        ttk.Radiobutton(brush_frame, text="油漆桶", variable=self.draw_mode, value="fill").pack(anchor=tk.W)

        # 可選：保留橡皮擦模式 checkbox，與 draw_mode 綁定
        # ttk.Checkbutton(brush_frame, text="橡皮擦模式 (E)", variable=self.erase_mode).pack(anchor=tk.W, pady=(0, 10))

        # 筆刷大小
        ttk.Label(brush_frame, text="筆刷大小:").pack(anchor=tk.W)
        self.brush_size_var = tk.IntVar(value=15)
        brush_scale = ttk.Scale(brush_frame, from_=1, to=100, variable=self.brush_size_var,
                               orient=tk.HORIZONTAL, command=self.update_brush_size)
        brush_scale.pack(fill=tk.X, pady=(0, 5))
        self.brush_size_label = ttk.Label(brush_frame, text="15px")
        self.brush_size_label.pack(anchor=tk.W)

        # 透明度
        ttk.Label(brush_frame, text="透明度:").pack(anchor=tk.W, pady=(10, 0))
        self.opacity_var = tk.IntVar(value=80)
        opacity_scale = ttk.Scale(brush_frame, from_=10, to=100, variable=self.opacity_var,
                                 orient=tk.HORIZONTAL, command=self.update_opacity)
        opacity_scale.pack(fill=tk.X, pady=(0, 5))
        self.opacity_label = ttk.Label(brush_frame, text="80%")
        self.opacity_label.pack(anchor=tk.W)

        # 顯示設定
        display_frame = ttk.LabelFrame(tools_frame, text="📏 顯示設定", padding=10)
        display_frame.pack(fill=tk.X, pady=(0, 10))

        ttk.Label(display_frame, text="最大顯示尺寸:").pack(anchor=tk.W)
        self.max_size_var = tk.IntVar(value=800)
        size_scale = ttk.Scale(display_frame, from_=400, to=1200, variable=self.max_size_var,
                              orient=tk.HORIZONTAL, command=self.update_max_size)
        size_scale.pack(fill=tk.X, pady=(0, 5))
        self.max_size_label = ttk.Label(display_frame, text="800px")
        self.max_size_label.pack(anchor=tk.W)

        # 操作按鈕
        action_frame = ttk.LabelFrame(tools_frame, text="⚡ 操作", padding=10)
        action_frame.pack(fill=tk.X, pady=(0, 10))

        # Undo/Redo 按鈕
        undo_redo_frame = ttk.Frame(action_frame)
        undo_redo_frame.pack(fill=tk.X, pady=2)
        ttk.Button(undo_redo_frame, text="↩️ Undo (Ctrl+Z)", command=self.undo).pack(side=tk.LEFT, expand=True, fill=tk.X, padx=(0,2))
        ttk.Button(undo_redo_frame, text="↪️ Redo (Ctrl+Y)", command=self.redo).pack(side=tk.LEFT, expand=True, fill=tk.X, padx=(2,0))

        ttk.Button(action_frame, text="🗑️ 清除遮罩",
                  command=self.clear_mask).pack(fill=tk.X, pady=2)
        ttk.Button(action_frame, text="💾 儲存遮罩",
                  command=self.save_mask).pack(fill=tk.X, pady=2)
        ttk.Button(action_frame, text="📂 載入遮罩",
                  command=self.load_mask).pack(fill=tk.X, pady=2)
        ttk.Button(action_frame, text="👁️ 顯示/隱藏",
                  command=self.toggle_mask).pack(fill=tk.X, pady=2)

        # 縮放控制
        zoom_frame = ttk.LabelFrame(tools_frame, text="🔍 縮放控制", padding=10)
        zoom_frame.pack(fill=tk.X)

        zoom_buttons_frame = ttk.Frame(zoom_frame)
        zoom_buttons_frame.pack(fill=tk.X)

        ttk.Button(zoom_buttons_frame, text="-", width=3,
                  command=lambda: self.zoom(0.8)).pack(side=tk.LEFT)
        self.zoom_label = ttk.Label(zoom_buttons_frame, text="100%")
        self.zoom_label.pack(side=tk.LEFT, padx=10)
        ttk.Button(zoom_buttons_frame, text="+", width=3,
                  command=lambda: self.zoom(1.2)).pack(side=tk.LEFT)

        ttk.Button(zoom_frame, text="重置縮放",
                  command=self.reset_zoom).pack(fill=tk.X, pady=(5, 0))

        # 狀態欄
        status_frame = ttk.Frame(main_frame)
        status_frame.pack(fill=tk.X, pady=(10, 0))

        self.status_label = ttk.Label(status_frame, text="請選擇圖片開始標記")
        self.status_label.pack(side=tk.LEFT)

    def setup_key_bindings(self):
        """設定快捷鍵"""
        self.root.bind('<Control-z>', lambda event: self.undo())
        self.root.bind('<Control-y>', lambda event: self.redo())
        self.root.bind('e', lambda event: self.toggle_erase_mode())
        self.root.bind('E', lambda event: self.toggle_erase_mode())

    def toggle_erase_mode(self):
        """切換橡皮擦模式 (E) 鍵切換 brush/eraser"""
        # 若目前是 eraser，切回 brush，否則切到 eraser
        if self.draw_mode.get() == "eraser":
            self.draw_mode.set("brush")
        else:
            self.draw_mode.set("eraser")

    def load_images(self):
        """載入圖片檔案"""
        filetypes = [('TIF files', '*.tif *.tiff'), ('All files', '*.*')]
        filenames = filedialog.askopenfilenames(
            title="選擇TIF圖片檔案",
            filetypes=filetypes
        )
        
        if filenames:
            self.images = []
            self.image_listbox.delete(0, tk.END)
            
            for filename in filenames:
                if filename.lower().endswith(('.tif', '.tiff')):
                    self.images.append(filename)
                    self.image_listbox.insert(tk.END, os.path.basename(filename))
            
            if self.images:
                self.image_listbox.selection_set(0)
                self.select_image(0)
            else:
                messagebox.showerror("錯誤", "未找到TIF格式圖片！")
    
    def on_image_select(self, event):
        """處理圖片選擇事件"""
        selection = self.image_listbox.curselection()
        if selection:
            self.select_image(selection[0])
    
    def select_image(self, index):
        """選擇並載入圖片"""
        if 0 <= index < len(self.images):
            try:
                self.current_image_index = index
                
                # 載入圖片
                self.current_pil_image = Image.open(self.images[index])
                
                # 如果是RGBA，轉換為RGB
                if self.current_pil_image.mode == 'RGBA':
                    self.current_pil_image = self.current_pil_image.convert('RGB')
                
                self.original_width = self.current_pil_image.width
                self.original_height = self.current_pil_image.height
                
                self.setup_display()
                self.update_status()
                self.reset_zoom()
                
            except Exception as e:
                messagebox.showerror("錯誤", f"無法載入圖片: {str(e)}")
    
    def setup_display(self):
        """設置顯示"""
        if self.current_pil_image is None:
            return
        
        # 計算顯示縮放比例
        max_size = self.max_display_size
        img_width = self.original_width
        img_height = self.original_height
        
        self.display_scale = min(max_size / img_width, max_size / img_height, 1.0)
        
        display_width = int(img_width * self.display_scale)
        display_height = int(img_height * self.display_scale)
        
        # 調整顯示圖片大小
        self.display_image = self.current_pil_image.resize(
            (display_width, display_height), Image.Resampling.LANCZOS)
        
        # 初始化遮罩
        self.mask_array = np.zeros((img_height, img_width), dtype=np.uint8)
        
        # 清空 Undo/Redo 堆疊
        self.undo_stack = []
        self.redo_stack = []

        self.draw_image()
    
    def draw_image(self):
        """繪製圖片到畫布"""
        if self.display_image is None:
            return
        
        # 創建合成圖片
        composite = self.display_image.copy()
        
        if self.mask_visible and self.mask_array is not None:
            # 調整遮罩大小以匹配顯示圖片
            mask_resized = Image.fromarray(self.mask_array).resize(
                (self.display_image.width, self.display_image.height), 
                Image.Resampling.NEAREST)
            
            # 創建紅色遮罩
            mask_rgba = Image.new('RGBA', mask_resized.size, (0, 0, 0, 0))
            mask_pixels = np.array(mask_resized)
            mask_rgba_array = np.array(mask_rgba)
            
            # 將遮罩區域設為紅色
            mask_rgba_array[mask_pixels > 0] = [255, 0, 0, int(255 * self.opacity)]
            mask_rgba = Image.fromarray(mask_rgba_array)
            
            # 合成圖片
            composite = composite.convert('RGBA')
            composite = Image.alpha_composite(composite, mask_rgba)
            composite = composite.convert('RGB')
        
        # 應用縮放
        scaled_width = int(composite.width * self.scale)
        scaled_height = int(composite.height * self.scale)
        
        if self.scale != 1.0:
            composite = composite.resize((scaled_width, scaled_height), 
                                       Image.Resampling.LANCZOS)
        
        # 轉換為tkinter格式
        self.current_image = ImageTk.PhotoImage(composite)
        
        # 更新畫布
        self.canvas.delete("all")
        self.canvas.create_image(0, 0, anchor=tk.NW, image=self.current_image)
        self.canvas.configure(scrollregion=self.canvas.bbox("all"))
    
    def get_canvas_coords(self, event):
        """獲取畫布座標"""
        canvas_x = self.canvas.canvasx(event.x)
        canvas_y = self.canvas.canvasy(event.y)
        
        # 轉換為原始圖片座標
        original_x = int(canvas_x / (self.scale * self.display_scale))
        original_y = int(canvas_y / (self.scale * self.display_scale))
        
        return original_x, original_y
    
    def start_drawing(self, event):
        """開始繪製"""
        if self.current_pil_image is None:
            return
        # 填色模式（fill）時，改呼叫 fill_mask
        if self.draw_mode.get() == "fill":
            self.fill_mask(event)
            return
        # 儲存當前狀態以供 undo
        if self.mask_array is not None:
            self.undo_stack.append(self.mask_array.copy())
            self.redo_stack.clear() # 開始新繪製時，清除 redo 堆疊
        self.is_drawing = True
        self.last_draw_pos = self.get_canvas_coords(event)
        self.draw_at_position(event)
    
    def draw(self, event):
        """繪製過程"""
        if self.is_drawing:
            self.draw_at_position(event)
    
    def stop_drawing(self, event=None):
        """停止繪製"""
        self.is_drawing = False
        self.last_draw_pos = None
    
    def draw_at_position(self, event):
        """在指定位置繪製"""
        # 僅在 brush 或 eraser 模式下繪製
        if self.draw_mode.get() not in ("brush", "eraser"):
            return
        if self.mask_array is None:
            return

        x, y = self.get_canvas_coords(event)
        if not (0 <= x < self.original_width and 0 <= y < self.original_height):
            return

        mask_img = Image.fromarray(self.mask_array)
        draw = ImageDraw.Draw(mask_img)
        # 根據模式決定填充值
        fill_value = 0 if self.draw_mode.get() == "eraser" else 255
        r = self.brush_size

        if self.last_draw_pos:
            # 畫線段（筆刷軌跡）
            draw.line([self.last_draw_pos, (x, y)], fill=fill_value, width=r * 2)

            # 補起點圓形
            lx, ly = self.last_draw_pos
            draw.ellipse([lx - r, ly - r, lx + r, ly + r], fill=fill_value)

            # 補終點圓形
            draw.ellipse([x - r, y - r, x + r, y + r], fill=fill_value)
        else:
            # 只點一下的情況
            draw.ellipse([x - r, y - r, x + r, y + r], fill=fill_value)

        self.mask_array = np.array(mask_img)
        self.last_draw_pos = (x, y)
        self.draw_image()

    def fill_mask(self, event):
        """滑鼠右鍵填充遮罩（顏色相近區域）"""
        # 僅在 fill 模式下執行
        if self.draw_mode.get() != "fill" or self.mask_array is None or self.current_pil_image is None:
            return

        x, y = self.get_canvas_coords(event)
        if not (0 <= x < self.original_width and 0 <= y < self.original_height):
            return

        self.undo_stack.append(self.mask_array.copy())
        self.redo_stack.clear()

        # 填充值
        fill_value = 255
        # 以原圖顏色作為起始點
        self.flood_fill(x, y, None, fill_value)
        self.draw_image()

    def flood_fill(self, x, y, target_value, fill_value):
        """顏色相近的區域塗色"""
        if self.mask_array is None or self.current_pil_image is None:
            return

        rgb_img = self.current_pil_image.convert('RGB')
        rgb_array = np.array(rgb_img)
        h, w, _ = rgb_array.shape

        if not (0 <= x < w and 0 <= y < h):
            return

        # 起始點顏色
        base_color = rgb_array[y, x].astype(np.int16)
        color_diff_threshold = 30  # 容差值，越小表示越嚴格

        # 建立 mask
        filled = np.zeros((h, w), dtype=bool)
        to_fill = [(x, y)]

        while to_fill:
            new_fill = []
            for px, py in to_fill:
                if 0 <= px < w and 0 <= py < h:
                    if filled[py, px]:
                        continue
                    pixel = rgb_array[py, px].astype(np.int16)
                    color_diff = np.linalg.norm(base_color - pixel)

                    if color_diff <= color_diff_threshold:
                        filled[py, px] = True
                        new_fill.extend([
                            (px+1, py), (px-1, py),
                            (px, py+1), (px, py-1)
                        ])
            to_fill = new_fill

        self.mask_array[filled] = fill_value

    def undo(self):
        """回復上一步"""
        if not self.undo_stack:
            return
        
        # 將當前狀態推入 redo 堆疊
        if self.mask_array is None:
            return
        self.redo_stack.append(self.mask_array.copy())
        
        # 從 undo 堆疊中恢復上一個狀態
        self.mask_array = self.undo_stack.pop()
        
        self.draw_image()

    def redo(self):
        """重做下一步"""
        if not self.redo_stack:
            return
            
        # 將當前狀態推入 undo 堆疊
        if self.mask_array is None:
            return
        self.undo_stack.append(self.mask_array.copy())
        
        # 從 redo 堆疊中恢復下一個狀態
        self.mask_array = self.redo_stack.pop()
        
        self.draw_image()

    def clear_mask(self):
        """清除遮罩"""
        if self.mask_array is not None:
            # 儲存清除前的狀態以供 undo
            self.undo_stack.append(self.mask_array.copy())
            self.redo_stack.clear()
            
            self.mask_array.fill(0)
            self.draw_image()
    
    def save_mask(self):
        """儲存遮罩"""
        if self.mask_array is None or self.current_image_index == -1:
            messagebox.showwarning("警告", "請先選擇圖片！")
            return
        
        # 獲取原始檔名
        original_name = os.path.splitext(os.path.basename(self.images[self.current_image_index]))[0]
        default_name = f"mask_{original_name}.png"
        
        filename = filedialog.asksaveasfilename(
            title="儲存遮罩",
            defaultextension=".png",
            initialfile=default_name,
            filetypes=[('PNG files', '*.png'), ('All files', '*.*')]
        )
        
        if filename:
            try:
                mask_img = Image.fromarray(self.mask_array)
                mask_img.save(filename)
                messagebox.showinfo("成功", f"遮罩已儲存至: {filename}")
            except Exception as e:
                messagebox.showerror("錯誤", f"儲存失敗: {str(e)}")
    
    def load_mask(self):
        """載入遮罩"""
        if self.current_pil_image is None:
            messagebox.showwarning("警告", "請先選擇圖片！")
            return
        
        filename = filedialog.askopenfilename(
            title="載入遮罩",
            filetypes=[('Image files', '*.png *.jpg *.jpeg *.bmp *.tiff'), 
                      ('All files', '*.*')]
        )
        
        if filename:
            try:
                # 儲存載入前的狀態以供 undo
                if self.mask_array is not None:
                    self.undo_stack.append(self.mask_array.copy())
                    self.redo_stack.clear()

                mask_img = Image.open(filename).convert('L')
                
                # 調整遮罩大小以匹配原始圖片
                mask_img = mask_img.resize((self.original_width, self.original_height), 
                                         Image.Resampling.NEAREST)
                
                self.mask_array = np.array(mask_img)
                self.draw_image()
                
                messagebox.showinfo("成功", "遮罩載入成功！")
            except Exception as e:
                messagebox.showerror("錯誤", f"載入失敗: {str(e)}")
    
    def toggle_mask(self):
        """切換遮罩顯示"""
        self.mask_visible = not self.mask_visible
        self.draw_image()
    
    def zoom(self, factor):
        """縮放"""
        self.scale *= factor
        self.scale = max(0.1, min(5.0, self.scale))
        self.zoom_label.config(text=f"{int(self.scale * 100)}%")
        self.draw_image()
    
    def reset_zoom(self):
        """重置縮放"""
        self.scale = 1.0
        self.zoom_label.config(text="100%")
        self.draw_image()
    
    def on_mousewheel(self, event):
        """滑鼠滾輪縮放"""
        if event.state & 0x4:  # Ctrl鍵被按下
            if event.delta > 0:
                self.zoom(1.1)
            else:
                self.zoom(0.9)
        else:
            # 正常滾動
            self.canvas.yview_scroll(-1 * int(event.delta / 120), "units")
    
    def update_brush_size(self, value):
        """更新筆刷大小"""
        self.brush_size = int(float(value))
        self.brush_size_label.config(text=f"{self.brush_size}px")
    
    def update_opacity(self, value):
        """更新透明度"""
        self.opacity = int(float(value)) / 100
        self.opacity_label.config(text=f"{int(float(value))}%")
        self.draw_image()
    
    def update_max_size(self, value):
        """更新最大顯示尺寸"""
        self.max_display_size = int(float(value))
        self.max_size_label.config(text=f"{self.max_display_size}px")
        if self.current_pil_image:
            self.setup_display()
    
    def update_status(self):
        """更新狀態列"""
        if self.current_image_index >= 0:
            filename = os.path.basename(self.images[self.current_image_index])
            display_info = f"顯示: {int(self.original_width * self.display_scale)}×{int(self.original_height * self.display_scale)} ({int(self.display_scale * 100)}%)"
            status_text = (f"圖片: {filename} | 原尺寸: {self.original_width}×{self.original_height} | "
                          f"{display_info} | 第 {self.current_image_index + 1}/{len(self.images)} 張")
            self.status_label.config(text=status_text)

def main():
    """主函數"""
    root = tk.Tk()
    app = SemanticSegmentationTool(root)
    root.mainloop()

if __name__ == "__main__":
    main()
