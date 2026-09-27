from __future__ import annotations

from seventhings.models import (
    FilterOperator,
    HistoryListOptions,
    ListOptions,
    PersonListOptions,
    SortDirection,
    TaskListOptions,
    TaskReferenceType,
    TaskStatus,
    UserListOptions,
    UserSortBy,
    UserSortOrder,
    eq,
    gt,
    gt_or_null,
    gte,
    gte_or_null,
    in_,
    like,
    lt,
    lt_or_null,
    lte,
    lte_or_null,
    neq,
    nin,
    not_like,
)


def test_empty_options_encode_to_empty_string() -> None:
    assert ListOptions().encode() == ""
    assert UserListOptions().encode() == ""
    assert PersonListOptions().encode() == ""
    assert TaskListOptions().encode() == ""
    assert HistoryListOptions().encode() == ""


def test_page_and_per_page() -> None:
    assert ListOptions(page=2, per_page=50).encode() == "page=2&per_page=50"
    # Zero means "unset", as in the Go SDK.
    assert ListOptions(page=0, per_page=0).encode() == ""


def test_sort_uses_literal_brackets() -> None:
    opts = ListOptions().sort_by("name", SortDirection.ASC).sort_by("id", SortDirection.DESC)
    assert opts.encode() == "sort[name]=ASC&sort[id]=DESC"


def test_single_value_filters() -> None:
    cases = [
        (eq, "eq"),
        (neq, "neq"),
        (gt, "gt"),
        (gt_or_null, "gt_or_null"),
        (gte, "gte"),
        (gte_or_null, "gte_or_null"),
        (lt, "lt"),
        (lt_or_null, "lt_or_null"),
        (lte, "lte"),
        (lte_or_null, "lte_or_null"),
    ]
    for fn, op in cases:
        assert ListOptions().where(fn("f", "v")).encode() == f"filter[f][{op}]=v"


def test_multi_value_filters_use_array_form() -> None:
    assert ListOptions().where(like("name", "chair")).encode() == "filter[name][like][]=chair"
    assert ListOptions().where(not_like("name", "x")).encode() == "filter[name][not_like][]=x"
    assert ListOptions().where(in_("s", "a", "b")).encode() == "filter[s][in][]=a&filter[s][in][]=b"
    assert ListOptions().where(nin("s", "a")).encode() == "filter[s][nin][]=a"


def test_values_are_query_escaped() -> None:
    assert ListOptions().where(eq("title", "a b&c=d/é")).encode() == (
        "filter[title][eq]=a+b%26c%3Dd%2F%C3%A9"
    )


def test_full_combination() -> None:
    opts = (
        ListOptions()
        .with_page(3)
        .with_per_page(25)
        .sort_by("name", SortDirection.DESC)
        .where(eq("status", "active"), in_("room", "r1", "r2"))
    )
    assert opts.encode() == (
        "page=3&per_page=25&sort[name]=DESC"
        "&filter[status][eq]=active&filter[room][in][]=r1&filter[room][in][]=r2"
    )


def test_filter_entry_fields() -> None:
    f = in_("x", "1", "2")
    assert f.field == "x"
    assert f.operator is FilterOperator.IN
    assert f.values == ("1", "2")


def test_user_list_options() -> None:
    opts = UserListOptions(page=1, per_page=10, sort_by=UserSortBy.EMAIL, order=UserSortOrder.DESC)
    assert opts.encode() == "page=1&per_page=10&sort_by=email&order=desc"


def test_person_list_options_free_form_sort() -> None:
    opts = PersonListOptions(page=2, sort_by="last name", order=UserSortOrder.ASC)
    assert opts.encode() == "page=2&sort_by=last+name&order=asc"


def test_task_list_options() -> None:
    opts = TaskListOptions(
        status=TaskStatus.OPEN,
        deadline_from="2026-01-01",
        deadline_to="2026-12-31 23:59:59",
        assignee="u1",
        author="u2",
        reference_type=TaskReferenceType.ASSET,
    )
    assert opts.encode() == (
        "status=open&deadline_from=2026-01-01&deadline_to=2026-12-31+23%3A59%3A59"
        "&assignee=u1&author=u2&reference_type=asset"
    )


def test_history_list_options() -> None:
    assert HistoryListOptions(page=2, per_page=200).encode() == "page=2&per_page=200"
    assert HistoryListOptions(per_page=5).encode() == "per_page=5"
