"""Offline analysis checks; never contact a model endpoint."""
import copy
import importlib.util
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location("paired_audit", ROOT / "experiments/analyze_paired.py")
audit = importlib.util.module_from_spec(spec)
spec.loader.exec_module(audit)


@pytest.mark.parametrize(("text", "expected"), [
    ("SAFE\n\nThe old workflow was unsafe.", "SAFE"),
    ("CONDITIONAL\nAutomatic execution remains unsafe.", "CONDITIONAL"),
    ("**UNSAFE**\n\nDo not execute.", "UNSAFE"),
    ("\ufeff\n  **SAFE**  \nAnswer", "SAFE"),
    ("safe\nAnswer", "SAFE"),
    ("No safe conclusion is available", None),
    ("SAFE or UNSAFE", None),
    ("", None),
])
def test_explicit_label_only(text, expected):
    assert audit.parse_declared_label(text) == expected


def fixture():
    cases = {"CL-001": {"case_id": "CL-001", "gold": {"decision": "UNSAFE"}}}
    row = {"case_id": "CL-001", "trial": 1, "response_id": "response-1",
           "parent_case_id": "CL-001", "variant_family": "SEED", "gold": "UNSAFE",
           "predicted": "UNSAFE", "output_text": "CONDITIONAL\nThe action is unsafe.",
           "model": "test-deployment"}
    return cases, row


def test_parser_correction_preserves_original_row():
    cases, row = fixture()
    original = copy.deepcopy(row)
    checked = audit.validate_rows([row], cases, 1)
    assert row == original
    assert checked[0]["declared"] == "CONDITIONAL"
    assert checked[0]["predicted"] == "UNSAFE"


def test_duplicate_trial_rejected():
    cases, row = fixture()
    with pytest.raises(ValueError, match="duplicate"):
        audit.validate_rows([row, row], cases, 1)


def test_missing_trial_rejected():
    cases, row = fixture()
    with pytest.raises(ValueError, match="Missing"):
        audit.validate_rows([row], cases, 2)


def test_gold_mismatch_rejected():
    cases, row = fixture()
    row["gold"] = "SAFE"
    with pytest.raises(ValueError, match="gold"):
        audit.validate_rows([row], cases, 1)


def test_reused_response_id_rejected():
    cases, row = fixture()
    second = dict(row, trial=2)
    with pytest.raises(ValueError, match="response ID"):
        audit.validate_rows([row, second], cases, 2)


def test_wrong_parent_rejected():
    cases, row = fixture()
    row["parent_case_id"] = "CL-999"
    with pytest.raises(ValueError, match="parent_case_id"):
        audit.validate_rows([row], cases, 1)


def test_unparseable_output_is_counted_not_dropped():
    rows = [{"case_id": "x", "gold": "SAFE", "declared": None}]
    m = audit.metrics(rows, "declared")
    assert m["rows"] == 1 and m["correct"] == 0
    assert m["confusion"]["SAFE"]["UNPARSEABLE"] == 1


def test_bootstrap_is_reproducible():
    assert audit.cluster_interval([.1, .3, -.1], 200, 17) == audit.cluster_interval(
        [.1, .3, -.1], 200, 17)


def test_constant_cluster_interval():
    assert audit.cluster_interval([.25] * 10, 200, 17) == [.25, .25]


def test_exact_sign_flip_small_example():
    assert audit.sign_flip([1, 1]) == .5


def test_empty_bootstrap_is_error():
    with pytest.raises(ValueError):
        audit.cluster_interval([], 100, 17)


def test_input_fingerprint_ignores_gold_and_preserves_order():
    a = {"question": "Q", "evidence": [1, 2], "relations": [], "gold": "SAFE"}
    b = dict(a, gold="UNSAFE")
    assert audit.canonical(audit.request_payload(a)) == audit.canonical(audit.request_payload(b))
    b["evidence"] = [2, 1]
    assert audit.canonical(audit.request_payload(a)) != audit.canonical(audit.request_payload(b))


def test_frozen_reconstruction_has_160_cases_without_writes():
    audit.verify_sources(ROOT)
    cases = audit.build_cases(ROOT)
    assert len(cases) == 160
    assert len({c.get("parent_case_id", c["case_id"]) for c in cases.values()}) == 10
    request_hashes = {audit.canonical(audit.request_payload(c)) for c in cases.values()}
    assert len(request_hashes) == 127
    assert audit.request_payload(cases["CL-001-N-01"]) == audit.request_payload(
        cases["CL-001-N-02"])
