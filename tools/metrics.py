"""Power BI Service text metrics, measured empirically from the live report on
2026-08-17 by reading the rendered DOM in app.powerbi.com.

Findings that drive every number below:

  textbox
    * fontSize is honoured verbatim as CSS px ("10px" renders 10px).
    * BUT every paragraph line occupies a FIXED 21px line box, whatever the
      font size (verified at 8, 9, 10, 12, 13, 16 and 17px - all reported a
      21px content height for one line, 43px for two).
    * the visual reserves ~10px of vertical chrome (customPadding) and ~8px
      horizontal, so usable height = boxH - 10.
    * font family resolves to Segoe UI - BC Sans does NOT render in the
      Service. This settles the 7 Aug feasibility question.

  cardVisual
    * fontSize is in POINTS, not px: size 10 renders 13.333px, size 9 -> 12px.
      (This is the opposite of textbox and was the source of the collapsed
      trust badges.)
    * line box ~18px; vertical chrome ~26px.
    * horizontal chrome ~40px plain, ~72px once a background + border +
      radius are applied - which is why a 96px-wide badge truncated
      "Certified" down to an ellipsis.

Everything here is deliberately a little generous: clipping is visible and
embarrassing, a few px of slack is not.
"""
import math

TB_LINE = 21          # fixed paragraph line box
TB_VPAD = 12          # vertical chrome + 2px slack
TB_HPAD = 8           # horizontal chrome

CARD_LINE = 18
CARD_VPAD = 26
CARD_HPAD_PLAIN = 40
CARD_HPAD_PILL = 72   # background + border + radius

# Segoe UI advance width as a fraction of font px, measured across the
# rendered strings on the Executive page.
ADV_REG = 0.515
ADV_BOLD = 0.545


def pt_to_px(pt):
    """cardVisual font sizes are points."""
    return pt * 4.0 / 3.0


def adv(font_px, bold=False):
    return font_px * (ADV_BOLD if bold else ADV_REG)


def text_width(txt, font_px, bold=False):
    return len(txt) * adv(font_px, bold)


def wrap_lines(txt, usable_w, font_px, bold=False):
    """Greedy word wrap, matching how the browser breaks the paragraph."""
    if usable_w <= 0:
        return 1
    cw = adv(font_px, bold)
    lines, cur = 1, 0.0
    for word in txt.split():
        w = len(word) * cw
        step = w + (cw if cur else 0.0)
        if cur and cur + step > usable_w:
            lines += 1
            cur = w
        else:
            cur += step
    return lines


def tb_height(txt, box_w, font_px, bold=False, lines=None):
    n = lines if lines is not None else wrap_lines(txt, box_w - TB_HPAD, font_px, bold)
    return TB_LINE * n + TB_VPAD


def card_height(lines=1):
    return CARD_LINE * lines + CARD_VPAD


def card_min_width(sample_text, size_pt, pill=False, bold=False):
    """Narrowest box that will render sample_text on one line."""
    chrome = CARD_HPAD_PILL if pill else CARD_HPAD_PLAIN
    return int(math.ceil(text_width(sample_text, pt_to_px(size_pt), bold) + chrome))


def card_lines(txt, box_w, size_pt, pill=False, bold=False):
    chrome = CARD_HPAD_PILL if pill else CARD_HPAD_PLAIN
    return wrap_lines(txt, box_w - chrome, pt_to_px(size_pt), bold)
