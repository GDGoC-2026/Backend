from neo4j import AsyncGraphDatabase
from Backend.core.config import settings

class Neo4jConnection:
    def __init__(self):
        self.driver = AsyncGraphDatabase.driver(
            settings.neo4j_uri, 
            auth=(settings.neo4j_username, settings.neo4j_password)
        )

    async def close(self):
        await self.driver.close()

neo4j_db = Neo4jConnection()