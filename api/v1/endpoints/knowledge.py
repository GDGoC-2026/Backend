from fastapi import APIRouter, Depends, UploadFile, File, HTTPException
from Backend.api.deps import get_current_user
from Backend.models.user import User
from Backend.workers.ingestion_tasks import process_markdown_note

router = APIRouter()

@router.post("/upload-note", status_code=202)
async def upload_markdown_note(
    file: UploadFile = File(...),
    current_user: User = Depends(get_current_user)
):
    if not file.filename or not file.filename.endswith('.md'):
        raise HTTPException(status_code=400, detail="Only Markdown (.md) files are supported.")
    
    content = await file.read()
    try:
        text_content = content.decode("utf-8")
    except UnicodeDecodeError:
        raise HTTPException(status_code=400, detail="Invalid file encoding. Must be UTF-8.")
    
    # Dispatch to Celery for background processing
    task = process_markdown_note.delay(
        str(current_user.id), 
        file.filename, 
        text_content
    )
    
    return {
        "message": "Note accepted for processing into the Knowledge Graph.",
        "task_id": task.id,
        "filename": file.filename
    }
