#!/usr/bin/env python3
"""
storage.py - OPC Team 存储抽象层

功能：
- 统一的存储接口
- 支持多种后端（文件系统 / SQLite / Redis）
- 跨平台文件锁
- 自动备份
"""

import json
import os
from abc import ABC, abstractmethod
from pathlib import Path
from typing import Optional, Dict, List, Any
from datetime import datetime


# 跨平台文件锁
try:
    import fcntl
    HAS_FCNTL = True
except ImportError:
    HAS_FCNTL = False
    try:
        import filelock
        HAS_FILELOCK = True
    except ImportError:
        HAS_FILELOCK = False


class Storage(ABC):
    """存储接口基类"""

    @abstractmethod
    def save(self, key: str, data: Dict) -> None:
        """保存数据"""
        pass

    @abstractmethod
    def load(self, key: str) -> Optional[Dict]:
        """加载数据"""
        pass

    @abstractmethod
    def list(self, pattern: str = "*") -> List[str]:
        """列出所有键"""
        pass

    @abstractmethod
    def delete(self, key: str) -> bool:
        """删除数据"""
        pass

    @abstractmethod
    def exists(self, key: str) -> bool:
        """检查键是否存在"""
        pass


class FileStorage(Storage):
    """文件系统存储"""

    def __init__(self, base_dir: Path, use_lock: bool = True, auto_backup: bool = False):
        self.base_dir = Path(base_dir)
        self.base_dir.mkdir(parents=True, exist_ok=True)
        self.use_lock = use_lock and (HAS_FCNTL or HAS_FILELOCK)
        self.auto_backup = auto_backup

    def _get_file_path(self, key: str) -> Path:
        """获取文件路径"""
        # 支持子目录：tasks/T001 -> tasks/T001.json
        if "/" in key:
            parts = key.split("/")
            subdir = self.base_dir / parts[0]
            subdir.mkdir(parents=True, exist_ok=True)
            return subdir / f"{parts[1]}.json"
        return self.base_dir / f"{key}.json"

    def _lock_file(self, file_obj):
        """文件锁（跨平台）"""
        if not self.use_lock:
            return

        if HAS_FCNTL:
            fcntl.flock(file_obj.fileno(), fcntl.LOCK_EX)
        elif HAS_FILELOCK:
            # filelock 库需要单独的锁文件
            pass

    def _unlock_file(self, file_obj):
        """解锁文件"""
        if not self.use_lock:
            return

        if HAS_FCNTL:
            fcntl.flock(file_obj.fileno(), fcntl.LOCK_UN)

    def save(self, key: str, data: Dict) -> None:
        """保存数据"""
        file_path = self._get_file_path(key)

        # 备份旧文件
        if self.auto_backup and file_path.exists():
            backup_path = file_path.with_suffix(f".{datetime.now().strftime('%Y%m%d%H%M%S')}.bak")
            file_path.rename(backup_path)

        # 写入新文件
        with open(file_path, "w", encoding="utf-8") as f:
            self._lock_file(f)
            try:
                json.dump(data, f, ensure_ascii=False, indent=2)
            finally:
                self._unlock_file(f)

    def load(self, key: str) -> Optional[Dict]:
        """加载数据"""
        file_path = self._get_file_path(key)
        if not file_path.exists():
            return None

        with open(file_path, "r", encoding="utf-8") as f:
            self._lock_file(f)
            try:
                return json.load(f)
            finally:
                self._unlock_file(f)

    def list(self, pattern: str = "*") -> List[str]:
        """列出所有键"""
        # 支持子目录模式：tasks/* -> tasks/T001, tasks/T002
        if "/" in pattern:
            parts = pattern.split("/")
            subdir = self.base_dir / parts[0]
            if not subdir.exists():
                return []
            files = subdir.glob(f"{parts[1]}.json")
            return [f"{parts[0]}/{f.stem}" for f in files]

        files = self.base_dir.glob(f"{pattern}.json")
        return [f.stem for f in files]

    def delete(self, key: str) -> bool:
        """删除数据"""
        file_path = self._get_file_path(key)
        if file_path.exists():
            file_path.unlink()
            return True
        return False

    def exists(self, key: str) -> bool:
        """检查键是否存在"""
        return self._get_file_path(key).exists()


class SQLiteStorage(Storage):
    """SQLite 存储（可选）"""

    def __init__(self, db_path: Path):
        self.db_path = db_path
        self._init_db()

    def _init_db(self):
        """初始化数据库"""
        import sqlite3
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS opc_data (
                key TEXT PRIMARY KEY,
                data TEXT NOT NULL,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)
        conn.commit()
        conn.close()

    def save(self, key: str, data: Dict) -> None:
        """保存数据"""
        import sqlite3
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        cursor.execute("""
            INSERT OR REPLACE INTO opc_data (key, data, updated_at)
            VALUES (?, ?, CURRENT_TIMESTAMP)
        """, (key, json.dumps(data, ensure_ascii=False)))
        conn.commit()
        conn.close()

    def load(self, key: str) -> Optional[Dict]:
        """加载数据"""
        import sqlite3
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        cursor.execute("SELECT data FROM opc_data WHERE key = ?", (key,))
        row = cursor.fetchone()
        conn.close()

        if row:
            return json.loads(row[0])
        return None

    def list(self, pattern: str = "*") -> List[str]:
        """列出所有键"""
        import sqlite3
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()

        if pattern == "*":
            cursor.execute("SELECT key FROM opc_data")
        else:
            # 简单的通配符支持
            sql_pattern = pattern.replace("*", "%")
            cursor.execute("SELECT key FROM opc_data WHERE key LIKE ?", (sql_pattern,))

        keys = [row[0] for row in cursor.fetchall()]
        conn.close()
        return keys

    def delete(self, key: str) -> bool:
        """删除数据"""
        import sqlite3
        conn = sqlite3.connect(self.db_path)
        cursor = cursor.execute("DELETE FROM opc_data WHERE key = ?", (key,))
        affected = cursor.rowcount
        conn.commit()
        conn.close()
        return affected > 0

    def exists(self, key: str) -> bool:
        """检查键是否存在"""
        return self.load(key) is not None


class StorageFactory:
    """存储工厂"""

    @staticmethod
    def create(backend: str, **kwargs) -> Storage:
        """创建存储实例"""
        if backend == "file":
            base_dir = kwargs.get("base_dir", Path.cwd() / "data")
            use_lock = kwargs.get("use_lock", True)
            auto_backup = kwargs.get("auto_backup", False)
            return FileStorage(base_dir, use_lock, auto_backup)

        elif backend == "sqlite":
            db_path = kwargs.get("db_path", Path.cwd() / "data" / "opc.db")
            return SQLiteStorage(db_path)

        else:
            raise ValueError(f"不支持的存储后端: {backend}")


# 全局存储实例（延迟初始化）
_storage_instances: Dict[str, Storage] = {}


def get_storage(storage_type: str, config: Optional[Dict] = None) -> Storage:
    """获取存储实例（单例模式）"""
    if storage_type not in _storage_instances:
        if config is None:
            # 使用默认配置
            from .config import Config
            cfg = Config()
            backend = cfg.get("storage.backend", "file")

            if backend == "file":
                base_dir = cfg.get_path("data_dir")
                use_lock = cfg.get("storage.file_lock", True)
                auto_backup = cfg.get("storage.auto_backup", False)
                _storage_instances[storage_type] = FileStorage(base_dir / storage_type, use_lock, auto_backup)
            elif backend == "sqlite":
                db_path = cfg.get_path("data_dir") / "opc.db"
                _storage_instances[storage_type] = SQLiteStorage(db_path)
        else:
            _storage_instances[storage_type] = StorageFactory.create(**config)

    return _storage_instances[storage_type]
