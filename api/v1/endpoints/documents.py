from typing import List, Optional
from fastapi import APIRouter, Depends, UploadFile, File, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from uuid import UUID
import io

from Backend.api.deps import get_current_user
from Backend.db.session import get_db
from Backend.models.user import User
from Backend.models.notes import Note, Folder
from Backend.schemas.notes import NoteResponse
from Backend.workers.ingestion_tasks import process_markdown_note

import pypdf
import docx


router = APIRouter()


def extract_text_from_pdf(file_bytes: bytes) -> str:
    pdf_file = io.BytesIO(file_bytes)
    reader = pypdf.PdfReader(pdf_file)
    text = ""
    for page in reader.pages:
        text += page.extract_text() + "\n"
    return text


def extract_text_from_docx(file_bytes: bytes) -> str:
    doc_file = io.BytesIO(file_bytes)
    doc = docx.Document(doc_file)
    text = "\n".join([para.text for para in doc.paragraphs])
    return text


@router.post("/upload", status_code=status.HTTP_202_ACCEPTED)
async def upload_general_document(
    file: UploadFile = File(...),
    folder_id: Optional[UUID] = None,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    if not file.filename:
        raise HTTPException(status_code=400, detail="Invalid filename.")
        
    supported_extensions = ['.pdf', '.docx', '.txt']
    ext = next((ext for ext in supported_extensions if file.filename.lower().endswith(ext)), None)
    
    if not ext:
        raise HTTPException(
            status_code=400, 
            detail=f"Unsupported file type. Supported types are: {', '.join(supported_extensions)}"
        )
    
    content = await file.read()

    if folder_id is not None:
        folder_result = await db.execute(
            select(Folder.id).where(Folder.id == folder_id, Folder.user_id == current_user.id)
        )
        if folder_result.scalar_one_or_none() is None:
            raise HTTPException(status_code=404, detail="Folder not found")
    
    try:
        if ext == '.pdf':
            text_content = extract_text_from_pdf(content)
        elif ext == '.docx':
            text_content = extract_text_from_docx(content)
        elif ext == '.txt':
            text_content = content.decode("utf-8")
        else:
            raise ValueError("Unknown explicitly caught extension")
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Failed to process {ext} file: {str(e)}")
        
    # Standardize the file naming for note title
    note_title = file.filename.rsplit('.', 1)[0]

    # Save to PostgreSQL as a generic "Node/Document" using the existing Note model
    new_note = Note(
        user_id=current_user.id,
        title=note_title,
        content=text_content,
        folder_id=folder_id
    )
    db.add(new_note)
    await db.commit()
    await db.refresh(new_note)
    
    # Dispatch to Celery for background processing (we can reuse process_markdown_note for generic text or create process_text_document later)
    task = process_markdown_note.delay(
        str(current_user.id), 
        new_note.title, 
        new_note.content
    )
    
    return {
        "message": f"Document ({ext}) uploaded, saved, and queued for AI pipeline processing.",
        "task_id": task.id,
        "document": NoteResponse.model_validate(new_note)
    }
