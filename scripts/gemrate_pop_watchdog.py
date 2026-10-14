#!/usr/bin/env python3
"""Update KFC Pokémon PSA 10 populations from GemRate's public set report.

One public report load per run. No PSA keys, no auth, no captcha workarounds.
Fail closed: never substitute guessed, stale, or unmatched values.
"""
from __future__ import annotations

import json
import re
import sys
from datetime import datetime, timezone
from pathlib import Path

from playwright.sync_api import TimeoutError as BrowserTimeout, sync_playwright

ROOT = Path(__file__).resolve().parents[1]
DATA_FILE = ROOT / "alpha-web/public/psa-pop-watchdog/populations.json"
REPORT_URL = (
    "https://www.gemrate.com/item-details-advanced?"
    "category=non-sport-cards&grader=psa&set_name=Kfc+Pokemon+Card+Game&year=1998"
)
EXPECTED = {
    "Charizard": "06", "Ivysaur": "02", "Pikachu": "25", "Onix": "95",
    "Scyther": "123", "Snorlax": "143", "Dragonite": "149",
}
# AG Grid's displayed row may include columns beyond gem count. Use only the first
# numeric value immediately AFTER the exact subject + Base + number. Never use
# totals, a similarly named set, or cards from another year.
MAX_REASONABLE_POP_JUMP = 80


def rows_from_dom(page):
    return page.evaluate("""() => {
      const selectors = ['.ag-center-cols-container .ag-row', '.ag-row',
                         '[role="row"]', 'table tbody tr'];
      const results = [];
      const seen = new Set();
      for (const selector of selectors) {
        for (const node of document.querySelectorAll(selector)) {
          const line = (node.innerText || '').replace(/\\s+/g, ' ').trim();
          if (line && !seen.has(line)) {seen.add(line); results.push(line);}
        }
      }
      return results;
    }""")


def extract_counts(rows: list[str]) -> dict[str, int]:
    parsed: dict[str, int] = {}
    for name, cardnum in EXPECTED.items():
        num = int(cardnum)
        pattern = re.compile(
            rf"\\b{re.escape(name)}\\s+(?:Base\\s+)?0*{num}\\b\\s+([0-9]{{1,6}})\\b",
            re.I,
        )
        matches = []
        for row in rows:
            if re.search(r"\\b(?:Total|Average|All Time)\\b", row, re.I) and "Base" not in row:
                continue
            found = pattern.search(row)
            if found:
                matches.append(int(found.group(1).replace(",", "")))
        if matches:
            # Several visible tables may repeat the same record; agreement is required.
            if len(set(matches)) != 1:
                raise ValueError(f"{name}: ambiguous numbers in rows: {matches}")
            parsed[name] = matches[0]
    return parsed


def pull_gemrate() -> tuple[dict[str, int], str]:
    with sync_playwright() as pw:
        browser = pw.chromium.launch(headless=True, args=["--no-sandbox"])
        page = browser.new_page(viewport={"width": 1600, "height": 1200})
        response = page.goto(REPORT_URL, wait_until="domcontentloaded", timeout=60000)
        if response is None or response.status >= 400:
            raise RuntimeError(f"Source returned HTTP {response.status if response else 'unknown'}")
        try:
            page.wait_for_function(
                "() => document.body && /Charizard\\s+Base\\s+0?6/.test(document.body.innerText)"
                " && /Ivysaur\\s+Base\\s+0?2/.test(document.body.innerText)",
                timeout=50000,
            )
        except BrowserTimeout:
            print("Could not find the 1998 KFC card rows in loaded public report.", file=sys.stderr)
            print("Body excerpt:", page.locator("body").inner_text()[:950], file=sys.stderr)
            raise RuntimeError("Public report data did not load") from None
        body = page.locator("body").inner_text()
        date_match = re.search(r"Updated:\\s*(20\\d{2}-\\d{2}-\\d{2})", body)
        if not date_match:
            raise RuntimeError("Could not verify GemRate report date; refusing undated data")
        report_date = date_match.group(1)
        rows = rows_from_dom(page)
        counts = extract_counts(rows)
        if len(counts) != len(EXPECTED):
            print("Matching DOM rows:", file=sys.stderr)
            for row in rows:
                if any(name.lower() in row.lower() for name in EXPECTED):
                    print(repr(row[:400]), file=sys.stderr)
            raise RuntimeError(
                f"Incomplete public set report: {len(counts)}/7 rows. "
                f"Found: {sorted(counts)}. Refusing to guess."
            )
        browser.close()
        return counts, report_date


def main() -> int:
    counts, report_date = pull_gemrate()
    data = json.loads(DATA_FILE.read_text(encoding="utf-8"))
    cards = data["cards"]
    by_name = {c["name"]: c for c in cards}
    if set(by_name) != set(EXPECTED):
        raise ValueError("Watchlist does not exactly match known KFC set")
    # Validate everything first, then apply updates atomically.
    for name, value in counts.items():
        if not isinstance(value, int) or value < 0:
            raise ValueError(f"{name}: invalid PSA 10 count")
        prior = next(
            (p["psa10"] for p in by_name[name].get("history", [])
             if p["date"] == report_date and p.get("source") == "GemRate"),
            None,
        )
        if prior is not None and prior != value:
            print(f"{name}: revised GemRate count for {report_date}: {prior} -> {value}")
        # A large jump might reflect recategorization / mismatched field. Fail closed.
        latest = int(by_name[name].get("latest_psa10", 0))
        if abs(value - latest) > MAX_REASONABLE_POP_JUMP:
            raise ValueError(f"{name}: anomalous change {latest} -> {value}; review source")

    fetched_at = datetime.now(timezone.utc).isoformat(timespec="seconds")
    updated_cards = 0
    for name, count in counts.items():
        card = by_name[name]
        hist = card.setdefault("history", [])
        previously = next((p for p in hist if p["date"] == report_date
                           and p.get("source") == "GemRate"), None)
        if previously is None:
            hist.append({"date": report_date, "psa10": count, "source": "GemRate"})
            updated_cards += 1
        else:
            previously["psa10"] = count
        hist.sort(key=lambda x: (x["date"], x.get("source", "")))
        # GemRate may lag PSA. Never overwrite a newer direct-PSA reading
        # with an older third-party observation.
        latest_date = str(card.get("latest_as_of", ""))
        if report_date >= latest_date:
            card.update({"latest_psa10": count, "latest_as_of": report_date,
                         "source": "GemRate public set report"})
    data["last_scan_at"] = fetched_at
    data["last_scan_source"] = REPORT_URL
    data["last_scan_source_updated"] = report_date
    data["last_scan_status"] = "success"
    data["automatic_refresh_enabled"] = True
    data["updated"] = fetched_at[:10]
    serialized = json.dumps(data, indent=2, ensure_ascii=False) + "\n"
    DATA_FILE.write_text(serialized, encoding="utf-8")
    print(f"Verified all seven GemRate rows, source updated {report_date}. "
          f"{updated_cards} new dated snapshots; fetched {fetched_at}.")
    for name, n in counts.items():
        print(f"{name:10s} #{EXPECTED[name]:>3s}: {n} PSA 10s")
    return 0


if __name__ == "__main__":
    try:
        sys.exit(main())
    except Exception as exc:
        print("No population data changed; source verification failed:", exc, file=sys.stderr)
        sys.exit(1)
