"""Localization and message settings: translation tables, macros and the message-log size.

``LocaleTable`` holds the text of one locale (``fr``, ``zh-TW``...) by key. ``Localizer`` looks a
key up in the current locale, then its parents (``zh-TW`` -> ``zh``), then the default locale, and
fills ``{name}`` placeholders. A missing key gives ``default`` (or the key itself), so an
untranslated game still shows something readable.
"""

from __future__ import annotations

from dataclasses import dataclass


def _text(value):
    return str(value or "").strip()


@dataclass(frozen=True, slots=True)
class LocaleTable:
    locale: str
    entries: tuple[tuple[str, str], ...] = ()

    def __init__(self, locale, entries=None):
        locale = _text(locale)
        if not locale:
            raise ValueError("locale is required")
        pairs = []
        for key, value in dict(entries or {}).items():
            key = _text(key)
            if not key:
                raise ValueError("translation keys are required")
            pairs.append((key, str(value)))
        object.__setattr__(self, "locale", locale)
        object.__setattr__(self, "entries", tuple(sorted(pairs)))

    def get(self, key):
        return dict(self.entries).get(key)

    def to_data(self):
        return {"locale": self.locale, "entries": dict(self.entries)}

    @classmethod
    def from_data(cls, data):
        return cls(data["locale"], data.get("entries"))


class Localizer:
    def __init__(self, tables=(), *, default_locale="", locale=""):
        self.tables = {t.locale: dict(t.entries) for t in tables}
        self.default_locale = _text(default_locale)
        self.locale = _text(locale) or self.default_locale

    def locales(self):
        return tuple(sorted(self.tables))

    def _chain(self):
        chain, locale = [], self.locale
        while locale:
            chain.append(locale)
            locale = locale.rsplit("-", 1)[0] if "-" in locale else ""
        if self.default_locale and self.default_locale not in chain:
            chain.append(self.default_locale)
        return chain

    def lookup(self, key):
        """The text for ``key`` in the best available locale, or ``None``."""
        for locale in self._chain():
            text = self.tables.get(locale, {}).get(str(key))
            if text is not None:
                return text
        return None

    def tr(self, key, default=None, **params):
        text = self.lookup(key)
        if text is None:
            text = str(key) if default is None else str(default)
        if not params:
            return text
        try:
            return text.format(**params)
        except (KeyError, IndexError, ValueError):
            return text  # a bad placeholder must not break a message


@dataclass(frozen=True, slots=True)
class MessageSettings:
    """Project-wide message options: macros (``\\M[name]``), currency label and the log size."""

    settings_id: str
    macros: tuple[tuple[str, str], ...] = ()
    currency_id: str = "gold"
    currency_label: str = ""
    backlog_limit: int = 0  # 0 = no message log screen
    default_locale: str = ""
    icons: tuple[tuple[str, str], ...] = ()  # \\I[n] number -> project icon id

    def __init__(
        self,
        settings_id,
        *,
        macros=None,
        currency_id="gold",
        currency_label="",
        backlog_limit=0,
        default_locale="",
        icons=None,
    ):
        settings_id = _text(settings_id)
        if not settings_id:
            raise ValueError("settings_id is required")
        if int(backlog_limit) < 0:
            raise ValueError("backlog_limit must be >= 0")
        object.__setattr__(self, "settings_id", settings_id)
        object.__setattr__(
            self,
            "macros",
            tuple(sorted((_text(k), str(v)) for k, v in dict(macros or {}).items())),
        )
        object.__setattr__(self, "currency_id", _text(currency_id) or "gold")
        object.__setattr__(self, "currency_label", _text(currency_label))
        object.__setattr__(self, "backlog_limit", int(backlog_limit))
        object.__setattr__(self, "default_locale", _text(default_locale))
        object.__setattr__(
            self,
            "icons",
            tuple(sorted((str(k), _text(v)) for k, v in dict(icons or {}).items())),
        )

    def to_data(self):
        return {
            "settings_id": self.settings_id,
            "macros": dict(self.macros),
            "currency_id": self.currency_id,
            "currency_label": self.currency_label,
            "backlog_limit": self.backlog_limit,
            "default_locale": self.default_locale,
            **({"icons": dict(self.icons)} if self.icons else {}),
        }

    @classmethod
    def from_data(cls, data):
        data = dict(data)
        return cls(data.pop("settings_id"), **data)
