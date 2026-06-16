from writer.writer import Writer
from display.fonts import FONT_BODY
from display.screens import log_display, make_writer


def _text_width(font, s):
    w = 0
    try:
        for ch in s:
            g = font.get_ch(ch)
            if isinstance(g, tuple) and len(g) >= 3:
                w += g[2]
            else:
                w += font.max_width()
    except Exception:
        w = len(s) * font.max_width()
    return w


def show(canvas, wifi_info):
    """初次設定導引畫面：顯示 SSID、密碼、IP、mDNS Domain。"""
    canvas.clear()
    wri = make_writer(canvas, FONT_BODY)
    lines = [
        "連線 Wi-Fi：{}".format(wifi_info.get("ssid", "")),
        "密碼：{}".format(wifi_info.get("password", "")),
        "用瀏覽器連線到以下網址完成初次設定",
        "http://{}".format(wifi_info.get("ip", "")),
        "或",
        "http://{}".format(wifi_info.get("domain", "")),
    ]
    log_display("guide", *lines)

    line_h = FONT_BODY.height() + 6
    total_h = line_h * len(lines)
    start_y = max(0, (canvas.height - total_h) // 2)

    y = start_y
    for line in lines:
        w = _text_width(FONT_BODY, line)
        x = max(0, (canvas.width - w) // 2)
        Writer.set_textpos(canvas, y, x)
        wri.printstring(line)
        y += line_h

    canvas.commit_full()
