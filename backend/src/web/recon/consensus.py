"""NLP "Name Guesser" — scrape reverse-search result pages, run local NER and
apply a cross-domain consensus algorithm.

Consensus rule: a candidate name is promoted only if it appears across at least
``min_domains`` *distinct* domains. The winner is the name with the highest
(distinct-domain-count, total-mentions) score. This suppresses one-off noise
from a single chatty page while surfacing a name echoed by many independent
sources.
"""

import logging
import re
from collections import defaultdict
from dataclasses import dataclass, field
from typing import Dict, List, Tuple

logger = logging.getLogger(__name__)

_NER = {"model": None, "kind": None, "tried": False}


@dataclass
class ConsensusResult:
    name: str = ""
    confidence: float = 0.0
    domains: List[str] = field(default_factory=list)
    mentions: int = 0
    # every candidate, ranked — for display / debugging
    ranked: List[dict] = field(default_factory=list)

    @property
    def found(self) -> bool:
        return bool(self.name)


def _load_ner(model: str):
    if _NER["tried"]:
        return _NER["kind"]
    _NER["tried"] = True
    if model == "gliner":
        try:
            from gliner import GLiNER

            _NER["model"] = GLiNER.from_pretrained("urchade/gliner_small-v2.1")
            _NER["kind"] = "gliner"
            return "gliner"
        except Exception as e:
            logger.info("gliner unavailable (%s); trying spaCy", e)
    try:
        import spacy

        _NER["model"] = spacy.load("en_core_web_sm")
        _NER["kind"] = "spacy"
        return "spacy"
    except Exception as e:
        logger.info("spaCy unavailable (%s); using heuristic NER", e)
    _NER["kind"] = "heuristic"
    return "heuristic"


# Two-or-three capitalised words in a row — a reasonable PERSON heuristic.
_NAME_RE = re.compile(r"\b([A-Z][a-z]{1,20}(?:\s+[A-Z][a-z]{1,20}){1,2})\b")
_STOP = {
    "The Best", "New York", "United States", "Sign In", "Log In", "Home Page",
    "Privacy Policy", "Terms Of", "All Rights", "Read More", "Search Results",
}


def extract_names(text: str, model: str = "gliner") -> List[str]:
    """Return candidate PERSON names from a blob of page text."""
    if not text:
        return []
    kind = _load_ner(model)
    names: List[str] = []
    try:
        if kind == "gliner":
            ents = _NER["model"].predict_entities(text[:2000], ["person"])
            names = [e["text"] for e in ents if e.get("label") == "person"]
        elif kind == "spacy":
            doc = _NER["model"](text[:2000])
            names = [ent.text for ent in doc.ents if ent.label_ == "PERSON"]
    except Exception as e:
        logger.warning("NER inference failed (%s); heuristic", e)
        kind = "heuristic"
    if kind == "heuristic" or not names:
        names = [m.group(1) for m in _NAME_RE.finditer(text)]
    # normalise + drop stopwords
    cleaned = []
    for n in names:
        n = " ".join(n.split()).strip()
        if len(n) >= 3 and n not in _STOP:
            cleaned.append(n)
    return cleaned


def consensus_names(
    documents: List[Tuple[str, str]],
    min_domains: int = 2,
    model: str = "gliner",
) -> ConsensusResult:
    """Given ``[(domain, page_text), ...]`` compute the consensus identity.

    A name must be seen on >= ``min_domains`` distinct domains to qualify. Ties
    break on total mention count.
    """
    domain_hits: Dict[str, set] = defaultdict(set)   # name -> {domains}
    mention_count: Dict[str, int] = defaultdict(int)

    for domain, text in documents:
        seen_here = set()
        for name in extract_names(text, model=model):
            key = name.lower()
            mention_count[key] += 1
            if key not in seen_here:
                domain_hits[key].add(domain)
                seen_here.add(key)

    if not domain_hits:
        return ConsensusResult()

    # canonical display form = the most common original casing per key
    display: Dict[str, str] = {}
    for _domain, text in documents:
        for name in extract_names(text, model=model):
            display.setdefault(name.lower(), name)

    ranked = []
    for key, domains in domain_hits.items():
        ranked.append({
            "name": display.get(key, key.title()),
            "domain_count": len(domains),
            "domains": sorted(domains),
            "mentions": mention_count[key],
        })
    ranked.sort(key=lambda r: (r["domain_count"], r["mentions"]), reverse=True)

    best = ranked[0]
    result = ConsensusResult(ranked=ranked)
    if best["domain_count"] >= min_domains:
        result.name = best["name"]
        result.domains = best["domains"]
        result.mentions = best["mentions"]
        # confidence = fraction of participating domains that agree, lightly
        # boosted by repeated mentions.
        participating = len({d for d, _t in documents})
        agree = best["domain_count"] / max(1, participating)
        result.confidence = min(1.0, 0.5 * agree + 0.5 * min(1.0, best["domain_count"] / 4.0))
    return result
