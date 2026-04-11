from neo4j import AsyncGraphDatabase
from Backend.core.config import settings
import logging

logger = logging.getLogger(__name__)

class Neo4jConnection:
    def __init__(self):
        self.driver = AsyncGraphDatabase.driver(
            settings.neo4j_uri, 
            auth=(settings.neo4j_username, settings.neo4j_password)
        )

    async def close(self):
        await self.driver.close()

    async def insert_note_chunk(self, user_id: str, note_title: str, chunk_index: int, content: str):
        """
        Inserts a processed note chunk into the Graph database.
        Creates a User node, a Note node, a Chunk node, and relationships between them.
        """
        query = (
            "MERGE (u:User {id: $user_id}) "
            "MERGE (n:Note {title: $note_title, user_id: $user_id}) "
            "MERGE (c:Chunk {note_title: $note_title, index: $chunk_index, user_id: $user_id}) "
            "ON CREATE SET c.content = $content "
            "MERGE (u)-[:OWNS]->(n) "
            "MERGE (n)-[:CONTAINS]->(c)"
        )
        async with self.driver.session() as session:
            try:
                await session.run(query, user_id=user_id, note_title=note_title, chunk_index=chunk_index, content=content)
            except Exception as e:
                logger.error(f"Failed to insert chunk to neo4j: {e}")

neo4j_db = Neo4jConnection()
