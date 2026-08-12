"""Command-line entry point for the scheduled Market OS evidence run."""

from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
import tempfile

from evidence_store import EvidenceStore
from market_pipeline import ScheduledMarketPipeline
from providers.ebay_auth import EbayOAuthClient
from providers.ebay_browse import EbayBrowseProvider
from providers.ebay_marketplace_insights import EbayMarketplaceInsightsProvider
from providers.sold_comps import SoldCompsProvider
from providers.the_card_api import TheCardApiSoldProvider


PAID_CARD_API_PLANS={"starter","builder","pro","enterprise"}


def load_registry(path):
    assets=json.loads(Path(path).read_text(encoding="utf-8"))
    if not isinstance(assets,list):
        raise ValueError("The monitored-card registry must contain a JSON array.")
    required={"card_id","player","year","set","card_number","grade_company","grade"}
    for index,asset in enumerate(assets):
        missing=required-set(asset)
        if missing:
            raise ValueError(f"Registry row {index+1} is missing: {', '.join(sorted(missing))}")
    return assets


def write_contract(path,contract):
    destination=Path(path)
    destination.parent.mkdir(parents=True,exist_ok=True)
    with tempfile.NamedTemporaryFile("w",encoding="utf-8",dir=destination.parent,delete=False) as handle:
        json.dump(contract,handle,indent=2,sort_keys=False)
        handle.write("\n")
        temporary=Path(handle.name)
    temporary.replace(destination)


def configured_sold_provider(oauth,marketplace):
    requested=(os.getenv("MARKET_SOLD_PROVIDER") or "auto").strip().lower()
    sold_comps_key=os.getenv("SOLD_COMPS_API_KEY","").strip()
    card_api_key=os.getenv("THE_CARD_API_KEY","").strip()
    card_api_plan=os.getenv("THE_CARD_API_PLAN","").strip().lower()
    insights_enabled=os.getenv("EBAY_MARKETPLACE_INSIGHTS_ENABLED","").lower() in {"1","true","yes"}

    use_sold_comps=requested=="sold_comps" or (requested=="auto" and bool(sold_comps_key))
    if use_sold_comps:
        if not sold_comps_key:
            raise RuntimeError("SOLD_COMPS_API_KEY is required when MARKET_SOLD_PROVIDER=sold_comps.")
        return SoldCompsProvider(
            sold_comps_key,
            ebay_site=os.getenv("SOLD_COMPS_EBAY_SITE") or "ebay.com",
            max_queries_per_run=int(os.getenv("SOLD_COMPS_MAX_QUERIES_PER_RUN") or "3"),
        )

    use_card_api=requested=="the_card_api" or (requested=="auto" and bool(card_api_key))
    if use_card_api:
        if not card_api_key:
            raise RuntimeError("THE_CARD_API_KEY is required when MARKET_SOLD_PROVIDER=the_card_api.")
        if card_api_plan not in PAID_CARD_API_PLANS:
            raise RuntimeError(
                "Persistent evidence ingestion requires a paid The Card API plan. "
                "Set THE_CARD_API_PLAN to starter, builder, pro, or enterprise only after the license is active."
            )
        platforms=tuple(
            value.strip() for value in (os.getenv("THE_CARD_API_PLATFORMS") or "ebay").split(",") if value.strip()
        )
        premium=os.getenv("THE_CARD_API_GOLDIN_BUYER_PREMIUM","").strip()
        return TheCardApiSoldProvider(
            card_api_key,
            platforms=platforms,
            goldin_buyer_premium=float(premium) if premium else None,
        )

    if requested not in {"auto","ebay_marketplace_insights"}:
        raise ValueError(f"Unknown MARKET_SOLD_PROVIDER: {requested}")
    if oauth.configured() and insights_enabled:
        return EbayMarketplaceInsightsProvider(oauth,marketplace)
    return None


def run(args):
    assets=load_registry(args.registry)
    oauth=EbayOAuthClient()
    configured=oauth.configured()
    marketplace=os.getenv("EBAY_MARKETPLACE_ID","EBAY_US")
    listing_provider=EbayBrowseProvider(oauth,marketplace) if configured else None
    sold_provider=configured_sold_provider(oauth,marketplace)
    result=ScheduledMarketPipeline(
        EvidenceStore(args.database),
        sold_provider=sold_provider,
        listing_provider=listing_provider,
    ).run(assets,as_of=args.as_of)
    if result.status!="complete" and not args.allow_blocked:
        raise RuntimeError(
            "The scheduled scan did not publish because sold-data access is unavailable. "
            "Configure a supported sold-evidence provider before retrying."
        )
    write_contract(args.output,result.contract)
    return result


def main():
    parser=argparse.ArgumentParser(description="Run the automatic sports-card evidence pipeline.")
    parser.add_argument("--registry",default="config/monitored_cards.json")
    parser.add_argument("--database",default="market_state.sqlite")
    parser.add_argument("--output",default="alpha-web/public/data/market-scan.json")
    parser.add_argument("--as-of")
    parser.add_argument("--allow-blocked",action="store_true",help="Write a clearly labeled blocked-state payload.")
    args=parser.parse_args()
    result=run(args)
    print(json.dumps({
        "run_id":result.run_id,
        "status":result.status,
        "cards":result.contract["universe_size"],
        "errors":len(result.errors),
        "output":args.output,
    },sort_keys=True))


if __name__=="__main__":
    main()
