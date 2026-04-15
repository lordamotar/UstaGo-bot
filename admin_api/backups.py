import os
import json
import asyncio
from datetime import datetime, date
from decimal import Decimal
from enum import Enum
from sqlalchemy import select, inspect
from database.engine import async_session_maker
from database.base import Base
import database.models  # Ensure models are registered

BACKUP_DIR = "backups"

if not os.path.exists(BACKUP_DIR):
    os.makedirs(BACKUP_DIR)

def serialize_value(val):
    """Convert any DB value to a JSON-safe type."""
    if val is None:
        return None
    if isinstance(val, Enum):
        return val.value
    if isinstance(val, datetime):
        return val.isoformat()
    if isinstance(val, date):
        return val.isoformat()
    if isinstance(val, Decimal):
        return float(val)
    if isinstance(val, bytes):
        return val.hex()
    if isinstance(val, (list, tuple)):
        return [serialize_value(v) for v in val]
    # int, str, float, bool — already JSON-safe
    return val

async def create_backup():
    """Creates a JSON snapshot of the entire database."""
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    filename = f"backup_{timestamp}.json"
    filepath = os.path.join(BACKUP_DIR, filename)
    
    snapshot = {
        "metadata": {
            "timestamp": datetime.now().isoformat(),
            "version": "1.0"
        },
        "data": {}
    }
    
    async with async_session_maker() as session:
        # Get all tables from metadata
        for table_name, table in Base.metadata.tables.items():
            try:
                stmt = select(table)
                result = await session.execute(stmt)
                rows = result.all()
                
                snapshot["data"][table_name] = [
                    {col: serialize_value(val) for col, val in row._mapping.items()} 
                    for row in rows
                ]
            except Exception as e:
                print(f"Failed to backup table {table_name}: {e}")
                
    with open(filepath, "w", encoding="utf-8") as f:
        json.dump(snapshot, f, ensure_ascii=False, indent=2)
        
    return filename

def list_backups():
    """Lists all available backup files."""
    if not os.path.exists(BACKUP_DIR):
        return []
    
    files = []
    for f in os.listdir(BACKUP_DIR):
        if f.endswith(".json"):
            path = os.path.join(BACKUP_DIR, f)
            stat = os.stat(path)
            files.append({
                "filename": f,
                "size": stat.st_size,
                "created_at": datetime.fromtimestamp(stat.st_ctime).isoformat()
            })
    
    # Sort by date desc
    return sorted(files, key=lambda x: x["created_at"], reverse=True)

def delete_backup(filename: str):
    """Deletes a specific backup file."""
    path = os.path.join(BACKUP_DIR, filename)
    if os.path.exists(path) and ".." not in filename:
        os.remove(path)
        return True
    return False

def get_backup_path(filename: str):
    """Returns absolute path to a backup file for download."""
    path = os.path.abspath(os.path.join(BACKUP_DIR, filename))
    if os.path.exists(path) and path.startswith(os.path.abspath(BACKUP_DIR)):
        return path
    return None
