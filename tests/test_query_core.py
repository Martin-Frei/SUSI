from rag.query import build_prompt, worth_saving, get_suggestions


def test_build_prompt_includes_question_and_context():
    p = build_prompt("Wie heisst der Hund?", "Der Hund heisst Rex.", "01.01.2026 10:00 Uhr")
    assert "Wie heisst der Hund?" in p
    assert "Der Hund heisst Rex." in p
    assert "01.01.2026 10:00 Uhr" in p
    assert "SUSI" in p


def test_build_prompt_unknown_prompt_falls_back():
    p = build_prompt("q", "c", "now", system_prompt="does_not_exist")
    assert "SUSI" in p  # fell back to susi_standard


def test_worth_saving_does_not_false_match_substring():
    # 'gut' must NOT match inside 'gute' -> this is a real question worth saving
    assert worth_saving("Was ist eine gute Trading-Strategie?") is True


def test_worth_saving_filters_acknowledgements():
    assert worth_saving("danke") is False
    assert worth_saving("guten morgen") is False


def test_get_suggestions_ranks_by_keywords():
    top = get_suggestions("Wie trainiere ich das LSTM?", "Mit XGBoost und Backtest.")
    assert "coding/stockpredict" in top


def test_get_suggestions_default_when_no_match():
    assert get_suggestions("zzz", "qqq") == ["persoenlich/"]
