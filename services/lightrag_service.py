import os
from pathlib import Path
import networkx as nx
from uuid import UUID
from lightrag import LightRAG
from lightrag.llm.gemini import gpt_embedding_gemini
from lightrag.llm import gpt_complete_gemini

from Backend.core.config import settings
from Backend.schemas.knowledge import GraphNode, GraphEdge


class LightRAGService:
    """
    Service to manage LightRAG instances per user.
    Each user gets an isolated working directory for their knowledge graph.
    """

    def __init__(self):
        """Initialize the LightRAG service."""
        if not settings.gemini_api_key:
            raise ValueError("GEMINI_API_KEY is not set in configuration")
        
        self._rag_instances = {}  # Cache for RAG instances per user_id

    def _get_working_dir(self, user_id: UUID | str) -> str:
        """
        Get or create user-specific working directory.
        
        Args:
            user_id: User identifier
            
        Returns:
            Path to user's working directory
        """
        user_working_dir = os.path.join(
            settings.lightrag_working_dir,
            str(user_id)
        )
        Path(user_working_dir).mkdir(parents=True, exist_ok=True)
        return user_working_dir

    def get_rag_instance(self, user_id: UUID | str) -> LightRAG:
        """
        Get or create a LightRAG instance for a user.
        Caches instances in memory for performance.
        
        Args:
            user_id: User identifier
            
        Returns:
            LightRAG instance configured with Gemini
        """
        user_id_str = str(user_id)
        
        if user_id_str not in self._rag_instances:
            working_dir = self._get_working_dir(user_id_str)
            
            self._rag_instances[user_id_str] = LightRAG(
                working_dir=working_dir,
                llm_model_func=gpt_complete_gemini,
                llm_model_name="gemini-2.0-flash",
                embedding_func=gpt_embedding_gemini,
                embedding_batch_num=1,
            )
        
        return self._rag_instances[user_id_str]

    async def ingest_content(self, user_id: UUID | str, content: str) -> None:
        """
        Ingest content into the user's knowledge graph.
        
        Args:
            user_id: User identifier
            content: Formatted content to ingest
        """
        rag = self.get_rag_instance(user_id)
        await rag.ainsert(content)

    async def query_knowledge(
        self, 
        user_id: UUID | str, 
        question: str, 
        mode: str = "hybrid"
    ) -> str:
        """
        Query the knowledge graph for a user.
        
        Args:
            user_id: User identifier
            question: Question to ask
            mode: Query mode (local, global, hybrid, mix)
            
        Returns:
            Answer from the knowledge graph
        """
        rag = self.get_rag_instance(user_id)
        
        # Map mode string to QueryParam mode
        from lightrag.query_param import QueryParam
        query_param = QueryParam(mode=mode)
        
        answer = await rag.aquery(question, param=query_param)
        return answer

    def get_graph_data(self, user_id: UUID | str) -> dict:
        """
        Get graph nodes and edges for visualization.
        Parses GraphML file from working directory.
        
        Args:
            user_id: User identifier
            
        Returns:
            Dictionary with nodes and edges lists
        """
        working_dir = self._get_working_dir(user_id)
        graph_file = os.path.join(working_dir, "graph_chunk_entity_relation.graphml")
        
        nodes = []
        edges = []
        
        if os.path.exists(graph_file):
            try:
                # Load GraphML file
                graph = nx.read_graphml(graph_file)
                
                # Extract nodes
                for node_id, node_data in graph.nodes(data=True):
                    node_label = node_data.get("description", node_id)
                    nodes.append(
                        GraphNode(
                            id=node_id,
                            label=node_label,
                            properties=dict(node_data)
                        )
                    )
                
                # Extract edges
                for source, target, edge_data in graph.edges(data=True):
                    edge_label = edge_data.get("description", "related")
                    edges.append(
                        GraphEdge(
                            source=source,
                            target=target,
                            label=edge_label,
                            properties=dict(edge_data)
                        )
                    )
            except Exception as e:
                # Log error but return empty graph
                print(f"Error parsing graph file: {str(e)}")
        
        return {
            "nodes": nodes,
            "edges": edges
        }

    def delete_graph(self, user_id: UUID | str) -> bool:
        """
        Delete user's knowledge graph.
        
        Args:
            user_id: User identifier
            
        Returns:
            True if deletion successful
        """
        import shutil
        
        user_id_str = str(user_id)
        working_dir = self._get_working_dir(user_id_str)
        
        try:
            # Remove from cache
            if user_id_str in self._rag_instances:
                del self._rag_instances[user_id_str]
            
            # Remove working directory
            if os.path.exists(working_dir):
                shutil.rmtree(working_dir)
            
            return True
        except Exception as e:
            print(f"Error deleting graph: {str(e)}")
            return False


# Global instance
_lightrag_service = None


def get_lightrag_service() -> LightRAGService:
    """Get or create the global LightRAG service instance."""
    global _lightrag_service
    if _lightrag_service is None:
        _lightrag_service = LightRAGService()
    return _lightrag_service
