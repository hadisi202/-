import os
import sys
from PyQt5.QtWidgets import QApplication

# 修正模块导入路径到项目根目录
PROJECT_ROOT = os.path.dirname(os.path.dirname(__file__))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

from reports import ExportWorker

# 初始化 Qt 应用以满足可能的信号/线程依赖
app = QApplication(sys.argv)

exports_dir = os.path.join(PROJECT_ROOT, 'exports')
os.makedirs(exports_dir, exist_ok=True)

base_file = os.path.join(exports_dir, 'export_test.xlsx')
filters = {
    'include_package_qr': False,
    'include_pallet_qr': False,
}

export_types = [
    ('pallets', base_file.replace('.xlsx', '_pallets.xlsx')),
    ('package_components', base_file.replace('.xlsx', '_package_components.xlsx')),
    ('pallet_package_components', base_file.replace('.xlsx', '_pallet_package_components.xlsx')),
]

results = []
for etype, fpath in export_types:
    try:
        worker = ExportWorker(etype, fpath, filters)
        # 直接调用 run()，避免对话框交互
        worker.run()
        results.append((etype, True, fpath))
    except Exception as e:
        results.append((etype, False, str(e)))

for etype, ok, info in results:
    print(f"{etype}: {'OK' if ok else 'FAILED'} -> {info}")

print('DONE')