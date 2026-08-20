from evidence_readiness import build_evidence_readiness


def identity_report(*, ready=True):
    return {
        "schema": "public-ebay-corpus-report.v1",
        "ready": ready,
        "matcher_gate_ready": ready,
        "coverage_gate_ready": ready,
        "validation": {"valid": ready},
        "price_sanity_subset": {"authoritative_product_research": False},
    }


def product_research_proof(*, proof_ready=True, sha="abc123"):
    return {
        "proof_version": "routing-proof.v6",
        "proof_ready": proof_ready,
        "authoritative_source": {
            "schema": "product-research-corpus-proof.v1",
            "binding": {
                "verified": True,
                "sha256": sha,
                "size_bytes": 123,
                "raw_rows": 50,
                "provider": "ebay_product_research",
                "price_basis": "sold_price_plus_shipping",
            },
            "receipt": {
                "provider": "ebay_product_research",
                "price_basis": "sold_price_plus_shipping",
                "source": {"sha256": sha, "size_bytes": 123},
                "rows": {"raw": 50, "accepted": 48},
            },
        },
    }


def calibration_history(*, ready=True):
    return {
        "schema": "calibration-history.v1",
        "calibration_review_allowed": ready,
        "automatic_threshold_changes_allowed": False,
        "blockers": [] if ready else ["insufficient_calibration_checkpoints"],
    }


def test_public_identity_pass_alone_stops_at_identity_proven():
    report = build_evidence_readiness(public_identity_report=identity_report())

    assert report["stage"] == "IDENTITY_PROVEN"
    assert report["identity_ready"] is True
    assert report["authoritative_research_ready"] is False
    assert report["private_engine_alpha_ready"] is False
    assert "authoritative:missing_product_research_proof" in report["blockers"]
    assert "calibration:missing_calibration_history" in report["blockers"]
    assert report["public_item_pages_authorize_valuation"] is False
    assert report["evidence_substitution_allowed"] is False


def test_receipt_bound_product_research_advances_to_authoritative_research():
    report = build_evidence_readiness(
        public_identity_report=identity_report(),
        product_research_proof=product_research_proof(),
    )

    assert report["stage"] == "AUTHORITATIVE_RESEARCH_READY"
    assert report["identity_ready"] is True
    assert report["authoritative_research_ready"] is True
    assert report["private_engine_alpha_ready"] is False
    assert report["gates"]["product_research"]["ready"] is True


def test_full_evidence_chain_is_required_for_private_engine_alpha():
    report = build_evidence_readiness(
        public_identity_report=identity_report(),
        product_research_proof=product_research_proof(),
        calibration_history=calibration_history(),
    )

    assert report["stage"] == "PRIVATE_ENGINE_ALPHA_READY"
    assert report["private_engine_alpha_ready"] is True
    assert report["blockers"] == []


def test_unbound_routing_proof_cannot_substitute_for_product_research_receipt():
    proof = {"proof_version": "routing-proof.v6", "proof_ready": True}
    report = build_evidence_readiness(
        public_identity_report=identity_report(),
        product_research_proof=proof,
        calibration_history=calibration_history(),
    )

    assert report["stage"] == "IDENTITY_PROVEN"
    assert report["authoritative_research_ready"] is False
    assert "authoritative:product_research_proof_not_receipt_bound" in report["blockers"]


def test_product_research_source_hash_mismatch_fails_closed():
    proof = product_research_proof()
    proof["authoritative_source"]["receipt"]["source"]["sha256"] = "different"
    report = build_evidence_readiness(
        public_identity_report=identity_report(),
        product_research_proof=proof,
        calibration_history=calibration_history(),
    )

    assert report["authoritative_research_ready"] is False
    assert "authoritative:product_research_source_hash_mismatch" in report["blockers"]


def test_public_identity_report_cannot_claim_product_research_authority():
    identity = identity_report()
    identity["price_sanity_subset"]["authoritative_product_research"] = True
    report = build_evidence_readiness(
        public_identity_report=identity,
        product_research_proof=product_research_proof(),
        calibration_history=calibration_history(),
    )

    assert report["stage"] == "BLOCKED"
    assert report["identity_ready"] is False
    assert "identity:public_identity_claims_product_research_authority" in report["blockers"]


def test_calibration_failure_does_not_revoke_authoritative_research():
    report = build_evidence_readiness(
        public_identity_report=identity_report(),
        product_research_proof=product_research_proof(),
        calibration_history=calibration_history(ready=False),
    )

    assert report["stage"] == "AUTHORITATIVE_RESEARCH_READY"
    assert report["authoritative_research_ready"] is True
    assert report["private_engine_alpha_ready"] is False
    assert "calibration:calibration_history_not_ready" in report["blockers"]


def test_binding_row_count_or_price_basis_mismatch_fails_closed():
    proof = product_research_proof()
    proof["authoritative_source"]["binding"]["raw_rows"] = 49
    proof["authoritative_source"]["binding"]["price_basis"] = "asking_price"
    report = build_evidence_readiness(
        public_identity_report=identity_report(),
        product_research_proof=proof,
        calibration_history=calibration_history(),
    )

    assert report["authoritative_research_ready"] is False
    assert "authoritative:product_research_binding_row_count_mismatch" in report["blockers"]
    assert "authoritative:product_research_binding_price_basis_mismatch" in report["blockers"]
