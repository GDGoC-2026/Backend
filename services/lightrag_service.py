import asyncio
import logging
import os
import random
import time
from collections import deque
from pathlib import Path
from typing import Literal, cast
from uuid import UUID
from dotenv import load_dotenv
load_dotenv()

import google.auth
import networkx as nx
import numpy as np
import vertexai
from google.api_core.exceptions import ResourceExhausted, TooManyRequests
from google.auth.transport.requests import Request as GoogleAuthRequest
from lightrag import LightRAG, QueryParam
from lightrag.llm.openai import create_openai_async_client, openai_complete_if_cache
from openai import BadRequestError, RateLimitError
from lightrag.utils import EmbeddingFunc
from vertexai.language_models import TextEmbeddingInput, TextEmbeddingModel

from Backend.core.config import settings
from Backend.schemas.knowledge import GraphNode, GraphEdge


logger = logging.getLogger(__name__)

SupportedQueryMode = Literal["local", "global", "hybrid", "naive", "mix", "bypass"]


class AsyncRateLimiter:
    """Simple async sliding-window rate limiter."""

    def __init__(self, max_calls: int, period_seconds: float = 60.0):
        self._max_calls = max(1, max_calls)
        self._period_seconds = max(1.0, period_seconds)
        self._timestamps: deque[float] = deque()
        self._lock = asyncio.Lock()

    async def acquire(self) -> None:
        while True:
            async with self._lock:
                now = time.monotonic()
                while self._timestamps and now - self._timestamps[0] >= self._period_seconds:
                    self._timestamps.popleft()

                if len(self._timestamps) < self._max_calls:
                    self._timestamps.append(now)
                    return

                wait_seconds = self._period_seconds - (now - self._timestamps[0])

            await asyncio.sleep(max(wait_seconds, 0.01))


class LightRAGService:
    """
    Service to manage LightRAG instances per user.
    Each user gets an isolated working directory for their knowledge graph.
    """

    def __init__(self):
        """Initialize the LightRAG service."""
        self._rag_instances: dict[str, LightRAG] = {}
        self._vertex_embedding_models: dict[str, TextEmbeddingModel] = {}

        self._location = os.getenv("VERTEX_AI_LOCATION", "us-central1")
        self._llm_model_name = os.getenv("LIGHTRAG_LLM_MODEL", "google/gemini-2.5-flash")
        self._embedding_model_name = os.getenv("LIGHTRAG_EMBEDDING_MODEL", "text-embedding-005")
        self._embedding_dim = int(os.getenv("LIGHTRAG_EMBEDDING_DIM", "768"))
        self._embedding_max_tokens = int(os.getenv("LIGHTRAG_EMBEDDING_MAX_TOKENS", "8192"))
        self._embedding_batch_num = max(1, int(os.getenv("LIGHTRAG_EMBEDDING_BATCH_NUM", "8")))
        self._embedding_rate_limit_rpm = max(
            1,
            int(os.getenv("LIGHTRAG_EMBEDDING_RATE_LIMIT_RPM", "5")),
        )
        self._embedding_max_concurrency = max(
            1,
            int(os.getenv("LIGHTRAG_EMBEDDING_MAX_CONCURRENCY", "1")),
        )
        self._embedding_retry_attempts = max(
            1,
            int(os.getenv("LIGHTRAG_EMBEDDING_RETRY_ATTEMPTS", "6")),
        )
        self._embedding_retry_base_delay_seconds = max(
            0.1,
            float(os.getenv("LIGHTRAG_EMBEDDING_RETRY_BASE_DELAY_SECONDS", "5")),
        )
        self._embedding_retry_max_delay_seconds = max(
            self._embedding_retry_base_delay_seconds,
            float(os.getenv("LIGHTRAG_EMBEDDING_RETRY_MAX_DELAY_SECONDS", "120")),
        )
        self._embedding_retry_jitter_ratio = max(
            0.0,
            float(os.getenv("LIGHTRAG_EMBEDDING_RETRY_JITTER_RATIO", "0.2")),
        )
        self._llm_max_async = int(os.getenv("LIGHTRAG_LLM_MAX_ASYNC", "1"))

        self._embedding_rate_limiter = AsyncRateLimiter(
            max_calls=self._embedding_rate_limit_rpm,
            period_seconds=60.0,
        )
        self._embedding_semaphore = asyncio.Semaphore(self._embedding_max_concurrency)

        # Acquire Application Default Credentials for Vertex OpenAI-compatible endpoints.
        self._credentials, detected_project = google.auth.default(
            scopes=["https://www.googleapis.com/auth/cloud-platform"]
        )
        self._project_id = settings.vertex_ai_project_id
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
        self._pipeline_initialized = False

        logger.info(
            "LightRAG embedding controls: batch=%s rpm=%s concurrency=%s retries=%s",
            self._embedding_batch_num,
            self._embedding_rate_limit_rpm,
            self._embedding_max_concurrency,
            self._embedding_retry_attempts,
        )

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
            async with self._embedding_semaphore:
                return await self._embed_with_resilience(texts)

        return EmbeddingFunc(
            embedding_dim=self._embedding_dim,
            max_token_size=self._embedding_max_tokens,
            func=_embedding_func,
        )

    async def _embed_with_resilience(self, texts: list[str]) -> np.ndarray:
        delay = self._embedding_retry_base_delay_seconds
        attempt = 1

        while attempt <= self._embedding_retry_attempts:
            await self._embedding_rate_limiter.acquire()

            try:
                if not self._is_openai_publisher_model(self._embedding_model_name):
                    vertex_model_name = self._normalize_vertex_embedding_model_name(
                        self._embedding_model_name
                    )
                    return await asyncio.to_thread(
                        self._embed_with_vertex_native,
                        vertex_model_name,
                        texts,
                    )

                return await self._embed_with_openai_compatible(texts)

            except Exception as exc:
                is_retryable = self._is_quota_or_rate_limit_error(exc)
                if not is_retryable or attempt >= self._embedding_retry_attempts:
                    raise

                jitter = random.uniform(0.0, delay * self._embedding_retry_jitter_ratio)
                sleep_seconds = min(self._embedding_retry_max_delay_seconds, delay + jitter)
                logger.warning(
                    "Embedding rate/quota limited (attempt %s/%s). Retrying in %.2fs. Error: %s",
                    attempt,
                    self._embedding_retry_attempts,
                    sleep_seconds,
                    str(exc),
                )
                await asyncio.sleep(sleep_seconds)
                delay = min(self._embedding_retry_max_delay_seconds, delay * 2)
                attempt += 1

        raise RuntimeError("Embedding failed after retry loop")

    async def _embed_with_openai_compatible(self, texts: list[str]) -> np.ndarray:
        # Vertex OpenAI-compatible embeddings expect encoding_format="float".
        openai_async_client = create_openai_async_client(
            api_key=self._get_access_token(),
            base_url=self._embedding_base_url,
        )

        async with openai_async_client:
            try:
                response = await openai_async_client.embeddings.create(
                    model=self._embedding_model_name,
                    input=texts,
                    encoding_format="float",
                )
            except BadRequestError as exc:
                fallback_model = (
                    f"openai/{self._embedding_model_name}"
                    if "/" not in self._embedding_model_name
                    else self._embedding_model_name
                )
                if (
                    fallback_model != self._embedding_model_name
                    and "malformed publisher model" in str(exc).lower()
                ):
                    logger.warning(
                        "Embedding model '%s' malformed, retrying with '%s'",
                        self._embedding_model_name,
                        fallback_model,
                    )
                    response = await openai_async_client.embeddings.create(
                        model=fallback_model,
                        input=texts,
                        encoding_format="float",
                    )
                    self._embedding_model_name = fallback_model
                else:
                    raise

        vectors = [np.array(item.embedding, dtype=np.float32) for item in response.data]
        return np.array(vectors, dtype=np.float32)

    @staticmethod
    def _is_quota_or_rate_limit_error(exc: Exception) -> bool:
        if isinstance(exc, (ResourceExhausted, TooManyRequests, RateLimitError)):
            return True

        status_code = getattr(exc, "status_code", None)
        if status_code == 429:
            return True

        message = str(exc).lower()
        return any(
            token in message
            for token in (
                "quota exceeded",
                "resource_exhausted",
                "too many requests",
                "rate limit",
                "statuscode.resource_exhausted",
                "error code: 429",
            )
        )

    @staticmethod
    def _is_openai_publisher_model(model_name: str) -> bool:
        """Return True if model is explicitly configured for OpenAI-compatible publisher routing."""
        return model_name.startswith("openai/")

    @staticmethod
    def _normalize_vertex_embedding_model_name(model_name: str) -> str:
        """Normalize model names for native Vertex embedding API."""
        if model_name.startswith("google/"):
            return model_name.split("/", 1)[1]
        return model_name

    def _get_vertex_embedding_model(self, model_name: str) -> TextEmbeddingModel:
        if model_name not in self._vertex_embedding_models:
            self._vertex_embedding_models[model_name] = TextEmbeddingModel.from_pretrained(model_name)
        return self._vertex_embedding_models[model_name]

    def _embed_with_vertex_native(self, model_name: str, texts: list[str]) -> np.ndarray:
        """Embed text using native Vertex model API for Google publisher models."""
        model = self._get_vertex_embedding_model(model_name)
        vertex_texts = cast(list[str | TextEmbeddingInput], texts)

        try:
            response = model.get_embeddings(vertex_texts, output_dimensionality=self._embedding_dim)
        except Exception as exc:
            # Some embedding models may not support explicit output_dimensionality.
            if "output_dimensionality" not in str(exc).lower():
                raise
            response = model.get_embeddings(vertex_texts)

        vectors = [np.array(item.values, dtype=np.float32) for item in response]
        return np.array(vectors, dtype=np.float32)

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
    
    async def _ensure_initialized(self, rag: LightRAG):
        if not getattr(rag, "_initialized", False):
            await rag.initialize_storages()

            if not self._pipeline_initialized:
                from lightrag.kg.shared_storage import initialize_pipeline_status
                await initialize_pipeline_status()
                self._pipeline_initialized = True

            rag._initialized = True # type: ignore

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
                embedding_batch_num=self._embedding_batch_num,
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
        await self._ensure_initialized(rag)
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
        await self._ensure_initialized(rag)

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
