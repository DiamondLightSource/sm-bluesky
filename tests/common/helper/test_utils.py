from sm_bluesky.common.helper.utils import deep_update, unique_objs


def test_unique_objs_removes_duplicates_preserving_order():
    objs = ["a", "b", "a", "c", "b", "d"]

    assert unique_objs(objs) == ["a", "b", "c", "d"]


def test_unique_objs_returns_empty_list_for_empty_sequence():
    assert unique_objs([]) == []


def test_unique_objs_preserves_object_identity():
    first = object()
    second = object()

    result = unique_objs([first, second, first])

    assert result == [first, second]
    assert result[0] is first
    assert result[1] is second


def test_deep_update_adds_new_values():
    original = {"a": 1}
    updates = {"b": 2}

    deep_update(original, updates)

    assert original == {"a": 1, "b": 2}


def test_deep_update_replaces_existing_values():
    original = {"a": 1, "b": "original"}
    updates = {"a": 2, "b": "updated"}

    deep_update(original, updates)

    assert original == {"a": 2, "b": "updated"}


def test_deep_update_merges_nested_mappings():
    original = {
        "plan_args": {
            "start_field": 0.0,
            "stop_field": 1.0,
        }
    }
    updates = {
        "plan_args": {
            "beam_energy": "beam_energy",
            "energies": (600, 600.05),
        }
    }

    deep_update(original, updates)

    assert original == {
        "plan_args": {
            "start_field": 0.0,
            "stop_field": 1.0,
            "beam_energy": "beam_energy",
            "energies": (600, 600.05),
        }
    }


def test_deep_update_recursively_merges_nested_mappings():
    original = {
        "level_one": {
            "level_two": {
                "existing": 1,
            },
        },
    }
    updates = {
        "level_one": {
            "level_two": {
                "new": 2,
            },
        },
    }

    deep_update(original, updates)

    assert original == {
        "level_one": {
            "level_two": {
                "existing": 1,
                "new": 2,
            },
        },
    }


def test_deep_update_replaces_mapping_with_non_mapping():
    original = {"value": {"nested": 1}}
    updates = {"value": 2}

    deep_update(original, updates)

    assert original == {"value": 2}


def test_deep_update_replaces_non_mapping_with_mapping():
    original = {"value": 1}
    updates = {"value": {"nested": 2}}

    deep_update(original, updates)

    assert original == {"value": {"nested": 2}}


def test_deep_update_mutates_original_in_place():
    original = {"a": {"b": 1}}
    original_id = id(original)

    deep_update(original, {"a": {"c": 2}})

    assert id(original) == original_id
    assert original == {"a": {"b": 1, "c": 2}}
