# -*- coding: utf-8 -*-
from database import db
print('db_path:', db.db_path)
print('backup_path:', db.get_setting('backup_path', './backups'))
print('backup_compress_enabled:', db.get_setting('backup_compress_enabled', 'true'))
print('auto_backup_enabled:', db.get_setting('auto_backup_enabled', 'false'))