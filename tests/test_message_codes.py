"""Message text codes: data codes expand, formatting codes parse into spans."""

from asteria.presentation.message_codes import (
    DEFAULT_PALETTE,
    MessageContext,
    Span,
    auto_wait,
    expand_message,
    parse_message,
    plain_message,
)

VARS = {"gold_spent": 7, "boss": "Hydra"}
CONTEXT = MessageContext(
    variable=VARS.get,
    switch=lambda name: name == "door",
    actor_name={"hero_01": "Ayla"}.get,
    party_name=lambda n: {1: "Ayla", 2: "Bram"}.get(n),
    currency_label="gold",
    currency_amount=lambda: 1250,
    macros={"greet": r"Hello, \N[hero_01]!", "loop": r"\M[loop]"},
    translate={"bye": "Farewell"}.get,
)


def test_data_codes_are_replaced_by_their_values():
    text = r"\N[hero_01] spent \V[gold_spent] \G; \$ left. Door: \S[door] / \S[lock]. \P[2] waits."
    assert (
        expand_message(text, CONTEXT)
        == "Ayla spent 7 gold; 1250 left. Door: ON / OFF. Bram waits."
    )


def test_a_code_without_a_value_stays_visible():
    assert expand_message(r"\V[nope] \N[ghost] \P[9] \T[none] \M[none]", CONTEXT) == (
        r"\V[nope] \N[ghost] \P[9] \T[none] \M[none]"
    )
    assert expand_message(r"\G \$ \V[a]") == r"\G \$ \V[a]"  # no context at all


def test_macros_expand_inside_macros_and_recursion_stops():
    assert expand_message(r"\M[greet] \T[bye]", CONTEXT) == "Hello, Ayla! Farewell"
    assert "\\M[loop]" in expand_message(r"\M[loop]", CONTEXT)  # no endless loop


def test_formatting_codes_become_spans():
    spans = parse_message(r"Red \C[2]alarm\C[0] and \I[12]an icon\{ big\} small")
    assert [(s.text, s.color) for s in spans if s.text] == [
        ("Red ", DEFAULT_PALETTE[0]),
        ("alarm", DEFAULT_PALETTE[2]),
        (" and ", DEFAULT_PALETTE[0]),
        ("an icon", DEFAULT_PALETTE[0]),
        (" big", DEFAULT_PALETTE[0]),
        (" small", DEFAULT_PALETTE[0]),
    ]
    assert [s.icon for s in spans if s.icon is not None] == [12]
    sizes = [s.size_steps for s in spans if s.text]
    assert sizes == [0, 0, 0, 0, 1, 0]


def test_pauses_and_waits_are_controls():
    spans = parse_message(r"Wait.\.\|now\!done")
    assert [s.text for s in spans if s.text] == ["Wait.", "now", "done"]
    assert [s.pause for s in spans if s.pause] == [0.25, 1.0]
    assert any(s.wait for s in spans)


def test_a_double_backslash_is_one_backslash_and_unknown_colors_fall_back():
    assert plain_message(r"C:\\path") == "C:\\path"
    spans = parse_message(r"\C[99]x")
    assert spans == (Span("x", DEFAULT_PALETTE[0]),)


def test_a_custom_palette_is_used():
    spans = parse_message(r"\C[1]blue", palette=((1, 1, 1), (9, 9, 9)))
    assert spans[0].color == (9, 9, 9)


def test_plain_message_is_for_logs_and_backlogs():
    assert plain_message(r"\C[2]\N[hero_01]\C[0]: \{hi\}\.", CONTEXT) == "Ayla: hi"


def test_message_end_marker():
    assert auto_wait("hello") and not auto_wait("hello\\^")
