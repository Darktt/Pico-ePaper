"""集中字型匯入。

CJK 字型（noto20 / noto12）需用 host 端 font-to-py 從 NotoSansTC 產生，
位置：writer/noto20.py / writer/noto12.py。
若還未生成，fallback 到既有英數字型 freesans20 / font10，畫面上中文會變方框。

使用法：
    from display.fonts import FONT_BODY, FONT_SMALL, FONT_MONO, FONT_LABEL
    Writer(canvas.fb, FONT_BODY).printstring("...")
"""

import writer.freesans20 as freesans20
import writer.courier20 as courier20
import writer.font10 as font10
import writer.font6 as font6


def _try_import(modname):
    try:
        return __import__("writer." + modname, None, None, [modname])
    except Exception:
        return None


_noto20 = _try_import("noto20")
_noto12 = _try_import("noto12")
_big_clock = _try_import("clock_big")  # 可選的大字鐘字型

# 對外名稱
FONT_BODY = _noto20 if _noto20 is not None else freesans20  # 主要 UI 文字（中文）
FONT_SMALL = _noto12 if _noto12 is not None else font10     # 月曆與小字
FONT_MONO = courier20                                       # 數字（時間）
FONT_LABEL = freesans20                                     # ASCII 標籤
FONT_TINY = font6                                           # 極小提示
FONT_CLOCK = _big_clock if _big_clock is not None else courier20  # 大時鐘


HAS_CJK = _noto20 is not None
