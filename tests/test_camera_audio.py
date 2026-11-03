from governor.audio import Segmenter
from governor.camera import choose_match


def test_face_matching_rejects_unknown_and_ambiguous():
    assert choose_match([]) is None
    assert choose_match([('a', .49)]) is None
    assert choose_match([('a', .8), ('b', .75)]) is None
    assert choose_match([('a', .8), ('b', .4)]) == 'a'


def test_vad_ignores_clicks_and_retains_onset():
    s = Segmenter()
    for _ in range(40):
        assert s.feed(b's', 0) is None
    assert s.feed(b'c', 0.5) is None
    assert s.feed(b's', 0) is None
    for _ in range(5):
        assert s.feed(b'v', .1) is None
    result = None
    for _ in range(30):
        result = s.feed(b's', 0)
    assert b'vvvvv' in result
    assert not s.active


def test_vad_caps_continuous_noise():
    s = Segmenter()
    result = None
    for _ in range(1000):
        result = s.feed(b'v', .2)
    assert result is not None
    assert len(result) == 1000
