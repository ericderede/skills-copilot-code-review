"""
Announcements management endpoints for the High School Management System API
"""

from fastapi import APIRouter, HTTPException, Query
from typing import Dict, Any, List, Optional
from bson import ObjectId
from datetime import datetime

from ..database import announcements_collection, teachers_collection

router = APIRouter(
    prefix="/announcements",
    tags=["announcements"]
)


@router.get("", response_model=List[Dict[str, Any]])
@router.get("/", response_model=List[Dict[str, Any]])
def get_active_announcements() -> List[Dict[str, Any]]:
    """Get all active announcements (not expired and started)"""
    today = datetime.now().strftime("%Y-%m-%d")
    
    # Find announcements that are:
    # - Started (start_date is None or <= today)
    # - Not expired (expiration_date >= today)
    announcements = list(announcements_collection.find({
        "$or": [
            {"start_date": {"$exists": False}},
            {"start_date": {"$lte": today}}
        ],
        "expiration_date": {"$gte": today}
    }))
    
    # Convert ObjectId to string for JSON serialization
    for announcement in announcements:
        if "_id" in announcement:
            announcement["_id"] = str(announcement["_id"])
    
    return announcements


@router.get("/all", response_model=List[Dict[str, Any]])
def get_all_announcements(username: Optional[str] = Query(None)) -> List[Dict[str, Any]]:
    """Get all announcements (admin only)"""
    # Verify teacher authentication
    if not username:
        raise HTTPException(
            status_code=401, detail="Authentication required")
    
    teacher = teachers_collection.find_one({"_id": username})
    if not teacher:
        raise HTTPException(status_code=401, detail="Invalid credentials")
    
    announcements = list(announcements_collection.find())
    
    # Convert ObjectId to string for JSON serialization
    for announcement in announcements:
        if "_id" in announcement:
            announcement["_id"] = str(announcement["_id"])
    
    return announcements


@router.post("", response_model=Dict[str, Any])
def create_announcement(
    title: str,
    message: str,
    expiration_date: str,
    start_date: Optional[str] = None,
    username: Optional[str] = Query(None)
) -> Dict[str, Any]:
    """Create a new announcement (authenticated users only)"""
    # Verify teacher authentication
    if not username:
        raise HTTPException(
            status_code=401, detail="Authentication required")
    
    teacher = teachers_collection.find_one({"_id": username})
    if not teacher:
        raise HTTPException(status_code=401, detail="Invalid credentials")
    
    # Validate dates
    try:
        exp_date = datetime.strptime(expiration_date, "%Y-%m-%d")
        if start_date:
            start = datetime.strptime(start_date, "%Y-%m-%d")
            if start > exp_date:
                raise HTTPException(
                    status_code=400,
                    detail="Start date cannot be after expiration date"
                )
    except ValueError:
        raise HTTPException(
            status_code=400,
            detail="Invalid date format. Use YYYY-MM-DD"
        )
    
    announcement = {
        "title": title,
        "message": message,
        "expiration_date": expiration_date,
        "start_date": start_date,
        "created_by": username,
        "created_at": datetime.now().isoformat()
    }
    
    result = announcements_collection.insert_one(announcement)
    
    announcement["_id"] = str(result.inserted_id)
    return announcement


@router.put("/{announcement_id}", response_model=Dict[str, Any])
def update_announcement(
    announcement_id: str,
    title: str = Query(None),
    message: str = Query(None),
    expiration_date: str = Query(None),
    start_date: Optional[str] = Query(None),
    username: Optional[str] = Query(None)
) -> Dict[str, Any]:
    """Update an announcement (authenticated users only)"""
    # Verify teacher authentication
    if not username:
        raise HTTPException(
            status_code=401, detail="Authentication required")
    
    teacher = teachers_collection.find_one({"_id": username})
    if not teacher:
        raise HTTPException(status_code=401, detail="Invalid credentials")
    
    # Validate ObjectId
    try:
        obj_id = ObjectId(announcement_id)
    except Exception:
        raise HTTPException(status_code=400, detail="Invalid announcement ID")
    
    # Get existing announcement
    announcement = announcements_collection.find_one({"_id": obj_id})
    if not announcement:
        raise HTTPException(status_code=404, detail="Announcement not found")
    
    # Build update data
    update_data = {}
    if title:
        update_data["title"] = title
    if message:
        update_data["message"] = message
    if expiration_date:
        try:
            datetime.strptime(expiration_date, "%Y-%m-%d")
        except ValueError:
            raise HTTPException(
                status_code=400,
                detail="Invalid expiration_date format. Use YYYY-MM-DD"
            )
        update_data["expiration_date"] = expiration_date
    
    if start_date is not None:  # Allow clearing start_date with None
        if start_date:
            try:
                datetime.strptime(start_date, "%Y-%m-%d")
            except ValueError:
                raise HTTPException(
                    status_code=400,
                    detail="Invalid start_date format. Use YYYY-MM-DD"
                )
            update_data["start_date"] = start_date
        else:
            update_data["start_date"] = None
    
    # Validate dates if both are provided
    if "start_date" in update_data or "expiration_date" in update_data:
        start = update_data.get("start_date") or announcement.get("start_date")
        exp = update_data.get("expiration_date") or announcement.get("expiration_date")
        
        if start and exp:
            try:
                start_dt = datetime.strptime(start, "%Y-%m-%d")
                exp_dt = datetime.strptime(exp, "%Y-%m-%d")
                if start_dt > exp_dt:
                    raise HTTPException(
                        status_code=400,
                        detail="Start date cannot be after expiration date"
                    )
            except ValueError:
                pass  # Already validated above
    
    update_data["updated_at"] = datetime.now().isoformat()
    
    result = announcements_collection.update_one(
        {"_id": obj_id},
        {"$set": update_data}
    )
    
    if result.modified_count == 0:
        raise HTTPException(
            status_code=500, detail="Failed to update announcement")
    
    # Return updated announcement
    updated = announcements_collection.find_one({"_id": obj_id})
    updated["_id"] = str(updated["_id"])
    return updated


@router.delete("/{announcement_id}")
def delete_announcement(
    announcement_id: str,
    username: Optional[str] = Query(None)
) -> Dict[str, str]:
    """Delete an announcement (authenticated users only)"""
    # Verify teacher authentication
    if not username:
        raise HTTPException(
            status_code=401, detail="Authentication required")
    
    teacher = teachers_collection.find_one({"_id": username})
    if not teacher:
        raise HTTPException(status_code=401, detail="Invalid credentials")
    
    # Validate ObjectId
    try:
        obj_id = ObjectId(announcement_id)
    except Exception:
        raise HTTPException(status_code=400, detail="Invalid announcement ID")
    
    result = announcements_collection.delete_one({"_id": obj_id})
    
    if result.deleted_count == 0:
        raise HTTPException(status_code=404, detail="Announcement not found")
    
    return {"message": "Announcement deleted successfully"}
