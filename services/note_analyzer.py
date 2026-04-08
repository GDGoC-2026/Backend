import re
from typing import List

class NoteAnalyzer:
    @staticmethod
    def chunk_markdown(content: str) -> List[str]:
        """
        Splits markdown notes into semantic chunks based on headers.
        """
        # Simple regex to split by Markdown headers (## or #)
        chunks = re.split(r'(?m)^#{1,3}\s', content)
        # Clean up empty strings and re-attach a generic header flag if needed
        cleaned_chunks = [chunk.strip() for chunk in chunks if chunk.strip()]
        return cleaned_chunks