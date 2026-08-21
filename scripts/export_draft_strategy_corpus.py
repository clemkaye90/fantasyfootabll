"""Export the draft_strategy_articles DB to one markdown file per article,
ready to upload into the Lyzr knowledge base for the Week 2 RAG chatbot.

The DB (see scripts/ingest_draft_strategy_articles.py) is the source of
truth; this script just re-renders corpus/draft_strategy/ from it, so it's
safe to delete and regenerate that folder at any time.

    uv run python scripts/export_draft_strategy_corpus.py
"""

import re
import sqlite3
from pathlib import Path

DB_PATH = Path(__file__).parent.parent / "src" / "nfl_fantasy_app" / "data" / "draft_strategy_articles.db"
OUT_DIR = Path(__file__).parent.parent / "corpus" / "draft_strategy"


def slugify(title: str) -> str:
    slug = re.sub(r"[^a-z0-9]+", "-", title.lower()).strip("-")
    return slug[:80]


def main() -> None:
    with sqlite3.connect(DB_PATH) as conn:
        rows = conn.execute(
            "SELECT source, url, title, author, published_date, topic_tags, content "
            "FROM draft_strategy_articles ORDER BY id"
        ).fetchall()

    OUT_DIR.mkdir(parents=True, exist_ok=True)
    for existing in OUT_DIR.glob("*.md"):
        existing.unlink()

    for source, url, title, author, published_date, topic_tags, content in rows:
        frontmatter = (
            "---\n"
            f"title: {title}\n"
            f"source: {source}\n"
            f"author: {author}\n"
            f"published_date: {published_date}\n"
            f"url: {url}\n"
            f"topic_tags: {topic_tags}\n"
            "---\n\n"
        )
        body = f"# {title}\n\n{content}\n"
        out_path = OUT_DIR / f"{slugify(source)}-{slugify(title)}.md"
        out_path.write_text(frontmatter + body, encoding="utf-8")
        print(f"Wrote {out_path.relative_to(OUT_DIR.parent.parent)}")

    print(f"\n{len(rows)} files ready in {OUT_DIR} for upload to the Lyzr knowledge base.")


if __name__ == "__main__":
    main()
