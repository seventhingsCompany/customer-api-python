from __future__ import annotations

from dataclasses import replace
from typing import TypeVar

from .models.list_options import ListOptions, PersonListOptions, UserListOptions

DEFAULT_PAGE_SIZE = 100
"""Page size used by the ``all()`` iterators when the caller leaves ``per_page`` unset."""

OptionsT = TypeVar("OptionsT", ListOptions, UserListOptions, PersonListOptions)


def options_for_page(opts: OptionsT | None, factory: type[OptionsT], page: int) -> OptionsT:
    """Copy of opts (or a fresh one) for the given page; the caller's value is never mutated."""
    base = opts if opts is not None else factory()
    return replace(base, page=page, per_page=base.per_page or DEFAULT_PAGE_SIZE)
