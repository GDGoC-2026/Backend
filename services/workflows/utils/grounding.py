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


def _spread_indices(total: int, target: int) -> list[int]:
    if total <= 0 or target <= 0:
        return []
    if target >= total:
        return list(range(total))
    if target == 1:
        return [total // 2]

    step = (total - 1) / (target - 1)
    indices = {int(round(i * step)) for i in range(target)}
    indices.add(0)
    indices.add(total - 1)
    return sorted(indices)


def _token_set(text: str) -> set[str]:
    return {
        token.casefold()
        for token in re.findall(r"[A-Za-z0-9]{3,}", text or "")
        if token.casefold() not in STOPWORDS
    }


def _jaccard_similarity(left: set[str], right: set[str]) -> float:
    if not left or not right:
        return 0.0
    union = left | right
    if not union:
        return 0.0
    return len(left & right) / len(union)


def extract_keywords(*parts: str) -> list[str]:
    words: list[str] = []

    for part in parts:
        for word in re.findall(r"[A-Za-z][A-Za-z0-9_/+-]{2,}", part or ""):
            lowered = word.casefold()
            if lowered in STOPWORDS:
                continue
            words.append(word)

    return unique_preserve_order(words)


def chunk_source_material(
    text: str,
    *,
    chunk_size: int = 2400,
    overlap: int = 240,
    max_chunks: int | None = 220,
) -> list[str]:
    normalized = normalize_text(text)
    if not normalized:
        return []

    safe_chunk_size = max(400, chunk_size)
    safe_overlap = max(0, min(overlap, safe_chunk_size // 2))
    step = max(1, safe_chunk_size - safe_overlap)

    chunks: list[str] = []
    start = 0
    total_len = len(normalized)

    while start < total_len:
        end = min(total_len, start + safe_chunk_size)

        if end < total_len:
            soft_break_start = start + int(safe_chunk_size * 0.65)
            whitespace_break = normalized.rfind(" ", soft_break_start, end)
            if whitespace_break > start:
                end = whitespace_break

        chunk = normalized[start:end].strip()
        if chunk:
            chunks.append(chunk)

        if end >= total_len:
            break

        next_start = max(start + step, end - safe_overlap)
        if next_start <= start:
            next_start = start + step
        start = next_start

    chunks = unique_preserve_order(chunks)

    if max_chunks is not None and len(chunks) > max_chunks:
        selected_indices = _spread_indices(len(chunks), max_chunks)
        chunks = [chunks[index] for index in selected_indices]

    return chunks


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


def build_source_context(prompt: str, source_materials: list[str], *, max_chars: int = 42000) -> str:
    prompt_text = normalize_text(prompt)

    material_chunks: list[str] = []
    for material in source_materials:
        if not material:
            continue
        material_chunks.extend(
            chunk_source_material(
                material,
                chunk_size=2400,
                overlap=240,
                max_chunks=220,
            )
        )

    chunks = unique_preserve_order(material_chunks)
    if not chunks and prompt_text:
        chunks = [prompt_text]

    if not chunks:
        return ""

    combined = "\n\n".join(chunks).strip()
    if len(combined) <= max_chars:
        return combined

    keywords = extract_keywords(prompt_text)
    scored_chunks: list[tuple[int, int, int, str]] = []

    for index, chunk in enumerate(chunks):
        lowered_chunk = chunk.casefold()
        score = 0
        keyword_hits = 0

        for priority, keyword in enumerate(keywords):
            lowered_keyword = keyword.casefold()
            if lowered_keyword in lowered_chunk:
                keyword_hits += 1
                score += max(2, 10 - priority)

        score += min(4, len(chunk) // 450)
        scored_chunks.append((score, keyword_hits, -index, chunk))

    scored_chunks.sort(reverse=True)

    selected: list[str] = []
    selected_set: set[str] = set()
    remaining = max_chars
    prioritized_budget = int(max_chars * 0.7)
    prioritized_used = 0

    for score, _, _, chunk in scored_chunks:
        if score <= 0:
            break

        chunk_cost = len(chunk) + 2
        if chunk_cost > remaining:
            continue
        if prioritized_used + chunk_cost > prioritized_budget:
            continue

        selected.append(chunk)
        selected_set.add(chunk.casefold())
        remaining -= chunk_cost
        prioritized_used += chunk_cost

        if remaining <= 0:
            break

    if remaining > 0:
        remaining_chunks = [chunk for chunk in chunks if chunk.casefold() not in selected_set]
        coverage_target = min(len(remaining_chunks), 48)

        for index in _spread_indices(len(remaining_chunks), coverage_target):
            chunk = remaining_chunks[index]
            chunk_cost = len(chunk) + 2
            if chunk_cost > remaining:
                continue
            selected.append(chunk)
            remaining -= chunk_cost
            if remaining <= 0:
                break

    if prompt_text and prompt_text.casefold() not in "\n\n".join(selected).casefold():
        prompt_excerpt = prompt_text[: min(800, max_chars // 8)]
        if prompt_excerpt:
            selected.insert(0, prompt_excerpt)

    return "\n\n".join(unique_preserve_order(selected))[:max_chars].strip()


def select_relevant_sentences(
    source_context: str,
    keywords: Iterable[str],
    *,
    limit: int = 3,
) -> list[str]:
    sentences = split_into_sentences(source_context)
    normalized_keywords = [keyword.casefold() for keyword in keywords if keyword]

    if not sentences:
        return []

    max_scan = max(300, limit * 70)
    if len(sentences) > max_scan:
        sampled_indices = _spread_indices(len(sentences), max_scan)
        sentences = [sentences[index] for index in sampled_indices]

    if not normalized_keywords:
        ranked = unique_preserve_order(sentences)
        selected: list[str] = []
        selected_tokens: list[set[str]] = []
        for sentence in ranked:
            tokens = _token_set(sentence)
            if any(_jaccard_similarity(tokens, existing) >= 0.86 for existing in selected_tokens):
                continue
            selected.append(sentence)
            selected_tokens.append(tokens)
            if len(selected) >= limit:
                break
        return selected[:limit]

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

    selected: list[str] = []
    selected_tokens: list[set[str]] = []

    for sentence in unique_preserve_order(ranked):
        tokens = _token_set(sentence)

        if any(_jaccard_similarity(tokens, existing) >= 0.84 for existing in selected_tokens):
            continue

        selected.append(sentence)
        selected_tokens.append(tokens)

        if len(selected) >= limit:
            break

    return selected[:limit]


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
