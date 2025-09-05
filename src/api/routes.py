from fastapi import APIRouter, HTTPException, Depends
from typing import Dict, Any
from src.services.sync_service import SyncService
from src.services.scheduler import SyncScheduler
from src.core.config import Settings, get_settings
from src.core.sync_state import sync_state

router = APIRouter()


@router.post("/sync/manual")
async def manual_sync(settings: Settings = Depends(get_settings)) -> Dict[str, Any]:
    """Manually trigger a sync between Keycloak and vCenter"""
    try:
        async with SyncService(settings) as sync_service:
            result = await sync_service.full_sync()
            sync_state.update_sync("manual", result)
            return {"status": "success", "result": result}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/sync/users")
async def sync_users_only(settings: Settings = Depends(get_settings)) -> Dict[str, Any]:
    """Sync only users from Keycloak to vCenter"""
    try:
        async with SyncService(settings) as sync_service:
            result = await sync_service.sync_users()
            sync_state.update_sync("users", result)
            return {"status": "success", "result": result}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/sync/groups")
async def sync_groups_only(settings: Settings = Depends(get_settings)) -> Dict[str, Any]:
    """Sync only groups from Keycloak to vCenter"""
    try:
        async with SyncService(settings) as sync_service:
            result = await sync_service.sync_groups()
            sync_state.update_sync("groups", result)
            return {"status": "success", "result": result}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/sync/preview")
async def sync_preview(settings: Settings = Depends(get_settings)) -> Dict[str, Any]:
    """Preview what would be synced without making changes"""
    if settings.environment != "DEV":
        raise HTTPException(status_code=403, detail="This endpoint is only available in DEV environment")
    
    try:
        async with SyncService(settings) as sync_service:
            result = await sync_service.get_sync_preview()
            return {"status": "success", "preview": result}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/scheduler/status")
async def scheduler_status() -> Dict[str, Any]:
    """Get the status of the sync scheduler"""
    from src.main import scheduler
    if scheduler:
        return scheduler.get_status()
    return {"error": "Scheduler not initialized"}


@router.post("/scheduler/start")
async def start_scheduler() -> Dict[str, Any]:
    """Start the sync scheduler"""
    from src.main import scheduler
    if scheduler:
        scheduler.start()
        return {"status": "Scheduler started"}
    return {"error": "Scheduler not initialized"}


@router.post("/scheduler/stop")
async def stop_scheduler() -> Dict[str, Any]:
    """Stop the sync scheduler"""
    from src.main import scheduler
    if scheduler:
        scheduler.stop()
        return {"status": "Scheduler stopped"}
    return {"error": "Scheduler not initialized"}