"""Scheduled evidence ingestion and fail-closed market-state reconstruction."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime, timezone
import statistics
from typing import Any, Iterable, Mapping

from entity_matcher import MatchDecision, SportsCardEntityMatcher, build_ebay_query
from evidence_store import EvidenceStore
from market_contract import build_evidence_market_scan, card_title
from market_engine import estimate_market, valuation_sample
from reconstruction import summarize_reconstruction_health


@dataclass(frozen=True)
class PipelineResult:
    run_id: str
    contract: dict[str, Any]
    status: str
    errors: tuple[str, ...]


def _day(value: str) -> date:
    return datetime.fromisoformat(str(value)[:10]).date()


def _cap_grade(grade: str, cap: str | None) -> str:
    order={"A":0,"B":1,"C":2,"D":3,"F":4}
    if cap in order and grade in order and order[grade] < order[cap]:
        return cap
    return grade


def _public_source(provider: str) -> str:
    return {
        "sold_comps":"eBay sold result",
        "ebay_marketplace_insights":"eBay Marketplace Insights",
        "ebay_product_research":"eBay Product Research",
        "the_card_api":"Licensed marketplace result",
    }.get(provider,str(provider or "market source").replace("_"," ").title())


def _public_reason(status: str, reason: str | None, *, used_in_valuation: bool=False) -> str:
    reason=str(reason or "")
    if status=="accepted":
        return "Used in valuation" if used_in_valuation else "Accepted match; filtered from valuation as a price outlier"
    if status=="review":
        return "Card identity needs review before this sale can affect valuation"
    if reason.startswith("provider_policy:"):
        reason=reason.split(":",1)[1]
    labels={
        "best_offer_price_is_upper_bound":"Best Offer price cannot be verified",
        "non_usd_currency":"Sale was not reported in USD",
        "shipping_price_unknown":"Shipping cost was unavailable",
        "invalid_sold_price":"Sold price was missing or invalid",
        "invalid_sale_date":"Sale date was missing or invalid",
        "player_mismatch":"Different player",
        "wrong_year":"Different card year",
        "wrong_card_number":"Different card number",
        "wrong_grade":"Different grade",
        "wrong_grading_company":"Different grading company",
        "raw_vs_graded_mismatch":"Raw card does not match the graded target",
        "base_vs_parallel_mismatch":"Base card does not match the target parallel",
        "unexpected_parallel":"Different parallel",
        "multi_card_lot":"Multi-card lot is not a clean single-card comp",
        "low_match_score":"Listing identity was not close enough",
    }
    if reason.startswith("hard_exclude:"):
        return f"Listing is a {reason.split(':',1)[1]}"
    return labels.get(reason,"Listing did not meet the evidence rules")


def _ledger_entry(row, status: str, sample_ids: set[str] | None=None) -> dict[str, Any]:
    evidence_id=row["evidence_id"]
    used=evidence_id in (sample_ids or set())
    price=float(row["price"] or 0)
    currency=str(row["currency"] or "").upper()
    url=str(row["url"] or "")
    if not url.startswith(("https://","http://")):
        url=""
    return {
        "evidence_id":evidence_id,
        "status":status,
        "title":row["title"] or "Untitled listing",
        "price":round(price,2) if price > 0 and currency=="USD" else None,
        "currency":"USD" if price > 0 and currency=="USD" else None,
        "event_date":row["event_date"],
        "source":_public_source(row["provider"]),
        "url":url or None,
        "used_in_valuation":used if status=="accepted" else False,
        "reason":_public_reason(status,row["match_reason"],used_in_valuation=used),
    }


class ScheduledMarketPipeline:
    """Turn approved provider evidence into the contract consumed by the product."""

    def __init__(
        self,
        store: EvidenceStore,
        *,
        sold_provider=None,
        listing_provider=None,
        matcher: SportsCardEntityMatcher | None=None,
    ):
        self.store=store
        self.sold_provider=sold_provider
        self.listing_provider=listing_provider
        self.matcher=matcher or SportsCardEntityMatcher()

    def _route(self, records, assets, query, run_id):
        accepted={asset["card_id"]:[] for asset in assets}
        per_card={asset["card_id"]:{"review":0,"rejected":0} for asset in assets}
        for record in records:
            ranked=sorted(
                ((self.matcher.match(asset,record.title),asset) for asset in assets),
                key=lambda pair:pair[0].score,
                reverse=True,
            )
            decision,asset=ranked[0]
            if not getattr(record,"policy_eligible",True):
                decision=MatchDecision(False,0.0,f"provider_policy:{record.policy_reason or 'ineligible'}",{
                    "provider":record.provider,
                    "policy_reason":record.policy_reason or "ineligible",
                })
            elif len(ranked)>1 and decision.accepted and ranked[1][0].score >= decision.score-3:
                decision=MatchDecision(False,decision.score,"manual_review",{
                    **decision.diagnostics,
                    "ambiguous_candidates":[asset["card_id"],ranked[1][1]["card_id"]],
                })
            self.store.save(record,asset["card_id"],query,decision,run_id=run_id)
            if decision.accepted:
                accepted[asset["card_id"]].append(record)
            elif decision.reason=="manual_review":
                per_card[asset["card_id"]]["review"]+=1
            else:
                per_card[asset["card_id"]]["rejected"]+=1
        return accepted,per_card

    def run(self, assets: Iterable[Mapping[str, Any]], *, as_of: str | None=None) -> PipelineResult:
        assets=[dict(asset) for asset in assets]
        if not assets:
            raise ValueError("The monitored card registry is empty.")
        as_of=as_of or datetime.now(timezone.utc).isoformat()
        cutoff=_day(as_of)
        source="scheduled_market_evidence"
        run_id=self.store.start_market_run(as_of,source,{
            "sold_provider":getattr(self.sold_provider,"provider_name",None),
            "listing_provider":getattr(self.listing_provider,"provider_name",None),
        })
        errors=[]
        accepted_active={asset["card_id"]:[] for asset in assets}
        sold_queries_attempted=set()
        sold_queries_completed=set()
        sold_queries_failed=set()
        listing_queries_attempted=set()
        listing_queries_completed=set()
        listing_queries_failed=set()

        if self.sold_provider is not None:
            planner=getattr(self.sold_provider,"plan_queries",None)
            plans=(planner(assets,as_of=as_of) if planner else [{
                "query":build_ebay_query(asset),
                "assets":[asset],
                "category_id":str(asset.get("ebay_category_id") or "261328"),
            } for asset in assets])
            for plan in plans:
                query=plan["query"]
                plan_assets=plan.get("assets") or assets
                plan_card_ids={asset["card_id"] for asset in plan_assets}
                sold_queries_attempted.update(plan_card_ids)
                try:
                    result=self.sold_provider.search_sold(
                        query,
                        category_id=plan.get("category_id"),
                        asset=plan_assets[0],
                    )
                    sold_queries_completed.update(plan_card_ids)
                    self._route(result.records,plan_assets,query,run_id)
                except Exception as exc:
                    sold_queries_failed.update(plan_card_ids)
                    group=",".join(asset["card_id"] for asset in plan_assets)
                    errors.append(f"sold:{group}:{type(exc).__name__}:{exc}")

        if self.listing_provider is not None:
            for asset in assets:
                card_id=asset["card_id"]
                listing_queries_attempted.add(card_id)
                query=build_ebay_query(asset)
                category_id=str(asset.get("ebay_category_id") or "261328")
                try:
                    result=self.listing_provider.search_active(query,category_id=category_id)
                    listing_queries_completed.add(card_id)
                    accepted,_=self._route(result.records,[asset],query,run_id)
                    for accepted_card_id,records in accepted.items():
                        accepted_active[accepted_card_id].extend(records)
                except Exception as exc:
                    listing_queries_failed.add(card_id)
                    errors.append(f"active:{card_id}:{type(exc).__name__}:{exc}")

        states=[]
        sold_source_available=self.sold_provider is not None and bool(sold_queries_completed or not sold_queries_attempted)
        sold_source_partial=bool(sold_queries_completed and sold_queries_failed)
        listing_source_available=self.listing_provider is not None and bool(listing_queries_completed or not listing_queries_attempted)
        listing_source_partial=bool(listing_queries_completed and listing_queries_failed)
        for asset in assets:
            card_id=asset["card_id"]
            scanned_this_run=card_id in sold_queries_completed
            if self.sold_provider is None:
                scan_state="unavailable"
            elif scanned_this_run:
                scan_state="complete"
            elif card_id in sold_queries_failed or card_id in sold_queries_attempted:
                scan_state="failed"
            else:
                scan_state="deferred_rotation"
            card_sold_source_available=self.sold_provider is not None and scan_state != "failed"
            card_listing_source_available=(
                self.listing_provider is not None
                and card_id not in listing_queries_failed
            )
            accepted_rows=self.store.accepted_sales(card_id)
            recent=[]
            latest_sale=None
            for row in accepted_rows:
                try:
                    sold=_day(row["event_date"])
                except Exception:
                    continue
                age=(cutoff-sold).days
                if 0 <= age <= 180:
                    recent.append({
                        "evidence_id":row["evidence_id"],
                        "sale_date":row["event_date"],
                        "sale_price":row["price"],
                        "currency":row["currency"],
                    })
                    if latest_sale is None or sold > latest_sale:
                        latest_sale=sold
            estimate=estimate_market(card_id,recent,cutoff.isoformat())
            sample_ids={row["evidence_id"] for row in valuation_sample(recent,cutoff.isoformat())}
            recent_ids={row["evidence_id"] for row in recent}
            accepted_ledger=[
                _ledger_entry(row,"accepted",sample_ids)
                for row in accepted_rows if row["evidence_id"] in recent_ids
            ]
            review_ledger=[
                _ledger_entry(row,"review")
                for row in self.store.evidence_rows(card_id,"review",limit=12,record_type=None)
            ]
            excluded_ledger=[
                _ledger_entry(row,"rejected")
                for row in self.store.evidence_rows(card_id,"rejected",limit=12,record_type=None)
            ]
            evidence_counts=self.store.evidence_counts(card_id)
            review_total=int(evidence_counts.get("review",0))
            excluded_total=int(evidence_counts.get("rejected",0))
            grade_cap=getattr(self.sold_provider,"evidence_grade_cap",None)
            evidence_grade=_cap_grade(estimate.evidence_grade,grade_cap)
            display_ready=(
                card_sold_source_available
                and evidence_grade in {"A","B"}
                and estimate.sample_size >= 8
            )
            fair_value=estimate.fair_value if display_ready else None
            dispersion=estimate.dispersion if estimate.dispersion is not None else None
            spread=max(0.05,dispersion or 0) if display_ready else None
            evidence_range={
                "low":round(fair_value*(1-spread),2),
                "high":round(fair_value*(1+spread),2),
            } if fair_value is not None else None
            active=list({record.source_item_id:record for record in accepted_active[card_id]}.values())
            active_prices=[record.price for record in active if record.currency.upper()=="USD" and record.price>0]
            accepted_sales_30d=sum(1 for sale in recent if (cutoff-_day(sale["sale_date"])).days <= 30)
            accepted_sales_label=f"{len(recent)} accepted USD {'sale' if len(recent)==1 else 'sales'}"
            liquidity=min(100,round(accepted_sales_30d*5+len(active_prices)*1.5,1))
            blockers=[]
            if self.sold_provider is None:
                blockers.append("Confirmed sold-data source is unavailable")
            elif scan_state=="failed":
                blockers.append("Confirmed sold-data query failed for this card")
            if scan_state=="deferred_rotation":
                blockers.append("Scheduled for a later free-plan rotation; no sold query ran for this card today")
            if card_id in listing_queries_failed:
                blockers.append("Active-listing query failed for this card; supply/liquidity context is incomplete")
            if not display_ready:
                blockers.append("Accepted sold evidence has not cleared the valuation gate")
            if grade_cap:
                blockers.append(
                    f"This sold-result source is capped at evidence grade {grade_cap} until an independent source agrees"
                )
            blockers.append("Forward calibration has not cleared the action gate")
            state={
                "observation_id":asset.get("observation_id") or f"registry:{card_id}",
                "card_id":card_id,
                "sport":asset.get("league") or asset.get("sport") or "",
                "player":asset.get("player") or "",
                "card":card_title(asset,card_id),
                "action":None,
                "engine_classification":"EVIDENCE_READY" if display_ready else "NOT_ENOUGH_EVIDENCE",
                "alerts":[],
                "confidence":estimate.confidence,
                "evidence_grade":evidence_grade,
                "fair_value":fair_value,
                "evidence_range":evidence_range,
                "move_30d":None,
                "liquidity_score":liquidity,
                "accepted_sales_30d":accepted_sales_30d,
                "accepted_sales_total":len(recent),
                "valuation_sample_size":estimate.sample_size,
                "accepted_active_count":len(active_prices),
                "review_count":review_total,
                "excluded_count":excluded_total,
                "lowest_ask":round(min(active_prices),2) if active_prices else None,
                "median_ask":round(statistics.median(active_prices),2) if active_prices else None,
                "latest_sale_date":latest_sale.isoformat() if latest_sale else None,
                "last_updated":as_of,
                "scanned_this_run":scanned_this_run,
                "scan_state":scan_state,
                "sold_source_available":card_sold_source_available,
                "listing_source_available":card_listing_source_available,
                "thesis":(
                    "Accepted sold evidence supports a valuation, but the system is withholding a capital action until forward calibration passes."
                    if display_ready else
                    "Not enough accepted sold evidence exists to publish a trustworthy fair value."
                ),
                "evidence_explanation":(
                    f"{accepted_sales_label}; {estimate.sample_size} used after robust outlier filtering; dispersion {estimate.dispersion:.1%}; source ceiling {grade_cap or 'none'}."
                    if estimate.dispersion is not None else
                    (
                        f"{accepted_sales_label}; {estimate.sample_size} used after robust outlier filtering."
                        if recent else
                        "No accepted USD sold observations are available."
                    )
                ),
                "blockers":blockers,
                "evidence_ledger":{
                    "accepted":accepted_ledger,
                    "review":review_ledger,
                    "excluded":excluded_ledger,
                    "accepted_total":len(recent),
                    "review_total":review_total,
                    "excluded_total":excluded_total,
                },
            }
            persisted_state=self.store.save_market_state(run_id,state)
            states.append(persisted_state)

        reconstruction_health=summarize_reconstruction_health(states)
        if self.sold_provider is None or (sold_queries_failed and not sold_queries_completed):
            status="blocked_sold_source"
        elif sold_source_partial:
            status="partial_sold_source"
        else:
            status="complete"
        provider_label=getattr(self.sold_provider,"source_label",None)
        if status=="complete":
            label=f"Scheduled {provider_label or 'confirmed sold evidence'}"
            source_kind="scheduled_evidence"
        elif status=="partial_sold_source":
            label=f"Scheduled {provider_label or 'confirmed sold evidence'} — partial sold-query failure"
            source_kind="partial_evidence"
        else:
            label="Automatic evidence pipeline — confirmed sold access pending"
            source_kind="blocked_evidence"
        contract=build_evidence_market_scan(
            states,
            source_kind=source_kind,
            source_label=label,
            generated_at=as_of,
            universe_size=len(assets),
            provenance={
                "run_id":run_id,
                "sold_provider":getattr(self.sold_provider,"provider_name",None),
                "listing_provider":getattr(self.listing_provider,"provider_name",None),
                "evidence_grade_cap":getattr(self.sold_provider,"evidence_grade_cap",None),
                "sold_source_available":sold_source_available,
                "sold_source_partial":sold_source_partial,
                "listing_source_available":listing_source_available,
                "listing_source_partial":listing_source_partial,
                "sold_queries_attempted":sorted(sold_queries_attempted),
                "sold_queries_completed":sorted(sold_queries_completed),
                "sold_queries_failed":sorted(sold_queries_failed),
                "listing_queries_attempted":sorted(listing_queries_attempted),
                "listing_queries_completed":sorted(listing_queries_completed),
                "listing_queries_failed":sorted(listing_queries_failed),
                "reconstruction_health":reconstruction_health,
                "errors":errors,
            },
        )
        contract["reconstruction_health"]=reconstruction_health
        self.store.finish_market_run(run_id,status,{
            "errors":errors,
            "cards":len(assets),
            "reconstruction_health":reconstruction_health,
        })
        return PipelineResult(run_id,contract,status,tuple(errors))