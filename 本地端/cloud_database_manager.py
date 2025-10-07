# 云数据库管理工具
# 用于在微信云开发控制台创建数据库集合和索引

import json
import os
from typing import Dict, List

class CloudDatabaseManager:
    """云数据库管理器"""
    
    def __init__(self):
        self.collections = {
            'components': {
                'description': '板件数据集合',
                'indexes': [
                    {'name': 'component_code_idx', 'fields': ['component_code']},
                    {'name': 'order_number_idx', 'fields': ['order_number']},
                    {'name': 'package_id_idx', 'fields': ['package_id']},
                    {'name': 'status_idx', 'fields': ['status']},
                    {'name': 'updated_at_idx', 'fields': ['updated_at']}
                ]
            },
            'packages': {
                'description': '包裹数据集合',
                'indexes': [
                    {'name': 'package_number_idx', 'fields': ['package_number']},
                    {'name': 'order_number_idx', 'fields': ['order_number']},
                    {'name': 'pallet_id_idx', 'fields': ['pallet_id']},
                    {'name': 'status_idx', 'fields': ['status']},
                    {'name': 'updated_at_idx', 'fields': ['updated_at']}
                ]
            },
            'pallets': {
                'description': '托盘数据集合',
                'indexes': [
                    {'name': 'pallet_number_idx', 'fields': ['pallet_number']},
                    {'name': 'order_number_idx', 'fields': ['order_number']},
                    {'name': 'status_idx', 'fields': ['status']},
                    {'name': 'updated_at_idx', 'fields': ['updated_at']}
                ]
            }
        }
        
    def generate_setup_instructions(self) -> str:
        """生成云数据库设置说明"""
        instructions = """
# 微信云开发数据库设置说明

## 1. 创建数据库集合

在微信开发者工具中，按照以下步骤操作：

### 步骤1：打开云开发控制台
1. 打开微信开发者工具
2. 选择你的小程序项目
3. 点击顶部菜单栏的【云开发】
4. 进入【数据库】页面

### 步骤2：创建集合
在数据库页面，点击【+】按钮创建以下集合：

"""
        
        for collection_name, collection_info in self.collections.items():
            instructions += f"""
#### {collection_name}
- 集合名称：`{collection_name}`
- 描述：{collection_info['description']}

"""
        
        instructions += """
### 步骤3：创建索引
为每个集合创建以下索引以提高查询性能：

"""
        
        for collection_name, collection_info in self.collections.items():
            instructions += f"""
#### {collection_name} 集合索引：
"""
            for index in collection_info['indexes']:
                instructions += f"""
- 索引名称：`{index['name']}`
- 索引字段：`{', '.join(index['fields'])}`
"""
            instructions += "\n"
        
        instructions += """
### 步骤4：设置权限
为每个集合设置以下权限规则：

```json
{
  "read": true,
  "write": true
}
```

或者更精细的权限控制：

```json
{
  "read": "auth != null",
  "write": "auth != null"
}
```

### 步骤5：数据导入
使用以下文件进行数据导入：

1. 板件数据：`cloud_sync_components_*.json`
2. 包裹数据：`cloud_sync_packages_*.json`
3. 托盘数据：`cloud_sync_pallets_*.json`

在数据库页面，选择对应的集合，点击【导入】按钮，选择相应的JSON文件。

## 2. 云函数部署

确保以下云函数已正确部署：

1. `searchComponents` - 查询板件
2. `searchPackages` - 查询包裹
3. `searchPallets` - 查询托盘
4. `getStatistics` - 获取统计数据

## 3. 小程序配置

确保小程序配置正确：

1. `config.js` 中 `USE_CLOUD_DATABASE` 设置为 `true`
2. 小程序已启用云开发能力
3. 环境ID配置正确

## 4. 验证步骤

1. 在小程序中点击【测试数据库连接】
2. 查询板件、包裹、托盘数据
3. 确认数据能够正常显示
4. 检查云开发控制台中的数据是否正确

## 5. 注意事项

1. 确保云开发环境已开通
2. 数据库权限设置正确
3. 索引创建完整以提高查询性能
4. 定期备份重要数据
5. 监控云开发资源使用情况

## 6. 问题排查

如果遇到问题，请检查：

1. 云开发环境是否正常
2. 数据库集合是否存在
3. 权限设置是否正确
4. 云函数是否正确部署
5. 小程序配置是否正确
"""
        
        return instructions
        
    def save_setup_instructions(self, filename: str = 'cloud_database_setup_instructions.md'):
        """保存设置说明到文件"""
        instructions = self.generate_setup_instructions()
        with open(filename, 'w', encoding='utf-8') as f:
            f.write(instructions)
        print(f"云数据库设置说明已保存到: {filename}")

if __name__ == '__main__':
    # 创建云数据库管理器
    manager = CloudDatabaseManager()
    
    # 生成并保存设置说明
    manager.save_setup_instructions()
    
    print("云数据库管理文件生成完成！")
    print("请按照 cloud_database_setup_instructions.md 中的说明在微信云开发控制台创建数据库集合。")