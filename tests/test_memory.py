import pytest
from governor.memory import Memory


def test_memory_survives_restart_and_deletion_cascades(tmp_path):
    store = Memory(tmp_path)
    person = store.create("Sam")
    store.remember(person['id'], "Likes old films")
    store.enroll(person['id'], [0.1, 0.2])
    store.interacted(person['id'])
    store.close()
    store = Memory(tmp_path)
    assert store.person(person['id'])['turns'] == 1
    assert store.facts(person['id'])[0]['text'] == "Likes old films"
    store.delete(person['id'])
    assert store.facts(person['id']) == []
    assert store.embeddings() == []
    store.close()


def test_profile_isolation_and_input_limits(tmp_path):
    store = Memory(tmp_path)
    a, b = store.create('A')['id'], store.create('B')['id']
    fact = store.remember(a, 'Only A knows this')
    store.forget(b, fact['id'])
    assert len(store.facts(a)) == 1
    assert store.facts(b) == []
    with pytest.raises(ValueError):
        store.remember(a, 'x' * 501)
    with pytest.raises(KeyError):
        store.remember('missing', 'test')
    with pytest.raises(ValueError):
        store.create('   ')
    store.close()
