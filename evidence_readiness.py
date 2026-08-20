"""Fail-closed evidence readiness boundary for Sports Card Market OS.

A passing public-eBay identity corpus is not the same thing as authoritative valuation
readiness. This module makes that distinction machine-readable by composing three
independent gates:

1. public identity-resolution proof,
2. receipt-bound eBay Product Research routing proof,
3. repeated out-of-sample calibration evidence.

The stages are monotonic. Later stages can never be reached by substituting public item
pages for Product Research or by supplying an unbound routing proof.
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any, Mapping

SCHEMA = "evidence-readiness.v1"
PUBLIC_IDENTITY_SCHEMA = "public-ebay-corpus-report.v1"
PRODUCT_RESEARCH_BINDING_SCHEMA = "product-research-corpus-proof.v1"
CALIBRATION_HISTORY_SCHEMA = "calibration-history.v1"
EXPECTED_PROVIDER = "ebay_product_research"
EXPECTED_PRICE_BASIS = "sold_price_plus_shipping"


def _identity_gate(report: Mapping[str, Any] | None) -> dict[str, Any]:
    blockers: list[str] = []
    warnings: list[str] = []
    if not isinstance(report, Mapping):
        return {"ready": False, "blockers": ["missing_public_identity_report"], "warnings": []}

    if report.get("schema") != PUBLIC_IDENTITY_SCHEMA:
        blockers.append("unsupported_public_identity_schema")
    if report.get("ready") is not True:
        blockers.append("public_identity_report_not_ready")
    if report.get("matcher_gate_ready") is not True:
        blockers.append("public_identity_matcher_gate_not_ready")
    if report.get("coverage_gate_ready") is not True:
        blockers.append("public_identity_coverage_gate_not_ready")

    validation = report.get("validation")
    if not isinstance(validation, Mapping) or validation.get("valid") is not True:
        blockers.append("public_identity_provenance_invalid")

    price_subset = report.get("price_sanity_subset")
    if not isinstance(price_subset, Mapping):
        blockers.append("public_identity_price_authority_metadata_missing")
    elif price_subset.get("authoritative_product_research") is not False:
        blockers.append("public_identity_claims_product_research_authority")
    else:
        warnings.append("public_prices_are_non_authoritative_sanity_only")

    return {
        "ready": not blockers,
        "blockers": list(dict.fromkeys(blockers)),
        "warnings": warnings,
    }


def _product_research_gate(proof: Mapping[str, Any] | None) -> dict[str, Any]:
    blockers: list[str] = []
    if not isinstance(proof, Mapping):
        return {"ready": False, "blockers": ["missing_product_research_proof"], "warnings": []}

    if proof.get("proof_ready") is not True:
        blockers.append("product_research_routing_proof_not_ready")

    authoritative = proof.get("authoritative_source")
    if not isinstance(authoritative, Mapping):
        blockers.append("product_research_proof_not_receipt_bound")
        return {"ready": False, "blockers": blockers, "warnings": []}
    if authoritative.get("schema") != PRODUCT_RESEARCH_BINDING_SCHEMA:
        blockers.append("unsupported_product_research_binding_schema")

    binding = authoritative.get("binding")
    receipt = authoritative.get("receipt")
    if not isinstance(binding, Mapping) or binding.get("verified") is not True:
        blockers.append("product_research_source_binding_unverified")
    if not isinstance(receipt, Mapping):
        blockers.append("product_research_receipt_missing")
        return {"ready": False, "blockers": list(dict.fromkeys(blockers)), "warnings": []}

    if receipt.get("provider") != EXPECTED_PROVIDER:
        blockers.append("product_research_provider_not_authoritative")
    if receipt.get("price_basis") != EXPECTED_PRICE_BASIS:
        blockers.append("product_research_price_basis_not_landed")

    source = receipt.get("source")
    if not isinstance(source, Mapping):
        blockers.append("product_research_receipt_source_missing")
    elif isinstance(binding, Mapping):
        if str(source.get("sha256") or "") != str(binding.get("sha256") or ""):
            blockers.append("product_research_source_hash_mismatch")
        if source.get("size_bytes") != binding.get("size_bytes"):
            blockers.append("product_research_source_size_mismatch")

    if isinstance(binding, Mapping):
        if binding.get("provider") != EXPECTED_PROVIDER:
            blockers.append("product_research_binding_provider_mismatch")
        if binding.get("price_basis") != EXPECTED_PRICE_BASIS:
            blockers.append("product_research_binding_price_basis_mismatch")
        rows = receipt.get("rows")
        if not isinstance(rows, Mapping) or rows.get("raw") != binding.get("raw_rows"):
            blockers.append("product_research_binding_row_count_mismatch")

    return {
        "ready": not blockers,
        "blockers": list(dict.fromkeys(blockers)),
        "warnings": [],
    }


def _calibration_gate(report: Mapping[str, Any] | None) -> dict[str, Any]:
    blockers: list[str] = []
    if not isinstance(report, Mapping):
        return {"ready": False, "blockers": ["missing_calibration_history"], "warnings": []}
    if report.get("schema") != CALIBRATION_HISTORY_SCHEMA:
        blockers.append("unsupported_calibration_history_schema")
    if report.get("calibration_review_allowed") is not True:
        blockers.append("calibration_history_not_ready")
    if report.get("automatic_threshold_changes_allowed") is not False:
        blockers.append("calibration_history_allows_automatic_threshold_changes")
    return {
        "ready": not blockers,
        "blockers": list(dict.fromkeys(blockers)),
        "warnings": [],
    }


def build_evidence_readiness(
    *,
    public_identity_report: Mapping[str, Any] | None,
    product_research_proof: Mapping[str, Any] | None = None,
    calibration_history: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    """Return monotonic readiness stages without allowing evidence substitution."""

    identity = _identity_gate(public_identity_report)
    authoritative = _product_research_gate(product_research_proof)
    calibration = _calibration_gate(calibration_history)

    identity_ready = identity["ready"]
    authoritative_research_ready = identity_ready and authoritative["ready"]
    private_engine_alpha_ready = authoritative_research_ready and calibration["ready"]

    if private_engine_alpha_ready:
        stage = "PRIVATE_ENGINE_ALPHA_READY"
    elif authoritative_research_ready:
        stage = "AUTHORITATIVE_RESEARCH_READY"
    elif identity_ready:
        stage = "IDENTITY_PROVEN"
    else:
        stage = "BLOCKED"

    blockers: list[str] = []
    if not identity["ready"]:
        blockers.extend(f"identity:{value}" for value in identity["blockers"])
    if not authoritative["ready"]:
        blockers.extend(f"authoritative:{value}" for value in authoritative["blockers"])
    if not calibration["ready"]:
        blockers.extend(f"calibration:{value}" for value in calibration["blockers"])

    warnings = [
        *(f"identity:{value}" for value in identity["warnings"]),
        *(f"authoritative:{value}" for value in authoritative["warnings"]),
        *(f"calibration:{value}" for value in calibration["warnings"]),
    ]

    return {
        "schema": SCHEMA,
        "stage": stage,
        "identity_ready": identity_ready,
        "authoritative_research_ready": authoritative_research_ready,
        "private_engine_alpha_ready": private_engine_alpha_ready,
        "gates": {
            "public_identity": identity,
            "product_research": authoritative,
            "calibration_history": calibration,
        },
        "blockers": blockers,
        "warnings": warnings,
        "evidence_substitution_allowed": False,
        "public_item_pages_authorize_valuation": False,
    }


def _read_optional(path: str | None) -> Mapping[str, Any] | None:
    if path is None:
        return None
    payload = json.loads(Path(path).read_text())
    if not isinstance(payload, Mapping):
        raise ValueError(f"{path} must contain a JSON object")
    return payload


def main() -> int:
    parser = argparse.ArgumentParser(description="Assess Market OS evidence readiness without evidence substitution.")
    parser.add_argument("--public-identity", required=True, help="public-ebay-corpus-report JSON")
    parser.add_argument("--product-research-proof", help="receipt-bound Product Research corpus proof JSON")
    parser.add_argument("--calibration-history", help="calibration-history.v1 JSON")
    parser.add_argument("-o", "--output", required=True)
    args = parser.parse_args()

    report = build_evidence_readiness(
        public_identity_report=_read_optional(args.public_identity),
        product_research_proof=_read_optional(args.product_research_proof),
        calibration_history=_read_optional(args.calibration_history),
    )
    Path(args.output).write_text(json.dumps(report, indent=2, sort_keys=True) + "\n")
    return 0 if report["private_engine_alpha_ready"] else 2


if __name__ == "__main__":
    raise SystemExit(main())
