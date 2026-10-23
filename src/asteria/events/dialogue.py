from __future__ import annotations

from collections.abc import Iterable
from dataclasses import dataclass

PORTRAIT_SIDES = ("left", "right")  # where a line's portrait sits in the message window


@dataclass(frozen=True, slots=True)
class DialogueLine:
    text: str
    speaker: str = ""
    portrait_asset_id: str = ""
    portrait_side: str = "left"
    text_key: str = ""  # its translation's key in the locale tables (D60); "" = the text as is

    def __post_init__(self):
        if not str(self.text):
            raise ValueError("dialogue text is required")
        if self.portrait_side not in PORTRAIT_SIDES:
            raise ValueError(f"portrait side must be one of {PORTRAIT_SIDES}")

    def to_data(self):
        data = {
            "text": str(self.text),
            "speaker": str(self.speaker),
            "portrait_asset_id": str(self.portrait_asset_id),
        }
        if self.portrait_side != "left":  # written only when set: older data reads the same
            data["portrait_side"] = self.portrait_side
        if self.text_key:
            data["text_key"] = str(self.text_key)
        return data

    @classmethod
    def from_data(cls, data):
        keys = set(data)
        required = {"text", "speaker", "portrait_asset_id"}
        if not required <= keys or keys - required - {"portrait_side", "text_key"}:
            raise ValueError("invalid dialogue line")
        return cls(
            text=str(data["text"]),
            speaker=str(data["speaker"]),
            portrait_asset_id=str(data["portrait_asset_id"]),
            portrait_side=str(data.get("portrait_side", "left")),
            text_key=str(data.get("text_key", "")),
        )


@dataclass(frozen=True, slots=True)
class DialogueChoice:
    text: str
    value: object
    text_key: str = ""  # its translation's key in the locale tables (D60)

    def __post_init__(self):
        if not str(self.text):
            raise ValueError("choice text is required")

    def to_data(self):
        data = {"text": str(self.text), "value": self.value}
        if self.text_key:  # written only when set
            data["text_key"] = str(self.text_key)
        return data

    @classmethod
    def from_data(cls, data):
        if not {"text", "value"} <= set(data) or set(data) - {"text", "value", "text_key"}:
            raise ValueError("invalid dialogue choice")
        return cls(
            text=str(data["text"]), value=data["value"], text_key=str(data.get("text_key", ""))
        )


@dataclass(frozen=True, slots=True)
class DialogueRequest:
    line: DialogueLine

    def to_data(self):
        return {
            "schema": "asteria.dialogue_request",
            "version": 1,
            "line": self.line.to_data(),
        }

    @classmethod
    def from_data(cls, data):
        if set(data) != {"schema", "version", "line"}:
            raise ValueError("invalid dialogue request")
        if data["schema"] != "asteria.dialogue_request" or data["version"] != 1:
            raise ValueError("unsupported dialogue request")
        return cls(DialogueLine.from_data(data["line"]))


@dataclass(frozen=True, slots=True)
class ChoiceRequest:
    prompt: str
    choices: tuple[DialogueChoice, ...]
    variable_name: str = ""
    local_name: str = ""
    prompt_key: str = ""  # the prompt's translation key (D60)

    def __init__(
        self,
        prompt: str,
        choices: Iterable[DialogueChoice],
        *,
        variable_name: str = "",
        local_name: str = "",
        prompt_key: str = "",
    ):
        items = tuple(choices)
        if not items:
            raise ValueError("choice request requires at least one choice")
        if any(not isinstance(item, DialogueChoice) for item in items):
            raise TypeError("choices must be DialogueChoice values")
        object.__setattr__(self, "prompt", str(prompt))
        object.__setattr__(self, "choices", items)
        object.__setattr__(self, "variable_name", str(variable_name))
        object.__setattr__(self, "local_name", str(local_name))
        object.__setattr__(self, "prompt_key", str(prompt_key))

    def to_data(self):
        data = {
            "schema": "asteria.choice_request",
            "version": 1,
            "prompt": self.prompt,
            "choices": [c.to_data() for c in self.choices],
            "variable_name": self.variable_name,
            "local_name": self.local_name,
        }
        if self.prompt_key:  # written only when set
            data["prompt_key"] = self.prompt_key
        return data

    @classmethod
    def from_data(cls, data):
        expected = {
            "schema",
            "version",
            "prompt",
            "choices",
            "variable_name",
            "local_name",
        }
        if not expected <= set(data) or set(data) - expected - {"prompt_key"}:
            raise ValueError("invalid choice request")
        if data["schema"] != "asteria.choice_request" or data["version"] != 1:
            raise ValueError("unsupported choice request")
        if not isinstance(data["choices"], list):
            raise TypeError("choice request choices must be a list")
        return cls(
            data["prompt"],
            [DialogueChoice.from_data(item) for item in data["choices"]],
            variable_name=data["variable_name"],
            local_name=data["local_name"],
            prompt_key=str(data.get("prompt_key", "")),
        )


@dataclass(slots=True)
class DialogueRuntimeState:
    dialogue: DialogueRequest | None = None
    choice: ChoiceRequest | None = None

    @property
    def blocked(self) -> bool:
        return self.dialogue is not None or self.choice is not None

    def clear(self) -> None:
        self.dialogue = None
        self.choice = None

    def to_data(self):
        return {
            "schema": "asteria.dialogue_runtime_state",
            "version": 1,
            "dialogue": self.dialogue.to_data() if self.dialogue is not None else None,
            "choice": self.choice.to_data() if self.choice is not None else None,
        }

    @classmethod
    def from_data(cls, data):
        if set(data) != {"schema", "version", "dialogue", "choice"}:
            raise ValueError("invalid dialogue runtime state")
        if data["schema"] != "asteria.dialogue_runtime_state" or data["version"] != 1:
            raise ValueError("unsupported dialogue runtime state")
        if data["dialogue"] is not None and data["choice"] is not None:
            raise ValueError("dialogue runtime cannot block on dialogue and choice together")
        return cls(
            dialogue=(
                DialogueRequest.from_data(data["dialogue"])
                if data["dialogue"] is not None
                else None
            ),
            choice=(
                ChoiceRequest.from_data(data["choice"]) if data["choice"] is not None else None
            ),
        )
