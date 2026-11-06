from __future__ import annotations

import json

from ..other.session import EvaluationSession


def test_load_evaluation_file_switches_output_and_resumes_unrated(tmp_path):
    path = tmp_path / "asp_evaluations_previous.json"
    path.write_text(
        json.dumps({"asp_test01": {"asp": 4, "simple": 3, "reviewed": True}}),
        encoding="utf-8",
    )

    session = EvaluationSession(["asp_test01", "asp_test02"], str(tmp_path / "today.json"))
    session.load_evaluation_file(str(path))

    assert session.out_path == str(path)
    assert session.is_rated("asp_test01")
    assert session.current == "asp_test02"


def test_next_and_skip_walk_only_the_subset(tmp_path):
    names = [f"asp_test{i:02d}" for i in range(1, 7)]
    session = EvaluationSession(names, str(tmp_path / "e.json"))
    session.set_scope({"asp_test02", "asp_test05"})
    session.go_to("asp_test02")
    assert session.advance(skip=True) == "asp_test05"
    assert session.advance(skip=True) is None

    # a case outside the subset resumes at the next subset case after it
    session.go_to("asp_test03")
    entry = session.entry()
    entry.asp, entry.simple = 3, 3
    assert session.accept() == "asp_test05"

    session.set_scope(None)
    assert session.advance(skip=True) == "asp_test06"
