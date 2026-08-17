import io
import json
from contextlib import redirect_stderr, redirect_stdout

from opportunity_feed_cli import main


def _feed(*, generated_at: str = "2026-08-17T12:00:00Z", verified: bool = False) -> dict:
    observation = {
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
        "market_price_verified": verified,
    }
    if verified:
        observation["market_repricing_pct"] = 8.0
    return {
        "schema": "opportunity-radar-feed.v1",
        "publisher": "cli-test",
        "generated_at": generated_at,
        "observations": [observation],
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


def test_cli_writes_scan_delta_against_previous_scan(tmp_path):
    previous_feed_path = tmp_path / "previous-feed.json"
    previous_scan_path = tmp_path / "previous-scan.json"
    current_feed_path = tmp_path / "current-feed.json"
    current_scan_path = tmp_path / "current-scan.json"
    delta_path = tmp_path / "delta.json"

    previous_feed_path.write_text(json.dumps(_feed(generated_at="2026-08-17T12:00:00Z")), encoding="utf-8")
    assert main([str(previous_feed_path), "--output", str(previous_scan_path)]) == 0

    current_feed_path.write_text(json.dumps(_feed(generated_at="2026-08-17T13:00:00Z", verified=True)), encoding="utf-8")
    assert main([
        str(current_feed_path),
        "--output",
        str(current_scan_path),
        "--previous-scan",
        str(previous_scan_path),
        "--delta-output",
        str(delta_path),
    ]) == 0

    delta = json.loads(delta_path.read_text(encoding="utf-8"))
    assert delta["schema"] == "opportunity-radar-delta.v1"
    assert delta["summary"]["changed_count"] == 1
    assert delta["summary"]["attention_count"] == 1
    assert "REPRICING_VERIFIED" in delta["movements"][0]["changes"]


def test_cli_writes_attention_brief_for_changed_opportunity(tmp_path):
    previous_feed_path = tmp_path / "previous-feed.json"
    previous_scan_path = tmp_path / "previous-scan.json"
    current_feed_path = tmp_path / "current-feed.json"
    current_scan_path = tmp_path / "current-scan.json"
    delta_path = tmp_path / "delta.json"
    attention_path = tmp_path / "attention.json"

    previous_feed_path.write_text(json.dumps(_feed(generated_at="2026-08-17T12:00:00Z")), encoding="utf-8")
    assert main([str(previous_feed_path), "--output", str(previous_scan_path)]) == 0
    current_feed_path.write_text(json.dumps(_feed(generated_at="2026-08-17T13:00:00Z", verified=True)), encoding="utf-8")

    assert main([
        str(current_feed_path),
        "--output", str(current_scan_path),
        "--previous-scan", str(previous_scan_path),
        "--delta-output", str(delta_path),
        "--attention-output", str(attention_path),
    ]) == 0
    attention = json.loads(attention_path.read_text(encoding="utf-8"))
    assert attention["schema"] == "opportunity-radar-attention.v1"
    assert attention["summary"]["attention_count"] == 1
    assert attention["items"][0]["player_id"] == "player-1"
    assert "REPRICING_VERIFIED" in attention["items"][0]["changes"]


def test_cli_requires_previous_scan_and_delta_output_together(tmp_path):
    input_path = tmp_path / "feed.json"
    input_path.write_text(json.dumps(_feed()), encoding="utf-8")
    error = io.StringIO()
    with redirect_stderr(error):
        assert main([str(input_path), "--previous-scan", "missing.json"]) == 2
    assert "--previous-scan and --delta-output must be supplied together" in error.getvalue()


def test_cli_rejects_attention_output_without_previous_scan(tmp_path):
    input_path = tmp_path / "feed.json"
    input_path.write_text(json.dumps(_feed()), encoding="utf-8")
    error = io.StringIO()
    with redirect_stderr(error):
        assert main([str(input_path), "--attention-output", str(tmp_path / "attention.json")]) == 2
    assert "--attention-output requires --previous-scan" in error.getvalue()


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
