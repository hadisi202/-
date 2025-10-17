# 哈迪斯板件家具打包系统 v1.0

## 项目简介

哈迪斯板件家具打包系统是一个专业的板件家具生产打包管理系统，基于PyQt5开发的桌面应用程序。该系统提供了完整的订单管理、扫码打包、托盘管理、标签打印和数据统计功能，旨在提高板件家具生产企业的打包效率和管理水平。

## 主要功能

### 📋 订单管理
- **CSV数据导入**: 支持从Excel/CSV文件批量导入订单和板件数据
- **订单信息管理**: 管理客户信息、订单详情、板件清单
- **灵活的字段映射**: 可配置CSV文件字段与系统字段的对应关系
- **订单状态跟踪**: 实时跟踪订单处理进度

### 📦 扫描打包
- **智能扫码识别**: 支持多种扫码格式，可配置扫码处理规则
- **实时包装管理**: 扫码即时添加板件到包装中
- **包装状态控制**: 支持包装的开启、完成、撤销等操作
- **错误处理机制**: 完善的异常处理和撤销功能

### 🚛 托盘管理
- **物理托盘管理**: 管理实体托盘的装载和封装
- **虚拟托盘支持**: 支持虚拟物品的托盘管理
- **包装装载跟踪**: 实时跟踪托盘中的包装数量和状态
- **托盘封装控制**: 支持托盘的封装和重新开启

### 🏷️ 标签打印
- **可视化标签设计**: 拖拽式标签模板设计器
- **多种元素支持**: 支持文本、二维码、条形码等元素
- **模板管理**: 支持多套标签模板的保存和切换
- **批量打印**: 支持批量生成和打印标签

### 📊 报表统计
- **数据统计分析**: 提供详细的生产数据统计
- **报表导出**: 支持导出Excel格式的统计报表
- **实时状态监控**: 实时显示系统运行状态和统计信息

### ⚙️ 系统设置
- **扫码配置**: 灵活的扫码处理规则配置
- **导入配置**: CSV导入字段映射配置
- **系统参数**: 各种系统参数的配置管理

### 🔧 异常处理
- **操作撤销**: 支持关键操作的撤销功能
- **错误日志**: 详细的操作日志和错误记录
- **数据恢复**: 支持数据备份和恢复功能

## 技术架构

### 开发环境
- **编程语言**: Python 3.7+
- **GUI框架**: PyQt5
- **数据库**: SQLite3
- **开发工具**: 支持Windows平台

### 核心模块

#### 主程序模块 (`main.py`)
- 应用程序入口和主窗口管理
- 模块化的标签页界面设计
- 启动画面和应用程序生命周期管理
- 菜单栏和状态栏管理

#### 数据库模块 (`database.py`)
- SQLite数据库连接和管理
- 数据表结构定义和初始化
- 数据库迁移和版本管理
- 系统设置和配置管理

#### 订单管理模块 (`order_management.py`)
- CSV数据导入和解析
- 订单和板件数据管理
- 字段映射配置
- 数据验证和错误处理

#### 扫描打包模块 (`scan_packaging.py`)
- 扫码配置和处理逻辑
- 包装创建和管理
- 板件扫码添加
- 包装状态控制

#### 托盘管理模块 (`pallet_management.py`)
- 托盘创建和管理
- 包装装载控制
- 虚拟物品管理
- 托盘封装流程

#### 标签打印模块 (`label_printing.py`)
- 标签模板设计器
- 标签元素管理
- 打印预览和输出
- 模板保存和加载

#### 报表统计模块 (`reports.py`)
- 数据统计和分析
- 报表生成和导出
- 图表展示功能

#### 系统设置模块 (`system_settings.py`)
- 系统参数配置
- 扫码规则设置
- 导入配置管理

#### 异常处理模块 (`error_handling.py`)
- 操作撤销管理
- 错误日志记录
- 异常恢复机制

## 数据库结构

### 主要数据表

#### orders (订单表)
- `id`: 主键
- `order_number`: 订单号
- `customer_name`: 客户名称
- `customer_address`: 客户地址
- `customer_phone`: 客户电话
- `created_at`: 创建时间
- `status`: 订单状态

#### components (板件表)
- `id`: 主键
- `order_id`: 订单ID
- `component_name`: 板件名称
- `material`: 材质
- `finished_size`: 成品尺寸
- `component_code`: 板件编码
- `room_number`: 房间号
- `cabinet_number`: 柜号
- `package_id`: 包装ID
- `status`: 板件状态

#### packages (包装表)
- `id`: 主键
- `package_number`: 包装号
- `order_id`: 订单ID
- `component_count`: 板件数量
- `pallet_id`: 托盘ID
- `status`: 包装状态

#### pallets (托盘表)
- `id`: 主键
- `pallet_number`: 托盘号
- `pallet_type`: 托盘类型
- `package_count`: 包装数量
- `status`: 托盘状态

#### label_templates (标签模板表)
- `id`: 主键
- `template_name`: 模板名称
- `template_config`: 模板配置
- `label_width`: 标签宽度
- `label_height`: 标签高度

## 安装和使用

### 系统要求
- Windows 7/8/10/11
- Python 3.7 或更高版本
- 至少 2GB 内存
- 100MB 可用磁盘空间

### 安装步骤

1. **安装Python环境**
   ```bash
   # 安装Python 3.7+
   # 确保勾选"Add Python to PATH"选项
   ```

2. **安装依赖包**
   ```bash
   pip install -r requirements.txt
   ```

3. **运行程序**
   ```bash
   # 方式1: 直接运行Python文件
   python main.py
   
   # 方式2: 使用启动脚本
   start.bat
   ```

### 快速开始

1. **启动系统**
   - 双击 `start.bat` 或运行 `python main.py`
   - 系统将显示启动画面并初始化数据库

2. **导入订单数据**
   - 点击"订单管理"标签页
   - 点击"导入CSV数据"按钮
   - 选择包含订单和板件信息的CSV文件
   - 配置字段映射关系
   - 确认导入数据

3. **开始打包作业**
   - 切换到"扫描打包"标签页
   - 选择要打包的订单
   - 创建新包装
   - 扫描板件编码添加到包装中
   - 完成包装

4. **托盘管理**
   - 切换到"托盘管理"标签页
   - 创建新托盘
   - 扫描包装号添加到托盘
   - 封装托盘

5. **打印标签**
   - 切换到"标签打印"标签页
   - 选择标签模板
   - 选择要打印的包装或托盘
   - 预览并打印标签

## 配置文件说明

### qr_settings.json

## 构建与打包

- 使用 `packing_system.spec` 构建：在项目根目录执行 `pyinstaller packing_system.spec`。
- 构建产物位置：
  - 单目录版：`dist\PackingSystem\PackingSystem.exe`（推荐用于分发与运行）
  - 单文件版：`dist\PackingSystem.exe`
- 数据资源打包：已包含 `qr_settings.json`、`preview_component_display.html`、`templates/`、`custom_templates/`、`orders/`。
- 运行建议：优先使用单目录版，启动更快、被杀毒误报的概率更低。

### 修复说明（pyzbar DLL 缺失）
- 现象：直接使用命令 `pyinstaller -D -w -i ico10.ico main.py` 打包后，启动报错 `libiconv.dll` 未找到，`pyzbar` 无法加载。
- 修复：在 `packing_system.spec` 中动态收集并打包 `pyzbar` 的 DLL 文件：
  - 收集目录：`dist\PackingSystem\_internal\pyzbar`
  - 包含文件：`libiconv.dll`、`libzbar-64.dll`（以及其他匹配的 `libzbar*.dll`）
  - 同时将 `pyzbar`、`pyzbar.pyzbar`、`pyzbar.wrapper` 加入 `hiddenimports`
- 不使用 spec 的替代打包命令：
  - `pyinstaller -D -w -i ico10.ico main.py --collect-binaries pyzbar`

### 验证步骤
- 运行：`dist\PackingSystem\PackingSystem.exe`
- 检查 DLL：确认存在 `dist\PackingSystem\_internal\pyzbar\libiconv.dll` 与 `libzbar-64.dll`
- 首次运行前：确保 `orders/` 目录与 `packing_system.db` 文件具有读写权限

### 常见问题
- 启动报 `libiconv.dll` 缺失：请使用 `packing_system.spec` 构建或在命令行加 `--collect-binaries pyzbar`
- 单文件版启动缓慢：属正常现象（解压到临时目录）；建议改用单目录版
- 图标缺失：确认 `ico10.ico` 在项目根目录且在 spec 的 `icon` 字段正确指向
QR码和扫码相关配置：
```json
{
  "package_patterns": ["^[A-Z]{2,4}\\d{8,12}$"],
  "custom_prefix": "HDS",
  "auto_generate": true,
  "qr_size": 200,
  "qr_border": 4
}
```

### 标签模板文件
位于 `templates/` 和 `custom_templates/` 目录：
- 支持JSON格式的标签模板定义
- 包含画布尺寸、元素位置、字体样式等配置
- 支持文本、二维码等多种元素类型

## 常见问题

### Q: 导入CSV文件时出现编码错误？
A: 请确保CSV文件使用UTF-8编码保存，或在导入时选择正确的编码格式。

### Q: 扫码无法识别？
A: 检查扫码配置是否正确，可以在"系统设置"中调整扫码处理规则。

### Q: 标签打印不正常？
A: 确认打印机驱动正常，检查标签模板配置是否正确。

### Q: 数据库文件损坏？
A: 使用"工具"菜单中的"数据库恢复"功能，或从备份文件恢复。

## 开发说明

### 项目结构
```
021/
├── main.py                 # 主程序入口
├── database.py            # 数据库管理
├── order_management.py    # 订单管理模块
├── scan_packaging.py      # 扫描打包模块
├── pallet_management.py   # 托盘管理模块
├── label_printing.py      # 标签打印模块
├── reports.py            # 报表统计模块
├── system_settings.py    # 系统设置模块
├── error_handling.py     # 异常处理模块
├── qr_handler.py         # QR码处理
├── order_manager.py      # 订单管理器
├── report_generator.py   # 报表生成器
├── start.bat            # 启动脚本
├── packing_system.db    # SQLite数据库文件
├── qr_settings.json     # QR码配置文件
├── templates/           # 标签模板目录
├── custom_templates/    # 自定义模板目录
├── orders/             # 订单文件目录
└── reports/            # 报表输出目录
```

### 扩展开发
- 所有模块都采用面向对象设计，便于扩展
- 数据库操作统一通过database.py模块
- 界面组件采用PyQt5标准控件
- 支持插件式功能扩展

## 版本历史

### v1.0 (当前版本)
- 完整的订单管理功能
- 扫码打包作业流程
- 托盘管理和虚拟物品支持
- 可视化标签设计和打印
- 数据统计和报表导出
- 系统配置和异常处理

### 更新说明（2025-09-30）
- 待包板件删除后联动刷新订单管理页组件与总数。
- 托盘管理入托成功后切换显示当前订单的剩余包裹列表。
- 统一交互提示为 Prompt（信息/警告/错误与确认）。

## 技术支持

**开发者**: 哈迪斯 李昌顺  
**联系方式**: [请联系开发者获取技术支持]

## 许可证

本软件为专有软件，版权归开发者所有。未经授权不得复制、分发或修改。

---

*最后更新: 2025年*
