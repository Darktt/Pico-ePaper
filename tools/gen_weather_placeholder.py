#!/usr/bin/env python3
"""產生 80×80 weather icon 佔位符 (純 Python，無外部依賴)。

執行: python3 tools/gen_weather_placeholder.py

每個 icon 中央寫上 OpenWeather code 文字（內建 8×8 字型）。
產出之後可用 ImageMagick (weather_icon/build_icons.sh) 替換為真實圖檔。
"""

import os
import sys


W, H = 80, 80
CODES = [
    "01d", "01n", "02d", "02n", "03d", "03n", "04d", "04n",
    "09d", "09n", "10d", "10n", "11d", "11n", "13d", "13n",
    "50d", "50n",
]
FAILED = "weather_failed"


# 簡易 5×7 數字 + 英文字母字型 (僅作為佔位)
FONT_5x7 = {
    "0": ["01110","10001","10011","10101","11001","10001","01110"],
    "1": ["00100","01100","00100","00100","00100","00100","01110"],
    "2": ["01110","10001","00001","00010","00100","01000","11111"],
    "3": ["01110","10001","00001","00110","00001","10001","01110"],
    "4": ["00010","00110","01010","10010","11111","00010","00010"],
    "5": ["11111","10000","11110","00001","00001","10001","01110"],
    "6": ["00110","01000","10000","11110","10001","10001","01110"],
    "7": ["11111","00001","00010","00100","01000","01000","01000"],
    "8": ["01110","10001","10001","01110","10001","10001","01110"],
    "9": ["01110","10001","10001","01111","00001","00010","01100"],
    "d": ["00001","00001","00001","01111","10001","10001","01111"],
    "n": ["00000","00000","11110","10001","10001","10001","10001"],
    "_": ["00000","00000","00000","00000","00000","00000","11111"],
    "f": ["00110","01001","01000","11110","01000","01000","01000"],
    "a": ["00000","00000","01110","00001","01111","10001","01111"],
    "i": ["00100","00000","01100","00100","00100","00100","01110"],
    "l": ["01100","00100","00100","00100","00100","00100","01110"],
    "e": ["01110","10001","11111","10000","10000","10001","01110"],
}


def make_canvas():
    return [[0] * W for _ in range(H)]


def fill_rect(c, x, y, w, h, v=1):
    for j in range(y, y + h):
        for i in range(x, x + w):
            if 0 <= i < W and 0 <= j < H:
                c[j][i] = v


def stroke_rect(c, x, y, w, h, v=1):
    fill_rect(c, x, y, w, 1, v)
    fill_rect(c, x, y + h - 1, w, 1, v)
    fill_rect(c, x, y, 1, h, v)
    fill_rect(c, x + w - 1, y, 1, h, v)


def draw_char(c, ch, ox, oy, scale=2):
    if ch not in FONT_5x7:
        return
    rows = FONT_5x7[ch]
    for y, row in enumerate(rows):
        for x, bit in enumerate(row):
            if bit == "1":
                fill_rect(c, ox + x * scale, oy + y * scale, scale, scale, 1)


def draw_text(c, s, ox, oy, scale=2):
    cw = 6 * scale
    for i, ch in enumerate(s):
        draw_char(c, ch, ox + i * cw, oy, scale)


def draw_placeholder(code):
    c = make_canvas()
    stroke_rect(c, 4, 4, W - 8, H - 8, 1)
    # 中央寫上 code
    text_w = len(code) * 6 * 2
    tx = (W - text_w) // 2
    ty = (H - 7 * 2) // 2
    draw_text(c, code, tx, ty, scale=2)
    return c


def write_pbm(c, path):
    row_bytes = (W + 7) // 8
    data = bytearray(row_bytes * H)
    for y in range(H):
        for x in range(W):
            if c[y][x]:
                bidx = y * row_bytes + (x // 8)
                bit = 7 - (x % 8)
                data[bidx] |= 1 << bit
    with open(path, "wb") as f:
        f.write("P4\n{} {}\n".format(W, H).encode())
        f.write(data)


def main():
    out = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "weather_icon"))
    os.makedirs(out, exist_ok=True)
    for code in CODES:
        write_pbm(draw_placeholder(code), os.path.join(out, code + ".pbm"))
    # weather_failed: 中央三角警告
    c = make_canvas()
    for y in range(8, 72):
        span = (y - 8) * 32 // 64
        for x in range(40 - span, 40 + span):
            c[y][x] = 1
    fill_rect(c, 38, 28, 4, 22, 0)
    fill_rect(c, 38, 56, 4, 6, 0)
    write_pbm(c, os.path.join(out, "weather_failed.pbm"))
    print("已產生 {} + weather_failed.pbm 至 weather_icon/".format(len(CODES)))


if __name__ == "__main__":
    main()
