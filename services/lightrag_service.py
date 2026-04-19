import asyncio
import json
import logging
import os
import random
import time
from collections import deque
from pathlib import Path
from typing import Literal, Optional, cast
from uuid import UUID
from dotenv import load_dotenv
load_dotenv()

import google.auth
import networkx as nx
import numpy as np
import vertexai
from google.api_core.exceptions import ResourceExhausted, TooManyRequests
from google.auth.exceptions import DefaultCredentialsError
from google.auth.transport.requests import Request as GoogleAuthRequest
from lightrag import LightRAG, QueryParam
from lightrag.llm.openai import create_openai_async_client, openai_complete_if_cache
from openai import BadRequestError, NotFoundError, RateLimitError
from lightrag.utils import EmbeddingFunc
from vertexai.language_models import TextEmbeddingInput, TextEmbeddingModel

from Backend.core.config import settings
from Backend.schemas.knowledge import GraphEdge, GraphNode, IngestDocumentStatus


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
        self._use_vertex = False
        self._credentials = None
        self._auth_request = GoogleAuthRequest()
        self._project_id: Optional[str] = None

        self._location = os.getenv("VERTEX_AI_LOCATION", "us-central1")
        self._llm_model_name = os.getenv("LIGHTRAG_LLM_MODEL", "google/gemini-2.5-flash")
        self._embedding_model_name = os.getenv("LIGHTRAG_EMBEDDING_MODEL", "text-embedding-005")
        self._gemini_api_key = settings.gemini_api_key or os.getenv("GEMINI_API_KEY", "")
        self._gemini_embedding_fallback_models: list[str] = []
        self._gemini_embedding_dim = int(os.getenv("LIGHTRAG_GEMINI_EMBEDDING_DIM", "3072"))
        self._embedding_dim = int(os.getenv("LIGHTRAG_EMBEDDING_DIM", "768"))
        self._embedding_max_tokens = int(os.getenv("LIGHTRAG_EMBEDDING_MAX_TOKENS", "8192"))
        self._embedding_batch_num = max(1, int(os.getenv("LIGHTRAG_EMBEDDING_BATCH_NUM", "32")))
        self._embedding_rate_limit_rpm = max(
            1,
            int(os.getenv("LIGHTRAG_EMBEDDING_RATE_LIMIT_RPM", "120")),
        )
        self._embedding_max_concurrency = max(
            1,
            int(os.getenv("LIGHTRAG_EMBEDDING_MAX_CONCURRENCY", "4")),
        )
        self._embedding_retry_attempts = max(
            1,
            int(os.getenv("LIGHTRAG_EMBEDDING_RETRY_ATTEMPTS", "3")),
        )
        self._embedding_retry_base_delay_seconds = max(
            0.1,
            float(os.getenv("LIGHTRAG_EMBEDDING_RETRY_BASE_DELAY_SECONDS", "1")),
        )
        self._embedding_retry_max_delay_seconds = max(
            self._embedding_retry_base_delay_seconds,
            float(os.getenv("LIGHTRAG_EMBEDDING_RETRY_MAX_DELAY_SECONDS", "15")),
        )
        self._embedding_retry_jitter_ratio = max(
            0.0,
            float(os.getenv("LIGHTRAG_EMBEDDING_RETRY_JITTER_RATIO", "0.2")),
        )
        self._llm_max_async = int(os.getenv("LIGHTRAG_LLM_MAX_ASYNC", "4"))
        self._openai_timeout_seconds = max(
            5.0,
            float(os.getenv("LIGHTRAG_OPENAI_TIMEOUT_SECONDS", "45")),
        )
        self._openai_max_retries = max(
            0,
            int(os.getenv("LIGHTRAG_OPENAI_MAX_RETRIES", "1")),
        )

        self._embedding_rate_limiter = AsyncRateLimiter(
            max_calls=self._embedding_rate_limit_rpm,
            period_seconds=60.0,
        )
        self._embedding_semaphore = asyncio.Semaphore(self._embedding_max_concurrency)
        self._pipeline_initialized = False

        self._configure_model_endpoints()
        self._embedding_func = self._build_embedding_func()

        logger.info(
            "LightRAG provider=%s controls: batch=%s rpm=%s concurrency=%s retries=%s",
            "vertex" if self._use_vertex else "gemini-key",
            self._embedding_batch_num,
            self._embedding_rate_limit_rpm,
            self._embedding_max_concurrency,
            self._embedding_retry_attempts,
        )

    def _configure_model_endpoints(self) -> None:
        """
        Configure auth and endpoints.

        Priority:
        1) Vertex AI via ADC + project id.
        2) Gemini API key (OpenAI-compatible endpoint) fallback.
        """
        vertex_project_id = settings.vertex_ai_project_id or os.getenv("VERTEX_AI_PROJECT_ID", "")

        if vertex_project_id:
            try:
                self._credentials, _ = google.auth.default(
                    scopes=["https://www.googleapis.com/auth/cloud-platform"]
                )
                self._project_id = vertex_project_id
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
                self._use_vertex = True
                return
            except DefaultCredentialsError:
                logger.warning(
                    "Vertex AI project is configured but ADC is missing. Falling back to GEMINI_API_KEY."
                )
            except Exception as exc:
                logger.warning(
                    "Vertex AI initialization failed (%s). Falling back to GEMINI_API_KEY when available.",
                    str(exc),
                )

        if self._gemini_api_key:
            self._use_vertex = False
            self._chat_base_url = "https://generativelanguage.googleapis.com/v1beta/openai/"
            self._embedding_base_url = self._chat_base_url
            self._embedding_dim = self._gemini_embedding_dim

            # Normalize model names for Gemini OpenAI-compatible endpoint.
            self._llm_model_name = self._normalize_gemini_model_name(self._llm_model_name)
            gemini_embedding_model = os.getenv("LIGHTRAG_GEMINI_EMBEDDING_MODEL", "gemini-embedding-001")
            self._embedding_model_name = self._normalize_gemini_model_name(gemini_embedding_model)

            configured_fallbacks = os.getenv(
                "LIGHTRAG_GEMINI_EMBEDDING_FALLBACKS",
                "gemini-embedding-001",
            )
            self._gemini_embedding_fallback_models = [
                self._normalize_gemini_model_name(item)
                for item in configured_fallbacks.split(",")
                if item.strip()
            ]
            return

        raise ValueError(
            "LightRAG is not configured. Provide either:\n"
            "- Vertex setup: VERTEX_AI_PROJECT_ID + Application Default Credentials (ADC), or\n"
            "- GEMINI_API_KEY for OpenAI-compatible Gemini fallback."
        )

    def _get_access_token(self) -> str:
        """Get auth token for Vertex (ADC) or API key for Gemini fallback."""
        if not self._use_vertex:
            if not self._gemini_api_key:
                raise ValueError("GEMINI_API_KEY is missing for Gemini fallback.")
            return self._gemini_api_key

        try:
            if not self._credentials:
                raise ValueError("ADC credentials are not initialized.")

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
        """LLM function passed to LightRAG using configured OpenAI-compatible endpoint."""
        return await openai_complete_if_cache(
            self._llm_model_name,
            prompt,
            system_prompt=system_prompt,
            history_messages=history_messages,
            api_key=self._get_access_token(),
            base_url=self._chat_base_url,
            openai_client_configs={
                "max_retries": self._openai_max_retries,
                "timeout": self._openai_timeout_seconds,
            },
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
                started_at = time.perf_counter()
                if self._use_vertex and not self._is_openai_publisher_model(self._embedding_model_name):
                    vertex_model_name = self._normalize_vertex_embedding_model_name(
                        self._embedding_model_name
                    )
                    vectors = await asyncio.to_thread(
                        self._embed_with_vertex_native,
                        vertex_model_name,
                        texts,
                    )
                    elapsed = time.perf_counter() - started_at
                    if elapsed >= 3:
                        logger.info(
                            "Slow embedding batch detected: size=%s provider=%s model=%s duration=%.2fs",
                            len(texts),
                            "vertex" if self._use_vertex else "gemini-key",
                            self._embedding_model_name,
                            elapsed,
                        )
                    return vectors

                vectors = await self._embed_with_openai_compatible(texts)
                elapsed = time.perf_counter() - started_at
                if elapsed >= 3:
                    logger.info(
                        "Slow embedding batch detected: size=%s provider=%s model=%s duration=%.2fs",
                        len(texts),
                        "vertex" if self._use_vertex else "gemini-key",
                        self._embedding_model_name,
                        elapsed,
                    )
                return vectors

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
        # Both Vertex and Gemini OpenAI-compatible embeddings expect encoding_format="float".
        openai_async_client = create_openai_async_client(
            api_key=self._get_access_token(),
            base_url=self._embedding_base_url,
            client_configs={
                "max_retries": self._openai_max_retries,
                "timeout": self._openai_timeout_seconds,
            },
        )

        async with openai_async_client:
            try:
                response = await openai_async_client.embeddings.create(
                    model=self._embedding_model_name,
                    input=texts,
                    encoding_format="float",
                )
            except NotFoundError as exc:
                if not self._use_vertex:
                    response = await self._try_gemini_embedding_fallback_models(
                        openai_async_client=openai_async_client,
                        texts=texts,
                        original_error=exc,
                    )
                else:
                    raise
            except BadRequestError as exc:
                fallback_model = (
                    f"openai/{self._embedding_model_name}"
                    if "/" not in self._embedding_model_name
                    else self._embedding_model_name
                )
                if (
                    self._use_vertex
                    and
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
                elif not self._use_vertex and "not found" in str(exc).lower():
                    response = await self._try_gemini_embedding_fallback_models(
                        openai_async_client=openai_async_client,
                        texts=texts,
                        original_error=exc,
                    )
                else:
                    raise

        vectors = [np.array(item.embedding, dtype=np.float32) for item in response.data]
        return np.array(vectors, dtype=np.float32)

    async def _try_gemini_embedding_fallback_models(
        self,
        openai_async_client,
        texts: list[str],
        original_error: Exception,
    ):
        """Try alternative Gemini embedding models when current model is unavailable."""
        tried = {self._embedding_model_name}

        for model_name in self._gemini_embedding_fallback_models:
            if model_name in tried:
                continue
            tried.add(model_name)

            try:
                response = await openai_async_client.embeddings.create(
                    model=model_name,
                    input=texts,
                    encoding_format="float",
                )
                logger.warning(
                    "Gemini embedding model '%s' unavailable, switched to '%s'",
                    self._embedding_model_name,
                    model_name,
                )
                self._embedding_model_name = model_name
                return response
            except Exception:
                continue

        raise original_error

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

    @staticmethod
    def _normalize_gemini_model_name(model_name: str) -> str:
        """Normalize model names for Gemini OpenAI-compatible endpoint."""
        normalized = model_name.strip()
        if normalized.startswith("google/"):
            normalized = normalized.split("/", 1)[1]
        if normalized.startswith("openai/"):
            normalized = normalized.split("/", 1)[1]
        return normalized

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

        nodes, edges = self._load_graph_from_graphml(graph_file)
        if not nodes:
            fallback_nodes, fallback_edges = self._load_graph_from_kv_stores(working_dir)
            if fallback_nodes:
                nodes = fallback_nodes
                edges = fallback_edges

        return {
            "nodes": nodes,
            "edges": edges
        }

    def get_ingest_status(self, user_id: UUID | str) -> dict:
        """
        Retrieve ingestion pipeline statuses for the current user.

        Returns:
            Aggregated status counts and per-document statuses.
        """
        working_dir = self._get_working_dir(user_id)
        status_file = os.path.join(working_dir, "kv_store_doc_status.json")

        documents: list[IngestDocumentStatus] = []
        processing_docs = 0
        processed_docs = 0
        failed_docs = 0
        now_timestamp = int(time.time())
        stale_processing_seconds = max(
            60,
            int(os.getenv("LIGHTRAG_STALE_PROCESSING_SECONDS", "600")),
        )

        if os.path.exists(status_file):
            try:
                with open(status_file, "r", encoding="utf-8") as file_handle:
                    raw_statuses = json.load(file_handle)

                if isinstance(raw_statuses, dict):
                    for doc_id, payload in raw_statuses.items():
                        if not isinstance(payload, dict):
                            continue

                        status_value = str(payload.get("status", "unknown")).lower()
                        metadata = payload.get("metadata", {})
                        processing_start = None
                        if isinstance(metadata, dict):
                            raw_start = metadata.get("processing_start_time")
                            if raw_start is not None:
                                try:
                                    processing_start = int(raw_start)
                                except (TypeError, ValueError):
                                    processing_start = None

                        if (
                            status_value == "processing"
                            and processing_start is not None
                            and now_timestamp - processing_start > stale_processing_seconds
                        ):
                            status_value = "failed"

                        if status_value == "processing":
                            processing_docs += 1
                        elif status_value == "processed":
                            processed_docs += 1
                        elif status_value == "failed":
                            failed_docs += 1

                        error_message = payload.get("error")
                        if error_message is None and isinstance(metadata, dict):
                            error_message = metadata.get("error")
                        if error_message is None and status_value == "failed":
                            error_message = "Processing timed out. Please ingest again or reset graph."

                        documents.append(
                            IngestDocumentStatus(
                                doc_id=str(doc_id),
                                status=status_value,
                                chunks_count=int(payload.get("chunks_count", 0) or 0),
                                content_summary=payload.get("content_summary"),
                                created_at=payload.get("created_at"),
                                updated_at=payload.get("updated_at"),
                                error=str(error_message) if error_message else None,
                            )
                        )
            except Exception as exc:
                logger.warning("Failed to parse LightRAG status file '%s': %s", status_file, str(exc))

        documents.sort(
            key=lambda item: item.updated_at or item.created_at or "",
            reverse=True,
        )

        graph_data = self.get_graph_data(user_id)

        return {
            "total_docs": len(documents),
            "processing_docs": processing_docs,
            "processed_docs": processed_docs,
            "failed_docs": failed_docs,
            "graph_nodes": len(graph_data["nodes"]),
            "graph_edges": len(graph_data["edges"]),
            "documents": documents,
        }

    @staticmethod
    def _to_graph_label(value: object, fallback: str) -> str:
        if isinstance(value, str):
            stripped = value.strip()
            return stripped if stripped else fallback
        if value is None:
            return fallback
        return str(value)

    def _load_graph_from_graphml(self, graph_file: str) -> tuple[list[GraphNode], list[GraphEdge]]:
        nodes: list[GraphNode] = []
        edges: list[GraphEdge] = []

        if not os.path.exists(graph_file):
            return nodes, edges

        try:
            graph = nx.read_graphml(graph_file)

            for node_id, node_data in graph.nodes(data=True):
                node_id_text = self._to_graph_label(node_id, "node")
                node_label = self._to_graph_label(node_data.get("description"), node_id_text)
                nodes.append(
                    GraphNode(
                        id=node_id_text,
                        label=node_label,
                        properties=dict(node_data),
                    )
                )

            for source, target, edge_data in graph.edges(data=True):
                source_id = self._to_graph_label(source, "source")
                target_id = self._to_graph_label(target, "target")
                edge_label = self._to_graph_label(edge_data.get("description"), "related")
                edges.append(
                    GraphEdge(
                        source=source_id,
                        target=target_id,
                        label=edge_label,
                        properties=dict(edge_data),
                    )
                )
        except Exception as exc:
            logger.warning("Error parsing graph file '%s': %s", graph_file, str(exc))

        return nodes, edges

    def _load_graph_from_kv_stores(self, working_dir: str) -> tuple[list[GraphNode], list[GraphEdge]]:
        entities_file = os.path.join(working_dir, "kv_store_full_entities.json")
        relations_file = os.path.join(working_dir, "kv_store_full_relations.json")

        if not os.path.exists(entities_file):
            return [], []

        try:
            with open(entities_file, "r", encoding="utf-8") as file_handle:
                entities_payload = json.load(file_handle)
        except Exception as exc:
            logger.warning("Unable to parse entities store '%s': %s", entities_file, str(exc))
            return [], []

        relations_payload: dict = {}
        if os.path.exists(relations_file):
            try:
                with open(relations_file, "r", encoding="utf-8") as file_handle:
                    loaded = json.load(file_handle)
                    if isinstance(loaded, dict):
                        relations_payload = loaded
            except Exception as exc:
                logger.warning("Unable to parse relations store '%s': %s", relations_file, str(exc))

        if not isinstance(entities_payload, dict):
            return [], []

        node_map: dict[str, GraphNode] = {}
        for doc_id, payload in entities_payload.items():
            if not isinstance(payload, dict):
                continue
            entity_names = payload.get("entity_names", [])
            if not isinstance(entity_names, list):
                continue

            for entity_name in entity_names:
                if not isinstance(entity_name, str):
                    continue

                entity_id = entity_name.strip()
                if not entity_id or entity_id in node_map:
                    continue

                node_map[entity_id] = GraphNode(
                    id=entity_id,
                    label=entity_id,
                    properties={
                        "doc_id": str(doc_id),
                        "source": "kv_store_full_entities",
                    },
                )

        edges: list[GraphEdge] = []
        dedupe_edges: set[tuple[str, str]] = set()

        for doc_id, payload in relations_payload.items():
            if not isinstance(payload, dict):
                continue
            relation_pairs = payload.get("relation_pairs", [])
            if not isinstance(relation_pairs, list):
                continue

            for relation in relation_pairs:
                if not isinstance(relation, list) or len(relation) < 2:
                    continue

                source = relation[0] if isinstance(relation[0], str) else None
                target = relation[1] if isinstance(relation[1], str) else None
                if not source or not target:
                    continue

                source_id = source.strip()
                target_id = target.strip()
                if not source_id or not target_id:
                    continue

                if source_id not in node_map:
                    node_map[source_id] = GraphNode(
                        id=source_id,
                        label=source_id,
                        properties={"source": "kv_store_full_relations"},
                    )
                if target_id not in node_map:
                    node_map[target_id] = GraphNode(
                        id=target_id,
                        label=target_id,
                        properties={"source": "kv_store_full_relations"},
                    )

                edge_key = (source_id, target_id)
                if edge_key in dedupe_edges:
                    continue

                dedupe_edges.add(edge_key)
                edges.append(
                    GraphEdge(
                        source=source_id,
                        target=target_id,
                        label="related",
                        properties={
                            "doc_id": str(doc_id),
                            "source": "kv_store_full_relations",
                        },
                    )
                )

        return list(node_map.values()), edges

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
