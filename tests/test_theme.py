from asteria.editor.theme import ASTERIA_DARK, ASTERIA_DARK_QSS


def test_theme_has_coherent_tokens_and_nonempty_qss():
    assert ASTERIA_DARK.spacing_sm < ASTERIA_DARK.spacing_lg
    assert "QMainWindow" in ASTERIA_DARK_QSS
    assert "QTreeWidget::item:selected" in ASTERIA_DARK_QSS
    assert "QTextEdit#ConsoleOutput" in ASTERIA_DARK_QSS
    assert "border: 1px solid #343a44" in ASTERIA_DARK_QSS
