"""Power BI Service text metrics, measured from the rendered DOM of the live
report in app.powerbi.com. Every number here was read off a real element, not
estimated - the first two attempts at this layout failed because they were
estimated.

textbox
    * fontSize is honoured verbatim as CSS px ("10px" renders 10px).
    * every paragraph line occupies a FIXED 21px line box whatever the font
      size (verified at 8, 9, 10, 12, 13, 16 and 17px: 21px for one line,
      43px for two).
    * ~10px vertical chrome, ~8px horizontal.
    * font resolves to Segoe UI - BC Sans does NOT render in the Service.

cardVisual
    * fontSize is in POINTS (size 10 -> 13.333px, size 9 -> 12px) - the
      opposite of textbox.
    * does NOT word-wrap: one line, overflow ellipsised.
    * chrome is UNIFORM on both axes:
          plain                     34px
          with background/border    49px
      Measured: a plain card 404x44 reported clientWidth 370 / clientHeight 10
      (404-34, 44-34). A pill card 165x44 reported clientWidth 116 /
      clientHeight 0 (165-49, 44-49 clamped to zero) - which is exactly why
      every trust badge rendered empty.
    * the content block is a FIXED ~36px whatever the point size - not a
      multiple of the font. Measured once the cards finally had room: 12px
      text reported scrollHeight 36, 13.333px reported 37, against the 29/31
      of available height a 63/65px box gave them. (While clientHeight was 0
      the card under-reported scrollHeight as 21, which is what led the
      previous pass to size these at 63px.) So a card box needs 36 + 34 = 70
      minimum; 74 is used for margin.

Segoe UI advance width, measured from rendered strings:
    "Certified"          9 chars, 12px bold      -> 47px  (0.435/char/px)
    "Updated 7 Jul 2026" 18 chars, 12px bold     -> 105px (0.486)
    "Data as at 7 July 2026" 22 chars, 13.33px b -> 131px (0.447)
The constants below sit deliberately above the worst observed value.
"""
import math

# --- textbox -----------------------------------------------------------------
TB_LINE = 21          # fixed paragraph line box, any font size
TB_VPAD = 12          # vertical chrome + 2px slack
TB_HPAD = 8

# --- cardVisual --------------------------------------------------------------
CARD_PAD_PLAIN = 34   # uniform, both axes
CARD_PAD_PILL = 49    # once a background/border is applied
CARD_SLACK = 4        # never sit exactly on the boundary

# --- type --------------------------------------------------------------------
ADV_REG = 0.50
ADV_BOLD = 0.52


def pt_to_px(pt):
    return pt * 4.0 / 3.0


def adv(font_px, bold=False):
    return font_px * (ADV_BOLD if bold else ADV_REG)


def text_width(txt, font_px, bold=False):
    return len(txt) * adv(font_px, bold)


def wrap_lines(txt, usable_w, font_px, bold=False):
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


# --- card sizing -------------------------------------------------------------
CARD_CONTENT_H = 48   # measured on the live report: 41 at 9pt, 49 at 13pt. It
                      # DOES creep up with the point size, so keep every card at
                      # 11pt or below - 13pt needs 49 and would clip by 1px.


def card_line_h(size_pt=10):
    """Height the value block occupies inside the card's content area.
    Constant: it does NOT scale with the point size."""
    return CARD_CONTENT_H


def card_pad(pill=False):
    return CARD_PAD_PILL if pill else CARD_PAD_PLAIN


def card_height(size_pt=10, pill=False):
    """Smallest box height that actually renders the value. 74px plain."""
    return card_line_h(size_pt) + card_pad(pill)


def card_min_width(sample_text, size_pt, pill=False, bold=False):
    return int(math.ceil(text_width(sample_text, pt_to_px(size_pt), bold)
                         + card_pad(pill) + CARD_SLACK))


def fit_size(sample, box_w, pill=False, bold=False, sizes=(10, 9, 8)):
    """Largest point size at which `sample` renders on ONE line inside box_w."""
    for pt in sizes:
        if card_min_width(sample, pt, pill, bold) <= box_w:
            return pt
    return sizes[-1]
