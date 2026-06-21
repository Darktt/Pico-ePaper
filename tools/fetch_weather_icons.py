#!/usr/bin/env python3
"""下載 OpenWeather 官方 icon，轉成 80×80 PBM P4 給 e-paper 使用。

需要 Pillow:
    python3 -m venv /tmp/pbmvenv
    /tmp/pbmvenv/bin/pip install Pillow

執行:
    /tmp/pbmvenv/bin/python tools/fetch_weather_icons.py

來源: https://openweathermap.org/img/wn/<code>@2x.png
"""

import os
import sys
import urllib.request

from PIL import Image, ImageFilter, ImageOps


CODES = [
    "01d", "01n", "02d", "02n", "03d", "03n", "04d", "04n",
    "09d", "09n", "10d", "10n", "11d", "11n", "13d", "13n",
    "50d", "50n",
]
# WEATHER_RECT 120×140；text 區（temp 20 + 4 + desc 12 = 36）佔下方
# 約 40px，icon 留 96×96 上方置中。
SIZE = 96
OUT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "weather_icon")


def fetch(code):
    url = "https://openweathermap.org/img/wn/{}@2x.png".format(code)
    print("下載", url)
    with urllib.request.urlopen(url, timeout=30) as r:
        return r.read()


def to_pbm(png_bytes, code):
    from io import BytesIO
    img = Image.open(BytesIO(png_bytes))
    # 合成到白底（處理透明背景）
    if img.mode != "RGBA":
        img = img.convert("RGBA")
    bg = Image.new("RGBA", img.size, (255, 255, 255, 255))
    bg.paste(img, mask=img.split()[3])
    img = bg.convert("L")
    img = img.resize((SIZE, SIZE), Image.LANCZOS)
    # OpenWeather 原圖灰階範圍窄（多落在 200–255），直接 dither 出來像素稀疏 → 灰白一片。
    # 流程：autocontrast 拉到滿幅 → 輕銳化加邊緣 → FS dither 保留漸層。
    img = ImageOps.autocontrast(img, cutoff=8)
    img = img.filter(ImageFilter.UnsharpMask(radius=1, percent=120, threshold=2))
    img = img.convert("1", dither=Image.FLOYDSTEINBERG)

    # PIL "1" mode: 0 = 黑、255 = 白。PBM P4: bit 1 = 黑、bit 0 = 白。
    row_bytes = (SIZE + 7) // 8
    data = bytearray(row_bytes * SIZE)
    pixels = img.load()
    for y in range(SIZE):
        for x in range(SIZE):
            if pixels[x, y] == 0:  # 黑
                bidx = y * row_bytes + (x // 8)
                bit = 7 - (x % 8)
                data[bidx] |= 1 << bit
    return data


def write_pbm(data, path, w=SIZE, h=SIZE):
    with open(path, "wb") as f:
        f.write("P4\n{} {}\n".format(w, h).encode())
        f.write(data)


def main():
    os.makedirs(OUT, exist_ok=True)
    failed = []
    for code in CODES:
        try:
            png = fetch(code)
            data = to_pbm(png, code)
            write_pbm(data, os.path.join(OUT, code + ".pbm"))
        except Exception as e:
            print("  失敗:", code, e)
            failed.append(code)

    # weather_failed.pbm: 簡單三角警告
    img = Image.new("L", (SIZE, SIZE), 255)
    from PIL import ImageDraw
    d = ImageDraw.Draw(img)
    d.polygon([(SIZE // 2, 6), (SIZE - 6, SIZE - 6), (6, SIZE - 6)], fill=0)
    # 中央驚嘆號（白）
    d.rectangle([SIZE // 2 - 3, 24, SIZE // 2 + 3, SIZE - 26], fill=255)
    d.rectangle([SIZE // 2 - 3, SIZE - 20, SIZE // 2 + 3, SIZE - 12], fill=255)
    bw = img.convert("1", dither=Image.NONE)
    row_bytes = (SIZE + 7) // 8
    data = bytearray(row_bytes * SIZE)
    px = bw.load()
    for y in range(SIZE):
        for x in range(SIZE):
            if px[x, y] == 0:
                bidx = y * row_bytes + (x // 8)
                bit = 7 - (x % 8)
                data[bidx] |= 1 << bit
    write_pbm(data, os.path.join(OUT, "weather_failed.pbm"))

    print()
    print("已產生 {} / {} 個 icon + weather_failed.pbm".format(len(CODES) - len(failed), len(CODES)))
    if failed:
        print("失敗:", failed)
        sys.exit(1)


if __name__ == "__main__":
    main()
