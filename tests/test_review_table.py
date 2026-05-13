from pathlib import Path
from doc_cleaner.review_table import ReviewRow, _status_str, _is_confident, _is_applicable


def _row(**kw):
    defaults = dict(
        original_path=Path("/docs/a.pdf"),
        original_name="a.pdf",
        target_path=Path("/out/Finance/Invoices/2024-01-01 - X.pdf"),
        new_name="2024-01-01 - X.pdf",
        category="Finance/Invoices",
        confidence=95,
        needs_review=False,
    )
    return ReviewRow(**{**defaults, **kw})


def test_status_excluded():
    assert _status_str(_row(excluded=True)) == "skip"


def test_status_user_edited():
    assert _status_str(_row(user_edited=True)) == "✓ edited"


def test_status_needs_review():
    assert _status_str(_row(confidence=60, needs_review=True)) == "⚠ review"


def test_status_planned():
    assert _status_str(_row()) == "✓"


def test_is_confident_above():
    assert _is_confident(_row(confidence=95), threshold=90)


def test_is_confident_below():
    assert not _is_confident(_row(confidence=89), threshold=90)


def test_is_confident_excluded():
    assert not _is_confident(_row(excluded=True), threshold=90)


def test_is_applicable_normal():
    assert _is_applicable(_row())


def test_is_applicable_review_category():
    assert not _is_applicable(_row(category="Review"))


def test_is_applicable_excluded():
    assert not _is_applicable(_row(excluded=True))


def test_is_applicable_needs_review_but_has_category():
    # low confidence but still has a real classification — applicable for "Apply all"
    assert _is_applicable(_row(confidence=60, needs_review=True))


from doc_cleaner.review_table import ReviewTableApp


def _make_app(rows=None, threshold=90):
    if rows is None:
        rows = [_row()]
    return ReviewTableApp(rows, threshold=threshold)


def test_app_initial_state():
    app = _make_app()
    assert app.cursor == 0
    assert not app.edit_mode
    assert app.edit_field == "name"
    assert app.edit_buffer == ""


def test_total_includes_three_actions():
    app = _make_app([_row(), _row(confidence=60, needs_review=True)])
    assert app._total == 5  # 2 rows + 3 actions


def test_on_action_false_for_row():
    app = _make_app([_row()])
    app.cursor = 0
    assert not app._on_action


def test_on_action_true_for_action_item():
    app = _make_app([_row()])
    app.cursor = 1  # first action
    assert app._on_action
    assert app._action_index == 0


def test_action_labels_confident_count():
    rows = [
        _row(confidence=95),
        _row(confidence=60, needs_review=True),
    ]
    app = _make_app(rows, threshold=90)
    labels = app._action_labels()
    assert "1 files" in labels[0]   # only 1 confident
    assert "2 files" in labels[1]   # both have a real category → applicable


def test_action_labels_excludes_excluded():
    rows = [_row(confidence=95), _row(confidence=95, excluded=True)]
    app = _make_app(rows, threshold=90)
    labels = app._action_labels()
    assert "1 files" in labels[0]
    assert "1 files" in labels[1]
