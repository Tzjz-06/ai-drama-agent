"""Deterministic context compression using a forgetting-curve budget."""

from __future__ import annotations

import math
import re
from dataclasses import dataclass


@dataclass(frozen=True)
class CompressionResult:
    text: str
    original_chars: int
    compressed_chars: int
    retained_ratio: float
    compressed: bool
    selected_blocks: int
    total_blocks: int


class ForgettingCurveCompressor:
    """Keep a bounded, ordered subset of context blocks.

    Older blocks receive an exponentially smaller retention score. Query-term
    overlap acts as a relevance signal, approximating a rate-distortion budget
    without requiring a tokenizer or a second model call.
    """

    def __init__(
        self,
        max_chars: int = 12000,
        floor_ratio: float = 0.2,
        decay: float = 2.2,
    ) -> None:
        if max_chars < 256:
            raise ValueError("max_chars 必须至少为 256。")
        self.max_chars = max_chars
        self.floor_ratio = max(0.0, min(1.0, floor_ratio))
        self.decay = max(0.01, decay)

    def compress(self, text: str, query: str = "") -> CompressionResult:
        source = text.strip()
        original_chars = len(source)
        if original_chars <= self.max_chars:
            return CompressionResult(
                text=source,
                original_chars=original_chars,
                compressed_chars=original_chars,
                retained_ratio=1.0 if original_chars else 0.0,
                compressed=False,
                selected_blocks=len(_split_blocks(source)),
                total_blocks=len(_split_blocks(source)),
            )

        blocks = _split_blocks(source)
        if len(blocks) < 2:
            compact = _head_tail(source, self.max_chars)
            return CompressionResult(
                text=compact,
                original_chars=original_chars,
                compressed_chars=len(compact),
                retained_ratio=len(compact) / original_chars,
                compressed=True,
                selected_blocks=1,
                total_blocks=1,
            )

        query_terms = _terms(query)
        last_index = len(blocks) - 1
        scored: list[tuple[float, int, str]] = []
        for index, block in enumerate(blocks):
            distance = (last_index - index) / max(1, last_index)
            retention = self.floor_ratio + (1.0 - self.floor_ratio) * math.exp(
                -self.decay * distance
            )
            relevance = _relevance(block, query_terms)
            score = 0.7 * retention + 0.3 * relevance
            scored.append((score, index, block))

        # The first block anchors the subject; the last block preserves the
        # current state. Fill the remaining budget by descending score, then
        # restore source order so the model sees a coherent timeline.
        selected: set[int] = {0, last_index}
        used = sum(len(blocks[index]) for index in selected)
        for _, index, block in sorted(scored, reverse=True):
            if index in selected:
                continue
            if used + len(block) > self.max_chars:
                continue
            selected.add(index)
            used += len(block)

        ordered_indexes = sorted(selected)
        parts: list[str] = []
        previous_index = -1
        for index in ordered_indexes:
            if previous_index >= 0 and index > previous_index + 1:
                parts.append("[中间上下文已按遗忘曲线压缩]")
            parts.append(blocks[index])
            previous_index = index
        compact = "\n\n".join(parts)
        if len(compact) > self.max_chars:
            compact = _head_tail(compact, self.max_chars)
        return CompressionResult(
            text=compact,
            original_chars=original_chars,
            compressed_chars=len(compact),
            retained_ratio=len(compact) / original_chars,
            compressed=True,
            selected_blocks=len(selected),
            total_blocks=len(blocks),
        )


def _split_blocks(text: str) -> list[str]:
    paragraphs = [block.strip() for block in re.split(r"\n\s*\n+", text) if block.strip()]
    if len(paragraphs) > 1 or "\n" not in text:
        return paragraphs
    return [line.strip() for line in text.splitlines() if line.strip()]


def _terms(text: str) -> set[str]:
    terms: set[str] = set()
    for run in re.findall(r"[\u4e00-\u9fff]{2,}", text.lower()):
        terms.add(run)
        terms.update(run[index : index + 2] for index in range(len(run) - 1))
    terms.update(re.findall(r"[A-Za-z0-9_]{3,}", text.lower()))
    return terms


def _relevance(block: str, query_terms: set[str]) -> float:
    if not query_terms:
        return 0.5
    block_terms = _terms(block)
    return min(1.0, len(block_terms & query_terms) / max(1, min(8, len(query_terms))))


def _head_tail(text: str, limit: int) -> str:
    if len(text) <= limit:
        return text
    head = max(64, int(limit * 0.58))
    tail = max(64, limit - head - 40)
    return f"{text[:head].rstrip()}\n\n[较早上下文已按遗忘曲线压缩]\n\n{text[-tail:].lstrip()}"
