"""
Unit tests for Universal AI Agent Harness and CDM Plugin.
"""

from __future__ import annotations

from pathlib import Path

import cdm_compat
from cdm_workspace.harness import (
    doctor,
    verify,
    exec_code,
    inspect_model,
    list_business_events,
    generate_irs_sample,
    main,
)


def test_harness_doctor():
    """Verify that doctor diagnostics return healthy status."""
    res = doctor()
    assert res["ok"] is True
    assert len(res["checks"]) >= 4
    assert "HEALTHY" in res["report"]


def test_inspect_model_trade():
    """Verify inspection of CDM Trade class."""
    res = inspect_model("Trade")
    assert res["found"] is True
    assert res["class_name"] == "Trade"
    field_names = [f["name"] for f in res["fields"]]
    assert "tradeIdentifier" in field_names
    assert "tradeDate" in field_names
    assert "product" in field_names
    assert "CDM MODEL INSPECTOR" in res["report"]


def test_inspect_model_not_found():
    """Verify graceful handling of non-existent model name."""
    res = inspect_model("NonExistentUnknownModel123")
    assert res["found"] is False
    assert "not found" in res["report"]


def test_list_business_events():
    """Verify listing of IRS business events and qualifiers."""
    res = list_business_events()
    assert res["count"] > 0
    event_names = [e["name"] for e in res["events"]]
    assert "Reset" in event_names
    assert "CashTransfer" in event_names
    assert "Termination" in event_names
    assert "Novation" in event_names
    assert "FINOS CDM" in res["report"]


def test_generate_irs_sample_tmp(tmp_path: Path):
    """Verify IRS sample generation via harness."""
    out_file = tmp_path / "test_irs.json"
    res = generate_irs_sample(str(out_file))
    assert res["ok"] is True
    assert out_file.exists()
    assert res["size_bytes"] > 1000


def test_exec_code():
    """Verify safe execution of Python code snippet."""
    res = exec_code("print('HARNESS_TEST_OK')")
    assert res["ok"] is True
    assert "HARNESS_TEST_OK" in res["stdout"]


def test_cli_subcommands(capsys):
    """Verify CLI subcommands execution."""
    assert main(["doctor"]) == 0
    captured = capsys.readouterr()
    assert "HEALTHY" in captured.out

    assert main(["events"]) == 0
    captured = capsys.readouterr()
    assert "Reset" in captured.out

    assert main(["inspect", "Trade"]) == 0
    captured = capsys.readouterr()
    from cdm_workspace.deserialize_trade_state import get_sample_irs_json_path
    sample_p = get_sample_irs_json_path()
    assert main(["qualify", str(sample_p)]) == 0
    captured = capsys.readouterr()
    assert "InterestRate_IRSwap_FixedFloat" in captured.out
    assert "Vanilla Fixed/Float Interest Rate Swap" in captured.out
