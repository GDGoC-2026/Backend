import google.generativeai as genai
from Backend.core.config import settings


class FormatterAgent:
    """
    Formatter Agent using Google Gemini to enhance and structure raw notes.
    Transforms raw, unstructured notes into well-formatted markdown content.
    """

    def __init__(self):
        """Initialize the Formatter Agent with Gemini API key."""
        if not settings.gemini_api_key:
            raise ValueError("GEMINI_API_KEY is not set in configuration")
        
        genai.configure(api_key=settings.gemini_api_key)
        self.model = genai.GenerativeModel("gemini-2.0-flash")

    async def format_notes(self, raw_content: str, title: str | None = None) -> str:
        """
        Format and enhance raw notes using Gemini.
        
        Args:
            raw_content: Raw, unstructured notes (bullet points, abbreviations, etc.)
            title: Optional title for the notes
            
        Returns:
            Formatted markdown content with structure, context, and improved readability
        """
        
        system_prompt = """You are an expert note formatter and content optimizer.
Your task is to transform raw, unstructured notes into well-formatted, structured markdown content.

Guidelines:
1. Preserve all original information and facts
2. Expand abbreviations and acronyms with explanations
3. Organize content into logical sections with headers
4. Add context where needed to improve clarity
5. Fix grammar and spelling while maintaining the author's voice
6. Use markdown formatting: headers, lists, bold, italic, code blocks where appropriate
7. Add relationships between concepts to improve understanding
8. Create a clear hierarchy of information

Output ONLY the formatted markdown content, no additional commentary."""

        user_message = f"Format these raw notes into well-structured markdown:\n\n"
        if title:
            user_message += f"Title: {title}\n\n"
        user_message += raw_content

        try:
            response = self.model.generate_content(
                f"{system_prompt}\n\n{user_message}",
                generation_config={
                    "temperature": 0.7,
                    "top_p": 0.95,
                    "top_k": 40,
                    "max_output_tokens": 4096,
                }
            )
            return response.text
        except Exception as e:
            raise RuntimeError(f"Error formatting notes with Gemini: {str(e)}")


async def format_notes(raw_content: str, title: str | None = None) -> str:
    """
    Utility function to format notes using the FormatterAgent.
    
    Args:
        raw_content: Raw notes text
        title: Optional title
        
    Returns:
        Formatted markdown content
    """
    formatter = FormatterAgent()
    return await formatter.format_notes(raw_content, title)
