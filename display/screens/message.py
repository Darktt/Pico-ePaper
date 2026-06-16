from writer.writer import Writer
from display.fonts import FONT_BODY
from display.screens import log_display, make_writer


def _text_width(font, s):
    """估算字串像素寬度（非完美，但 set_textpos 不會 raise）。"""
    w = 0
    try:
        for ch in s:
            g = font.get_ch(ch)
            # font-to-py 產生的字型 get_ch 通常回傳 (data, height, width)
            if isinstance(g, tuple) and len(g) >= 3:
                w += g[2]
            else:
                w += font.max_width()
    except Exception:
        w = len(s) * font.max_width()
    return w


def show(canvas, text, font=None):
    """畫面置中顯示單行訊息。"""
    if font is None:
        font = FONT_BODY
    log_display("message", text)
    canvas.clear()
    wri = make_writer(canvas, font)
    w = _text_width(font, text)
    h = font.height()
    x = max(0, (canvas.width - w) // 2)
    y = max(0, (canvas.height - h) // 2)
    Writer.set_textpos(canvas, y, x)
    wri.printstring(text)
    canvas.commit_full()
