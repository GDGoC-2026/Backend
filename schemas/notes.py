from pydantic import BaseModel, ConfigDict
from typing import Optional, List
from uuid import UUID
from datetime import datetime

# --- Folders ---
class FolderBase(BaseModel):
    name: str
    parent_id: Optional[UUID] = None

class FolderCreate(FolderBase):
    pass

class FolderResponse(FolderBase):
    model_config = ConfigDict(from_attributes=True)
    id: UUID
    created_at: datetime
    
# --- Notes ---
class NoteBase(BaseModel):
    title: str
    content: str
    folder_id: Optional[UUID] = None

class NoteCreate(NoteBase):
    pass

class NoteUpdate(BaseModel):
    title: Optional[str] = None
    content: Optional[str] = None
    folder_id: Optional[UUID] = None

class NoteResponse(NoteBase):
    model_config = ConfigDict(from_attributes=True)
    id: UUID
    created_at: datetime
    updated_at: datetime
    is_synced_with_graph: bool

# --- Extended Folder Response ---
class FolderDetailResponse(FolderResponse):
    subfolders: List[FolderResponse] = []
    notes: List[NoteResponse] = []