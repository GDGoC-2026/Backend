import logging
import os
from pathlib import Path
from typing import Literal, cast
from uuid import UUID

import google.auth
import networkx as nx
import vertexai
from google.auth.transport.requests import Request as GoogleAuthRequest
from lightrag import LightRAG, QueryParam
from lightrag.llm.openai import openai_complete_if_cache, openai_embed
from lightrag.utils import EmbeddingFunc

from Backend.core.config import settings
from Backend.schemas.knowledge import GraphNode, GraphEdge


logger = logging.getLogger(__name__)

SupportedQueryMode = Literal["local", "global", "hybrid", "naive", "mix", "bypass"]


class LightRAGService:
    """
    Service to manage LightRAG instances per user.
    Each user gets an isolated working directory for their knowledge graph.
    """

    def __init__(self):
        """Initialize the LightRAG service."""
        self._rag_instances: dict[str, LightRAG] = {}

        self._location = os.getenv("VERTEX_AI_LOCATION", "us-central1")
        self._llm_model_name = os.getenv("LIGHTRAG_LLM_MODEL", "google/gemini-1.5-flash")
        self._embedding_model_name = os.getenv("LIGHTRAG_EMBEDDING_MODEL", "google/text-embedding-005")
        self._embedding_dim = int(os.getenv("LIGHTRAG_EMBEDDING_DIM", "768"))
        self._embedding_max_tokens = int(os.getenv("LIGHTRAG_EMBEDDING_MAX_TOKENS", "8192"))
        self._llm_max_async = int(os.getenv("LIGHTRAG_LLM_MAX_ASYNC", "1"))

        # Acquire Application Default Credentials for Vertex OpenAI-compatible endpoints.
        self._credentials, detected_project = google.auth.default(
            scopes=["https://www.googleapis.com/auth/cloud-platform"]
        )
        self._project_id = (
            os.getenv("VERTEX_AI_PROJECT_ID")
            or os.getenv("GOOGLE_CLOUD_PROJECT")
            or detected_project
        )
        if not self._project_id:
            raise ValueError(
                "Vertex AI project ID is missing. Set VERTEX_AI_PROJECT_ID or GOOGLE_CLOUD_PROJECT."
            )

        self._auth_request = GoogleAuthRequest()
        self._get_access_token()
        vertexai.init(project=self._project_id, location=self._location)

        self._chat_base_url = (
            f"https://{self._location}-aiplatform.googleapis.com/v1beta1/projects/"
            f"{self._project_id}/locations/{self._location}/endpoints/openapi"
        )
        self._embedding_base_url = (
            f"https://{self._location}-aiplatform.googleapis.com/v1/projects/"
            f"{self._project_id}/locations/{self._location}/endpoints/openapi"
        )
        self._embedding_func = self._build_embedding_func()

    def _get_access_token(self) -> str:
        """Get a fresh OAuth token for Vertex OpenAI-compatible endpoints."""
        try:
            if not self._credentials.token or not self._credentials.valid:
                self._credentials.refresh(self._auth_request)

            if not self._credentials.token:
                raise ValueError("Access token is empty after credential refresh")

            return self._credentials.token
        except Exception as e:
            raise ValueError(
                "Unable to obtain Google Cloud access token. "
                "Run 'gcloud auth application-default login' and ensure Vertex AI API is enabled."
            ) from e

    async def _llm_model_func(
        self,
        prompt: str,
        system_prompt: str | None = None,
        history_messages: list[dict] | None = None,
        **kwargs,
    ) -> str:
        """LLM function passed to LightRAG using Vertex OpenAI-compatible chat endpoint."""
        return await openai_complete_if_cache(
            self._llm_model_name,
            prompt,
            system_prompt=system_prompt,
            history_messages=history_messages,
            api_key=self._get_access_token(),
            base_url=self._chat_base_url,
            **kwargs,
        )

    def _build_embedding_func(self) -> EmbeddingFunc:
        """Create embedding function configured for Vertex OpenAI-compatible endpoint."""

        async def _embedding_func(texts: list[str]):
            return await openai_embed.func(
                texts,
                model=self._embedding_model_name,
                api_key=self._get_access_token(),
                base_url=self._embedding_base_url,
            )

        return EmbeddingFunc(
            embedding_dim=self._embedding_dim,
            max_token_size=self._embedding_max_tokens,
            func=_embedding_func,
        )

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
                llm_model_func=self._llm_model_func,
                llm_model_name=self._llm_model_name,
                llm_model_max_async=self._llm_max_async,
                embedding_func=self._embedding_func,
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

        valid_modes = {"local", "global", "hybrid", "naive", "mix", "bypass"}
        if mode not in valid_modes:
            raise ValueError(f"Invalid query mode '{mode}'. Allowed modes: {sorted(valid_modes)}")

        query_param = QueryParam(mode=cast(SupportedQueryMode, mode))
        
        answer = await rag.aquery(question, param=query_param)
        if isinstance(answer, str):
            return answer

        chunks: list[str] = []
        async for chunk in answer:
            chunks.append(chunk)
        return "".join(chunks)

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
        working_dir = os.path.join(settings.lightrag_working_dir, user_id_str)
        
        try:
            # Remove from cache
            if user_id_str in self._rag_instances:
                del self._rag_instances[user_id_str]
            
            # Remove working directory
            if os.path.exists(working_dir):
                shutil.rmtree(working_dir)
            
            return True
        except Exception as e:
            logger.error("Error deleting graph: %s", str(e))
            return False


# Global instance
_lightrag_service = None


def get_lightrag_service() -> LightRAGService:
    """Get or create the global LightRAG service instance."""
    global _lightrag_service
    if _lightrag_service is None:
        _lightrag_service = LightRAGService()
    return _lightrag_service
