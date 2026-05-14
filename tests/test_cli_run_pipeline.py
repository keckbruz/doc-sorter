from pathlib import Path
from types import SimpleNamespace

from typer.testing import CliRunner

from doc_cleaner import cli


runner = CliRunner()


def test_run_pipeline_requires_yes(tmp_path):
    result = runner.invoke(
        cli.app,
        [
            "run",
            "--input",
            str(tmp_path),
            "--output-root",
            str(tmp_path / "sorted"),
        ],
    )

    assert result.exit_code == 1
    assert "Refusing to move files without --yes" in result.output


def test_run_pipeline_scans_and_applies_without_prompt(monkeypatch, tmp_path):
    calls = {}

    def fake_scan(**kwargs):
        calls["scan"] = kwargs
        Path(kwargs["plan"]).parent.mkdir(parents=True, exist_ok=True)
        Path(kwargs["plan"]).write_text("approved,status\n", encoding="utf-8")

    def fake_apply_plan(plan_path, undo_path, yes, apply_all_above_threshold, confidence_threshold):
        calls["apply"] = {
            "plan_path": plan_path,
            "undo_path": undo_path,
            "yes": yes,
            "apply_all_above_threshold": apply_all_above_threshold,
            "confidence_threshold": confidence_threshold,
        }
        return SimpleNamespace(moved=1, skipped=0, errors=[])

    monkeypatch.setattr(cli, "scan", fake_scan)
    monkeypatch.setattr("doc_cleaner.applier.apply_plan", fake_apply_plan)

    plan_path = tmp_path / "plan.csv"
    undo_path = tmp_path / "undo.json"
    result = runner.invoke(
        cli.app,
        [
            "run",
            "--input",
            str(tmp_path),
            "--output-root",
            str(tmp_path / "sorted"),
            "--plan",
            str(plan_path),
            "--undo",
            str(undo_path),
            "--confidence-threshold",
            "95",
            "--yes",
        ],
    )

    assert result.exit_code == 0
    assert calls["scan"]["plan"] == plan_path
    assert calls["scan"]["confidence_threshold"] == 95
    assert calls["apply"] == {
        "plan_path": plan_path,
        "undo_path": undo_path,
        "yes": True,
        "apply_all_above_threshold": True,
        "confidence_threshold": 95,
    }
