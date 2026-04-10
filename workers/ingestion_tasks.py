import asyncio
from Backend.core.celery_app import celery_app
from Backend.services.note_analyzer import NoteAnalyzer
from Backend.db.session import AsyncSessionLocal
from Backend.models.notes import Note
from sqlalchemy import update

# Import LightRAG orchestration here

async def mark_note_as_synced(user_id: str, file_name: str):
    """
    Connects to PostgreSQL to toggle the is_synced_with_graph flag.
    """
    async with AsyncSessionLocal() as session:
        stmt = (
            update(Note)
            .where(Note.user_id == user_id, Note.title == file_name)
            .values(is_synced_with_graph=True)
        )
        await session.execute(stmt)
        await session.commit()

@celery_app.task(bind=True, max_retries=3)
def process_markdown_note(self, user_id: str, file_name: str, content: str):
    """
    Background task to process markdown, extract entities, and populate databases.
    """
    analyzer = NoteAnalyzer()
    chunks = analyzer.chunk_markdown(content)
    
    # Simulating the LightRAG Graph generation pipeline
    for index, chunk in enumerate(chunks):
        print(f"Processing chunk {index} for user {user_id} from {file_name}")
        
        # 1. LLM Entity Extraction would happen here
        # 2. Insert Nodes/Edges into Neo4j
        # 3. Generate Embeddings for chunk
        # 4. Insert Vector into Milvus
        
    # Mark as synced upon completion
    asyncio.run(mark_note_as_synced(user_id, file_name))
        
    return {"status": "success", "chunks_processed": len(chunks), "file": file_name}