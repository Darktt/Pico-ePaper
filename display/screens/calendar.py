import utime
from writer.writer import Writer
from display.fonts import FONT_SMALL
from display.screens import make_writer


WEEK_DAYS_MON = ["一", "二", "三", "四", "五", "六", "日"]
WEEK_DAYS_SUN = ["日", "一", "二", "三", "四", "五", "六"]


def _days_in_month(year, month):
    if month == 12:
        nxt = utime.mktime((year + 1, 1, 1, 0, 0, 0, 0, 0))
    else:
        nxt = utime.mktime((year, month + 1, 1, 0, 0, 0, 0, 0))
    cur = utime.mktime((year, month, 1, 0, 0, 0, 0, 0))
    return int((nxt - cur) // 86400)


def _first_weekday(year, month, week_start):
    """回傳該月 1 號在週曆中的欄位 index (0 = 該週起始日)。"""
    wd = utime.localtime(utime.mktime((year, month, 1, 0, 0, 0, 0, 0)))[6]
    # MicroPython: weekday 0=Mon..6=Sun
    if week_start == 7:  # 週日開始
        return (wd + 1) % 7
    return wd  # 週一開始


def _strwidth(font, s):
    try:
        return sum(font.get_ch(c)[2] for c in s)
    except Exception:
        return len(s) * font.max_width()


def render(canvas, year, month, today, week_start, x, y, w, h, font=None):
    """於 (x, y, w, h) 區域繪製月曆；不 commit，由呼叫端決定全刷/部分刷新。
    版面：上方月份置中 → 星期標頭 → 6 列日期；今天反白。
    """
    if font is None:
        font = FONT_SMALL

    # 清空指定區塊（白）
    canvas.fill_rect(x, y, w, h, 1)

    wri = make_writer(canvas, font)
    fh = font.height()

    # 月份標頭（置中）— 字型內若沒「月」字會 fallback 為 "YYYY-MM" ASCII。
    month_str = "{}月".format(month)
    mw = _strwidth(font, month_str)
    mx = x + (w - mw) // 2
    month_h = fh + 2
    Writer.set_textpos(canvas, y, mx)
    try:
        wri.printstring(month_str)
    except Exception:
        canvas.text("{}-{:02d}".format(year, month), x + 2, y, 0)

    # 星期標頭：一二三四五六日
    week_days = WEEK_DAYS_SUN if week_start == 7 else WEEK_DAYS_MON
    cols = 7
    col_w = w // cols
    header_y = y + month_h
    header_h = fh + 2
    for i, wd in enumerate(week_days):
        cx = x + i * col_w + 2
        Writer.set_textpos(canvas, header_y, cx)
        try:
            wri.printstring(wd)
        except Exception:
            # 無中文字型 fallback
            canvas.text(["Mo", "Tu", "We", "Th", "Fr", "Sa", "Su"][i],
                        cx, header_y, 0)

    # 日期格（最多 6 列；row_h 配合容器高度避免溢出 CAL_RECT）
    date_y0 = header_y + header_h
    avail = h - month_h - header_h
    row_h = max(fh, avail // 6)

    first_col = _first_weekday(year, month, week_start)
    days = _days_in_month(year, month)
    row = 0
    col = first_col
    for d in range(1, days + 1):
        cx = x + col * col_w + 2
        cy = date_y0 + row * row_h
        if d == today:
            canvas.fill_rect(cx - 2, cy - 1, col_w, row_h, 0)
            Writer.set_textpos(canvas, cy, cx)
            try:
                wri.printstring(str(d), invert=True)
            except Exception:
                canvas.text(str(d), cx, cy, 1)
        else:
            Writer.set_textpos(canvas, cy, cx)
            try:
                wri.printstring(str(d))
            except Exception:
                canvas.text(str(d), cx, cy, 0)
        col += 1
        if col >= 7:
            col = 0
            row += 1
