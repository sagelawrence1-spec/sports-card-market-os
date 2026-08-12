"""CLI entry point for Opportunity Engine Spark and Radar inspection."""

from __future__ import annotations

import argparse
import json

from opportunity_contract import build_opportunity_radar
from opportunity_engine import OpportunityEngine, OpportunityStore, OpportunityType, SignalType


def main() -> None:
    parser = argparse.ArgumentParser(description="Sports Card Market OS Opportunity Engine")
    parser.add_argument("--db", default="opportunity.sqlite")
    sub = parser.add_subparsers(dest="command", required=True)

    spark = sub.add_parser("spark", help="Journal a user-observed pre-consensus signal")
    spark.add_argument("player")
    spark.add_argument("--sport", required=True)
    spark.add_argument("--observation", required=True)
    spark.add_argument("--signal-type", choices=[x.value for x in SignalType], default="USER_SPARK")
    spark.add_argument("--type", choices=[x.value for x in OpportunityType], default=None)
    spark.add_argument("--market-repricing-pct", type=float, default=0.0)

    sub.add_parser("radar", help="Print active Opportunity Radar JSON")

    show = sub.add_parser("show", help="Print one thesis plus its ledger and signals")
    show.add_argument("thesis_id")

    args = parser.parse_args()
    store = OpportunityStore(args.db)
    engine = OpportunityEngine(store)

    if args.command == "spark":
        thesis = engine.spark(
            player=args.player,
            sport=args.sport,
            observation=args.observation,
            signal_type=SignalType(args.signal_type),
            opportunity_type=OpportunityType(args.type) if args.type else None,
            market_repricing_pct=args.market_repricing_pct,
        )
        print(json.dumps(thesis.to_dict(), indent=2, sort_keys=True))
        return

    if args.command == "radar":
        print(json.dumps(build_opportunity_radar(store.list_theses()), indent=2, sort_keys=True))
        return

    thesis = store.get_thesis(args.thesis_id)
    if thesis is None:
        raise SystemExit(f"Unknown thesis_id: {args.thesis_id}")
    print(
        json.dumps(
            {
                "thesis": thesis.to_dict(),
                "signals": store.signals(args.thesis_id),
                "ledger": store.ledger(args.thesis_id),
            },
            indent=2,
            sort_keys=True,
        )
    )


if __name__ == "__main__":
    main()
