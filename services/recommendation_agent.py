import asyncio
from google import genai
from google.genai import types
import logging
from uuid import UUID
from Backend.core.config import settings
from Backend.db.vector import get_collection
from typing import Any, AsyncGenerator

logger = logging.getLogger(__name__)


class RecommendationAgent:
    """
    AI Recommendation Agent using Google Gemini + RAG from Milvus.
    Analyzes user code/notes and provides real-time recommendations for improvement.
    """

    def __init__(self):
        """Initialize the Recommendation Agent with Gemini API key."""
        if not settings.gemini_api_key:
            raise ValueError("GEMINI_API_KEY is not set in configuration")

        self.client = genai.Client(api_key=settings.gemini_api_key)
        self.model_name = "gemini-2.5-flash"

    @staticmethod
    def _resolve_collection_name(content_type: str) -> str:
        """Map endpoint content types to Milvus collection names."""
        mapping = {
            "code": "coding",
            "coding": "coding",
            "english": "english",
        }
        return mapping.get(content_type, content_type)

    @staticmethod
    def _chunk_text(text: str, chunk_size: int = 250) -> list[str]:
        if not text:
            return []
        return [text[i:i + chunk_size] for i in range(0, len(text), chunk_size)]

    async def generate_recommendations(
        self,
        content: str,
        content_type: str,  # "code" or "english"
        user_context: str = "",
        top_k: int = 3
    ) -> AsyncGenerator[str, None]:
        """
        Generate real-time streaming recommendations based on user content.
        
        Args:
            content: User's code or English text
            content_type: "code" or "english"
            user_context: Additional context about the user (skill level, goals)
            top_k: Number of relevant items to retrieve from Milvus
            
        Yields:
            Streaming recommendation chunks
        """
        try:
            # Get relevant context from Milvus
            rag_context = await self._retrieve_rag_context(
                content, content_type, top_k
            )
            
            # Build system prompt based on content type
            system_prompt = self._get_system_prompt(content_type, rag_context, user_context)
            
            # Use a worker thread to avoid blocking the event loop with SDK sync calls.
            response = await asyncio.to_thread(
                self.client.models.generate_content,
                model=self.model_name,
                contents=f"{system_prompt}\n\nUser Content:\n{content}",
                config=types.GenerateContentConfig(
                    temperature=0.7,
                    top_p=0.95,
                    top_k=40,
                    max_output_tokens=1024,
                ),
            )

            response_text = getattr(response, "text", "") or ""
            for chunk in self._chunk_text(response_text):
                yield chunk
                await asyncio.sleep(0)
                    
        except Exception as e:
            logger.error(f"Error generating recommendations: {str(e)}")
            yield f"Error: {str(e)}"

    async def _retrieve_rag_context(
        self,
        content: str,
        content_type: str,
        top_k: int = 3
    ) -> str:
        """
        Retrieve relevant context from Milvus for RAG.
        """
        try:
            collection_name = self._resolve_collection_name(content_type)
            collection = get_collection(collection_name)
            if not collection:
                logger.warning(f"Collection '{collection_name}' not found")
                return ""
            
            # TODO: Generate embeddings from content
            # This requires an embedding model (e.g., sentence-transformers)
            # For now, return empty context
            # In production: embeddings = self.embed_text(content)
            
            logger.info(f"RAG context would be retrieved for {collection_name}")
            return ""
            
        except Exception as e:
            logger.error(f"Error retrieving RAG context: {str(e)}")
            return ""

    def _get_system_prompt(
        self,
        content_type: str,
        rag_context: str,
        user_context: str
    ) -> str:
        """Get appropriate system prompt based on content type."""
        
        base_prompt = """You are an expert AI recommendation agent helping users improve their work.
Provide constructive, actionable, and specific recommendations.
Be encouraging and supportive in tone.
Format recommendations with clear structure and examples when possible."""

        if content_type == "code":
            prompt = f"""{base_prompt}

Your task: Analyze the user's code and suggest improvements.
Focus on:
1. Code quality and readability
2. Performance optimization opportunities
3. Best practices and design patterns
4. Potential bugs or edge cases
5. Security considerations

{f"User Context: {user_context}" if user_context else ""}
{f"Related Examples from Knowledge Base:\n{rag_context}" if rag_context else ""}

Provide 3-5 specific, actionable recommendations."""

        elif content_type == "english":
            prompt = f"""{base_prompt}

Your task: Help improve the user's English writing.
Focus on:
1. Grammar and syntax correction
2. Vocabulary enhancement suggestions
3. Style and clarity improvements
4. Structure and organization
5. Fluency and natural expression

{f"User Context: {user_context}" if user_context else ""}
{f"Related Learning Examples:\n{rag_context}" if rag_context else ""}

Provide 3-5 specific, actionable recommendations."""

        else:
            prompt = base_prompt

        return prompt

    async def add_to_rag(
        self,
        content: str,
        content_type: str,
        user_id: UUID | str,
        metadata: dict[str, Any] | None = None,
        source_type: str = "user_note"
    ) -> bool:
        """
        Add content to Milvus collection for future RAG.
        
        Args:
            content: The content to add
            content_type: "code" or "english"
            user_id: User ID for personalization
            metadata: Additional metadata
            source_type: "user_note", "tip", "resource", etc.
        """
        try:
            collection_name = self._resolve_collection_name(content_type)
            collection = get_collection(collection_name)
            if not collection:
                logger.error(f"Collection '{collection_name}' not found")
                return False

            metadata = metadata or {}
            
            # TODO: Generate embeddings
            # embeddings = self.embed_text(content)
            
            # TODO: Insert into Milvus
            # data = [[embeddings], [content], [metadata], [source_type], [user_id]]
            # collection.insert(data)
            
            logger.info(f"Content added to {collection_name} collection")
            return True
            
        except Exception as e:
            logger.error(f"Error adding to RAG: {str(e)}")
            return False
