#!/usr/bin/env python3
"""產生 5 個 32×20 px Wi-Fi 強度 icon (level0..4.pbm)。

使用純 Python stdlib，不需安裝任何套件。

執行:
    python3 tools/gen_wifi_icons.py

輸出檔案:
    wifi_icon/level0.pbm  — 無訊號 (僅外框)
    wifi_icon/level1.pbm  — 1 格
    wifi_icon/level2.pbm  — 2 格
    wifi_icon/level3.pbm  — 3 格
    wifi_icon/level4.pbm  — 4 格
"""

import os
import sys


WIDTH = 32
HEIGHT = 20
OUT_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "wifi_icon")


def make_canvas(w, h):
    return [[0 for _ in range(w)] for _ in range(h)]  # 0 = 白


def fill_rect(canvas, x, y, w, h, value=1):
    for j in range(y, y + h):
        if 0 <= j < len(canvas):
            for i in range(x, x + w):
                if 0 <= i < len(canvas[0]):
                    canvas[j][i] = value


def stroke_rect(canvas, x, y, w, h, value=1):
    fill_rect(canvas, x, y, w, 1, value)
    fill_rect(canvas, x, y + h - 1, w, 1, value)
    fill_rect(canvas, x, y, 1, h, value)
    fill_rect(canvas, x + w - 1, y, 1, h, value)


def draw_bars(level):
    """level: 0..4，回傳 32x20 canvas"""
    canvas = make_canvas(WIDTH, HEIGHT)

    # 4 根 bar 配置：bar 寬 5、間距 2、左右邊距 4
    # 4 bar 總寬 = 4*5 + 3*2 = 26，剩 32-26 = 6 → 各邊 3
    bar_w = 5
    gap = 2
    margin = 3

    # bar 高度遞增 (從下方對齊)
    heights = [5, 9, 13, 17]

    for i in range(4):
        x = margin + i * (bar_w + gap)
        bh = heights[i]
        y = HEIGHT - 1 - bh  # 底部對齊
        if i < level:
            fill_rect(canvas, x, y, bar_w, bh, 1)
        else:
            stroke_rect(canvas, x, y, bar_w, bh, 1)

    # level 0：在中央畫個 X 表示無訊號
    if level == 0:
        for d in range(8):
            canvas[6 + d][12 + d] = 1
            canvas[6 + d][19 - d] = 1

    return canvas


def write_pbm(canvas, path):
    h = len(canvas)
    w = len(canvas[0])
    row_bytes = (w + 7) // 8
    data = bytearray(row_bytes * h)
    for y in range(h):
        for x in range(w):
            if canvas[y][x]:
                byte_idx = y * row_bytes + (x // 8)
                bit = 7 - (x % 8)
                data[byte_idx] |= 1 << bit
    header = "P4\n{} {}\n".format(w, h).encode()
    with open(path, "wb") as f:
        f.write(header)
        f.write(data)


def main():
    out_dir = os.path.abspath(OUT_DIR)
    os.makedirs(out_dir, exist_ok=True)
    for level in range(5):
        canvas = draw_bars(level)
        path = os.path.join(out_dir, "level{}.pbm".format(level))
        write_pbm(canvas, path)
        print("已產生 {}".format(path))


if __name__ == "__main__":
    main()
