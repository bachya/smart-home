"""Define string-related utilities."""
import re
from unicodedata import normalize

RE_SLUGIFY = re.compile(r"[^a-z0-9_]+")
TBL_SLUGIFY = {ord("ß"): "ss"}


def camel_to_underscore(string: str) -> str:
    """Convert ThisString to this_string."""
    return re.sub("(?!^)([A-Z]+)", r"_\1", string).lower()


def slugify(text: str) -> str:
    """Slugify a given text."""
    text = normalize("NFKD", text)
    text = text.lower()
    text = text.replace(" ", "_")
    text = text.translate(TBL_SLUGIFY)
    text = RE_SLUGIFY.sub("", text)

    return text


def underscore_to_camel(string: str) -> str:
    """Convert this_string to ThisString."""
    return "".join(x.capitalize() or "_" for x in string.split("_"))
