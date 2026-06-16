from machine import RTC
from writer.writer import Writer
from display import icons
from display.fonts import FONT_BODY, FONT_SMALL, FONT_MONO, FONT_CLOCK, FONT_LABEL
from display.screens import calendar as cal_screen
from display.screens import log_display, make_writer


# Landscape 排版常數
TIME_RECT = (0, 30, 360, 250)
WIFI_RECT = (440, 0, 40, 28)
WEATHER_RECT = (360, 30, 120, 140)
CAL_RECT = (360, 170, 120, 110)


def _fmt_time(hour, minute, is_24h):
    if is_24h:
        return "{:02d}:{:02d}".format(hour, minute), None
    am = hour < 12
    h12 = hour % 12 or 12
    return "{:02d}:{:02d}".format(h12, minute), ("AM" if am else "PM")


def _wifi_icon_path(level):
    return "wifi_icon/level{}.pbm".format(max(0, min(4, level)))


def _weather_icon_path(code):
    return "weather_icon/{}.pbm".format(code)


_wifi_icon_warned = False


def _draw_wifi(canvas, level):
    global _wifi_icon_warned
    x, y, w, h = WIFI_RECT
    canvas.fill_rect(x, y, w, h, 1)
    path = _wifi_icon_path(level)
    if icons.exists(path):
        try:
            fb, iw, ih = icons.load_pbm(path)
            ix = x + (w - iw) // 2
            iy = y + (h - ih) // 2
            canvas.blit(fb, ix, iy)
            return
        except Exception as e:
            print("[EPD] wifi icon 載入失敗 {}: {}".format(path, e))
    else:
        if not _wifi_icon_warned:
            print("[EPD] 找不到 {}（請確認 wifi_icon/ 已上傳到 Pico）".format(path))
            _wifi_icon_warned = True
    # Fallback：寫 "L{n}"
    canvas.text("L{}".format(level), x + 4, y + 8, 0)


def _draw_time(canvas, hour, minute, is_24h):
    x, y, w, h = TIME_RECT
    canvas.fill_rect(x, y, w, h, 1)

    time_str, ampm = _fmt_time(hour, minute, is_24h)

    # 大字時鐘：用 FONT_CLOCK（若有則用，否則 FONT_MONO 大字 fallback）
    font = FONT_CLOCK
    wri = make_writer(canvas, font)

    def _strwidth(f, s):
        try:
            return sum(f.get_ch(c)[2] for c in s)
        except Exception:
            return len(s) * f.max_width()

    tw = _strwidth(font, time_str)
    th = font.height()

    # 12h 時把 AM/PM 一起納入「整塊」的置中計算，避免 tx 算成負值
    ampm_gap = 8
    ampm_w = _strwidth(FONT_LABEL, ampm) if ampm else 0
    total_w = tw + (ampm_gap + ampm_w if ampm else 0)

    tx = x + (w - total_w) // 2
    ty = y + (h - th) // 2

    # 防呆：時鐘字型超寬時也別讓 set_textpos 拋例外
    tx = max(x, min(canvas.width - 1, tx))
    ty = max(y, min(canvas.height - 1, ty))

    Writer.set_textpos(canvas, ty, tx)
    try:
        wri.printstring(time_str)
    except Exception:
        canvas.text(time_str, tx, ty, 0)

    if ampm:
        small = make_writer(canvas, FONT_LABEL)
        ax = max(x, min(canvas.width - 1, tx + tw + ampm_gap))
        ay = max(y, min(canvas.height - 1,
                        ty + th - FONT_LABEL.height()))
        Writer.set_textpos(canvas, ay, ax)
        try:
            small.printstring(ampm)
        except Exception:
            canvas.text(ampm, ax, ay, 0)


_weather_icon_warned = set()


def _draw_weather(canvas, weather, is_celsius):
    x, y, w, h = WEATHER_RECT
    canvas.fill_rect(x, y, w, h, 1)

    # icon 高度依實際載到的 PBM 動態決定（96×96 為主，但 fallback 也適用）
    icon_top = y + 2
    icon_bottom = icon_top + 96  # 預設值，沒載 icon 也好讓文字位置不亂跳

    if weather and weather.get("ok"):
        icon_code = weather.get("icon", "")
        path = _weather_icon_path(icon_code)
        if icons.exists(path):
            try:
                fb, iw, ih = icons.load_pbm(path)
                ix = x + (w - iw) // 2
                canvas.blit(fb, ix, icon_top)
                icon_bottom = icon_top + ih
            except Exception as e:
                print("[EPD] weather icon 載入失敗 {}: {}".format(path, e))
        elif path not in _weather_icon_warned:
            print("[EPD] 找不到 {}（請確認 weather_icon/ 已上傳到 Pico）".format(path))
            _weather_icon_warned.add(path)
        temp = weather.get("temp", 0)
        unit = "C" if is_celsius else "F"
        temp_str = "{:.0f}{}".format(temp, unit)
        desc = weather.get("desc", "")

        temp_y = icon_bottom + 4
        wri_body = make_writer(canvas, FONT_BODY)
        Writer.set_textpos(canvas, temp_y, x + 8)
        try:
            wri_body.printstring(temp_str)
        except Exception:
            canvas.text(temp_str, x + 8, temp_y, 0)

        desc_y = temp_y + FONT_BODY.height() + 4
        wri_small = make_writer(canvas, FONT_SMALL)
        Writer.set_textpos(canvas, desc_y, x + 4)
        try:
            wri_small.printstring(desc)
        except Exception:
            canvas.text(desc[:12], x + 4, desc_y, 0)
    else:
        # 失敗：顯示 weather_failed.pbm + 錯誤訊息
        path = "weather_icon/weather_failed.pbm"
        if icons.exists(path):
            try:
                fb, iw, ih = icons.load_pbm(path)
                ix = x + (w - iw) // 2
                canvas.blit(fb, ix, icon_top)
                icon_bottom = icon_top + ih
            except Exception:
                pass
        err = (weather or {}).get("error", "no data")
        err_y = icon_bottom + 4
        wri_small = make_writer(canvas, FONT_SMALL)
        Writer.set_textpos(canvas, err_y, x + 4)
        try:
            wri_small.printstring(err[:14])
        except Exception:
            canvas.text(err[:14], x + 4, err_y, 0)


def _draw_calendar(canvas, year, month, today, week_start):
    x, y, w, h = CAL_RECT
    cal_screen.render(canvas, year, month, today, week_start, x, y, w, h)


def render_full(canvas, config, weather, wifi_level):
    """主畫面全幀重繪 — 用於初次進入 RUN、weather 重新抓取後。"""
    rtc = RTC()
    now = rtc.datetime()
    year, month, day = now[0], now[1], now[2]
    hour, minute = now[4], now[5]
    is_24h = bool(config.get("time", "is_24h"))
    week_start = config.get("time", "week_start") or 1
    is_celsius = bool(config.get("weather", "is_celsius"))

    time_str, ampm = _fmt_time(hour, minute, is_24h)
    if weather and weather.get("ok"):
        w_part = "weather={:.0f}{} {}".format(
            weather.get("temp", 0),
            "C" if is_celsius else "F",
            weather.get("desc", ""))
    else:
        w_part = "weather=FAIL ({})".format((weather or {}).get("error", "no data"))
    log_display(
        "main_full",
        "time={}{}".format(time_str, " " + ampm if ampm else ""),
        "wifi=L{}".format(wifi_level),
        w_part,
        "cal={:04d}-{:02d}-{:02d} week_start={}".format(year, month, day, week_start),
    )

    canvas.clear()
    _draw_wifi(canvas, wifi_level)
    _draw_time(canvas, hour, minute, is_24h)
    _draw_weather(canvas, weather, is_celsius)
    _draw_calendar(canvas, year, month, day, week_start)
    canvas.commit_full()


def render_time(canvas, config):
    """每分鐘 tick — 只重繪時間區並部分刷新。"""
    rtc = RTC()
    now = rtc.datetime()
    hour, minute = now[4], now[5]
    is_24h = bool(config.get("time", "is_24h"))
    time_str, ampm = _fmt_time(hour, minute, is_24h)
    log_display("main_time(part)", "{}{}".format(time_str, " " + ampm if ampm else ""))
    _draw_time(canvas, hour, minute, is_24h)
    canvas.commit_part(TIME_RECT)


def render_wifi(canvas, level):
    """Wi-Fi 等級變化時 — 只重繪右上角 icon。"""
    log_display("main_wifi(part)", "L{}".format(level))
    _draw_wifi(canvas, level)
    canvas.commit_part(WIFI_RECT)


def render_calendar(canvas, config):
    """NTP 同步後 — 只重繪月曆區（規格 6.4）。"""
    rtc = RTC()
    now = rtc.datetime()
    year, month, day = now[0], now[1], now[2]
    week_start = config.get("time", "week_start") or 1
    log_display(
        "main_calendar(part)",
        "{:04d}-{:02d} today={} week_start={}".format(year, month, day, week_start),
    )
    _draw_calendar(canvas, year, month, day, week_start)
    canvas.commit_part(CAL_RECT)
