from moodmesh.lexicon import score_text, average_score, average_length


def test_neutral_text_scores_zero_ish():
    result = score_text("Update README with install instructions")
    assert result.score >= 0
    assert not result.is_stress_indicative


def test_positive_text_scores_positive():
    result = score_text("Add tests and improve documentation, thanks!")
    assert result.positive_hits > 0
    assert result.score > 0


def test_stress_text_scores_negative():
    result = score_text("URGENT hotfix: revert broken build, sorry, my bad")
    assert result.stress_hits > 0
    assert result.score < 0
    assert result.is_stress_indicative


def test_repeated_stress_words_increase_signal():
    mild = score_text("fix bug")
    severe = score_text("fix fix fix ugh broken again, sorry, emergency hotfix")
    assert severe.score < mild.score


def test_empty_text_scores_zero():
    result = score_text("")
    assert result.score == 0.0
    assert result.word_count == 0


def test_average_score_over_multiple_texts():
    texts = ["add feature", "urgent hotfix revert", "improve docs"]
    avg = average_score(texts)
    assert -1.0 <= avg <= 1.0


def test_average_score_empty_list():
    assert average_score([]) == 0.0


def test_average_length():
    texts = ["short", "a bit longer message"]
    avg = average_length(texts)
    assert avg == (len(texts[0]) + len(texts[1])) / 2


def test_average_length_empty():
    assert average_length([]) == 0.0
