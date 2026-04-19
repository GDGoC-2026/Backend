"""
Utilities for grounding generated content in prompt and source materials.
"""

from __future__ import annotations

import re
from collections.abc import Iterable

STOPWORDS = {
    "about",
    "after",
    "also",
    "among",
    "because",
    "before",
    "being",
    "between",
    "could",
    "does",
    "from",
    "have",
    "into",
    "just",
    "main",
    "more",
    "most",
    "other",
    "over",
    "same",
    "some",
    "such",
    "than",
    "that",
    "their",
    "there",
    "these",
    "this",
    "through",
    "under",
    "using",
    "very",
    "what",
    "when",
    "where",
    "which",
    "while",
    "with",
    "would",
    "your",
}


def normalize_text(text: str) -> str:
    return " ".join((text or "").split())


def unique_preserve_order(values: Iterable[str]) -> list[str]:
    seen: set[str] = set()
    result: list[str] = []

    for value in values:
        normalized = normalize_text(value)
        if not normalized:
            continue
        key = normalized.casefold()
        if key in seen:
            continue
        seen.add(key)
        result.append(normalized)

    return result


def extract_keywords(*parts: str) -> list[str]:
    words: list[str] = []

    for part in parts:
        for word in re.findall(r"[A-Za-z][A-Za-z0-9_/+-]{2,}", part or ""):
            lowered = word.casefold()
            if lowered in STOPWORDS:
                continue
            words.append(word)

    return unique_preserve_order(words)


def split_into_sentences(text: str, *, max_sentences: int | None = None) -> list[str]:
    normalized = normalize_text(text)
    if not normalized:
        return []

    pieces = re.split(r"(?<=[.!?])\s+|\s*[\r\n]+\s*", normalized)
    sentences = [
        piece.strip(" -")
        for piece in pieces
        if 25 <= len(piece.strip()) <= 320
    ]

    if max_sentences is not None:
        return sentences[:max_sentences]

    return sentences


def build_source_context(prompt: str, source_materials: list[str], *, max_chars: int = 12000) -> str:
    chunks = [normalize_text(material) for material in source_materials if material]
    if not chunks and prompt:
        chunks.append(normalize_text(prompt))
    combined = "\n\n".join(chunk for chunk in chunks if chunk)
    return combined[:max_chars].strip()


def select_relevant_sentences(
    source_context: str,
    keywords: Iterable[str],
    *,
    limit: int = 3,
) -> list[str]:
    sentences = split_into_sentences(source_context, max_sentences=120)
    normalized_keywords = [keyword.casefold() for keyword in keywords if keyword]

    if not sentences:
        return []

    if not normalized_keywords:
        return unique_preserve_order(sentences)[:limit]

    scored: list[tuple[int, int, int, str]] = []
    for sentence in sentences:
        lowered = sentence.casefold()
        score = 0
        keyword_hits = 0
        for index, keyword in enumerate(normalized_keywords):
            if keyword in lowered:
                keyword_hits += 1
                score += max(2, 8 - index)
        score += min(3, len(sentence) // 80)
        scored.append((score, keyword_hits, -len(sentence), sentence))

    scored.sort(reverse=True)
    ranked = [sentence for score, _, _, sentence in scored if score > 0]
    if not ranked:
        ranked = sentences

    return unique_preserve_order(ranked)[:limit]


def extract_focus_terms(text: str, seed_terms: Iterable[str] | None = None, *, limit: int = 5) -> list[str]:
    seed_values = list(seed_terms or [])
    candidates = extract_keywords(text, *seed_values)
    prioritized = unique_preserve_order([*seed_values, *candidates])
    return prioritized[:limit]


def prioritize_phrase_matches(sentences: list[str], phrase: str, *, limit: int) -> list[str]:
    normalized_phrase = normalize_text(phrase).casefold()
    if not normalized_phrase:
        return unique_preserve_order(sentences)[:limit]

    exact_matches = [sentence for sentence in sentences if normalized_phrase in sentence.casefold()]
    remaining = [sentence for sentence in sentences if normalized_phrase not in sentence.casefold()]
    return unique_preserve_order([*exact_matches, *remaining])[:limit]


def replace_first_case_insensitive(text: str, target: str, replacement: str) -> str:
    if not text or not target:
        return text

    pattern = re.compile(re.escape(target), flags=re.IGNORECASE)
    return pattern.sub(replacement, text, count=1)
