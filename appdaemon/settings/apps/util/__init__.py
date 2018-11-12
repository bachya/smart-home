"""Define generic utils."""
import datetime
import itertools
import operator
from typing import Any, Tuple

import Levenshtein


def grammatical_list_join(the_list: list) -> str:
    """Return a grammatically correct list join."""
    return ', '.join(the_list[:-2] + [' and '.join(the_list[-2:])])


def most_common(the_list: list) -> Any:
    """Return the most common element in a list."""
    # get an iterable of (item, iterable) pairs
    sorted_list = sorted((x, i) for i, x in enumerate(the_list))

    # print 'SL:', SL
    groups = itertools.groupby(sorted_list, key=operator.itemgetter(0))

    # auxiliary function to get "quality" for an item
    def _auxfun(item):
        _, iterable = item
        count = 0
        min_index = len(the_list)
        for _, where in iterable:
            count += 1
            min_index = min(min_index, where)

        # print 'item %r, count %r, minind %r' % (item, count, min_index)
        return count, -min_index

    # pick the highest-count/earliest item
    return max(groups, key=_auxfun)[0]


def relative_search_dict(the_dict: dict, search: str,
                         threshold: float = 0.3) -> Tuple[str, str]:
    """Return a key/value pair (or its closest neighbor) from a dict."""
    _search = search.lower()
    try:
        _match = [key for key in the_dict.keys() if key.lower() in _search][0]
        match = (_match, the_dict[_match])
    except IndexError:
        try:
            _match = sorted(
                [
                    key for key in the_dict.keys()
                    if Levenshtein.ratio(_search, key.lower()) > threshold
                ],
                key=lambda k: Levenshtein.ratio(_search, k.lower()),
                reverse=True)[0]
            match = (_match, the_dict[_match])
        except IndexError:
            match = (None, None)

    return match


def relative_search_list(the_list: list, search: str,
                         threshold: float = 0.3) -> Tuple[str, str]:
    """Return an item (or its closest neighbor) from a list."""
    _search = search.lower()
    try:
        match = [value for value in the_list if value.lower() in _search][0]
    except IndexError:
        try:
            _match = sorted(
                [
                    value for value in the_list
                    if Levenshtein.ratio(_search, value.lower()) > threshold
                ],
                key=lambda v: Levenshtein.ratio(_search, v.lower()),
                reverse=True)[0]
            match = _match
        except IndexError:
            match = None

    return match


def suffix_strftime(frmt: str, input_dt: datetime.datetime) -> str:
    """Define a version of strftime() that puts a suffix on dates."""
    day_endings = {
        1: 'st',
        2: 'nd',
        3: 'rd',
        21: 'st',
        22: 'nd',
        23: 'rd',
        31: 'st'
    }
    return input_dt.strftime(frmt).replace(
        '{TH}',
        str(input_dt.day) + day_endings.get(input_dt.day, 'th'))
