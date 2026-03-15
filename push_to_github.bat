@echo off
chcp 65001 >nul
echo 🐱 正在推送猫猫音乐播放器到 GitHub...
cd /d "%~dp0"

git branch -M main
git remote remove origin 2>nul
git remote add origin https://github.com/296569015/cat-music-player.git
git push -u origin main

if %errorlevel% == 0 (
    echo.
    echo ✅ 推送成功！
    echo 🌐 访问: https://github.com/296569015/cat-music-player
) else (
    echo.
    echo ❌ 推送失败，请检查：
    echo    1. 是否已在 GitHub 创建了 cat-music-player 仓库？
    echo    2. 网络连接是否正常？
    echo    3. 是否已配置 Git 用户名和邮箱？
)

pause
