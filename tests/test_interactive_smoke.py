from doc_cleaner.interactive import default_plan_paths


def test_default_plan_paths_use_plans_directory():
    plan_path, jsonl_path, undo_path = default_plan_paths()
    assert plan_path.parent.name == "plans"
    assert plan_path.suffix == ".csv"
    assert jsonl_path.suffix == ".jsonl"
    assert undo_path.suffix == ".json"
