"""NER consensus algorithm tests (heuristic backend — no model download)."""

from backend.src.web.recon.consensus import consensus_names


def _docs():
    return [
        ("reddit.com", "John Doe is a street photographer based in Berlin."),
        ("danbooru.donmai.us", "Illustration by John Doe, uploaded today."),
        ("bing.com", "John Doe portfolio and biography."),
        ("random.blog", "Some unrelated text about Jane Roe only here."),
    ]


class TestConsensus:
    def test_cross_domain_winner(self):
        r = consensus_names(_docs(), min_domains=2, model="heuristic")
        assert r.found
        assert r.name.lower() == "john doe"
        assert len(r.domains) >= 2
        assert 0.0 < r.confidence <= 1.0

    def test_single_domain_name_rejected(self):
        # "Jane Roe" appears on only one domain → must not win
        r = consensus_names(_docs(), min_domains=2, model="heuristic")
        assert r.name.lower() != "jane roe"

    def test_threshold_not_met_returns_empty(self):
        docs = [("a.com", "Solo Mention here"), ("a.com", "Solo Mention again")]
        r = consensus_names(docs, min_domains=2, model="heuristic")
        assert not r.found

    def test_empty_documents(self):
        assert not consensus_names([], min_domains=2, model="heuristic").found

    def test_ranked_output_present(self):
        r = consensus_names(_docs(), min_domains=2, model="heuristic")
        assert r.ranked
        assert r.ranked[0]["domain_count"] >= r.ranked[-1]["domain_count"]
