"""Vision pool-detection: verdict parsing + photo sampling (pure parts)."""

from vision import _sample, parse_verdict


def test_verdict_pool():
    assert parse_verdict('{"verdict": "pool", "evidence": "backyard pool"}')[0] is True


def test_verdict_no_pool():
    assert parse_verdict('{"verdict": "no_pool", "evidence": "grass yard"}')[0] is False


def test_verdict_unsure_is_none():
    assert parse_verdict('{"verdict": "unsure", "evidence": "interior only"}')[0] is None


def test_verdict_json_embedded_in_prose():
    assert parse_verdict('Sure: {"verdict":"pool","evidence":"x"} done')[0] is True


def test_verdict_text_fallback_pool():
    assert parse_verdict("I can see a pool in the back")[0] is True


def test_verdict_text_fallback_no_pool():
    assert parse_verdict("there is no_pool visible")[0] is False


def test_verdict_empty_is_none():
    assert parse_verdict("")[0] is None


def test_verdict_garbage_is_none():
    assert parse_verdict("asdf qwer zxcv")[0] is None


def test_sample_returns_all_when_few():
    assert _sample(["a", "b"], 6) == ["a", "b"]


def test_sample_caps_and_includes_first():
    out = _sample([str(i) for i in range(20)], 5)
    assert len(out) == 5
    assert out[0] == "0"


def test_sample_handles_none_and_blanks():
    assert _sample(None, 6) == []
    assert _sample(["", "x", None], 6) == ["x"]
