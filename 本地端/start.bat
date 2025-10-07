@echo off
chcp 65001 >nul
title 哈迪斯打包系统

echo ========================================
echo 哈迪斯打包系统启动脚本
echo ========================================
echo.

:: 检查Python是否安装
python --version >nul 2>&1
if %errorlevel% neq 0 (
    echo [错误] 未检测到Python，请先安装Python 3.7或更高版本
    echo 下载地址: https://www.python.org/downloads/
    pause
    exit /b 1
)

echo [信息] Python版本检查通过
echo.

:: 检查依赖包
echo [信息] 检查依赖包...
python -c "import PyQt5" >nul 2>&1
if %errorlevel% neq 0 (
    echo [警告] PyQt5未安装，正在安装依赖包...
    pip install PyQt5 PyQt5-tools
    if %errorlevel% neq 0 (
        echo [错误] 依赖包安装失败，请手动安装
        pause
        exit /b 1
    )
)

echo [信息] 依赖包检查完成
echo.

:: 检查数据库
if not exist "packing_system.db" (
    echo [信息] 首次运行，正在初始化数据库...
    python -c "from database import Database; Database()"
    echo [信息] 数据库初始化完成
    echo.
)

:: 启动应用程序
echo [信息] 启动哈迪斯打包系统...
echo [提示] 关闭此窗口将退出系统
echo.
python main.py

:: 如果程序异常退出，显示错误信息
if %errorlevel% neq 0 (
    echo.
    echo [错误] 程序异常退出，错误代码: %errorlevel%
    echo [建议] 请检查错误信息或联系技术支持
    pause
)