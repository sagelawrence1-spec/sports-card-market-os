import re
from dataclasses import dataclass
from typing import Dict, Any

STOP={"the","a","an","card","sports","trading","mint","gem","graded","grade","rookie","rc"}
HARD_EXCLUDE={"reprint","facsimile","digital","custom","proxy","reproduction","replica","you pick","pick your","break spot","case break","box break"}
GRADER_ALIASES={
    "psa":{"psa"},
    "bgs":{"bgs","beckett"},
    "sgc":{"sgc"},
    "cgc":{"cgc"},
    "tag":{"tag"},
}
GRADE_COMPANIES=set().union(*GRADER_ALIASES.values())
MANUFACTURER_IDENTITY_MARKERS={"topps","panini","upper deck","leaf","playoff","donruss","fleer"}
BRAND_MANUFACTURER_EVIDENCE={"topps":{"bowman"}}
DISTINCTIVE_SET_MARKERS={
    "bowman","prizm","select","optic","mosaic","finest","heritage","stadium",
    "inception","museum","definitive","transcendent","immaculate","flawless","now","cosmic",
}
COLOR_PARALLEL_MARKERS={"gold","red","blue","green","orange","purple","black","pink","aqua","teal"}
DISTINCT_PARALLEL_MARKERS={
    "silver","sepia","negative","xfractor","superfractor","wave","shimmer","sapphire","atomic",
    "speckle","raywave","lava","variation",
}
PARALLEL_IDENTITY_MARKERS=COLOR_PARALLEL_MARKERS | DISTINCT_PARALLEL_MARKERS
PARALLEL_CONTEXT_TERMS={"refractor","prizm","parallel","wave","shimmer","sapphire","atomic","speckle","raywave","lava"}


def norm(s:str)->str:
    s=(s or "").lower().replace("’","'")
    s=re.sub(r"[^a-z0-9/#.+-]+"," ",s)
    return re.sub(r"\s+"," ",s).strip()


def toks(s:str)->set:
    value=norm(s).replace("#"," ")
    return {x for x in value.split() if x not in STOP and len(x)>1}


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


def canonical_grader(value:str) -> str:
    value=norm(value)
    for canonical,aliases in GRADER_ALIASES.items():
        if value in aliases:
            return canonical
    return value


def observed_graders(title_tokens:set) -> set[str]:
    return {
        canonical
        for canonical,aliases in GRADER_ALIASES.items()
        if aliases & title_tokens
    }


def observed_parallel_markers(title:str) -> set[str]:
    """Extract hard parallel markers without mistaking team/color words for parallels."""
    t=norm(title)
    title_tokens=toks(t)
    found=DISTINCT_PARALLEL_MARKERS & title_tokens
    contexts="|".join(sorted(PARALLEL_CONTEXT_TERMS))
    for color in COLOR_PARALLEL_MARKERS & title_tokens:
        contextual=bool(re.search(
            rf"\b{re.escape(color)}\b(?:\s+[a-z0-9.+-]+){{0,3}}\s+(?:{contexts})\b",
            t,
        ))
        numbered=bool(re.search(rf"\b{re.escape(color)}\b[^/]{{0,30}}/\s*\d+\b",t))
        if contextual or numbered:
            found.add(color)
    return found


def card_number_evidence(cardnum:str, title:str) -> tuple[bool,list[str]]:
    """Return whether the target card number is explicitly supported by title evidence."""
    if not cardnum:
        return False,[]
    if cardnum.isdigit():
        pat=rf"(?<![a-z0-9])(?:#\s*|no\.?\s*|card\s+#?\s*){re.escape(cardnum)}(?![a-z0-9])"
    else:
        pat=rf"(?<![a-z0-9])(?:#\s*|no\.?\s*|card\s+#?\s*)?{re.escape(cardnum)}(?![a-z0-9])"
    matched=bool(re.search(pat,title))
    raw_explicit=re.findall(r"(?:#\s*|no\.?\s*|card\s+#?\s*)([a-z0-9-]+)",title)
    explicit_nums=[value for value in raw_explicit if any(ch.isdigit() for ch in value) or "-" in value]
    return matched,explicit_nums


def can_infer_missing_card_number(cardnum:str,title:str) -> bool:
    """Conservative observed fallback for Bowman Chrome CPA Prospect Autographs."""
    if not cardnum.startswith("cpa-"):
        return False
    return bool(re.search(r"\bprospect\s+autographs?\b",norm(title)))


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
            card_match,explicit_nums=card_number_evidence(cardnum,t)
            if card_match:
                score += 9
                diag["card_number_match"]=1
            else:
                diag["card_number_match"]=0
                m=re.match(r"([a-z]+)([0-9].*)$",cardnum)
                same_prefix=[]
                if m:
                    prefix=m.group(1)
                    same_prefix=[tok for tok in title_tokens if tok.startswith(prefix) and tok!=cardnum and re.match(rf"^{re.escape(prefix)}[0-9]",tok)]
                if explicit_nums or same_prefix:
                    return MatchDecision(False,20.0,"wrong_card_number",{**diag,"explicit_card_numbers":explicit_nums,"same_prefix_numbers":same_prefix})
                if can_infer_missing_card_number(cardnum,t):
                    score += 4
                    diag["card_number_inferred"]=1
                else:
                    return MatchDecision(False,70.0,"manual_review",{**diag,"review_reason":"card_number_not_confirmed"})

        set_tokens=toks(setname)
        if set_tokens:
            cov=len(set_tokens & title_tokens)/len(set_tokens)
            diag["set_coverage"]=round(cov,3)
            score += 8*cov

            target_set_markers=DISTINCTIVE_SET_MARKERS & set_tokens
            title_set_markers=DISTINCTIVE_SET_MARKERS & title_tokens
            diag["target_set_markers"]=sorted(target_set_markers)
            diag["title_set_markers"]=sorted(title_set_markers)
            if target_set_markers and not (target_set_markers & title_set_markers):
                return MatchDecision(False,25.0,"set_family_not_confirmed",diag)
            conflicting_set_markers=title_set_markers-target_set_markers
            if conflicting_set_markers:
                return MatchDecision(False,25.0,"wrong_set_family",{**diag,"conflicting_set_markers":sorted(conflicting_set_markers)})

            target_chrome="chrome" in set_tokens
            title_chrome="chrome" in title_tokens
            diag["target_chrome"]=int(target_chrome)
            diag["title_chrome"]=int(title_chrome)
            if target_chrome and not title_chrome:
                return MatchDecision(False,25.0,"set_family_not_confirmed",diag)
            if title_chrome and not target_chrome:
                return MatchDecision(False,25.0,"wrong_set_family",diag)

            target_update="update" in set_tokens
            title_update="update" in title_tokens
            diag["target_update"]=int(target_update)
            diag["title_update"]=int(title_update)
            if target_update != title_update:
                return MatchDecision(False,25.0,"wrong_set_family",diag)

            target_draft="draft" in set_tokens
            title_draft="draft" in title_tokens
            diag["target_draft"]=int(target_draft)
            diag["title_draft"]=int(title_draft)
            if target_draft != title_draft:
                return MatchDecision(False,25.0,"wrong_set_family",diag)

        man_tokens=toks(manufacturer)
        if man_tokens:
            cov=len(man_tokens & title_tokens)/len(man_tokens)
            score += 4*cov
            diag["manufacturer_coverage"]=round(cov,3)

            target_manufacturer_markers={m for m in MANUFACTURER_IDENTITY_MARKERS if m in manufacturer}
            title_manufacturer_markers={m for m in MANUFACTURER_IDENTITY_MARKERS if m in t}
            implied_manufacturer_markers={
                m for m,brand_markers in BRAND_MANUFACTURER_EVIDENCE.items()
                if brand_markers & title_tokens
            }
            title_manufacturer_markers |= implied_manufacturer_markers
            diag["target_manufacturer_markers"]=sorted(target_manufacturer_markers)
            diag["title_manufacturer_markers"]=sorted(title_manufacturer_markers)
            diag["implied_manufacturer_markers"]=sorted(implied_manufacturer_markers)
            if target_manufacturer_markers and not (target_manufacturer_markers & title_manufacturer_markers):
                if title_manufacturer_markers:
                    return MatchDecision(False,25.0,"wrong_manufacturer",{**diag,"conflicting_manufacturer_markers":sorted(title_manufacturer_markers)})
                return MatchDecision(False,70.0,"manual_review",{**diag,"review_reason":"manufacturer_not_confirmed"})
            conflicting_manufacturer_markers=title_manufacturer_markers-target_manufacturer_markers
            if conflicting_manufacturer_markers:
                return MatchDecision(False,25.0,"wrong_manufacturer",{**diag,"conflicting_manufacturer_markers":sorted(conflicting_manufacturer_markers)})

        if grade_company:
            canonical_target=canonical_grader(grade_company)
            target_aliases=GRADER_ALIASES.get(canonical_target,{grade_company})
            observed=observed_graders(title_tokens)
            company_present=canonical_target in observed
            grade_patterns=[
                rf"\b{re.escape(alias)}\s*{re.escape(grade)}\b"
                for alias in target_aliases
            ] + [
                rf"\b{re.escape(alias)}\s*gem\s*mint\s*{re.escape(grade)}\b"
                for alias in target_aliases
            ]
            exact=any(re.search(p,t) for p in grade_patterns)
            diag["grade_exact"]=int(exact)
            diag["target_grader"]=canonical_target
            diag["observed_graders"]=sorted(observed)
            if exact:
                score += 12
            elif company_present:
                shown=[]
                for alias in target_aliases:
                    shown.extend(re.findall(rf"\b{re.escape(alias)}\s*(\d+(?:\.\d+)?)\b",t))
                if shown and grade not in shown:
                    return MatchDecision(False,25.0,"wrong_grade",{**diag,"explicit_grades":shown})
                score -= 12
            else:
                if observed:
                    return MatchDecision(False,25.0,"wrong_grading_company",{**diag,"other_grader":sorted(observed)})
                return MatchDecision(False,28.0,"raw_vs_graded_mismatch",diag)
        else:
            observed=observed_graders(title_tokens)
            if observed:
                return MatchDecision(False,28.0,"raw_vs_graded_mismatch",{**diag,"unexpected_grader":sorted(observed)})

        title_parallel_markers=observed_parallel_markers(t)
        if parallel and parallel not in {"base","base card"}:
            palias=aliases_for_parallel(parallel)
            target_parallel_markers=PARALLEL_IDENTITY_MARKERS & toks(parallel)
            diag["target_parallel_markers"]=sorted(target_parallel_markers)
            diag["title_parallel_markers"]=sorted(title_parallel_markers)

            conflicting_parallel_markers=title_parallel_markers-target_parallel_markers
            if conflicting_parallel_markers:
                return MatchDecision(False,30.0,"wrong_parallel",{**diag,"conflicting_parallel_markers":sorted(conflicting_parallel_markers)})
            if target_parallel_markers and not target_parallel_markers.issubset(title_parallel_markers):
                return MatchDecision(False,70.0,"manual_review",{**diag,"review_reason":"parallel_not_confirmed"})

            pmatch=any(x in t for x in palias)
            diag["parallel_match"]=int(pmatch)
            if pmatch:
                score += 10
            elif "base" in title_tokens:
                return MatchDecision(False,30.0,"base_vs_parallel_mismatch",diag)
            else:
                return MatchDecision(False,70.0,"manual_review",{**diag,"review_reason":"parallel_not_confirmed"})
        else:
            found=title_parallel_markers | ({"refractor"} & title_tokens)
            if found:
                return MatchDecision(False,30.0,"unexpected_parallel",{**diag,"unexpected_parallel":sorted(found)})

        auto_terms={"auto","autograph","signed"}
        has_auto=bool(auto_terms & title_tokens)
        diag["auto_title"]=int(has_auto)
        if autograph:
            if has_auto:
                score += 7
            else:
                return MatchDecision(False,70.0,"manual_review",{**diag,"review_reason":"autograph_not_confirmed"})
        elif has_auto:
            return MatchDecision(False,20.0,"unexpected_autograph",diag)

        shown_denoms=re.findall(r"/\s*(\d+)\b",t)
        diag["explicit_serial_denominators"]=shown_denoms
        if serial and serial not in {"0","None"}:
            if serial in shown_denoms:
                score += 7
                diag["serial_denominator_match"]=1
            elif shown_denoms:
                return MatchDecision(False,20.0,"wrong_serial_denominator",{**diag,"target_serial_denominator":serial})
            else:
                return MatchDecision(False,70.0,"manual_review",{**diag,"serial_denominator_match":0,"review_reason":"serial_not_confirmed"})
        elif shown_denoms:
            return MatchDecision(False,20.0,"unexpected_serial_numbering",{**diag,"unexpected_serial_denominators":shown_denoms})

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
