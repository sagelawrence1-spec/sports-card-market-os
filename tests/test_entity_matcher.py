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

passed=0
for i,(asset,title,expected) in enumerate(CASES,1):
    d=M.match(asset,title)
    ok=(d.accepted==expected)
    print(i,"PASS" if ok else "FAIL",expected,d.accepted,d.score,d.reason,"|",title)
    passed+=ok
print(f"{passed}/{len(CASES)}")
assert passed==len(CASES)
