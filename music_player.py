"""
🐱 猫猫给你唱歌~ 🎵
一个可爱猫猫主题的本地MP3音乐播放器
支持多歌单、歌曲排序记忆功能
"""

import os
import json
import random
import subprocess
import tkinter as tk
from tkinter import filedialog, messagebox, ttk
import customtkinter as ctk
import pygame
from mutagen.mp3 import MP3
from mutagen.id3 import ID3
from PIL import Image, ImageDraw
import threading
import time
import pystray
from pystray import MenuItem, Menu

# ==================== 猫猫主题配色 ====================
COLORS = {
    "bg_primary": "#FFF0F5",
    "bg_secondary": "#FFE4E1",
    "accent": "#FF69B4",
    "accent_light": "#FFB6C1",
    "accent_dark": "#FF1493",
    "text_primary": "#8B4513",
    "text_secondary": "#CD853F",
    "button_bg": "#FF69B4",
    "button_hover": "#FF1493",
    "list_bg": "#FFF5F7",
    "list_select": "#FFB6C1",
    "progress": "#FF69B4",
    "frame_border": "#FFC0CB",
    "tab_active": "#FF69B4",
    "tab_inactive": "#FFE4E1",
}

ctk.set_appearance_mode("light")

# 配置文件路径
CONFIG_FILE = "player_config.json"

# 支持的音频格式（注：APE 格式需要额外解码器，建议使用 FLAC/MP3/WAV）
SUPPORTED_FORMATS = ('.mp3', '.flac', '.wav', '.ogg', '.m4a', '.aac')
# 可识别但播放可能失败的格式（用于提示用户转换）
KNOWN_UNSUPPORTED_FORMATS = ('.ape',)


class CatMusicPlayer:
    def __init__(self, root):
        self.root = root
        self.root.title("🐱 猫猫给你唱歌~")
        self.root.geometry("1100x750")
        self.root.minsize(1000, 700)
        self.root.configure(fg_color=COLORS["bg_primary"])
        
        # 窗口状态
        self.is_maximized = False
        self.normal_geometry = "1100x750"
        
        pygame.mixer.init()
        
        # 播放状态
        self.playlists = {}  # {歌单名: {folder: 路径, songs: [(文件名, 完整路径), ...]}}
        self.current_playlist_name = None
        self.current_index = -1
        self.is_playing = False
        self.is_paused = False
        self.play_mode = "list"
        
        # 播放进度
        self.song_length = 0
        self.current_pos = 0
        self.is_dragging = False
        self.seek_time = 0
        
        # 系统托盘
        self.tray_icon = None
        self.tray_thread = None
        self.tray_running = False
        self.is_minimized_to_tray = False
        
        # 动画状态
        self.cat_state = "normal"
        self.running = True
        
        # 拖动排序状态
        self.drag_start_index = None
        
        # 加载配置
        self.load_config()
        
        self.create_ui()
        
        self.root.protocol("WM_DELETE_WINDOW", self.on_close)
        self.root.bind("<Unmap>", self.on_minimize)
        
        # 启动后台线程
        self.update_thread = threading.Thread(target=self.update_progress_loop, daemon=True)
        self.update_thread.start()
        
        self.cat_thread = threading.Thread(target=self.cat_animation_loop, daemon=True)
        self.cat_thread.start()
        
        # 自动加载上次歌单
        self.root.after(500, self.auto_load_last_playlist)
    
    # ==================== 配置管理 ====================
    def load_config(self):
        """加载配置文件"""
        if os.path.exists(CONFIG_FILE):
            try:
                with open(CONFIG_FILE, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                    self.playlists = data.get('playlists', {})
                    self.current_playlist_name = data.get('last_playlist', None)
            except Exception as e:
                print(f"加载配置失败: {e}")
                self.playlists = {}
                self.current_playlist_name = None
    
    def save_config(self):
        """保存配置文件"""
        try:
            data = {
                'playlists': self.playlists,
                'last_playlist': self.current_playlist_name
            }
            with open(CONFIG_FILE, 'w', encoding='utf-8') as f:
                json.dump(data, f, ensure_ascii=False, indent=2)
        except Exception as e:
            print(f"保存配置失败: {e}")
    
    # ==================== UI创建 ====================
    def create_ui(self):
        """创建UI"""
        self.root.grid_columnconfigure(0, weight=1)
        self.root.grid_rowconfigure(0, weight=1)
        
        # 主内容框架
        main_frame = ctk.CTkFrame(self.root, fg_color=COLORS["bg_primary"], 
                                   corner_radius=20, border_width=3,
                                   border_color=COLORS["frame_border"])
        main_frame.grid(row=0, column=0, padx=15, pady=15, sticky="nsew")
        main_frame.grid_columnconfigure(0, weight=2)
        main_frame.grid_columnconfigure(1, weight=1)
        main_frame.grid_rowconfigure(0, weight=1)
        
        # 左侧播放器
        left_frame = ctk.CTkFrame(main_frame, fg_color=COLORS["bg_secondary"], corner_radius=15)
        left_frame.grid(row=0, column=0, padx=10, pady=10, sticky="nsew")
        left_frame.grid_columnconfigure(0, weight=1)
        left_frame.grid_rowconfigure(1, weight=1)
        
        # 标题
        title_frame = ctk.CTkFrame(left_frame, fg_color="transparent")
        title_frame.grid(row=0, column=0, pady=(15, 5))
        
        ctk.CTkLabel(title_frame, text="🐱 猫猫给你唱歌~ 🎵",
                     font=ctk.CTkFont(family="微软雅黑", size=26, weight="bold"),
                     text_color=COLORS["accent_dark"]).pack()
        
        self.current_playlist_label = ctk.CTkLabel(title_frame, text="当前歌单: 无",
                     font=ctk.CTkFont(size=12), text_color=COLORS["text_secondary"])
        self.current_playlist_label.pack()
        
        # 内容区
        content_frame = ctk.CTkFrame(left_frame, fg_color=COLORS["bg_primary"], corner_radius=12)
        content_frame.grid(row=1, column=0, padx=15, pady=10, sticky="nsew")
        content_frame.grid_columnconfigure(0, weight=1)
        
        # 猫咪 - 使用固定框架居中显示
        cat_frame = ctk.CTkFrame(content_frame, fg_color=COLORS["bg_secondary"], 
                                  corner_radius=10, width=220, height=130)
        cat_frame.grid(row=0, column=0, pady=15)
        cat_frame.grid_propagate(False)
        
        self.cat_label = ctk.CTkLabel(cat_frame, text=self.get_cat_art("normal"),
                                      font=ctk.CTkFont(family="Courier New", size=12),
                                      text_color=COLORS["accent"],
                                      fg_color="transparent",
                                      width=200, height=110)
        self.cat_label.place(relx=0.5, rely=0.5, anchor="center")
        
        # 歌曲信息
        info_card = ctk.CTkFrame(content_frame, fg_color=COLORS["bg_secondary"], corner_radius=10)
        info_card.grid(row=1, column=0, padx=20, pady=10, sticky="ew")
        info_card.grid_columnconfigure(0, weight=1)
        
        self.song_name_label = ctk.CTkLabel(info_card, text="🎵 还没有选择歌曲喵~",
                                            font=ctk.CTkFont(size=16, weight="bold"),
                                            text_color=COLORS["text_primary"], wraplength=400)
        self.song_name_label.grid(row=0, column=0, pady=(15, 5))
        
        self.artist_label = ctk.CTkLabel(info_card, text="🐾 等待音乐中...",
                                         font=ctk.CTkFont(size=13), text_color=COLORS["text_secondary"])
        self.artist_label.grid(row=1, column=0, pady=(0, 15))
        
        # 进度条
        progress_frame = ctk.CTkFrame(content_frame, fg_color="transparent")
        progress_frame.grid(row=2, column=0, padx=25, pady=15, sticky="ew")
        progress_frame.grid_columnconfigure(0, weight=1)
        
        time_frame = ctk.CTkFrame(progress_frame, fg_color="transparent")
        time_frame.grid(row=0, column=0, sticky="ew")
        time_frame.grid_columnconfigure(1, weight=1)
        
        self.time_current = ctk.CTkLabel(time_frame, text="0:00", font=ctk.CTkFont(size=12),
                                         text_color=COLORS["text_secondary"])
        self.time_current.grid(row=0, column=0, padx=5)
        
        self.progress_var = tk.DoubleVar(value=0)
        self.progress_slider = tk.Scale(progress_frame, from_=0, to=1000,
                                         orient=tk.HORIZONTAL, variable=self.progress_var,
                                         bg=COLORS["bg_primary"], fg=COLORS["accent"],
                                         highlightthickness=0, troughcolor=COLORS["accent_light"],
                                         sliderrelief=tk.FLAT, sliderlength=15, width=12,
                                         showvalue=False)
        self.progress_slider.grid(row=1, column=0, sticky="ew", pady=5)
        
        self.progress_slider.bind("<ButtonPress-1>", self.on_progress_press)
        self.progress_slider.bind("<B1-Motion>", self.on_progress_drag)
        self.progress_slider.bind("<ButtonRelease-1>", self.on_progress_release)
        
        self.time_total = ctk.CTkLabel(time_frame, text="0:00", font=ctk.CTkFont(size=12),
                                       text_color=COLORS["text_secondary"])
        self.time_total.grid(row=0, column=2, padx=5)
        
        # 播放模式
        mode_frame = ctk.CTkFrame(content_frame, fg_color="transparent")
        mode_frame.grid(row=3, column=0, pady=10)
        
        self.mode_var = ctk.StringVar(value="list")
        modes = [("list", "🔁 列表循环"), ("single", "🔂 单曲循环"), ("random", "🔀 随机播放")]
        
        for i, (mode, text) in enumerate(modes):
            ctk.CTkRadioButton(mode_frame, text=text, variable=self.mode_var, value=mode,
                               command=self.change_mode, font=ctk.CTkFont(size=11),
                               fg_color=COLORS["accent"], hover_color=COLORS["accent_light"],
                               text_color=COLORS["text_primary"]).grid(row=0, column=i, padx=8)
        
        # 控制按钮
        control_frame = ctk.CTkFrame(content_frame, fg_color="transparent")
        control_frame.grid(row=4, column=0, pady=20)
        
        self.prev_btn = ctk.CTkButton(control_frame, text="⏮ 🐾", width=70, height=45,
                                      font=ctk.CTkFont(size=16), fg_color=COLORS["button_bg"],
                                      hover_color=COLORS["button_hover"], text_color="white",
                                      corner_radius=22, command=self.play_previous)
        self.prev_btn.grid(row=0, column=0, padx=10)
        
        self.play_btn = ctk.CTkButton(control_frame, text="▶ 播放", width=100, height=50,
                                      font=ctk.CTkFont(size=16, weight="bold"),
                                      fg_color=COLORS["accent_dark"],
                                      hover_color=COLORS["accent"], text_color="white",
                                      corner_radius=25, command=self.toggle_play)
        self.play_btn.grid(row=0, column=1, padx=15)
        
        self.next_btn = ctk.CTkButton(control_frame, text="🐾 ⏭", width=70, height=45,
                                      font=ctk.CTkFont(size=16), fg_color=COLORS["button_bg"],
                                      hover_color=COLORS["button_hover"], text_color="white",
                                      corner_radius=22, command=self.play_next)
        self.next_btn.grid(row=0, column=2, padx=10)
        
        # 音量
        volume_frame = ctk.CTkFrame(content_frame, fg_color="transparent")
        volume_frame.grid(row=5, column=0, pady=10)
        
        ctk.CTkLabel(volume_frame, text="🐱 🔇", font=ctk.CTkFont(size=14)).grid(row=0, column=0)
        
        self.volume_slider = ctk.CTkSlider(volume_frame, from_=0, to=100, width=180,
                                           button_color=COLORS["accent"],
                                           button_hover_color=COLORS["accent_dark"],
                                           progress_color=COLORS["accent"],
                                           fg_color=COLORS["accent_light"],
                                           command=self.change_volume)
        self.volume_slider.grid(row=0, column=1, padx=10)
        self.volume_slider.set(70)
        pygame.mixer.music.set_volume(0.7)
        
        ctk.CTkLabel(volume_frame, text="🔊 🐱", font=ctk.CTkFont(size=14)).grid(row=0, column=2)
        
        self.status_label = ctk.CTkLabel(content_frame, text="🐾 喵喵~ 请添加或选择歌单",
                                         font=ctk.CTkFont(size=11), text_color=COLORS["text_secondary"])
        self.status_label.grid(row=6, column=0, pady=10)
        
        # 右侧：歌单和播放列表
        right_frame = ctk.CTkFrame(main_frame, fg_color=COLORS["bg_secondary"], corner_radius=15)
        right_frame.grid(row=0, column=1, padx=10, pady=10, sticky="nsew")
        right_frame.grid_columnconfigure(0, weight=1)
        right_frame.grid_rowconfigure(1, weight=1)  # 歌曲列表区域占主要空间
        
        # 上方区域：歌单选择（固定大小，不占用太多空间）
        top_right_frame = ctk.CTkFrame(right_frame, fg_color="transparent")
        top_right_frame.grid(row=0, column=0, pady=(15, 5), padx=10, sticky="new")
        top_right_frame.grid_columnconfigure(0, weight=1)
        
        ctk.CTkLabel(top_right_frame, text="📂 歌单选择", 
                     font=ctk.CTkFont(size=14, weight="bold"),
                     text_color=COLORS["text_primary"]).pack(anchor="w")
        
        # 歌单列表 - 减小高度
        self.playlist_listbox = tk.Listbox(top_right_frame, bg=COLORS["list_bg"],
                                           fg=COLORS["text_primary"], 
                                           selectbackground=COLORS["accent"],
                                           selectforeground="white",
                                           font=("微软雅黑", 11), height=2,
                                           borderwidth=0, highlightthickness=0)
        self.playlist_listbox.pack(fill="x", pady=5)
        self.playlist_listbox.bind("<Double-Button-1>", self.on_playlist_select)
        self.playlist_listbox.bind("<ButtonRelease-1>", self.on_playlist_click)
        self.playlist_listbox.bind("<Button-3>", self.on_playlist_right_click)
        
        # 歌单操作按钮
        playlist_btn_frame = ctk.CTkFrame(top_right_frame, fg_color="transparent")
        playlist_btn_frame.pack(fill="x", pady=(0, 5))
        
        self.add_playlist_btn = ctk.CTkButton(playlist_btn_frame, text="➕ 添加歌单",
                                              font=ctk.CTkFont(size=11),
                                              fg_color=COLORS["accent"],
                                              hover_color=COLORS["accent_dark"],
                                              text_color="white", corner_radius=15,
                                              height=30, command=self.add_playlist)
        self.add_playlist_btn.pack(side="left", padx=2)
        
        self.del_playlist_btn = ctk.CTkButton(playlist_btn_frame, text="🗑 删除",
                                              font=ctk.CTkFont(size=11),
                                              fg_color="transparent",
                                              border_width=1,
                                              border_color=COLORS["accent"],
                                              text_color=COLORS["accent"],
                                              hover_color=COLORS["accent_light"],
                                              corner_radius=15, height=30,
                                              command=self.delete_playlist)
        self.del_playlist_btn.pack(side="left", padx=2)
        
        # 下方区域：歌曲列表（占据主要空间）
        bottom_right_frame = ctk.CTkFrame(right_frame, fg_color="transparent")
        bottom_right_frame.grid(row=1, column=0, padx=10, pady=5, sticky="nsew")
        bottom_right_frame.grid_columnconfigure(0, weight=1)
        bottom_right_frame.grid_rowconfigure(2, weight=1)
        
        # 标题和搜索框
        title_search_frame = ctk.CTkFrame(bottom_right_frame, fg_color="transparent")
        title_search_frame.grid(row=0, column=0, pady=(5, 5), sticky="ew")
        title_search_frame.grid_columnconfigure(1, weight=1)
        
        ctk.CTkLabel(title_search_frame, text="📋 歌曲列表 (可拖动排序)", 
                     font=ctk.CTkFont(size=14, weight="bold"),
                     text_color=COLORS["accent_dark"]).grid(row=0, column=0, sticky="w")
        
        # 搜索框
        self.search_var = tk.StringVar()
        self.search_var.trace("w", self.on_search_change)
        
        search_entry = ctk.CTkEntry(title_search_frame, 
                                    textvariable=self.search_var,
                                    placeholder_text="🔍 搜索歌曲...",
                                    font=ctk.CTkFont(size=11),
                                    fg_color="white",
                                    border_color=COLORS["accent_light"],
                                    text_color=COLORS["text_primary"],
                                    corner_radius=15,
                                    height=28,
                                    width=150)
        search_entry.grid(row=0, column=1, padx=(10, 0), sticky="e")
        
        # 歌曲列表 - 支持拖动排序，占据更多空间
        list_frame = ctk.CTkFrame(bottom_right_frame, fg_color=COLORS["list_bg"], corner_radius=10)
        list_frame.grid(row=2, column=0, sticky="nsew")
        list_frame.grid_columnconfigure(0, weight=1)
        list_frame.grid_rowconfigure(0, weight=1)
        
        self.song_listbox = tk.Listbox(list_frame, bg=COLORS["list_bg"],
                                       fg=COLORS["text_primary"],
                                       selectbackground=COLORS["list_select"],
                                       selectforeground=COLORS["text_primary"],
                                       font=("微软雅黑", 11), borderwidth=0,
                                       highlightthickness=0, activestyle="none", 
                                       relief="flat")
        self.song_listbox.grid(row=0, column=0, sticky="nsew", padx=5, pady=5)
        
        # 拖动排序绑定
        self.song_listbox.bind("<Button-1>", self.on_song_drag_start)
        self.song_listbox.bind("<B1-Motion>", self.on_song_drag_motion)
        self.song_listbox.bind("<ButtonRelease-1>", self.on_song_drag_release)
        self.song_listbox.bind("<Double-Button-1>", self.on_song_select)
        self.song_listbox.bind("<Button-3>", self.on_song_right_click)
        
        scrollbar = ctk.CTkScrollbar(list_frame, command=self.song_listbox.yview,
                                      button_color=COLORS["accent"],
                                      button_hover_color=COLORS["accent_dark"])
        scrollbar.grid(row=0, column=1, sticky="ns", pady=5)
        self.song_listbox.configure(yscrollcommand=scrollbar.set)
        
        # 底部统计 - 放在歌曲列表下方
        bottom_frame = ctk.CTkFrame(bottom_right_frame, fg_color="transparent")
        bottom_frame.grid(row=3, column=0, pady=(5, 0), sticky="ew")
        
        self.count_label = ctk.CTkLabel(bottom_frame, text="🎵 0 首歌曲",
                                        font=ctk.CTkFont(size=11), 
                                        text_color=COLORS["text_secondary"])
        self.count_label.pack()
        
        # 搜索状态
        self.filtered_indices = []  # 过滤后的歌曲在原列表中的索引
        self.is_searching = False   # 是否正在搜索
    
    # ==================== 辅助函数 ====================
    def get_display_name(self, filename):
        """获取歌曲显示名称（去掉扩展名）"""
        filename_lower = filename.lower()
        for ext in SUPPORTED_FORMATS:
            if filename_lower.endswith(ext):
                return filename[:-len(ext)]
        return filename
    
    # ==================== 歌单管理 ====================
    def auto_load_last_playlist(self):
        """自动加载上次歌单"""
        self.update_playlist_listbox()
        
        if self.current_playlist_name and self.current_playlist_name in self.playlists:
            self.switch_playlist(self.current_playlist_name)
        elif self.playlists:
            # 加载第一个歌单
            first_name = list(self.playlists.keys())[0]
            self.switch_playlist(first_name)
    
    def update_playlist_listbox(self):
        """更新歌单列表显示"""
        self.playlist_listbox.delete(0, tk.END)
        for name in self.playlists.keys():
            prefix = "▶ " if name == self.current_playlist_name else "  "
            self.playlist_listbox.insert(tk.END, f"{prefix}📁 {name}")
    
    def add_playlist(self):
        """添加歌单"""
        folder = filedialog.askdirectory(title="🐱 选择音乐文件夹作为歌单")
        if not folder:
            return
        
        # 使用文件夹名作为歌单名
        playlist_name = os.path.basename(folder) or "未命名歌单"
        
        # 如果重名，添加数字后缀
        base_name = playlist_name
        counter = 1
        while playlist_name in self.playlists:
            playlist_name = f"{base_name}_{counter}"
            counter += 1
        
        # 扫描歌曲（支持多种格式）
        audio_files = []
        unsupported_files = []
        for file in os.listdir(folder):
            file_lower = file.lower()
            if file_lower.endswith(SUPPORTED_FORMATS):
                audio_files.append((file, os.path.join(folder, file)))
            elif file_lower.endswith(KNOWN_UNSUPPORTED_FORMATS):
                unsupported_files.append(file)
        
        if not audio_files:
            formats_str = ", ".join(SUPPORTED_FORMATS)
            msg = f"所选文件夹中没有找到支持的音频文件喵~\n\n支持格式: {formats_str}"
            if unsupported_files:
                msg += f"\n\n检测到 {len(unsupported_files)} 个不支持的文件:\n"
                msg += "• APE 格式需要转换为 FLAC/MP3/WAV"
            messagebox.showinfo("🐱 喵喵提示", msg)
            return
        
        # 提示有 APE 文件被跳过
        if unsupported_files:
            ape_count = len(unsupported_files)
            messagebox.showwarning("🐱 格式提示", 
                f"检测到 {ape_count} 个 APE 格式文件被跳过喵~\n\n"
                f"APE 格式需要转换为以下格式才能播放:\n"
                f"• FLAC (无损，推荐)\n"
                f"• MP3 (兼容性好)\n"
                f"• WAV (无损，文件较大)")
        
        # 保存歌单
        self.playlists[playlist_name] = {
            'folder': folder,
            'songs': audio_files
        }
        
        self.save_config()
        self.update_playlist_listbox()
        self.switch_playlist(playlist_name)
        
        self.status_label.configure(text=f"🐱 已添加歌单 [{playlist_name}]，共 {len(audio_files)} 首喵~")
    
    def delete_playlist(self):
        """删除歌单"""
        selection = self.playlist_listbox.curselection()
        if not selection:
            messagebox.showinfo("🐱 提示", "请先选择要删除的歌单喵~")
            return
        
        index = selection[0]
        playlist_name = list(self.playlists.keys())[index]
        
        if messagebox.askyesno("🐱 确认删除", f"确定要删除歌单 [{playlist_name}] 吗？\n不会删除实际文件喵~"):
            del self.playlists[playlist_name]
            
            if self.current_playlist_name == playlist_name:
                self.current_playlist_name = None
                self.current_index = -1
                self.stop_playback()
            
            self.save_config()
            self.update_playlist_listbox()
            self.update_song_listbox()
            
            self.status_label.configure(text=f"🐱 已删除歌单 [{playlist_name}]")
    
    def on_playlist_click(self, event):
        """单击歌单选择"""
        selection = self.playlist_listbox.curselection()
        if selection:
            index = selection[0]
            playlist_name = list(self.playlists.keys())[index]
            if playlist_name != self.current_playlist_name:
                self.switch_playlist(playlist_name)
    
    def on_playlist_select(self, event):
        """双击歌单切换"""
        selection = self.playlist_listbox.curselection()
        if selection:
            index = selection[0]
            playlist_name = list(self.playlists.keys())[index]
            self.switch_playlist(playlist_name)
    
    def on_playlist_right_click(self, event):
        """歌单右键菜单"""
        # 获取点击的位置对应的索引
        index = self.playlist_listbox.nearest(event.y)
        if index < 0 or index >= self.playlist_listbox.size():
            return
        
        # 选中该项
        self.playlist_listbox.selection_clear(0, tk.END)
        self.playlist_listbox.selection_set(index)
        self.playlist_listbox.activate(index)
        
        # 创建右键菜单
        menu = tk.Menu(self.root, tearoff=0, bg=COLORS["list_bg"],
                       fg=COLORS["text_primary"], activebackground=COLORS["accent"],
                       activeforeground="white", font=("微软雅黑", 10))
        menu.add_command(label="📂 打开歌单所在目录", command=lambda idx=index: self.open_playlist_folder(idx))
        
        # 显示菜单
        menu.post(event.x_root, event.y_root)
    
    def open_playlist_folder(self, index):
        """打开歌单所在目录"""
        if index < 0 or index >= len(self.playlists):
            return
        playlist_name = list(self.playlists.keys())[index]
        folder = self.playlists[playlist_name].get('folder', '')
        
        if folder and os.path.exists(folder):
            try:
                # 使用 explorer 打开文件夹
                subprocess.Popen(['explorer', folder])
            except Exception as e:
                print(f"打开文件夹失败: {e}")
        else:
            messagebox.showwarning("🐱 提示", "该歌单的文件夹不存在喵~")
    
    def switch_playlist(self, playlist_name):
        """切换歌单"""
        if playlist_name not in self.playlists:
            return
        
        # 停止当前播放
        self.stop_playback()
        
        # 清空搜索框
        self.search_var.set("")
        self.is_searching = False
        
        self.current_playlist_name = playlist_name
        self.current_index = -1
        
        # 检查文件夹是否还存在
        folder = self.playlists[playlist_name]['folder']
        if not os.path.exists(folder):
            messagebox.showwarning("🐱 警告", f"歌单文件夹不存在了喵:\n{folder}")
            return
        
        # 刷新歌曲列表（防止文件夹内容有变化）
        self.refresh_playlist_songs(playlist_name)
        
        self.update_playlist_listbox()
        self.update_song_listbox()
        
        songs_count = len(self.playlists[playlist_name]['songs'])
        self.current_playlist_label.configure(text=f"当前歌单: {playlist_name}")
        self.count_label.configure(text=f"🎵 {songs_count} 首歌曲")
        self.status_label.configure(text=f"🐱 已切换到歌单 [{playlist_name}]，共 {songs_count} 首喵~")
        
        self.save_config()
    
    def refresh_playlist_songs(self, playlist_name):
        """刷新歌单歌曲列表（支持多种格式）"""
        folder = self.playlists[playlist_name]['folder']
        audio_files = []
        for file in os.listdir(folder):
            if file.lower().endswith(SUPPORTED_FORMATS):
                audio_files.append((file, os.path.join(folder, file)))
        
        # 保留原有排序（如果有）- 注意：APE 文件会被移除
        old_songs = self.playlists[playlist_name].get('songs', [])
        old_order = {name: i for i, (name, _) in enumerate(old_songs)}
        
        # 按原有顺序排序，新歌曲放最后
        audio_files.sort(key=lambda x: old_order.get(x[0], 999999))
        
        self.playlists[playlist_name]['songs'] = audio_files
    
    def stop_playback(self):
        """停止播放"""
        pygame.mixer.music.stop()
        self.is_playing = False
        self.is_paused = False
        self.current_pos = 0
        self.seek_time = 0
        self.play_btn.configure(text="▶ 播放")
        self.song_name_label.configure(text="🎵 还没有选择歌曲喵~")
        self.artist_label.configure(text="🐾 等待音乐中...")
        self.progress_var.set(0)
        self.time_current.configure(text="0:00")
        self.time_total.configure(text="0:00")
    
    # ==================== 歌曲列表搜索功能 ====================
    def on_search_change(self, *args):
        """搜索框内容变化时触发"""
        keyword = self.search_var.get().strip().lower()
        self.is_searching = bool(keyword)
        self.update_song_listbox()
    
    def get_displayed_songs(self):
        """获取当前要显示的歌曲列表（考虑搜索过滤）"""
        if not self.current_playlist_name:
            return [], []
        
        all_songs = self.playlists[self.current_playlist_name].get('songs', [])
        keyword = self.search_var.get().strip().lower()
        
        if not keyword:
            # 没有搜索关键词，显示全部
            self.filtered_indices = list(range(len(all_songs)))
            return all_songs, list(range(len(all_songs)))
        
        # 过滤歌曲
        filtered = []
        indices = []
        for i, (filename, filepath) in enumerate(all_songs):
            display_name = self.get_display_name(filename)
            if keyword in display_name.lower():
                filtered.append((filename, filepath))
                indices.append(i)
        
        self.filtered_indices = indices
        return filtered, indices
    
    # ==================== 歌曲列表拖动排序 ====================
    def update_song_listbox(self):
        """更新歌曲列表显示（支持搜索过滤）"""
        self.song_listbox.delete(0, tk.END)
        
        if not self.current_playlist_name:
            self.count_label.configure(text="🎵 0 首歌曲")
            return
        
        songs, original_indices = self.get_displayed_songs()
        all_songs = self.playlists[self.current_playlist_name].get('songs', [])
        
        for display_idx, ((filename, _), original_idx) in enumerate(zip(songs, original_indices)):
            display_name = self.get_display_name(filename)
            prefix = "▶ " if original_idx == self.current_index else "  "
            # 搜索模式下显示原始序号
            original_num = original_idx + 1
            self.song_listbox.insert(tk.END, f"{prefix}{original_num}. 🎵 {display_name}")
        
        # 更新计数
        total = len(all_songs)
        showing = len(songs)
        if self.is_searching:
            self.count_label.configure(text=f"🎵 显示 {showing}/{total} 首")
        else:
            self.count_label.configure(text=f"🎵 {total} 首歌曲")
    
    def on_song_drag_start(self, event):
        """开始拖动"""
        # 搜索模式下禁用拖动排序
        if self.is_searching:
            self.drag_start_index = None
            return
        self.drag_start_index = self.song_listbox.nearest(event.y)
    
    def on_song_drag_motion(self, event):
        """拖动中"""
        if self.drag_start_index is None or self.is_searching:
            return
        
        # 获取当前鼠标位置对应的索引
        cur_index = self.song_listbox.nearest(event.y)
        
        if cur_index != self.drag_start_index and 0 <= cur_index < self.song_listbox.size():
            # 交换位置
            self.song_listbox.delete(self.drag_start_index)
            
            songs = self.playlists[self.current_playlist_name]['songs']
            item = songs.pop(self.drag_start_index)
            songs.insert(cur_index, item)
            
            # 更新当前播放索引
            if self.current_index == self.drag_start_index:
                self.current_index = cur_index
            elif self.drag_start_index < self.current_index <= cur_index:
                self.current_index -= 1
            elif cur_index <= self.current_index < self.drag_start_index:
                self.current_index += 1
            
            self.drag_start_index = cur_index
            self.update_song_listbox()
            
            # 高亮当前拖动项
            self.song_listbox.selection_set(cur_index)
            self.song_listbox.see(cur_index)
    
    def on_song_drag_release(self, event):
        """释放拖动"""
        if self.drag_start_index is not None and not self.is_searching:
            self.save_config()
        self.drag_start_index = None
    
    def on_song_right_click(self, event):
        """歌曲右键菜单"""
        if not self.current_playlist_name:
            return
        
        # 获取点击的位置对应的索引（显示列表中的索引）
        display_index = self.song_listbox.nearest(event.y)
        if display_index < 0 or display_index >= self.song_listbox.size():
            return
        
        # 选中该项
        self.song_listbox.selection_clear(0, tk.END)
        self.song_listbox.selection_set(display_index)
        self.song_listbox.activate(display_index)
        
        # 获取原始索引
        if self.is_searching and display_index < len(self.filtered_indices):
            original_index = self.filtered_indices[display_index]
        else:
            original_index = display_index
        
        songs = self.playlists[self.current_playlist_name].get('songs', [])
        if not songs or original_index < 0 or original_index >= len(songs):
            return
        
        # 创建右键菜单
        menu = tk.Menu(self.root, tearoff=0, bg=COLORS["list_bg"],
                       fg=COLORS["text_primary"], activebackground=COLORS["accent"],
                       activeforeground="white", font=("微软雅黑", 10))
        menu.add_command(label="📂 打开歌曲所在目录", 
                        command=lambda idx=original_index: self.open_song_folder(idx))
        menu.add_separator()
        
        # 搜索模式下禁用上移下移
        if not self.is_searching:
            menu.add_command(label="⬆️ 上移", 
                            command=lambda idx=original_index: self.move_song_up(idx),
                            state="normal" if original_index > 0 else "disabled")
            menu.add_command(label="⬇️ 下移", 
                            command=lambda idx=original_index: self.move_song_down(idx),
                            state="normal" if original_index < len(songs) - 1 else "disabled")
            menu.add_separator()
        
        menu.add_command(label="🗑 删除歌曲", 
                        command=lambda idx=original_index: self.delete_song(idx),
                        foreground="#FF1493")
        
        # 显示菜单
        menu.post(event.x_root, event.y_root)
    
    def open_song_folder(self, index):
        """打开歌曲所在目录"""
        if not self.current_playlist_name:
            return
        
        songs = self.playlists[self.current_playlist_name].get('songs', [])
        if index < 0 or index >= len(songs):
            return
        
        _, filepath = songs[index]
        folder = os.path.dirname(filepath)
        
        if folder and os.path.exists(folder):
            try:
                # 使用 explorer 打开文件夹并选中文件
                subprocess.Popen(['explorer', '/select,', os.path.normpath(filepath)])
            except Exception as e:
                print(f"打开文件夹失败: {e}")
        else:
            messagebox.showwarning("🐱 提示", "该歌曲的文件不存在喵~")
    
    def move_song_up(self, index):
        """上移歌曲"""
        if not self.current_playlist_name or index <= 0:
            return
        
        songs = self.playlists[self.current_playlist_name].get('songs', [])
        if index >= len(songs):
            return
        
        # 交换位置
        songs[index], songs[index - 1] = songs[index - 1], songs[index]
        
        # 更新当前播放索引
        if self.current_index == index:
            self.current_index = index - 1
        elif self.current_index == index - 1:
            self.current_index = index
        
        self.update_song_listbox()
        self.save_config()
        
        # 保持选中状态
        self.song_listbox.selection_clear(0, tk.END)
        self.song_listbox.selection_set(index - 1)
        self.song_listbox.see(index - 1)
    
    def move_song_down(self, index):
        """下移歌曲"""
        if not self.current_playlist_name:
            return
        
        songs = self.playlists[self.current_playlist_name].get('songs', [])
        if index < 0 or index >= len(songs) - 1:
            return
        
        # 交换位置
        songs[index], songs[index + 1] = songs[index + 1], songs[index]
        
        # 更新当前播放索引
        if self.current_index == index:
            self.current_index = index + 1
        elif self.current_index == index + 1:
            self.current_index = index
        
        self.update_song_listbox()
        self.save_config()
        
        # 保持选中状态
        self.song_listbox.selection_clear(0, tk.END)
        self.song_listbox.selection_set(index + 1)
        self.song_listbox.see(index + 1)
    
    def delete_song(self, index):
        """删除歌曲"""
        if not self.current_playlist_name:
            return
        
        songs = self.playlists[self.current_playlist_name].get('songs', [])
        if index < 0 or index >= len(songs):
            return
        
        filename, filepath = songs[index]
        display_name = self.get_display_name(filename)
        
        if messagebox.askyesno("🐱 确认删除", f"确定要从歌单中删除歌曲 [{display_name}] 吗？\n\n注意：不会删除实际文件喵~"):
            # 如果正在播放这首歌，先停止
            if self.current_index == index and self.is_playing:
                self.stop_playback()
                self.current_index = -1
            elif self.current_index > index:
                self.current_index -= 1
            
            # 从列表中删除
            songs.pop(index)
            
            self.update_song_listbox()
            self.save_config()
            
            # 更新计数
            total = len(songs)
            self.count_label.configure(text=f"🎵 {total} 首歌曲")
            self.status_label.configure(text=f"🐱 已删除歌曲 [{display_name}]")
    
    def on_song_select(self, event):
        """双击播放歌曲（支持搜索过滤后的索引映射）"""
        selection = self.song_listbox.curselection()
        if not selection:
            return
        
        display_index = selection[0]
        
        # 如果有搜索过滤，需要映射回原始索引
        if self.is_searching and display_index < len(self.filtered_indices):
            original_index = self.filtered_indices[display_index]
            self.play_song(original_index)
        else:
            self.play_song(display_index)
    
    # ==================== 播放控制 ====================
    def play_song(self, index):
        """播放歌曲"""
        if not self.current_playlist_name:
            messagebox.showinfo("🐱 提示", "请先选择歌单喵~")
            return
        
        songs = self.playlists[self.current_playlist_name].get('songs', [])
        
        if not songs or index < 0 or index >= len(songs):
            return
        
        self.current_index = index
        filename, filepath = songs[index]
        
        try:
            pygame.mixer.music.load(filepath)
            pygame.mixer.music.play()
            
            self.is_playing = True
            self.is_paused = False
            self.current_pos = 0
            self.seek_time = 0
            self.play_btn.configure(text="⏸ 暂停")
            
            display_name = self.get_display_name(filename)
            self.song_name_label.configure(text=f"🎵 {display_name}")
            
            # 读取音频元数据（支持多种格式）
            try:
                from mutagen import File as MutagenFile
                audio = MutagenFile(filepath)
                if audio is not None:
                    self.song_length = audio.info.length
                    # 尝试读取艺术家信息
                    artist = "未知艺术家"
                    if hasattr(audio, 'tags') and audio.tags:
                        # 尝试不同的标签字段
                        if 'TPE1' in audio.tags:
                            artist = str(audio.tags['TPE1'])
                        elif 'artist' in audio.tags:
                            artist = str(audio.tags['artist'])
                        elif 'Artist' in audio.tags:
                            artist = str(audio.tags['Artist'])
                    self.artist_label.configure(text=f"🐾 {artist}")
                    self.time_total.configure(text=self.format_time(self.song_length))
                else:
                    raise Exception("无法解析音频文件")
            except Exception as e:
                self.song_length = 0
                self.artist_label.configure(text="🐾 未知艺术家")
                self.time_total.configure(text="0:00")
            
            self.update_song_listbox()
            
            # 在搜索模式下，找到当前播放歌曲在过滤列表中的位置并滚动到可见
            if self.is_searching:
                try:
                    display_idx = self.filtered_indices.index(index)
                    self.song_listbox.see(display_idx)
                except ValueError:
                    pass  # 当前播放歌曲不在搜索结果中
            else:
                self.song_listbox.see(index)
            
            self.status_label.configure(text=f"🐱 正在播放: {display_name[:25]}...")
            
        except Exception as e:
            messagebox.showerror("🐱 播放错误", f"无法播放该文件喵:\n{str(e)}")
    
    def toggle_play(self):
        """播放/暂停切换"""
        if not self.current_playlist_name:
            messagebox.showinfo("🐱 喵喵提示", "请先添加或选择歌单喵~")
            return
        
        songs = self.playlists[self.current_playlist_name].get('songs', [])
        if not songs:
            messagebox.showinfo("🐱 喵喵提示", "当前歌单没有歌曲喵~")
            return
        
        if self.current_index == -1:
            self.play_song(0)
            return
        
        if self.is_playing:
            pygame.mixer.music.pause()
            self.is_playing = False
            self.is_paused = True
            self.play_btn.configure(text="▶ 播放")
            self.status_label.configure(text="🐱 已暂停，点击继续听喵~")
        else:
            if self.is_paused:
                pygame.mixer.music.unpause()
            else:
                self.play_song(self.current_index)
            self.is_playing = True
            self.is_paused = False
            self.play_btn.configure(text="⏸ 暂停")
    
    def play_next(self):
        """下一曲"""
        if not self.current_playlist_name:
            return
        
        songs = self.playlists[self.current_playlist_name].get('songs', [])
        if not songs:
            return
        
        if self.play_mode == "random":
            next_index = random.randint(0, len(songs) - 1)
        else:
            next_index = (self.current_index + 1) % len(songs)
        
        self.play_song(next_index)
    
    def play_previous(self):
        """上一曲"""
        if not self.current_playlist_name:
            return
        
        songs = self.playlists[self.current_playlist_name].get('songs', [])
        if not songs:
            return
        
        if self.play_mode == "random":
            prev_index = random.randint(0, len(songs) - 1)
        else:
            prev_index = (self.current_index - 1) % len(songs)
        
        self.play_song(prev_index)
    
    # ==================== 进度条控制 ====================
    def on_progress_press(self, event):
        self.is_dragging = True
    
    def on_progress_drag(self, event):
        if self.song_length > 0:
            try:
                val = self.progress_var.get()
                pos = (val / 1000.0) * self.song_length
                self.time_current.configure(text=self.format_time(pos))
            except:
                pass
    
    def on_progress_release(self, event):
        if self.song_length > 0 and self.current_index >= 0:
            try:
                val = self.progress_var.get()
                target_pos = (val / 1000.0) * self.song_length
                self.seek_to_position(target_pos)
            except:
                pass
        self.is_dragging = False
    
    def seek_to_position(self, position):
        """跳转到指定位置"""
        try:
            if not self.current_playlist_name or self.current_index < 0:
                return
            
            songs = self.playlists[self.current_playlist_name].get('songs', [])
            filename, filepath = songs[self.current_index]
            was_playing = self.is_playing
            
            pygame.mixer.music.stop()
            time.sleep(0.05)
            
            pygame.mixer.music.load(filepath)
            
            if was_playing:
                pygame.mixer.music.play(start=position)
                self.is_playing = True
                self.is_paused = False
                self.seek_time = position
                self.current_pos = position
            else:
                pygame.mixer.music.play(start=position)
                pygame.mixer.music.pause()
                self.is_playing = False
                self.is_paused = True
                self.seek_time = position
                self.current_pos = position
            
            progress = (position / self.song_length) * 1000
            self.progress_var.set(progress)
            self.time_current.configure(text=self.format_time(position))
            
        except Exception as e:
            print(f"Seek error: {e}")
    
    def change_mode(self):
        """切换播放模式"""
        self.play_mode = self.mode_var.get()
        modes = {"list": "列表循环", "single": "单曲循环", "random": "随机播放"}
        self.status_label.configure(text=f"🐱 播放模式: {modes[self.play_mode]}喵~")
    
    def change_volume(self, value):
        pygame.mixer.music.set_volume(int(value) / 100)
    
    # ==================== 进度更新 ====================
    def update_progress_loop(self):
        """更新播放进度"""
        while self.running:
            try:
                if self.is_playing and not self.is_dragging and self.song_length > 0:
                    pos_from_play = pygame.mixer.music.get_pos() / 1000.0
                    
                    if pos_from_play >= 0:
                        self.current_pos = self.seek_time + pos_from_play
                        
                        if self.current_pos > self.song_length:
                            self.current_pos = self.song_length
                        
                        progress = (self.current_pos / self.song_length) * 1000
                        
                        self.root.after(0, lambda p=progress, t=self.current_pos: 
                                        self.update_progress_ui(p, t))
                        
                        is_busy = pygame.mixer.music.get_busy()
                        is_near_end = self.current_pos >= self.song_length - 0.5
                        
                        if (not is_busy and not self.is_paused) or is_near_end:
                            self.is_playing = False
                            self.root.after(0, self.on_song_end)
                            
            except:
                pass
            
            time.sleep(0.3)
    
    def update_progress_ui(self, progress, current_time):
        try:
            if not self.is_dragging:
                self.progress_var.set(progress)
                self.time_current.configure(text=self.format_time(current_time))
        except:
            pass
    
    def on_song_end(self):
        """歌曲结束"""
        try:
            self.current_pos = 0
            self.seek_time = 0
            
            if not self.current_playlist_name:
                return
            
            songs = self.playlists[self.current_playlist_name].get('songs', [])
            if not songs:
                return
            
            if self.play_mode == "single":
                self.play_song(self.current_index)
            else:
                if self.play_mode == "random":
                    next_index = random.randint(0, len(songs) - 1)
                else:
                    next_index = (self.current_index + 1) % len(songs)
                
                self.play_song(next_index)
        except Exception as e:
            print(f"Song end error: {e}")
    
    def format_time(self, seconds):
        try:
            minutes = int(seconds // 60)
            secs = int(seconds % 60)
            return f"{minutes}:{secs:02d}"
        except:
            return "0:00"
    
    # ==================== 猫咪动画 ====================
    def get_cat_art(self, state):
        """获取猫咪ASCII艺术"""
        cats = {
            "normal": (
                "      /\\_/\\      \n"
                "     ( o.o )     \n"
                "      > ^ <      \n"
                "     /|   |\\     \n"
                "    (_|   |_) 喵~"
            ),
            "happy": (
                "      /\\_/\\      \n"
                "     ( ^.^ )     \n"
                "      > ^ <      \n"
                "     /|   |\\     \n"
                "    (_|   |_) 喵喵~"
            ),
            "singing": (
                "      /\\_/\\      \n"
                "     ( > < )     \n"
                "      > ^ <      \n"
                "     /|   |\\     \n"
                "    (_|   |_) 啦啦~"
            ),
            "sleeping": (
                "      /\\_/\\      \n"
                "     ( -.- )     \n"
                "      > ^ <      \n"
                "     /|   |\\     \n"
                "    (_|   |_) 呼噜~"
            ),
            "listening": (
                "      /\\_/\\      \n"
                "     ( o_o )     \n"
                "      > ^ <      \n"
                "     /|   |\\     \n"
                "    (_|   |_) 好听~"
            )
        }
        return cats.get(state, cats["normal"])
    
    def cat_animation_loop(self):
        states = ["normal", "happy", "listening", "happy"]
        i = 0
        while self.running:
            try:
                if self.is_playing:
                    new_state = "singing"
                elif self.is_paused:
                    new_state = "listening"
                else:
                    new_state = states[i % len(states)]
                    i += 1
                
                if new_state != self.cat_state:
                    self.cat_state = new_state
                    art = self.get_cat_art(self.cat_state)
                    self.root.after(0, lambda a=art: self.cat_label.configure(text=a))
            except:
                pass
            
            time.sleep(2)
    
    # ==================== 系统托盘 ====================
    def create_tray_icon(self):
        try:
            icon_image = self.create_cat_icon()
            
            menu = Menu(
                MenuItem("🐱 显示界面", self._on_tray_show, default=True),
                MenuItem("⏸ 暂停/播放", self._on_tray_play),
                MenuItem("⏭ 下一曲", self._on_tray_next),
                Menu.SEPARATOR,
                MenuItem("❌ 退出", self._on_tray_exit)
            )
            
            self.tray_icon = pystray.Icon("cat_music_player", icon_image, 
                                           "🐱 猫猫给你唱歌~", menu)
            self.tray_running = True
            self.tray_icon.run()
        except Exception as e:
            print(f"Tray error: {e}")
        finally:
            self.tray_running = False
    
    def _on_tray_activate(self):
        """双击托盘图标显示主界面"""
        self.show_from_tray()
    
    def _on_tray_show(self, icon=None, item=None):
        self.show_from_tray()
    
    def _on_tray_play(self, icon=None, item=None):
        self.root.after(0, self.toggle_play)
    
    def _on_tray_next(self, icon=None, item=None):
        self.root.after(0, self.play_next)
    
    def _on_tray_exit(self, icon=None, item=None):
        self.exit_from_tray()
    
    def create_cat_icon(self):
        size = 64
        image = Image.new("RGBA", (size, size), (255, 255, 255, 0))
        draw = ImageDraw.Draw(image)
        
        pink = (255, 105, 180, 255)
        draw.ellipse([4, 4, size-4, size-4], fill=pink)
        
        white = (255, 255, 255, 255)
        draw.ellipse([18, 22, 28, 32], fill=white)
        draw.ellipse([36, 22, 46, 32], fill=white)
        draw.polygon([(32, 35), (28, 42), (36, 42)], fill=white)
        draw.polygon([(12, 8), (20, 20), (8, 20)], fill=pink)
        draw.polygon([(52, 8), (44, 20), (56, 20)], fill=pink)
        
        return image
    
    def on_minimize(self, event=None):
        """最小化到托盘"""
        # 在overrideredirect模式下，使用withdraw代替iconify
        self.minimize_to_tray()
    
    def minimize_to_tray(self):
        self.is_minimized_to_tray = True
        self.root.withdraw()
        
        if not self.tray_running:
            if self.tray_thread is None or not self.tray_thread.is_alive():
                self.tray_thread = threading.Thread(target=self.create_tray_icon, daemon=True)
                self.tray_thread.start()
    
    def show_from_tray(self):
        try:
            self.is_minimized_to_tray = False
            
            def do_show():
                try:
                    self.root.deiconify()
                    self.root.lift()
                    self.root.focus_force()
                    self.root.attributes('-topmost', True)
                    self.root.after(100, lambda: self.root.attributes('-topmost', False))
                except Exception as e:
                    print(f"Show window error: {e}")
            
            self.root.after(0, do_show)
            
            if self.tray_icon:
                icon = self.tray_icon
                self.tray_icon = None
                self.tray_running = False
                threading.Thread(target=icon.stop, daemon=True).start()
                
        except Exception as e:
            print(f"Show from tray error: {e}")
    
    def exit_from_tray(self):
        self.running = False
        self.tray_running = False
        if self.tray_icon:
            self.tray_icon.stop()
        self.root.after(0, self.root.destroy)
    
    def on_close(self):
        """关闭窗口"""
        self.save_config()
        self.running = False
        self.tray_running = False
        if self.tray_icon:
            self.tray_icon.stop()
        pygame.mixer.music.stop()
        self.root.destroy()


def main():
    root = ctk.CTk()
    app = CatMusicPlayer(root)
    root.mainloop()


if __name__ == "__main__":
    main()
