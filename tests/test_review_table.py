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


def _rendered_text(app):
    return "".join(t for _, t in app._render())


def test_render_shows_original_name():
    app = _make_app([_row(original_name="allianz.pdf")])
    assert "allianz.pdf" in _rendered_text(app)


def test_render_shows_proposed_name():
    app = _make_app([_row(new_name="2024-01-01 - Allianz.pdf")])
    assert "2024-01-01 - Allianz.pdf" in _rendered_text(app)


def test_render_shows_category():
    app = _make_app([_row(category="Finance/Invoices")])
    assert "Finance/Invoices" in _rendered_text(app)


def test_render_shows_confidence():
    app = _make_app([_row(confidence=95)])
    assert "95" in _rendered_text(app)


def test_render_shows_review_status():
    app = _make_app([_row(confidence=60, needs_review=True)])
    assert "⚠ review" in _rendered_text(app)


def test_render_shows_skip_status():
    app = _make_app([_row(excluded=True)])
    assert "skip" in _rendered_text(app)


def test_render_shows_edited_status():
    app = _make_app([_row(user_edited=True, confidence=100)])
    assert "✓ edited" in _rendered_text(app)


def test_render_shows_action_labels():
    text = _rendered_text(_make_app())
    assert "Apply confident" in text
    assert "Apply all" in text
    assert "Cancel" in text


def test_render_cursor_marker_on_current_row():
    app = _make_app([_row(), _row()])
    app.cursor = 1
    text = _rendered_text(app)
    lines = text.splitlines()
    data_lines = [l for l in lines if l.startswith("▶") or l.startswith("  ") and "✓" in l]
    assert any(l.startswith("▶") for l in data_lines)


def test_start_edit_sets_state():
    app = _make_app([_row(new_name="old.pdf")])
    app._start_edit()
    assert app.edit_mode
    assert app.edit_field == "name"
    assert app.edit_buffer == "old.pdf"


def test_confirm_edit_name_updates_row():
    app = _make_app([_row(new_name="old.pdf", target_path=Path("/out/Finance/Invoices/old.pdf"))])
    app._start_edit()
    app.edit_buffer = "new.pdf"
    app._confirm_edit()
    assert app.rows[0].new_name == "new.pdf"
    assert app.rows[0].target_path.name == "new.pdf"
    assert app.rows[0].user_edited
    assert app.rows[0].confidence == 100
    assert not app.rows[0].needs_review
    assert not app.edit_mode


def test_confirm_edit_category_updates_row():
    app = _make_app([_row(category="Finance/Invoices")])
    app._start_edit()
    app._switch_field(1)   # move to category field
    app.edit_buffer = "Legal/Contracts"
    app._confirm_edit()
    assert app.rows[0].category == "Legal/Contracts"
    assert app.rows[0].user_edited


def test_switch_field_right():
    app = _make_app([_row(new_name="n.pdf", category="Finance/Invoices")])
    app._start_edit()                  # edit_field == "name", buffer == "n.pdf"
    app._switch_field(1)               # switch to category
    assert app.edit_field == "category"
    assert app.edit_buffer == "Finance/Invoices"


def test_switch_field_wraps():
    app = _make_app([_row()])
    app._start_edit()
    app._switch_field(1)   # name → category
    app._switch_field(1)   # category → name (wraps)
    assert app.edit_field == "name"


def test_switch_field_saves_buffer():
    app = _make_app([_row(new_name="n.pdf", category="Finance/Invoices")])
    app._start_edit()
    app.edit_buffer = "edited.pdf"
    app._switch_field(1)               # save "edited.pdf" into row.new_name, switch to category
    assert app.rows[0].new_name == "edited.pdf"
