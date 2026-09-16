"""One-time setup helper: turns a downloaded Google service-account JSON
key into the [connections.gsheets] block .streamlit/secrets.toml needs for
the Picks tab (see data/picks.py). Run this locally instead of pasting the
key anywhere -- it only ever reads the JSON file from disk and writes to
your own gitignored secrets.toml, nothing is sent anywhere else.

    uv run python scripts/write_gsheets_secret.py path/to/key.json "https://docs.google.com/spreadsheets/d/.../edit"
"""

import json
import sys
from pathlib import Path

SECRETS_PATH = Path(__file__).parent.parent / ".streamlit" / "secrets.toml"

REQUIRED_FIELDS = [
    "project_id", "private_key_id", "private_key", "client_email",
    "client_id", "auth_uri", "token_uri", "auth_provider_x509_cert_url",
    "client_x509_cert_url",
]


def _toml_escape(value: str) -> str:
    """Escape a value for a single-line TOML basic string -- the service
    account's private_key contains real newlines once JSON-decoded, which
    a one-line TOML string can't hold directly, so they're re-escaped to
    literal backslash-n instead (TOML unescapes them back to real newlines
    when the secrets file is parsed, same as the JSON did)."""
    return value.replace("\\", "\\\\").replace("\n", "\\n").replace('"', '\\"')


def build_block(key_data: dict, spreadsheet_url: str) -> str:
    lines = ["[connections.gsheets]", f'spreadsheet = "{_toml_escape(spreadsheet_url)}"', 'type = "service_account"']
    lines += [f'{field} = "{_toml_escape(key_data[field])}"' for field in REQUIRED_FIELDS]
    return "\n".join(lines) + "\n"


def _without_existing_gsheets_block(secrets_text: str) -> str:
    """Drop a prior [connections.gsheets] section (if this script has been
    run before) so re-running it replaces rather than duplicates it."""
    if "[connections.gsheets]" not in secrets_text:
        return secrets_text
    before, _, after = secrets_text.partition("[connections.gsheets]")
    _, _, next_section = after.partition("\n[")
    tail = ("\n[" + next_section) if next_section else ""
    return before.rstrip() + tail


def main() -> None:
    if len(sys.argv) != 3:
        print('Usage: uv run python scripts/write_gsheets_secret.py path/to/key.json "<spreadsheet_url>"')
        sys.exit(1)

    key_path, spreadsheet_url = Path(sys.argv[1]), sys.argv[2]
    if not key_path.exists():
        print(f"No such file: {key_path}")
        sys.exit(1)

    key_data = json.loads(key_path.read_text())
    missing = [f for f in REQUIRED_FIELDS if f not in key_data]
    if missing:
        print(f"That JSON file is missing expected fields: {missing} -- is it the right service account key?")
        sys.exit(1)

    block = build_block(key_data, spreadsheet_url)
    existing = _without_existing_gsheets_block(SECRETS_PATH.read_text()) if SECRETS_PATH.exists() else ""
    separator = "\n\n" if existing.strip() else ""
    SECRETS_PATH.parent.mkdir(parents=True, exist_ok=True)
    SECRETS_PATH.write_text(existing.rstrip() + separator + block if existing.strip() else block)

    print(f"Wrote [connections.gsheets] to {SECRETS_PATH}")
    print("Nothing from the key file was sent anywhere else -- only your local, gitignored secrets.toml was touched.")
    print("Remember: Streamlit Cloud needs this same block pasted into the app's Settings -> Secrets separately.")


if __name__ == "__main__":
    main()
