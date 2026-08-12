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


def run(args):
    assets=load_registry(args.registry)
    oauth=EbayOAuthClient()
    configured=oauth.configured()
    marketplace=os.getenv("EBAY_MARKETPLACE_ID","EBAY_US")
    listing_provider=EbayBrowseProvider(oauth,marketplace) if configured else None
    insights_enabled=os.getenv("EBAY_MARKETPLACE_INSIGHTS_ENABLED","").lower() in {"1","true","yes"}
    sold_provider=EbayMarketplaceInsightsProvider(oauth,marketplace) if configured and insights_enabled else None
    result=ScheduledMarketPipeline(
        EvidenceStore(args.database),
        sold_provider=sold_provider,
        listing_provider=listing_provider,
    ).run(assets,as_of=args.as_of)
    if result.status!="complete" and not args.allow_blocked:
        raise RuntimeError(
            "The scheduled scan did not publish because authoritative sold-data access is unavailable. "
            "Enable an eBay-approved Marketplace Insights application before retrying."
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
