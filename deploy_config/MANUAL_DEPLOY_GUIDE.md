# 微信云函数手动部署指南

## 📋 部署前准备
- 环境ID: `cloud1-7grjr7usb5d86f59`
- API密钥: `hds202hds202`
- 生成时间: `2025-10-02 18:02:00`

## 🖥️ 方法1：微信开发者工具手动部署

### 步骤1：打开微信开发者工具
1. 启动微信开发者工具
2. 打开您的小程序项目
3. 点击顶部菜单栏【云开发】

### 步骤2：进入云函数管理
1. 在云开发控制台中，点击【云函数】
2. 点击【新建云函数】按钮

### 步骤3：部署各个云函数

#### 🔍 searchComponents（查询板件）
- 函数名称: `searchComponents`
- 运行环境: `Node.js 16.13`
- 函数代码: 上传 `XCX/cloudfunctions/searchComponents` 文件夹
- 内存: 128MB
- 超时时间: 60秒
- 环境变量: 
  - `API_KEY = hds202hds202`
  - `ENV_ID = cloud1-7grjr7usb5d86f59`

#### 📦 searchPackages（查询包裹）
- 函数名称: `searchPackages`
- 运行环境: `Node.js 16.13`
- 函数代码: 上传 `XCX/cloudfunctions/searchPackages` 文件夹
- 内存: 128MB
- 超时时间: 60秒
- 环境变量:
  - `API_KEY = hds202hds202`
  - `ENV_ID = cloud1-7grjr7usb5d86f59`

#### 🏷️ searchPallets（查询托盘）
- 函数名称: `searchPallets`
- 运行环境: `Node.js 16.13`
- 函数代码: 上传 `XCX/cloudfunctions/searchPallets` 文件夹
- 内存: 128MB
- 超时时间: 60秒
- 环境变量:
  - `API_KEY = hds202hds202`
  - `ENV_ID = cloud1-7grjr7usb5d86f59`

#### 📊 getStatistics（获取统计）
- 函数名称: `getStatistics`
- 运行环境: `Node.js 16.13`
- 函数代码: 上传 `XCX/cloudfunctions/getStatistics` 文件夹
- 内存: 128MB
- 超时时间: 60秒
- 环境变量:
  - `API_KEY = hds202hds202`
  - `ENV_ID = cloud1-7grjr7usb5d86f59`

#### 🔧 repairOps（数据修复）
- 函数名称: `repairOps`
- 运行环境: `Node.js 16.13`
- 函数代码: 上传 `XCX/cloudfunctions/repairOps` 文件夹
- 内存: 256MB
- 超时时间: 120秒
- 环境变量:
  - `API_KEY = hds202hds202`
  - `ENV_ID = cloud1-7grjr7usb5d86f59`

#### 📦 packOps（数据同步与查询服务）
- 函数名称: `packOps`
- 运行环境: `Node.js 16.13`
- 函数代码: 上传 `XCX/cloudfunctions/packOps` 文件夹
- 内存: 256MB
- 超时时间: 120秒
- 环境变量:
  - `API_KEY = hds202hds202`
  - `ENV_ID = cloud1-7grjr7usb5d86f59`
- 功能说明:
  - 提供本地系统与云数据库的可靠同步接口
  - 支持板件、包裹、托盘的查询功能
  - 包含一次性迁移工具用于修复云端数据

### 步骤4：部署并测试
1. 点击【部署】按钮
2. 等待部署完成（每个函数约1-2分钟）
3. 使用【测试】功能验证每个云函数

## ⚙️ 方法2：使用微信云开发CLI（高级用户）

### 安装CLI工具
```bash
npm install -g @cloudbase/cli
```

### 登录认证
```bash
tcb login
```

### 批量部署
```bash
# 运行生成的部署脚本
./deploy_config/deploy_cloud_functions.sh
```

## 🧪 部署后验证

### 测试各个云函数
```javascript
// 测试查询函数
tcb fn invoke searchComponents --data '{"code":"TEST001"}' --env-id cloud1-7grjr7usb5d86f59

// 测试统计函数
tcb fn invoke getStatistics --data '{}' --env-id cloud1-7grjr7usb5d86f59
```

### 验证要点
- ✅ 所有函数部署成功
- ✅ 函数调用返回正确数据
- ✅ 无运行时错误
- ✅ 响应时间在预期范围内

## 🔍 常见问题排查

### 部署失败
1. 检查网络连接
2. 确认环境ID正确
3. 验证代码包完整性
4. 查看部署日志

### 函数运行错误
1. 检查环境变量设置
2. 确认数据库权限
3. 验证依赖包安装
4. 查看函数运行日志

### 性能问题
1. 调整内存配置
2. 优化数据库查询
3. 增加索引优化
4. 考虑缓存策略

## 📞 技术支持
如遇到问题，请检查微信云开发官方文档或联系技术支持。
