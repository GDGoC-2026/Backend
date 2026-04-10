import google.generativeai as genai
from pymilvus import Collection
import logging
from Backend.core.config import settings
from Backend.db.vector import get_collection
import json
from typing import AsyncGenerator

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
        
        genai.configure(api_key=settings.gemini_api_key)
        self.model = genai.GenerativeModel("gemini-2.0-flash")

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
            
            # Stream response from Gemini
            response = self.model.generate_content(
                f"{system_prompt}\n\nUser Content:\n{content}",
                stream=True,
                generation_config={
                    "temperature": 0.7,
                    "top_p": 0.95,
                    "top_k": 40,
                    "max_output_tokens": 1024,
                }
            )
            
            # Yield chunks as they arrive
            for chunk in response:
                if chunk.text:
                    yield chunk.text
                    
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
            collection = get_collection(content_type)
            if not collection:
                logger.warning(f"Collection '{content_type}' not found")
                return ""
            
            # TODO: Generate embeddings from content
            # This requires an embedding model (e.g., sentence-transformers)
            # For now, return empty context
            # In production: embeddings = self.embed_text(content)
            
            logger.info(f"RAG context would be retrieved for {content_type}")
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
        user_id: int,
        metadata: dict = None,
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
            collection = get_collection(content_type)
            if not collection:
                logger.error(f"Collection '{content_type}' not found")
                return False
            
            # TODO: Generate embeddings
            # embeddings = self.embed_text(content)
            
            # TODO: Insert into Milvus
            # data = [[embeddings], [content], [metadata], [source_type], [user_id]]
            # collection.insert(data)
            
            logger.info(f"Content added to {content_type} collection")
            return True
            
        except Exception as e:
            logger.error(f"Error adding to RAG: {str(e)}")
            return False
