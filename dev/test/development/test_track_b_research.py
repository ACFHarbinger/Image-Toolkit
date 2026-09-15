from tool.research.failure_analysis import failure_profile, kl_divergence, mutual_information, shannon_entropy
from tool.research.semantic_security import scan_python


def test_failure_measures_are_descriptive_and_handle_empty_data():
    rows = [
        {"stage": "register", "outcome": "failure"},
        {"stage": "register", "outcome": "failure"},
        {"stage": "compose", "outcome": "success"},
    ]
    assert shannon_entropy([]) == 0.0
    assert mutual_information(rows, "stage", "outcome") > 0
    assert failure_profile(rows, "stage")["register"] > 1
    assert kl_divergence(["a"], ["b"]) == float("inf")


def test_semantic_spike_reports_candidates_without_importing_source(tmp_path):
    path = tmp_path / "candidate.py"
    path.write_text("import subprocess\nsubprocess.run(user_input, shell=True)\n")
    finding = scan_python(path)[0]
    assert finding.rule == "shell-true"
    assert finding.line == 2


def test_research_plugins_expose_evidence_only_reports(tmp_path):
    from tool import WorkspaceStore, discover_plugins

    telemetry = tmp_path / "telemetry-1.jsonl"
    telemetry.write_text('{"t": 1, "category": "io", "event": "done"}\n')
    store = WorkspaceStore(root=tmp_path / "investigations", telemetry_dir=tmp_path)
    plugins = {item.manifest.name: item for item in discover_plugins(store)}
    reports = plugins["failure_analysis"].artifacts(store)
    assert reports[0].meta["research"] is True
    assert reports[0].meta["method"] == "descriptive"
    assert plugins["semantic_security"].manifest.description.startswith("Research-only")
