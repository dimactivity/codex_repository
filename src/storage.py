from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path


@dataclass
class SearchResult:
    path: Path
    score: int
    snippet: str


class MarkdownStorage:
    def __init__(self, root: str) -> None:
        self.root = Path(root)
        self.inbox = self.root / "inbox"
        self.entities = self.root / "entities"
        self.reviews = self.root / "reviews"
        self.logs = self.root / "logs"
        self.operations_log = self.logs / "operations.md"

        for folder in [self.inbox, self.entities, self.reviews, self.logs]:
            folder.mkdir(parents=True, exist_ok=True)
        if not self.operations_log.exists():
            self.operations_log.write_text("# Operations Log\n\n", encoding="utf-8")

    def save_capture(self, content: str, source: str, user_id: int) -> Path:
        ts = datetime.now(timezone.utc)
        filename = f"{ts.strftime('%Y%m%d_%H%M%S')}_{user_id}.md"
        path = self.inbox / filename
        body = (
            f"# Capture\n\n"
            f"- created_at_utc: {ts.isoformat()}\n"
            f"- source: {source}\n"
            f"- user_id: {user_id}\n\n"
            f"## Content\n\n{content.strip()}\n"
        )
        path.write_text(body, encoding="utf-8")
        self.log_operation(f"save_capture: {path}")
        return path

    def create_review(self, period: str, user_id: int) -> Path:
        ts = datetime.now(timezone.utc)
        filename = f"{period}_{ts.strftime('%Y%m%d')}_{user_id}.md"
        path = self.reviews / filename
        template = (
            f"# {period.title()} Review\n\n"
            f"- date_utc: {ts.isoformat()}\n"
            f"- user_id: {user_id}\n\n"
            "## Wins\n- \n\n"
            "## Problems\n- \n\n"
            "## Next Actions\n- \n"
        )
        path.write_text(template, encoding="utf-8")
        self.log_operation(f"create_review: {path}")
        return path

    def search(self, query: str, limit: int = 5) -> list[SearchResult]:
        terms = [t for t in re.split(r"\W+", query.lower()) if t]
        results: list[SearchResult] = []
        for path in self.root.rglob("*.md"):
            if path == self.operations_log:
                continue
            txt = path.read_text(encoding="utf-8", errors="ignore")
            low = txt.lower()
            score = sum(low.count(term) for term in terms)
            if score > 0:
                idx = low.find(terms[0]) if terms else 0
                start = max(0, idx - 120)
                end = min(len(txt), idx + 180)
                snippet = txt[start:end].replace("\n", " ")
                results.append(SearchResult(path=path, score=score, snippet=snippet))

        results.sort(key=lambda r: r.score, reverse=True)
        self.log_operation(f"search: query='{query}' results={len(results[:limit])}")
        return results[:limit]

    def log_operation(self, entry: str) -> None:
        ts = datetime.now(timezone.utc).isoformat()
        with self.operations_log.open("a", encoding="utf-8") as f:
            f.write(f"- {ts} | {entry}\n")
