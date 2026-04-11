import asyncio
from Backend.core.celery_app import celery_app
from Backend.services.note_analyzer import NoteAnalyzer
from Backend.db.session import AsyncSessionLocal
from Backend.db.graph import neo4j_db
from Backend.models.notes import Note
from sqlalchemy import update


# TODO: Import LightRAG orchestration here


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


async def process_chunks_to_graph(user_id: str, file_name: str, chunks: list):
    for index, chunk in enumerate(chunks):
        print(f"Processing chunk {index} for user {user_id} from {file_name}")
        # Insert Nodes/Edges into Neo4j
        await neo4j_db.insert_note_chunk(user_id, file_name, index, chunk)
        
        # TODO: 1. LLM Entity Extraction
        # TODO: 3. Generate Embeddings for chunk
        # TODO: 4. Insert Vector into Milvus


@celery_app.task(bind=True, max_retries=3)
def process_markdown_note(self, user_id: str, file_name: str, content: str):
    """
    Background task to process markdown, extract entities, and populate databases.
    """
    analyzer = NoteAnalyzer()
    chunks = analyzer.chunk_markdown(content)
    
    # Run graph DB async insertion
    asyncio.run(process_chunks_to_graph(user_id, file_name, chunks))
        
    # Mark as synced upon completion
    asyncio.run(mark_note_as_synced(user_id, file_name))
        
    return {"status": "success", "chunks_processed": len(chunks), "file": file_name}
