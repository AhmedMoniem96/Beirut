from beirut_pos.services.printer import _note_segments


def test_note_segments_excludes_sugar_by_default():
    notes = _note_segments("سكر: خفيف؛ بدون ثلج", include_sugar=False)
    assert all("سكر" not in n for n in notes)


def test_note_segments_can_include_sugar():
    notes = _note_segments("سكر: خفيف؛ بدون ثلج", include_sugar=True, tag_sugar=True)
    assert any(n.startswith("سكر") for n in notes)
