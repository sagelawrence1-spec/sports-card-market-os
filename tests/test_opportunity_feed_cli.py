import io
import json
from contextlib import redirect_stderr, redirect_stdout

from opportunity_feed_cli import main


def _feed() -> dict:
    return {
        "schema": "opportunity-radar-feed.v1",
        "publisher": "cli-test",
        "generated_at": "2026-08-17T12:00:00Z",
        "observations": [
            {
                "player_id": "player-1",
                "player": "Prospect One",
                "sport": "baseball",
                "signal_kind": "CALL_UP_WATCH",
                "signal_description": "Club is considering a near-term promotion.",
                "observed_at": "2026-08-17T11:00:00Z",
                "headline": "Promotion watch",
                "why_now": "Rotation opening plus public club comments.",
                "thesis": "Attention can move before the formal transaction.",
                "falsification": ["Player remains in the minors after the roster need resolves."],
                "source_urls": ["https://example.com/source"],
                "cards": [{"card_id": "card-1", "label": "2025 Bowman Chrome Prospect Auto"}],
                "market_price_verified": False,
            }
        ],
    }


def test_cli_reads_file_and_writes_scan(tmp_path):
    input_path = tmp_path / "feed.json"
    output_path = tmp_path / "scan.json"
    input_path.write_text(json.dumps(_feed()), encoding="utf-8")

    assert main([str(input_path), "--output", str(output_path)]) == 0
    artifact = json.loads(output_path.read_text(encoding="utf-8"))
    assert artifact["schema"] == "opportunity-radar-scan.v1"
    assert artifact["feed"]["publisher"] == "cli-test"
    assert artifact["summary"]["candidate_count"] == 1
    assert artifact["candidates"][0]["decision"] == "WATCH_FOR_COMPS"


def test_cli_supports_stdin_stdout(monkeypatch):
    monkeypatch.setattr("sys.stdin", io.StringIO(json.dumps(_feed())))
    output = io.StringIO()
    with redirect_stdout(output):
        assert main(["-"]) == 0
    artifact = json.loads(output.getvalue())
    assert artifact["schema"] == "opportunity-radar-scan.v1"


def test_cli_fails_closed_on_invalid_feed(tmp_path):
    input_path = tmp_path / "feed.json"
    input_path.write_text(json.dumps({"schema": "wrong"}), encoding="utf-8")
    error = io.StringIO()
    with redirect_stderr(error):
        assert main([str(input_path)]) == 2
    assert "unsupported Opportunity Radar feed schema" in error.getvalue()


def test_cli_rejects_non_object_json(tmp_path):
    input_path = tmp_path / "feed.json"
    input_path.write_text("[]", encoding="utf-8")
    error = io.StringIO()
    with redirect_stderr(error):
        assert main([str(input_path)]) == 2
    assert "feed JSON must be an object" in error.getvalue()
