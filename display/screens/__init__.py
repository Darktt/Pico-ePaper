def log_display(label, *parts):
    """把即將寫到電子紙上的文字摘要印到 REPL，方便確認顯示內容。"""
    try:
        text = " | ".join(str(p) for p in parts)
        print("[EPD] {}: {}".format(label, text))
    except Exception:
        pass


def make_writer(canvas, font):
    """建立 Writer 並讓字型正確顯示為白底黑字。

    writer.Writer 的 mono `_printchar` 完全不使用 bgcolor / fgcolor，
    而是直接 `device.blit(framebuf(glyph_buf), ...)`；對 1-bit blit
    source bit 1 → target bit 1。字型 1 = 字、0 = 背景，但 LandscapeCanvas
    約定 1 = 白、0 = 黑，所以直接畫出來會是「黑底白字」（與相機看到的反白
    一致）。`_printchar(invert=True)` 會把 glyph buf 反相 → 字 = 0 = 黑、
    背景 = 1 = 白。

    因此這裡包一層 printstring，預設加上 invert；calendar 等需要「強調黑底
    白字」的呼叫端傳 invert=True 仍能取消這層翻轉，語意維持自然。
    """
    from writer.writer import Writer
    wri = Writer(canvas, font, verbose=False)
    wri.bgcolor = 1
    wri.fgcolor = 0
    _orig = wri.printstring

    def _ps(s, invert=False):
        return _orig(s, not invert)

    wri.printstring = _ps
    return wri
