"""Export the injury_reports DB to one markdown file per position, ready to
upload into the Lyzr knowledge base for the Week 2 RAG chatbot.

Each player's row is rendered as a short standalone paragraph (not a table
row) so it chunks and embeds as one coherent, retrievable fact rather than
losing its column headers when a table gets split mid-chunk.

The DB (see scripts/ingest_injury_reports.py) is the source of truth; this
script just re-renders corpus/injury_reports/ from it, so it's safe to
delete and regenerate that folder at any time.

    uv run python scripts/export_injury_reports_corpus.py
"""

import sqlite3
from pathlib import Path

DB_PATH = Path(__file__).parent.parent / "src" / "nfl_fantasy_app" / "data" / "injury_reports.db"
OUT_DIR = Path(__file__).parent.parent / "corpus" / "injury_reports"

POSITIONS = ["QB", "RB", "WR", "TE"]


def main() -> None:
    with sqlite3.connect(DB_PATH) as conn:
        rows = conn.execute(
            "SELECT position, player, team, injury, status, report_date, "
            "fantasy_impact, source_url, scraped_date FROM injury_reports "
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
            f"title: {position} Injury Report\n"
            f"source: FantasyPros Injury News\n"
            f"position: {position}\n"
            f"as_of: {scraped_date}\n"
            f"url: {source_url}\n"
            "---\n\n"
        )
        header = (
            f"# {position} Injury Report (as of {scraped_date})\n\n"
            "This report is time-sensitive. Treat any player not listed here "
            "as having no known injury concern as of the date above, and note "
            "that status can change day to day during camp and week to week "
            "during the season.\n\n"
        )
        paragraphs = []
        for _, player, team, injury, status, report_date, fantasy_impact, _, _ in position_rows:
            paragraphs.append(
                f"**{player}** ({team}, {position}) — Status: {status}. "
                f"Injury: {injury}. Fantasy impact: {fantasy_impact}. "
                f"(Updated {report_date})"
            )

        out_path = OUT_DIR / f"{position.lower()}-injury-report.md"
        out_path.write_text(frontmatter + header + "\n\n".join(paragraphs) + "\n", encoding="utf-8")
        print(f"Wrote {out_path.relative_to(OUT_DIR.parent.parent)} ({len(position_rows)} players)")

    print(f"\n{len(rows)} players across {len(POSITIONS)} files ready in {OUT_DIR} for upload to the Lyzr knowledge base.")


if __name__ == "__main__":
    main()
