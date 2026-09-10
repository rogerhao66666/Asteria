from __future__ import annotations

from dataclasses import dataclass, field


def normalize_tag(value):
    tag = str(value).strip().lower()
    if not tag:
        raise ValueError("tag is required")
    if any(ch.isspace() for ch in tag):
        raise ValueError("tags cannot contain whitespace")
    return tag


@dataclass(slots=True)
class TagSet:
    """Small deterministic capability/classification tag set."""

    _tags: set[str] = field(default_factory=set)

    def __init__(self, values=()):
        self._tags = {normalize_tag(value) for value in values}

    def add(self, tag):
        tag = normalize_tag(tag)
        before = len(self._tags)
        self._tags.add(tag)
        return len(self._tags) != before

    def remove(self, tag):
        tag = normalize_tag(tag)
        if tag not in self._tags:
            return False
        self._tags.remove(tag)
        return True

    def contains(self, tag):
        return normalize_tag(tag) in self._tags

    def contains_all(self, tags):
        return all(normalize_tag(tag) in self._tags for tag in tags)

    def contains_any(self, tags):
        return any(normalize_tag(tag) in self._tags for tag in tags)

    def values(self):
        return tuple(sorted(self._tags))

    def to_data(self):
        return {
            "schema": "asteria.tag_set",
            "version": 1,
            "values": list(self.values()),
        }

    @classmethod
    def from_data(cls, data):
        if set(data) != {"schema", "version", "values"}:
            raise ValueError("invalid tag set")
        if data["schema"] != "asteria.tag_set" or data["version"] != 1:
            raise ValueError("unsupported tag set")
        if not isinstance(data["values"], list):
            raise TypeError("tag values must be a list")
        return cls(data["values"])

    def replace_from(self, other):
        """Replace contents from another validated TagSet."""
        if not isinstance(other, TagSet):
            raise TypeError("other must be TagSet")
        self._tags = set(other._tags)
        return self

    def replace_from_data(self, data):
        return self.replace_from(type(self).from_data(data))
