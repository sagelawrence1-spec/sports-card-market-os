import re
from dataclasses import dataclass
from typing import Dict, Any

STOP={"the","a","an","card","sports","trading","mint","gem","graded","grade","rookie","rc"}
HARD_EXCLUDE={"reprint","facsimile","digital","custom","proxy","reproduction","replica","you pick","pick your","break spot","case break","box break"}
GRADE_COMPANIES={"psa","bgs","beckett","sgc","cgc","tag"}


def norm(s:str)->str:
    s=(s or "").lower().replace("’","'")
    s=re.sub(r"[^a-z0-9/#.+-]+"," ",s)
    return re.sub(r"\s+"," ",s).strip()


def toks(s:str)->set:
    return {x for x in norm(s).split() if x not in STOP and len(x)>1}


def aliases_for_parallel(p:str)->set:
    p=norm(p)
    out={p} if p else set()
    mapping={
        "silver":{"silver","prizm silver","silver prizm"},
        "refractor":{"refractor","refr"},
        "gold":{"gold","gold refractor","gold prizm"},
        "red":{"red","red refractor","red prizm"},
        "blue":{"blue","blue refractor","blue prizm"},
    }
    for k,v in mapping.items():
        if k in p:
            out |= v
    if "/" in p:
        out.add(p.split("/")[0].strip())
    return {x for x in out if x}


@dataclass
class MatchDecision:
    accepted: bool
    score: float
    reason: str
    diagnostics: Dict[str,Any]


class SportsCardEntityMatcher:
    def __init__(self, accept_threshold: float=78.0, review_threshold: float=64.0):
        self.accept_threshold=accept_threshold
        self.review_threshold=review_threshold

    def match(self, asset:Dict[str,Any], title:str) -> MatchDecision:
        t=norm(title)
        diag={}
        for bad in HARD_EXCLUDE:
            if bad in t:
                return MatchDecision(False,0.0,f"hard_exclude:{bad}",{"hard_exclude":bad})

        player=norm(asset.get("player",""))
        year=str(asset.get("year") or "").strip()
        cardnum=norm(asset.get("card_number",""))
        setname=norm(asset.get("set_name") or asset.get("set") or "")
        manufacturer=norm(asset.get("manufacturer",""))
        parallel=norm(asset.get("parallel",""))
        grade_company=norm(asset.get("grade_company",""))
        grade=str(asset.get("grade") or "").replace(".0","")
        autograph=int(float(asset.get("autograph") or 0))
        serial=str(asset.get("serial_number") or "").strip()

        player_tokens=toks(player)
        title_tokens=toks(t)
        coverage=len(player_tokens & title_tokens)/max(1,len(player_tokens))
        diag["player_coverage"]=round(coverage,3)
        if coverage < .75:
            return MatchDecision(False,15.0,"player_mismatch",diag)

        score=42 + coverage*18

        if year:
            if year in t:
                score += 10
                diag["year_match"]=1
            else:
                shown_years=re.findall(r"\b(?:19|20)\d{2}(?:-\d{2})?\b",t)
                if shown_years:
                    return MatchDecision(False,20.0,"wrong_year",{**diag,"explicit_years":shown_years})
                score -= 9
                diag["year_match"]=0

        if cardnum:
            pat=rf"(?<![a-z0-9])(?:#|no\.?\s*)?{re.escape(cardnum)}(?![a-z0-9])"
            card_match=bool(re.search(pat,t))
            if card_match:
                score += 9
                diag["card_number_match"]=1
            else:
                diag["card_number_match"]=0
                explicit_nums=re.findall(r"(?:#|no\.?\s*)([a-z0-9-]+)",t)
                m=re.match(r"([a-z]+)([0-9].*)$",cardnum)
                same_prefix=[]
                if m:
                    prefix=m.group(1)
                    same_prefix=[tok for tok in title_tokens if tok.startswith(prefix) and tok!=cardnum and re.match(rf"^{re.escape(prefix)}[0-9]",tok)]
                if explicit_nums or same_prefix:
                    return MatchDecision(False,20.0,"wrong_card_number",{**diag,"explicit_card_numbers":explicit_nums,"same_prefix_numbers":same_prefix})
                score -= 12

        set_tokens=toks(setname)
        if set_tokens:
            cov=len(set_tokens & title_tokens)/len(set_tokens)
            diag["set_coverage"]=round(cov,3)
            score += 8*cov
            # Chrome and Chrome Update are different collectible families. When the
            # title explicitly says Chrome, Update presence must agree with target.
            if "chrome" in set_tokens and "chrome" in title_tokens:
                target_update="update" in set_tokens
                title_update="update" in title_tokens
                if target_update != title_update:
                    return MatchDecision(False,25.0,"wrong_set_family",{**diag,"target_update":target_update,"title_update":title_update})

        man_tokens=toks(manufacturer)
        if man_tokens:
            cov=len(man_tokens & title_tokens)/len(man_tokens)
            score += 4*cov
            diag["manufacturer_coverage"]=round(cov,3)

        if grade_company:
            company_present=grade_company in title_tokens
            grade_patterns=[rf"\b{re.escape(grade_company)}\s*{re.escape(grade)}\b",rf"\b{re.escape(grade_company)}\s*gem\s*mint\s*{re.escape(grade)}\b"]
            exact=any(re.search(p,t) for p in grade_patterns)
            diag["grade_exact"]=int(exact)
            if exact:
                score += 12
            elif company_present:
                shown=re.findall(rf"\b{re.escape(grade_company)}\s*(\d+(?:\.\d+)?)\b",t)
                if shown and grade not in shown:
                    return MatchDecision(False,25.0,"wrong_grade",{**diag,"explicit_grades":shown})
                score -= 12
            else:
                other=GRADE_COMPANIES & title_tokens
                if other:
                    return MatchDecision(False,25.0,"wrong_grading_company",{**diag,"other_grader":sorted(other)})
                return MatchDecision(False,28.0,"raw_vs_graded_mismatch",diag)

        if parallel and parallel not in {"base","base card"}:
            palias=aliases_for_parallel(parallel)
            pmatch=any(x in t for x in palias)
            diag["parallel_match"]=int(pmatch)
            if pmatch:
                score += 10
            else:
                if "base" in title_tokens:
                    return MatchDecision(False,30.0,"base_vs_parallel_mismatch",diag)
                score -= 14
        else:
            named={"silver","refractor","gold","red","blue","green","orange","purple","xfractor","superfractor"}
            found=named & title_tokens
            if found:
                return MatchDecision(False,30.0,"unexpected_parallel",{**diag,"unexpected_parallel":sorted(found)})

        auto_terms={"auto","autograph","signed"}
        has_auto=bool(auto_terms & title_tokens)
        diag["auto_title"]=int(has_auto)
        if autograph:
            if has_auto:
                score += 7
            else:
                # Do not auto-accept an autograph target unless the listing confirms it.
                return MatchDecision(False,70.0,"manual_review",{**diag,"review_reason":"autograph_not_confirmed"})
        elif has_auto:
            # An autograph is a different collectible, never a discounted base comp.
            return MatchDecision(False,20.0,"unexpected_autograph",diag)

        if serial and serial not in {"0","None"}:
            shown_denoms=re.findall(r"/\s*(\d+)\b",t)
            diag["explicit_serial_denominators"]=shown_denoms
            if serial in shown_denoms:
                score += 7
                diag["serial_denominator_match"]=1
            elif shown_denoms:
                return MatchDecision(False,20.0,"wrong_serial_denominator",{**diag,"target_serial_denominator":serial})
            else:
                # A numbered target without denominator evidence should be reviewed,
                # not silently accepted into valuation.
                return MatchDecision(False,70.0,"manual_review",{**diag,"serial_denominator_match":0,"review_reason":"serial_not_confirmed"})

        lot_hit=("lot of" in t or "bundle" in t or "set of" in t or bool(re.search(r"\blot\b",t)))
        if lot_hit:
            return MatchDecision(False,25.0,"multi_card_lot",{**diag,"lot":1})

        score=max(0,min(100,score))
        if score >= self.accept_threshold:
            return MatchDecision(True,round(score,1),"accepted",diag)
        if score >= self.review_threshold:
            return MatchDecision(False,round(score,1),"manual_review",diag)
        return MatchDecision(False,round(score,1),"low_match_score",diag)


def build_ebay_query(asset:Dict[str,Any]) -> str:
    parts=[]
    for k in ("year","manufacturer","set_name","set","player","card_number"):
        v=str(asset.get(k) or "").strip()
        if v and v not in parts:
            parts.append(v)
    p=str(asset.get("parallel") or "").strip()
    if p and p.lower() not in {"base","base card"}:
        parts.append(p)
    if int(float(asset.get("autograph") or 0)):
        parts.append("auto")
    gc=str(asset.get("grade_company") or "").strip()
    gr=str(asset.get("grade") or "").replace(".0","").strip()
    if gc:
        parts.append(gc)
    if gc and gr:
        parts.append(gr)
    return " ".join(parts)
