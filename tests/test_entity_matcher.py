import sys
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from entity_matcher import SportsCardEntityMatcher, build_ebay_query

M=SportsCardEntityMatcher()

CASES=[
({"year":2023,"manufacturer":"Panini","set_name":"Prizm","player":"Victor Wembanyama","card_number":"136","parallel":"Silver","autograph":0,"grade_company":"PSA","grade":10,"serial_number":""},
 "2023 Panini Prizm Victor Wembanyama #136 Silver Prizm PSA 10 Gem Mint", True),
({"year":2023,"manufacturer":"Panini","set_name":"Prizm","player":"Victor Wembanyama","card_number":"136","parallel":"Silver","autograph":0,"grade_company":"PSA","grade":10,"serial_number":""},
 "2023 Panini Prizm Victor Wembanyama #136 Base PSA 10", False),
({"year":2023,"manufacturer":"Panini","set_name":"Prizm","player":"Victor Wembanyama","card_number":"136","parallel":"Silver","autograph":0,"grade_company":"PSA","grade":10,"serial_number":""},
 "2023 Panini Prizm Victor Wembanyama #136 Silver Prizm RAW", False),
({"year":2018,"manufacturer":"Topps","set_name":"Chrome Update","player":"Shohei Ohtani","card_number":"HMT1","parallel":"Refractor","autograph":0,"grade_company":"PSA","grade":10,"serial_number":""},
 "2018 Topps Chrome Update Shohei Ohtani HMT1 Refractor PSA 10", True),
({"year":2018,"manufacturer":"Topps","set_name":"Chrome Update","player":"Shohei Ohtani","card_number":"HMT1","parallel":"Refractor","autograph":0,"grade_company":"PSA","grade":10,"serial_number":""},
 "2018 Topps Chrome Update Shohei Ohtani HMT32 Refractor PSA 10", False),
({"year":2000,"manufacturer":"Playoff","set_name":"Contenders","player":"Tom Brady","card_number":"144","parallel":"Base","autograph":1,"grade_company":"PSA","grade":9,"serial_number":"100"},
 "2000 Playoff Contenders Tom Brady #144 Rookie Ticket Auto /100 PSA 9", True),
({"year":2000,"manufacturer":"Playoff","set_name":"Contenders","player":"Tom Brady","card_number":"144","parallel":"Base","autograph":1,"grade_company":"PSA","grade":9,"serial_number":"100"},
 "2000 Playoff Contenders Tom Brady #144 Rookie Ticket Reprint Auto PSA 9", False),
({"year":2020,"manufacturer":"Panini","set_name":"Prizm","player":"Anthony Edwards","card_number":"258","parallel":"Base","autograph":0,"grade_company":"PSA","grade":10,"serial_number":""},
 "2020 Panini Prizm Anthony Edwards #258 PSA 10 LOT OF 3 CARDS", False),
({"year":2020,"manufacturer":"Panini","set_name":"Prizm","player":"Anthony Edwards","card_number":"258","parallel":"Base","autograph":0,"grade_company":"PSA","grade":10,"serial_number":""},
 "2020 Panini Prizm Anthony Edwards #258 Silver PSA 10", False),
]


def test_reference_cases():
    for asset,title,expected in CASES:
        assert M.match(asset,title).accepted is expected


def test_non_auto_target_rejects_explicit_autograph():
    asset={"year":2020,"manufacturer":"Panini","set_name":"Prizm","player":"Anthony Edwards","card_number":"258","parallel":"Base","autograph":0,"grade_company":"PSA","grade":10,"serial_number":""}
    decision=M.match(asset,"2020 Panini Prizm Anthony Edwards #258 Auto PSA 10")
    assert not decision.accepted
    assert decision.reason == "unexpected_autograph"


def test_auto_target_without_auto_language_goes_to_review():
    asset={"year":2000,"manufacturer":"Playoff","set_name":"Contenders","player":"Tom Brady","card_number":"144","parallel":"Base","autograph":1,"grade_company":"PSA","grade":9,"serial_number":"100"}
    decision=M.match(asset,"2000 Playoff Contenders Tom Brady #144 Rookie Ticket /100 PSA 9")
    assert not decision.accepted
    assert decision.reason == "manual_review"
    assert decision.diagnostics["review_reason"] == "autograph_not_confirmed"


def test_numbered_target_rejects_wrong_denominator():
    asset={"year":2024,"manufacturer":"Topps","set_name":"Chrome","player":"Shohei Ohtani","card_number":"1","parallel":"Gold","autograph":0,"grade_company":"PSA","grade":10,"serial_number":"50"}
    decision=M.match(asset,"2024 Topps Chrome Shohei Ohtani #1 Gold Refractor /99 PSA 10")
    assert not decision.accepted
    assert decision.reason == "wrong_serial_denominator"


def test_numbered_target_without_denominator_goes_to_review():
    asset={"year":2024,"manufacturer":"Topps","set_name":"Chrome","player":"Shohei Ohtani","card_number":"1","parallel":"Gold","autograph":0,"grade_company":"PSA","grade":10,"serial_number":"50"}
    decision=M.match(asset,"2024 Topps Chrome Shohei Ohtani #1 Gold Refractor PSA 10")
    assert not decision.accepted
    assert decision.reason == "manual_review"
    assert decision.diagnostics["review_reason"] == "serial_not_confirmed"


def test_chrome_update_and_chrome_are_distinct_set_families():
    asset={"year":2018,"manufacturer":"Topps","set_name":"Chrome Update","player":"Shohei Ohtani","card_number":"HMT1","parallel":"Refractor","autograph":0,"grade_company":"PSA","grade":10,"serial_number":""}
    decision=M.match(asset,"2018 Topps Chrome Shohei Ohtani HMT1 Refractor PSA 10")
    assert not decision.accepted
    assert decision.reason == "wrong_set_family"


def test_raw_target_rejects_graded_listing():
    asset={"year":2020,"manufacturer":"Panini","set_name":"Prizm","player":"Anthony Edwards","card_number":"258","parallel":"Base","autograph":0,"grade_company":"","grade":"","serial_number":""}
    decision=M.match(asset,"2020 Panini Prizm Anthony Edwards #258 PSA 10")
    assert not decision.accepted
    assert decision.reason == "raw_vs_graded_mismatch"
    assert decision.diagnostics["unexpected_grader"] == ["psa"]


def test_raw_target_accepts_ungraded_listing():
    asset={"year":2020,"manufacturer":"Panini","set_name":"Prizm","player":"Anthony Edwards","card_number":"258","parallel":"Base","autograph":0,"grade_company":"","grade":"","serial_number":""}
    decision=M.match(asset,"2020 Panini Prizm Anthony Edwards #258")
    assert decision.accepted
    assert decision.reason == "accepted"


def test_query_contains_discriminators():
    asset={"year":2000,"manufacturer":"Playoff","set_name":"Contenders","player":"Tom Brady","card_number":"144","parallel":"Base","autograph":1,"grade_company":"PSA","grade":9,"serial_number":"100"}
    query=build_ebay_query(asset)
    assert "Tom Brady" in query
    assert "auto" in query
    assert "PSA" in query
    assert "9" in query
