from email_bridge.subject import random_subject


def test_random_subject_has_between_one_and_five_words():
    for _ in range(200):
        words = random_subject().split()
        assert 1 <= len(words) <= 5
        assert all(word.isalpha() for word in words)


def test_random_subject_varies_across_calls():
    generated = {random_subject() for _ in range(100)}
    assert len(generated) > 50
