from __future__ import annotations

import logging
from typing import Any

import httpx

from Backend.services.workflows.utils.grounding import extract_keywords, normalize_text, unique_preserve_order

logger = logging.getLogger(__name__)


class WebResearchAgent:
    """
    Lightweight web research helper used to enrich lesson generation context.

    Uses DuckDuckGo Instant Answer API to gather public snippets and URLs
    without requiring API keys.
    """

    SEARCH_ENDPOINT = "https://api.duckduckgo.com/"

    def __init__(self, timeout_seconds: float = 10.0):
        self.timeout_seconds = timeout_seconds

    def _build_queries(
        self,
        *,
        topic: str,
        prompt: str,
        subtopics: list[str],
        learning_objectives: list[str],
        max_queries: int,
    ) -> list[str]:
        base_queries: list[str] = []
        normalized_prompt = normalize_text(prompt)
        normalized_topic = normalize_text(topic)

        if normalized_prompt:
            base_queries.append(normalized_prompt[:180])

        if normalized_topic:
            base_queries.append(f"{normalized_topic} overview")
            base_queries.append(f"{normalized_topic} key concepts")

        for subtopic in subtopics[:3]:
            cleaned = normalize_text(subtopic)
            if cleaned:
                base_queries.append(f"{cleaned} in {normalized_topic}" if normalized_topic else cleaned)

        for objective in learning_objectives[:2]:
            cleaned = normalize_text(objective)
            if cleaned:
                base_queries.append(f"{normalized_topic} {cleaned}".strip())

        keywords = extract_keywords(normalized_prompt, normalized_topic, *subtopics, *learning_objectives)
        if keywords:
            suffix = " ".join(keywords[:5])
            base_queries.append(f"{normalized_topic} {suffix}".strip())

        return unique_preserve_order(base_queries)[:max(1, max_queries)]

    async def _search_query(self, query: str, *, max_results: int) -> list[dict[str, str]]:
        params = {
            "q": query,
            "format": "json",
            "no_html": "1",
            "skip_disambig": "1",
        }

        async with httpx.AsyncClient(timeout=self.timeout_seconds, follow_redirects=True) as client:
            response = await client.get(self.SEARCH_ENDPOINT, params=params)
            response.raise_for_status()
            payload = response.json()

        collected: list[dict[str, str]] = []

        abstract_text = normalize_text(str(payload.get("AbstractText", "")))
        abstract_url = str(payload.get("AbstractURL", "") or "")
        abstract_source = str(payload.get("AbstractSource", "DuckDuckGo") or "DuckDuckGo")
        heading = normalize_text(str(payload.get("Heading", "")))

        if abstract_text:
            collected.append(
                {
                    "title": heading or query,
                    "url": abstract_url,
                    "snippet": abstract_text,
                    "source": abstract_source,
                    "query": query,
                }
            )

        related_topics = payload.get("RelatedTopics", [])

        def _extract_related(items: list[Any]) -> list[dict[str, str]]:
            results: list[dict[str, str]] = []
            for item in items:
                if isinstance(item, dict) and "Topics" in item and isinstance(item["Topics"], list):
                    results.extend(_extract_related(item["Topics"]))
                    continue

                if not isinstance(item, dict):
                    continue

                snippet = normalize_text(str(item.get("Text", "")))
                url = str(item.get("FirstURL", "") or "")

                if not snippet:
                    continue

                title = snippet.split(" - ", 1)[0].strip() if " - " in snippet else snippet[:90]
                results.append(
                    {
                        "title": title or query,
                        "url": url,
                        "snippet": snippet,
                        "source": "DuckDuckGo",
                        "query": query,
                    }
                )
            return results

        collected.extend(_extract_related(related_topics))

        deduped: list[dict[str, str]] = []
        seen: set[str] = set()
        for item in collected:
            key = (item.get("url") or item.get("title") or item.get("snippet") or "").casefold()
            if not key or key in seen:
                continue
            seen.add(key)
            deduped.append(item)
            if len(deduped) >= max_results:
                break

        return deduped

    async def research(
        self,
        *,
        topic: str,
        prompt: str,
        subtopics: list[str],
        learning_objectives: list[str],
        max_sources: int = 6,
        max_queries: int = 5,
    ) -> list[dict[str, str]]:
        queries = self._build_queries(
            topic=topic,
            prompt=prompt,
            subtopics=subtopics,
            learning_objectives=learning_objectives,
            max_queries=max_queries,
        )
        if not queries:
            return []

        per_query_limit = max(1, min(5, max_sources))
        aggregated: list[dict[str, str]] = []
        seen: set[str] = set()

        for query in queries:
            try:
                results = await self._search_query(query, max_results=per_query_limit)
            except Exception as exc:
                logger.warning("Web research query failed for '%s': %s", query, str(exc))
                continue

            for result in results:
                key = (result.get("url") or result.get("title") or result.get("snippet") or "").casefold()
                if not key or key in seen:
                    continue

                seen.add(key)
                aggregated.append(result)

                if len(aggregated) >= max_sources:
                    return aggregated

        return aggregated

    def to_source_materials(self, sources: list[dict[str, str]], *, snippet_chars: int = 900) -> list[str]:
        materials: list[str] = []

        for source in sources:
            title = normalize_text(source.get("title", "")) or "External source"
            url = normalize_text(source.get("url", ""))
            snippet = normalize_text(source.get("snippet", ""))[:snippet_chars]
            source_name = normalize_text(source.get("source", "Web")) or "Web"

            if not snippet:
                continue

            material_lines = [f"Source: {source_name}", f"Title: {title}"]
            if url:
                material_lines.append(f"URL: {url}")
            material_lines.append(f"Summary: {snippet}")
            materials.append("\n".join(material_lines))

        return materials


_web_research_agent: WebResearchAgent | None = None


def get_web_research_agent() -> WebResearchAgent:
    global _web_research_agent
    if _web_research_agent is None:
        _web_research_agent = WebResearchAgent()
    return _web_research_agent
