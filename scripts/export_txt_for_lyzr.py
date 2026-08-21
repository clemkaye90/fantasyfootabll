"""Mirror corpus/ into corpus_txt/ with a .txt extension on every file.

Lyzr's uploader only accepts PDF, DOCX, and TXT -- the corpus scripts write
markdown, which is already plain text, so this is a straight copy with a
renamed extension rather than a real format conversion. Re-run this after
any of the export_*_corpus.py scripts (see the refresh loop in the Lyzr
build plan) so corpus_txt/ stays in sync with corpus/:

    uv run python scripts/export_txt_for_lyzr.py
"""

import shutil
from pathlib import Path

SRC_DIR = Path(__file__).parent.parent / "corpus"
OUT_DIR = Path(__file__).parent.parent / "corpus_txt"


def main() -> None:
    if OUT_DIR.exists():
        shutil.rmtree(OUT_DIR)

    count = 0
    for md_path in sorted(SRC_DIR.rglob("*.md")):
        rel = md_path.relative_to(SRC_DIR).with_suffix(".txt")
        out_path = OUT_DIR / rel
        out_path.parent.mkdir(parents=True, exist_ok=True)
        out_path.write_text(md_path.read_text(encoding="utf-8"), encoding="utf-8")
        count += 1

    print(f"Wrote {count} .txt files to {OUT_DIR}, ready to upload to Lyzr.")


if __name__ == "__main__":
    main()
