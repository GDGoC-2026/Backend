from typing import List, Optional
from fastapi import APIRouter, Depends, UploadFile, File, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from uuid import UUID

from Backend.api.deps import get_current_user
from Backend.db.session import get_db
from Backend.models.user import User
from Backend.models.notes import Note, Folder
from Backend.db.graph import neo4j_db
from Backend.schemas.notes import (
    NoteCreate, NoteUpdate, NoteResponse, 
    FolderCreate, FolderResponse, FolderDetailResponse
)
from Backend.workers.ingestion_tasks import process_markdown_note


router = APIRouter()


async def _validate_owned_folder(
    folder_id: Optional[UUID],
    db: AsyncSession,
    current_user: User,
) -> None:
    if folder_id is None:
        return

    result = await db.execute(
        select(Folder.id).where(Folder.id == folder_id, Folder.user_id == current_user.id)
    )
    if result.scalar_one_or_none() is None:
        raise HTTPException(status_code=404, detail="Folder not found")


@router.get("/graph-visualizer")
async def get_knowledge_graph(current_user: User = Depends(get_current_user)):
    """Fetch the user's interactive knowledge map powered by Neo4j."""
    graph_data = await neo4j_db.get_user_graph(str(current_user.id))
    return graph_data


# --- Folders ---
@router.post("/folders", response_model=FolderResponse, status_code=status.HTTP_201_CREATED)
async def create_folder(
    folder_in: FolderCreate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    if folder_in.parent_id:
        parent = await db.execute(select(Folder).where(Folder.id == folder_in.parent_id, Folder.user_id == current_user.id))
        if not parent.scalar_one_or_none():
            raise HTTPException(status_code=404, detail="Parent folder not found")

    new_folder = Folder(
        user_id=current_user.id,
        name=folder_in.name,
        parent_id=folder_in.parent_id
    )
    db.add(new_folder)
    await db.commit()
    await db.refresh(new_folder)
    return new_folder


@router.get("/folders", response_model=List[FolderResponse])
async def get_root_folders(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Fetch all root folders (where parent_id is NULL)"""
    result = await db.execute(
        select(Folder)
        .where(Folder.user_id == current_user.id, Folder.parent_id == None)
        .order_by(Folder.created_at)
    )
    return result.scalars().all()


@router.get("/folders/{folder_id}", response_model=FolderDetailResponse)
async def get_folder_details(
    folder_id: UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Fetch folder details including its subfolders and notes."""
    result = await db.execute(
        select(Folder)
        .where(Folder.id == folder_id, Folder.user_id == current_user.id)
    )
    folder = result.scalar_one_or_none()
    if not folder:
        raise HTTPException(status_code=404, detail="Folder not found")
        
    subfolders_result = await db.execute(
        select(Folder).where(Folder.parent_id == folder_id)
    )
    notes_result = await db.execute(
        select(Note).where(Note.folder_id == folder_id, Note.user_id == current_user.id)
    )
    
    return {
        "id": folder.id,
        "name": folder.name,
        "parent_id": folder.parent_id,
        "created_at": folder.created_at,
        "subfolders": subfolders_result.scalars().all(),
        "notes": notes_result.scalars().all()
    }


@router.delete("/folders/{folder_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_folder(
    folder_id: UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    result = await db.execute(
        select(Folder).where(Folder.id == folder_id, Folder.user_id == current_user.id)
    )
    folder = result.scalar_one_or_none()
    if not folder:
        raise HTTPException(status_code=404, detail="Folder not found")
        
    await db.delete(folder)
    await db.commit()
    return None


# --- Notes ---
@router.post("/upload", status_code=status.HTTP_202_ACCEPTED)
async def upload_markdown_note(
    file: UploadFile = File(...),
    folder_id: Optional[UUID] = None,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    if not file.filename or not file.filename.endswith('.md'):
        raise HTTPException(status_code=400, detail="Only Markdown (.md) files are supported.")

    await _validate_owned_folder(folder_id, db, current_user)
    
    content = await file.read()
    try:
        text_content = content.decode("utf-8")
    except UnicodeDecodeError:
        raise HTTPException(status_code=400, detail="Invalid file encoding. Must be UTF-8.")
        
    # Standardize the file naming for note title
    note_title = file.filename.rsplit('.', 1)[0]

    # Save to PostgreSQL first
    new_note = Note(
        user_id=current_user.id,
        title=note_title,
        content=text_content,
        folder_id=folder_id
    )
    db.add(new_note)
    await db.commit()
    await db.refresh(new_note)
    
    # Dispatch to Celery for background processing
    task = process_markdown_note.delay(
        str(current_user.id), 
        new_note.title, 
        new_note.content
    )
    
    return {
        "message": "Note uploaded, saved, and queued for knowledge graph processing.",
        "task_id": task.id,
        "note": NoteResponse.model_validate(new_note)
    }


@router.get("/", response_model=List[NoteResponse])
async def get_notes(
    folder_id: Optional[UUID] = None,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Fetch all notes, optionally filtered by folder_id. If not provided, fetch root-level notes."""
    result = await db.execute(
        select(Note)
        .where(
            Note.user_id == current_user.id, 
            Note.folder_id == folder_id
        )
        .order_by(Note.updated_at.desc())
    )
    return result.scalars().all()


@router.post("/", response_model=NoteResponse, status_code=status.HTTP_201_CREATED)
async def create_note(
    note_in: NoteCreate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    await _validate_owned_folder(note_in.folder_id, db, current_user)

    new_note = Note(
        user_id=current_user.id,
        title=note_in.title,
        content=note_in.content,
        folder_id=note_in.folder_id
    )
    db.add(new_note)
    await db.commit()
    await db.refresh(new_note)
    
    # Optionally trigger graph ingestion on creation if the note has content
    if new_note.content.strip():
        process_markdown_note.delay(str(current_user.id), new_note.title, new_note.content)
        
    return new_note


@router.put("/{note_id}", response_model=NoteResponse)
async def update_note(
    note_id: UUID,
    note_in: NoteUpdate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    result = await db.execute(select(Note).where(Note.id == note_id, Note.user_id == current_user.id))
    note = result.scalar_one_or_none()
    
    if not note:
        raise HTTPException(status_code=404, detail="Note not found")

    # Update fields
    if note_in.title is not None:
        note.title = note_in.title
    if note_in.content is not None:
        note.content = note_in.content
    if note_in.folder_id is not None:
        await _validate_owned_folder(note_in.folder_id, db, current_user)
        note.folder_id = note_in.folder_id

    note.is_synced_with_graph = False # Mark as unsynced until Celery finishes
    await db.commit()
    await db.refresh(note)

    # AI Graph Integration Trigger
    # Dispatch to Celery to re-chunk, generate embeddings, and update Neo4j/Milvus
    process_markdown_note.delay(
        user_id=str(current_user.id), 
        file_name=note.title, 
        content=note.content
    )

    return note


@router.get("/{note_id}", response_model=NoteResponse)
async def get_note(
    note_id: UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    result = await db.execute(select(Note).where(Note.id == note_id, Note.user_id == current_user.id))
    note = result.scalar_one_or_none()
    if not note:
        raise HTTPException(status_code=404, detail="Note not found")
    return note


@router.delete("/{note_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_note(
    note_id: UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    result = await db.execute(select(Note).where(Note.id == note_id, Note.user_id == current_user.id))
    note = result.scalar_one_or_none()
    
    if not note:
        raise HTTPException(status_code=404, detail="Note not found")

    await db.delete(note)
    await db.commit()
    return None
