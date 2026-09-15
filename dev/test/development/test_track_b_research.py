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
