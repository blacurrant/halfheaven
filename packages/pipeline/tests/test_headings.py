"""Written text: telling it from captions, reading its shape, setting it."""
from halfheaven.analyze.onscreen_text import TextEvent, TextLine, coverage, group, text_kind
from halfheaven.plan.headings import _place, parse_cards, template_from
from halfheaven.render.caption_frames import CaptionFrame
from halfheaven.render.captions import LINE_BREAK, _lines, _tokens
from halfheaven.schemas import Canvas, CaptionProfile, TextRun


def line(text, y, h=0.05, fill="#B6FF12"):
    return TextLine(text=text, box=(0.2, y - h / 2, 0.8, y + h / 2), fill_hex=fill, score=0.99)


LISTICLE = [
    TextEvent(2.0, 7.0, [line("NON-NEGOTIABLE", 0.15, 0.09), line("job hunter picks", 0.22, 0.09, "#AE78F7")]),
    TextEvent(8.5, 10.0, [line("1) Very Strong", 0.2), line("(visibility)", 0.3, 0.03, "#F4FF16")]),
    TextEvent(11.0, 15.0, [line("2) Proof of skill", 0.21), line("(portfolio, projects)", 0.28, 0.03)]),
    TextEvent(15.5, 19.0, [line("3) Aggressive Networking", 0.19)]),
]
# She says each heading, among much else - which is what fools the naive test.
SPEECH = ([("so", 1.0), ("here", 1.2), ("are", 1.4), ("my", 1.5), ("picks", 1.7)]
          + [(w, 9.0 + i * 0.3) for i, w in enumerate(
              "first you need a very strong linkedin profile people really check".split())]
          + [(w, 11.5 + i * 0.3) for i, w in enumerate(
              "second proof of skill because recruiters want to see real work".split())])


def test_headings_that_echo_speech_are_still_written_text():
    assert coverage(LISTICLE, SPEECH) < 0.5
    assert text_kind(LISTICLE, SPEECH) == "authored"


def test_a_caption_track_is_spoken():
    words = [(w, i * 0.4) for i, w in enumerate("this is how you grade colour with scopes today".split())]
    events = [TextEvent(t, t + 0.5, [line(w, 0.35)]) for w, t in words]
    assert text_kind(events, words) == "spoken"


def test_no_readable_text_is_none():
    assert text_kind([], SPEECH) == "none"


def test_template_reads_title_numbering_and_sub_lines():
    template = template_from(LISTICLE, duration=34.0)
    assert template is not None
    assert [l.text for l in template.title] == ["NON-NEGOTIABLE", "job hunter picks"]
    assert template.numbered
    assert template.sub is not None and template.sub.text.startswith("(")
    assert 0.15 < template.centre_y < 0.3


def test_a_growing_card_is_one_event():
    looks = [(2.0, [line("NON-NEGOTI", 0.15)]),
             (2.5, [line("NON-NEGOTIABLE", 0.15), line("job hunter", 0.22)]),
             (3.0, [line("NON-NEGOTIABLE", 0.15), line("job hunter picks", 0.22)]),
             (4.0, [line("1) Very Strong", 0.2)])]
    events = group(looks, 0.5)
    assert len(events) == 2
    assert events[0].text == "NON-NEGOTIABLE job hunter picks"


def test_model_points_are_validated_not_repaired():
    cards = parse_cards({"title": ["Break big tasks", 7], "points": [
        {"at": 5, "text": "1) Treat your mind like a child"},
        {"at": 3, "text": "out of order"},
        {"at": 999, "text": "past the end"},
        {"at": "x", "text": "not an index"},
        {"at": 20, "text": "2) Break it down", "sub": "(five minutes)"},
    ]}, n_words=50)
    assert cards.title == ["Break big tasks"]
    assert [(p.at, p.sub) for p in cards.points] == [(5, None), (20, "(five minutes)")]


def test_a_card_never_covers_the_eyes():
    band = (0.3, 0.6)
    for centre in (0.2, 0.45, 0.7):
        y = _place(centre, 0.06, band)
        assert y + 0.06 <= band[0] or y - 0.06 >= band[1]
    # No room above: it goes under the chin.
    y = _place(0.2, 0.1, (0.15, 0.6))
    assert y - 0.1 >= 0.6


def test_a_line_break_run_starts_a_new_line():
    canvas = Canvas(width=720, height=1280, fps=30)
    style = CaptionProfile(present=True, size_pct=0.04)
    runs = [TextRun(text="BREAK BIG"), TextRun(text=LINE_BREAK), TextRun(text="tasks")]
    tokens = _tokens(CaptionFrame(runs=runs, duration=1.0), canvas, style)
    lines = _lines(tokens, style, max_width=1000, space=10)
    assert [[t.text for t in l] for l in lines] == [["BREAK", "BIG"], ["tasks"]]
