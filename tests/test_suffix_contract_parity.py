from autodoist.labeling import parse_type_suffix


def test_parse_type_suffix_project_cases() -> None:
    assert parse_type_suffix("Work -", "-", "=", 3) == "sss"
    assert parse_type_suffix("Work ==", "-", "=", 3) == "ppp"
    assert parse_type_suffix("Work =-", "-", "=", 3) == "pss"
    assert parse_type_suffix("Work -=-", "-", "=", 3) == "sps"


def test_parse_type_suffix_section_and_task_padding() -> None:
    assert parse_type_suffix("Section -", "-", "=", 2) == "xss"
    assert parse_type_suffix("Section =", "-", "=", 2) == "xpp"
    assert parse_type_suffix("Task -", "-", "=", 1) == "xxs"
    assert parse_type_suffix("Task =", "-", "=", 1) == "xxp"


def test_parse_type_suffix_without_suffix_returns_none() -> None:
    assert parse_type_suffix("No suffix", "-", "=", 3) is None
