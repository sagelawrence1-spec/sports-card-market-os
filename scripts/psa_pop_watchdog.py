#!/usr/bin/env python3
"""Daily PSA population monitor using PSA's documented, token-authenticated API.

No scraping. Requires GitHub Actions secret PSA_API_TOKEN.
API routes: /cert/GetByCertNumber/{cert} and /pop/GetPSASpecPopulation/{spec_id}.
"""
from __future__ import annotations

import json
import os
import re
import sys
import urllib.error
import urllib.request
from datetime import datetime, timezone
from pathlib import Path
from zoneinfo import ZoneInfo

DATA_PATH = Path(__file__).resolve().parents[1] / "alpha-web/public/psa-pop-watchdog/populations.json"
BASE = "https://api.psacard.com/publicapi"
TOKEN = os.environ.get("PSA_API_TOKEN", "").strip()


def request_json(path: str) -> dict:
    req = urllib.request.Request(
        BASE + path,
        headers={"Authorization": "bearer " + TOKEN, "Accept": "application/json",
                 "User-Agent": "PersonalPSAPopWatchdog/1.0"},
    )
    try:
        with urllib.request.urlopen(req, timeout=25) as response:
            payload = json.load(response)
    except urllib.error.HTTPError as exc:
        raise ValueError(f"PSA API HTTP {exc.code} for {path}") from None
    except (urllib.error.URLError, TimeoutError) as exc:
        raise ValueError(f"PSA API connection failed for {path}: {type(exc).__name__}") from None
    if not isinstance(payload, dict):
        raise ValueError("PSA API response was not a JSON object")
    if payload.get("IsValidRequest") is False:
        raise ValueError("PSA API rejected cert: " + str(payload.get("ServerMessage")))
    return payload


def normalized(s: object) -> str:
    return re.sub(r"[^A-Z0-9]", "", str(s or "").upper())


def cert_from_card(card: dict) -> str:
    cert = card.get("cert") or card.get("psa_url", "")
    match = re.search(r"(\d{8,11})", str(cert))
    if not match:
        raise ValueError("No usable PSA certification number on card")
    return match.group(1)


def validated_spec_id(card: dict) -> int:
    cert = cert_from_card(card)
    data = request_json(f"/cert/GetByCertNumber/{cert}")
    record = data.get("PSACert")
    if not isinstance(record, dict):
        raise ValueError("Cert lookup returned no PSACert data")
    if str(record.get("Year", "")).strip() != "1998":
        raise ValueError("Year did not match 1998")
    brand = normalized(record.get("Brand", ""))
    if "KFC" not in brand or "POKEMON" not in brand:
        raise ValueError("Cert was not identified as a KFC Pokemon card")
    if normalized(record.get("Subject")) != normalized(card.get("name")):
        raise ValueError("Cert subject mismatch")
    actual = re.sub(r"\D", "", str(record.get("CardNumber", "")))
    expected = re.sub(r"\D", "", str(card.get("number", "")))
    if not actual or not expected or int(actual) != int(expected):
        raise ValueError("Cert card number mismatch")
    spec_id = record.get("SpecID")
    if not isinstance(spec_id, int) or spec_id <= 0:
        raise ValueError("Cert API did not return a valid SpecID")
    return spec_id


def psa_ten_for_spec(spec_id: int) -> int:
    data = request_json(f"/pop/GetPSASpecPopulation/{spec_id}")
    if data.get("SpecID") not in (spec_id, str(spec_id)):
        raise ValueError("Population SpecID did not match cert SpecID")
    pop = data.get("PSAPop")
    if not isinstance(pop, dict):
        raise ValueError("Population endpoint returned no PSAPop")
    count = pop.get("Grade10")
    if isinstance(count, bool) or not isinstance(count, int) or count < 0:
        raise ValueError("Population endpoint did not return a valid Grade10 count")
    return count


def main() -> int:
    if not TOKEN:
        print("NOT CONFIGURED: add PSA_API_TOKEN to GitHub Actions secrets; no data changed.")
        return 0
    data = json.loads(DATA_PATH.read_text(encoding="utf-8"))
    cards = data.get("cards")
    if not isinstance(cards, list) or not cards:
        raise ValueError("No configured cards")
    now = datetime.now(timezone.utc)
    today = now.astimezone(ZoneInfo("America/Phoenix")).date().isoformat()
    errors: dict[str, str] = {}
    successes = 0
    for card in cards:
        name = str(card.get("name", "(unnamed)"))
        try:
            spec_id = validated_spec_id(card)
            count = psa_ten_for_spec(spec_id)
            history = card.setdefault("history", [])
            if not isinstance(history, list):
                raise ValueError("Card history was not a list")
            reading = {"date": today, "psa10": count, "source": "PSA official API",
                       "spec_id": spec_id}
            history[:] = [h for h in history if h.get("date") != today]
            history.append(reading)
            history.sort(key=lambda h: h["date"])
            card["latest_psa10"] = count
            card["latest_as_of"] = today
            card["source"] = "PSA official API"
            card["spec_id"] = spec_id
            card["last_success_at"] = now.isoformat(timespec="seconds")
            successes += 1
            print(f"{name} #{card.get('number')}: PSA 10 population {count} (spec {spec_id})")
        except (ValueError, TypeError, KeyError, json.JSONDecodeError) as exc:
            errors[name] = str(exc)
            print(f"FAILED {name}: {exc}", file=sys.stderr)
    if not successes:
        print("All lookups failed; keeping historical data unchanged.", file=sys.stderr)
        return 1
    data["updated"] = today
    data["last_scan_at"] = now.isoformat(timespec="seconds")
    data["last_scan_successful_cards"] = successes
    data["last_scan_total_cards"] = len(cards)
    data["last_scan_errors"] = errors
    data["automatic_refresh_enabled"] = True
    DATA_PATH.write_text(json.dumps(data, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    print(f"Saved {successes}/{len(cards)} validated readings for {today}.")
    return 0 if not errors else 1


if __name__ == "__main__":
    sys.exit(main())
