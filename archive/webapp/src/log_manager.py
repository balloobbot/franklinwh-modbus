"""
Log Manager for FranklinWH Battery Manager.

Provides file-based logging with rotation and SQLite storage for web UI access.
"""

import asyncio
import json
import logging
import os
import sqlite3
import threading
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Dict, List, Optional, Any
from dataclasses import dataclass
from enum import IntEnum

# AEDT timezone (Australian Eastern Daylight Time = UTC+11)
AEDT = timezone(timedelta(hours=11))


class LogLevel(IntEnum):
    DEBUG = 10
    INFO = 20
    WARNING = 30
    ERROR = 40
    CRITICAL = 50


class SQLiteLogHandler(logging.Handler):
    """
    Custom logging handler that writes to SQLite database.
    Runs in a separate thread to avoid blocking.
    """
    
    def __init__(self, log_manager):
        super().__init__()
        self.log_manager = log_manager
        self.loop = None
        
    def emit(self, record):
        """Log a record to the database."""
        try:
            # Get or create event loop
            try:
                loop = asyncio.get_running_loop()
            except RuntimeError:
                # No loop running, skip (we'll miss some startup logs)
                return
            
            # Schedule the log addition
            asyncio.create_task(self._log_async(record))
        except Exception:
            self.handleError(record)
    
    async def _log_async(self, record):
        """Async helper to add log."""
        try:
            await self.log_manager.add_log(
                level=record.levelname,
                source=record.name,
                message=record.getMessage(),
                metadata={
                    "filename": record.filename,
                    "lineno": record.lineno,
                    "funcName": record.funcName
                } if record.levelno >= logging.WARNING else None
            )
        except Exception:
            pass  # Don't let logging errors crash the app


@dataclass
class LogEntry:
    """Single log entry."""
    id: Optional[int]
    timestamp: datetime
    level: str
    source: str
    message: str
    metadata: Optional[Dict[str, Any]] = None


class LogManager:
    """
    Manages application logs with SQLite storage for web UI access.
    
    Features:
    - Persistent SQLite storage
    - Automatic rotation (keep last N days)
    - Filter by level, source, date range
    - Export to JSON/CSV
    """
    
    def __init__(self, data_dir: str = "./data", max_age_days: int = 30):
        self.data_dir = Path(data_dir)
        self.data_dir.mkdir(parents=True, exist_ok=True)
        self.db_path = self.data_dir / "logs.db"
        self.max_age_days = max_age_days
        self._lock = asyncio.Lock()
        
        # Initialize database
        self._init_db()
        
        # Setup file logger for raw logs
        self._setup_file_logger()
    
    def _init_db(self):
        """Initialize SQLite database."""
        with sqlite3.connect(self.db_path) as conn:
            conn.execute("""
                CREATE TABLE IF NOT EXISTS logs (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    timestamp TEXT NOT NULL,
                    level TEXT NOT NULL,
                    source TEXT NOT NULL,
                    message TEXT NOT NULL,
                    metadata TEXT
                )
            """)
            conn.execute("""
                CREATE INDEX IF NOT EXISTS idx_logs_timestamp ON logs(timestamp)
            """)
            conn.execute("""
                CREATE INDEX IF NOT EXISTS idx_logs_level ON logs(level)
            """)
            conn.execute("""
                CREATE INDEX IF NOT EXISTS idx_logs_source ON logs(source)
            """)
            conn.commit()
    
    def _setup_file_logger(self):
        """Setup file handler for raw log output."""
        log_file = self.data_dir / "app.log"
        file_handler = logging.FileHandler(log_file, mode='a')
        file_handler.setFormatter(logging.Formatter(
            '%(asctime)s AEDT - %(name)s - %(levelname)s - %(message)s',
            datefmt='%Y-%m-%d %H:%M:%S'
        ))
        
        # Add to root logger
        root_logger = logging.getLogger()
        root_logger.addHandler(file_handler)
        
        self.file_handler = file_handler
    
    async def add_log(self, level: str, source: str, message: str, metadata: Optional[Dict] = None):
        """Add a log entry."""
        async with self._lock:
            timestamp = datetime.now(tz=AEDT).isoformat()
            metadata_json = json.dumps(metadata) if metadata else None
            
            with sqlite3.connect(self.db_path) as conn:
                conn.execute(
                    "INSERT INTO logs (timestamp, level, source, message, metadata) VALUES (?, ?, ?, ?, ?)",
                    (timestamp, level.upper(), source, message, metadata_json)
                )
                conn.commit()
    
    async def get_logs(
        self,
        level: Optional[str] = None,
        levels: Optional[List[str]] = None,  # Multi-select filter
        source: Optional[str] = None,
        search: Optional[str] = None,
        start_date: Optional[str] = None,
        end_date: Optional[str] = None,
        limit: int = 100,
        offset: int = 0
    ) -> List[LogEntry]:
        """Get logs with filtering."""
        async with self._lock:
            query = "SELECT id, timestamp, level, source, message, metadata FROM logs WHERE 1=1"
            params = []
            
            # Multi-level OR filter (clickable badges)
            if levels:
                placeholders = ",".join(["?" for _ in levels])
                query += f" AND level IN ({placeholders})"
                params.extend([l.upper() for l in levels])
            elif level:
                # Single level filter (traditional dropdown)
                query += " AND level = ?"
                params.append(level.upper())
            
            if source:
                query += " AND source LIKE ?"
                params.append(f"%{source}%")
            
            if search:
                query += " AND (message LIKE ? OR source LIKE ?)"
                params.extend([f"%{search}%", f"%{search}%"])
            
            if start_date:
                query += " AND timestamp >= ?"
                params.append(start_date)
            
            if end_date:
                query += " AND timestamp <= ?"
                params.append(end_date)
            
            query += " ORDER BY timestamp DESC LIMIT ? OFFSET ?"
            params.extend([limit, offset])
            
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.execute(query, params)
                rows = cursor.fetchall()
                
                logs = []
                for row in rows:
                    metadata = json.loads(row[5]) if row[5] else None
                    logs.append(LogEntry(
                        id=row[0],
                        timestamp=datetime.fromisoformat(row[1]),
                        level=row[2],
                        source=row[3],
                        message=row[4],
                        metadata=metadata
                    ))
                return logs
    
    async def get_stats(self) -> Dict[str, Any]:
        """Get log statistics."""
        async with self._lock:
            with sqlite3.connect(self.db_path) as conn:
                # Total count
                total = conn.execute("SELECT COUNT(*) FROM logs").fetchone()[0]
                
                # Count by level
                levels = conn.execute(
                    "SELECT level, COUNT(*) FROM logs GROUP BY level"
                ).fetchall()
                
                # Count by source (top 10)
                sources = conn.execute(
                    "SELECT source, COUNT(*) FROM logs GROUP BY source ORDER BY COUNT(*) DESC LIMIT 10"
                ).fetchall()
                
                # Date range
                date_range = conn.execute(
                    "SELECT MIN(timestamp), MAX(timestamp) FROM logs"
                ).fetchone()
                
                return {
                    "total": total,
                    "by_level": {level: count for level, count in levels},
                    "by_source": {source: count for source, count in sources},
                    "oldest": date_range[0],
                    "newest": date_range[1]
                }
    
    async def export_json(self, start_date: Optional[str] = None, end_date: Optional[str] = None) -> str:
        """Export logs to JSON string."""
        logs = await self.get_logs(
            start_date=start_date,
            end_date=end_date,
            limit=10000  # Max export
        )
        
        data = [{
            "id": log.id,
            "timestamp": log.timestamp.isoformat(),
            "level": log.level,
            "source": log.source,
            "message": log.message,
            "metadata": log.metadata
        } for log in logs]
        
        return json.dumps(data, indent=2)
    
    async def export_csv(self, start_date: Optional[str] = None, end_date: Optional[str] = None) -> str:
        """Export logs to CSV string."""
        logs = await self.get_logs(
            start_date=start_date,
            end_date=end_date,
            limit=10000
        )
        
        import csv
        import io
        
        output = io.StringIO()
        writer = csv.writer(output)
        writer.writerow(["ID", "Timestamp", "Level", "Source", "Message", "Metadata"])
        
        for log in logs:
            writer.writerow([
                log.id,
                log.timestamp.isoformat(),
                log.level,
                log.source,
                log.message,
                json.dumps(log.metadata) if log.metadata else ""
            ])
        
        return output.getvalue()
    
    async def clear_old_logs(self):
        """Clear logs older than max_age_days."""
        cutoff = (datetime.now(tz=AEDT) - timedelta(days=self.max_age_days)).isoformat()
        
        async with self._lock:
            with sqlite3.connect(self.db_path) as conn:
                conn.execute("DELETE FROM logs WHERE timestamp < ?", (cutoff,))
                conn.commit()


# Global log manager instance - initialized with config
log_manager = None

def get_log_manager(config=None) -> LogManager:
    """Get or create the global log manager instance."""
    global log_manager
    if log_manager is None:
        retention_days = 30
        if config and hasattr(config, 'log_retention_days'):
            retention_days = config.log_retention_days
        log_manager = LogManager(max_age_days=retention_days)
    return log_manager


# Convenience function for logging
async def log_event(level: str, source: str, message: str, metadata: Optional[Dict] = None):
    """Log an event to the database."""
    if log_manager:
        await log_manager.add_log(level, source, message, metadata)
