"""Define generic utils."""
import datetime
import random
from typing import Any, Optional, Tuple

import Levenshtein

AFFIRMATIVE_RESPONSES = [
    "10-4.",
    "Affirmative.",
    "As you decree, so shall it be.",
    "As you wish.",
    "By your command.",
    "Consider it done.",
    "Done.",
    "I can do that.",
    "If you insist.",
    "It shall be done.",
    "Leave it to me.",
    "Making things happen.",
    "No problem.",
    "No worries.",
    "OK.",
    "Roger that.",
    "So say we all.",
    "Sure.",
    "Will do.",
    "You got it.",
]


def grammatical_list_join(the_list: list) -> str:
    """Return a grammatically correct list join."""
    return ", ".join(the_list[:-2] + [" and ".join(the_list[-2:])])


def most_common(the_list: list) -> Any:
    """Return the most common element in a list."""
    return max(set(the_list), key=the_list.count)


def random_affirmative_response(replace_hyphens: bool = True) -> str:
    """Return a randomly chosen affirmative response."""
    choice = random.choice(AFFIRMATIVE_RESPONSES)

    if replace_hyphens:
        return choice.replace("-", " ")

    return choice


def relative_search_dict(
    candidates: dict, target: str, threshold: float = 0.3
) -> Tuple[Optional[str], Any]:
    """Return a key/value pair (or its closest neighbor) from a dict."""
    try:
        key = next((k for k in candidates.keys() if target.lower() in k.lower()))
        return (key, candidates[key])
    except StopIteration:
        pass

    try:
        matches = sorted(
            [k for k in candidates.keys() if Levenshtein.ratio(target, k) > threshold],
            reverse=True,
        )
        winner = matches[0]
        return (winner, candidates[winner])
    except IndexError:
        pass

    return (None, None)


def relative_search_list(
    candidates: list, target: str, threshold: float = 0.3
) -> Optional[str]:
    """Return an item (or its closest neighbor) from a list."""
    try:
        return next((c for c in candidates if target.lower() in c.lower()))
    except StopIteration:
        pass

    try:
        matches = sorted(
            [c for c in candidates if Levenshtein.ratio(target, c) > threshold],
            reverse=True,
        )
        return matches[0]
    except IndexError:
        pass

    return None


def suffix_strftime(frmt: str, input_dt: datetime.datetime) -> str:
    """Define a version of strftime() that puts a suffix on dates."""
    day_endings = {1: "st", 2: "nd", 3: "rd", 21: "st", 22: "nd", 23: "rd", 31: "st"}
    return input_dt.strftime(frmt).replace(
        "{TH}", str(input_dt.day) + day_endings.get(input_dt.day, "th")
    )
