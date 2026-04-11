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

    async def get_user_graph(self, user_id: str):
        """
        Retrieves the complete graph of notes and chunks for a specific user to power the visualizer map.
        Returns a dictionary representing nodes and links.
        """
        query = (
            "MATCH (u:User {id: $user_id})-[:OWNS]->(n:Note)-[:CONTAINS]->(c:Chunk) "
            "RETURN u, n, c"
        )
        
        nodes = []
        links = []
        node_ids = set()
        
        async with self.driver.session() as session:
            try:
                result = await session.run(query, user_id=user_id)
                records = await result.data()
                
                for record in records:
                    u = record['u']
                    n = record['n']
                    c = record['c']
                    
                    if u['id'] not in node_ids:
                        nodes.append({"id": u['id'], "label": "User", "type": "User"})
                        node_ids.add(u['id'])
                        
                    note_id = f"note_{n['title']}"
                    if note_id not in node_ids:
                        nodes.append({"id": note_id, "label": n['title'], "type": "Note"})
                        node_ids.add(note_id)
                        links.append({"source": u['id'], "target": note_id, "label": "OWNS"})
                        
                    chunk_id = f"chunk_{n['title']}_{c['index']}"
                    if chunk_id not in node_ids:
                        nodes.append({"id": chunk_id, "label": f"Chunk {c['index']}", "type": "Chunk"})
                        node_ids.add(chunk_id)
                        links.append({"source": note_id, "target": chunk_id, "label": "CONTAINS"})
                        
                return {"nodes": nodes, "links": links}
            except Exception as e:
                logger.error(f"Neo4j query failed: {e}")
                return {"nodes": [], "links": []}

neo4j_db = Neo4jConnection()
