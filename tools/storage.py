#!/usr/bin/env python3
"""
storage.py - OPC Team 存储抽象层

功能：
- 统一的存储接口
- 支持两种后端：文件系统（默认）/ SQLite
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
HAS_FILELOCK = False
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
            import filelock
            lock_path = str(file_obj.name) + ".lock"
            lock = filelock.FileLock(lock_path)
            lock.acquire()
            setattr(file_obj, "_opc_lock", lock)

    def _unlock_file(self, file_obj):
        """解锁文件"""
        if not self.use_lock:
            return

        if HAS_FCNTL:
            fcntl.flock(file_obj.fileno(), fcntl.LOCK_UN)
        elif HAS_FILELOCK:
            lock = getattr(file_obj, "_opc_lock", None)
            if lock is not None:
                lock.release()
                delattr(file_obj, "_opc_lock")

    def _normalize_list_pattern(self, pattern: str) -> str:
        """兼容带或不带 .json 后缀的查询模式。"""
        if pattern.endswith(".json"):
            return pattern[:-5]
        return pattern

    def save(self, key: str, data: Dict) -> None:
        """保存数据"""
        file_path = self._get_file_path(key)

        # 备份旧文件
        if self.auto_backup and file_path.exists():
            backup_path = file_path.with_suffix(f".{datetime.now().strftime('%Y%m%d%H%M%S')}.bak")
            file_path.rename(backup_path)

        # 先加锁再覆盖，避免并发 open(..., "w") 提前截断导致文件损坏。
        mode = "r+" if file_path.exists() else "w+"
        with open(file_path, mode, encoding="utf-8") as f:
            self._lock_file(f)
            try:
                f.seek(0)
                json.dump(data, f, ensure_ascii=False, indent=2)
                f.truncate()
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
        pattern = self._normalize_list_pattern(pattern)

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
    """SQLite 存储。

    All storage types share a single ``opc.db`` so that one file holds the
    whole workspace. To avoid key collisions across types (e.g. a task ``T001``
    vs. an agent record ``T001``), every storage type passes a distinct
    ``namespace`` which is transparently prefixed onto keys at the SQL layer.
    Callers continue to use bare keys (``T001``, ``default/ceo``) — the
    namespace is invisible to them.
    """

    NAMESPACE_SEP = "::"

    def __init__(self, db_path: Path, namespace: str = ""):
        self.db_path = db_path
        self.namespace = namespace
        self._init_db()

    def _scoped(self, key: str) -> str:
        if not self.namespace:
            return key
        return f"{self.namespace}{self.NAMESPACE_SEP}{key}"

    def _unscoped(self, scoped_key: str) -> str:
        prefix = f"{self.namespace}{self.NAMESPACE_SEP}" if self.namespace else ""
        if prefix and scoped_key.startswith(prefix):
            return scoped_key[len(prefix):]
        return scoped_key

    def _init_db(self):
        """初始化数据库"""
        import sqlite3
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
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
        """, (self._scoped(key), json.dumps(data, ensure_ascii=False)))
        conn.commit()
        conn.close()

    def load(self, key: str) -> Optional[Dict]:
        """加载数据"""
        import sqlite3
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        cursor.execute("SELECT data FROM opc_data WHERE key = ?", (self._scoped(key),))
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
            scoped_pattern = self._scoped("%") if self.namespace else "%"
            cursor.execute("SELECT key FROM opc_data WHERE key LIKE ?", (scoped_pattern,))
        else:
            sql_pattern = self._scoped(pattern.replace("*", "%")) if self.namespace else pattern.replace("*", "%")
            cursor.execute("SELECT key FROM opc_data WHERE key LIKE ?", (sql_pattern,))

        keys = [self._unscoped(row[0]) for row in cursor.fetchall()]
        conn.close()
        return keys

    def delete(self, key: str) -> bool:
        """删除数据"""
        import sqlite3
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        cursor.execute("DELETE FROM opc_data WHERE key = ?", (self._scoped(key),))
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
            db_path = kwargs.get("db_path")
            namespace = kwargs.get("namespace", "")
            if not db_path:
                # Callers (task_flow, decision_log, …) pass base_dir like
                # ``<data_dir>/tasks``. For sqlite we want a single shared
                # ``opc.db`` at the data root, so derive it from base_dir's
                # parent and use the directory name as the namespace so each
                # storage type lives in its own keyspace. Only fall back to
                # Path.cwd() when neither is set, because that fallback
                # silently breaks workspace isolation.
                base_dir = kwargs.get("base_dir")
                if base_dir:
                    base_dir_path = Path(base_dir)
                    db_path = base_dir_path.parent / "opc.db"
                    if not namespace:
                        namespace = base_dir_path.name
                else:
                    db_path = Path.cwd() / "data" / "opc.db"
            return SQLiteStorage(Path(db_path), namespace=namespace)

        else:
            raise ValueError(f"不支持的存储后端: {backend}")


# 全局存储实例（延迟初始化）
_storage_instances: Dict[str, Storage] = {}


def get_storage(storage_type: str, config: Optional[Dict] = None) -> Storage:
    """获取存储实例（单例模式）"""
    if storage_type not in _storage_instances:
        if config is None:
            # 使用默认配置
            from config import Config
            cfg = Config()
            backend = cfg.get("storage.backend", "file")

            if backend == "file":
                base_dir = cfg.get_path("data_dir")
                use_lock = cfg.get("storage.file_lock", True)
                auto_backup = cfg.get("storage.auto_backup", False)
                _storage_instances[storage_type] = FileStorage(base_dir / storage_type, use_lock, auto_backup)
            elif backend == "sqlite":
                db_path = cfg.get_path("data_dir") / "opc.db"
                _storage_instances[storage_type] = SQLiteStorage(db_path, namespace=storage_type)
        else:
            _storage_instances[storage_type] = StorageFactory.create(**config)

    return _storage_instances[storage_type]


def reset_storage_cache() -> None:
    """Drop cached storage singletons. Used by tests and by callers that need
    to switch backends or workspaces mid-process."""
    _storage_instances.clear()
