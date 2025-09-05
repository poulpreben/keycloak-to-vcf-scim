from datetime import datetime
from typing import Optional, Dict, Any
from threading import Lock


class SyncState:
    """Singleton to store last sync information"""
    _instance = None
    _lock = Lock()
    
    def __new__(cls):
        if cls._instance is None:
            with cls._lock:
                if cls._instance is None:
                    cls._instance = super().__new__(cls)
                    cls._instance.last_sync_time: Optional[datetime] = None
                    cls._instance.last_sync_result: Optional[Dict[str, Any]] = None
                    cls._instance.last_sync_type: Optional[str] = None  # "manual", "scheduled", "users", "groups"
        return cls._instance
    
    def update_sync(self, sync_type: str, result: Dict[str, Any]):
        """Update last sync information"""
        self.last_sync_time = datetime.now()
        self.last_sync_result = result
        self.last_sync_type = sync_type
    
    def get_sync_info(self) -> Dict[str, Any]:
        """Get last sync information"""
        return {
            "last_sync_time": self.last_sync_time.isoformat() if self.last_sync_time else None,
            "last_sync_type": self.last_sync_type,
            "last_sync_result": self.last_sync_result
        }


# Global instance
sync_state = SyncState()