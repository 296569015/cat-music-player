"""
打包脚本：将猫猫音乐播放器打包成 exe 文件
"""
import PyInstaller.__main__
import os

# 获取当前目录
base_dir = os.path.dirname(os.path.abspath(__file__))

# 打包参数
args = [
    'music_player.py',  # 主程序文件
    '--name=猫猫音乐播放器',  # 应用程序名称
    '--onefile',  # 打包成单个 exe 文件
    '--windowed',  # 不显示控制台窗口
    '--clean',  # 清理临时文件
    '--noconfirm',  # 不确认覆盖
    # 隐藏导入
    '--hidden-import=customtkinter',
    '--hidden-import=pygame',
    '--hidden-import=mutagen.mp3',
    '--hidden-import=mutagen.id3',
    '--hidden-import=PIL.Image',
    '--hidden-import=PIL.ImageDraw',
    '--hidden-import=pystray',
]

print("开始打包猫猫音乐播放器...")
print("=" * 50)

PyInstaller.__main__.run(args)

print("=" * 50)
print("打包完成！")
print(f"可执行文件位置: {os.path.join(base_dir, 'dist', '猫猫音乐播放器.exe')}")
print("\n提示：第一次运行时会自动创建 player_config.json 配置文件")
