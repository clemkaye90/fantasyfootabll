"""Export the player_news DB to one markdown file per position, ready to
upload into the Lyzr knowledge base for the Week 2 RAG chatbot.

Each news item is rendered as a short standalone paragraph (player, rank,
headline, date, blurb) so it chunks and embeds as one coherent fact.

The DB (see scripts/ingest_player_news.py) is the source of truth; this
script just re-renders corpus/player_news/ from it, so it's safe to delete
and regenerate that folder at any time.

    uv run python scripts/export_player_news_corpus.py
"""

import sqlite3
from pathlib import Path

DB_PATH = Path(__file__).parent.parent / "src" / "nfl_fantasy_app" / "data" / "player_news.db"
OUT_DIR = Path(__file__).parent.parent / "corpus" / "player_news"

POSITIONS = ["QB", "RB", "WR", "TE"]


def main() -> None:
    with sqlite3.connect(DB_PATH) as conn:
        rows = conn.execute(
            "SELECT position, player, team, position_rank, headline, report_date, "
            "blurb, source_url, scraped_date FROM player_news "
            "ORDER BY position, report_date DESC"
        ).fetchall()

    OUT_DIR.mkdir(parents=True, exist_ok=True)
    for existing in OUT_DIR.glob("*.md"):
        existing.unlink()

    by_position: dict[str, list[tuple]] = {p: [] for p in POSITIONS}
    for row in rows:
        by_position[row[0]].append(row)

    for position in POSITIONS:
        position_rows = by_position[position]
        if not position_rows:
            continue
        scraped_date = position_rows[0][8]
        source_url = position_rows[0][7]

        frontmatter = (
            "---\n"
            f"title: {position} Player News\n"
            f"source: FantasyPros Player News\n"
            f"position: {position}\n"
            f"as_of: {scraped_date}\n"
            f"url: {source_url}\n"
            "---\n\n"
        )
        header = (
            f"# {position} Player News (as of {scraped_date})\n\n"
            "This is a snapshot of recent news, filtered to this app's own "
            "top-ranked players at this position. It is highly time-sensitive "
            "-- treat anything not listed here as having no recent news as of "
            "the date above, not as a sign nothing has happened.\n\n"
        )
        paragraphs = []
        for _, player, team, position_rank, headline, report_date, blurb, _, _ in position_rows:
            paragraphs.append(
                f"**{player}** ({team}, {position}{position_rank}) — {headline}. "
                f"{blurb} (Reported {report_date})"
            )

        out_path = OUT_DIR / f"{position.lower()}-player-news.md"
        out_path.write_text(frontmatter + header + "\n\n".join(paragraphs) + "\n", encoding="utf-8")
        print(f"Wrote {out_path.relative_to(OUT_DIR.parent.parent)} ({len(position_rows)} items)")

    print(f"\n{len(rows)} news items across {len(POSITIONS)} files ready in {OUT_DIR} for upload to the Lyzr knowledge base.")


if __name__ == "__main__":
    main()
