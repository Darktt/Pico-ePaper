#!/usr/bin/env bash
# 產生 noto20.py (20px) 與 noto12.py (12px) CJK 字型，並輸出到 writer/。
#
# 前置作業（host 端）：
#   1. brew install python3 (或系統 python3)
#   2. git clone https://github.com/peterhinch/micropython-font-to-py.git
#      設定環境變數: export FONT_TO_PY=/path/to/micropython-font-to-py
#   3. 下載 NotoSansTC-Regular.otf 並放到本資料夾 (fonts/)
#      下載: https://fonts.google.com/noto/specimen/Noto+Sans+TC
#
# 執行:
#   bash fonts/build_fonts.sh

set -euo pipefail
HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ROOT="$(cd "$HERE/.." && pwd)"

FONT_TO_PY="${FONT_TO_PY:-}"
CHARS_FILE="$HERE/chars_used.txt"

# 自動偵測 NotoSansTC 字型（.ttf 優先，.otf 次之；可用 FONT_FILE 覆寫）
if [[ -z "${FONT_FILE:-}" ]]; then
  for cand in \
    "$HERE/NotoSansTC-Regular.ttf" \
    "$HERE/NotoSansTC-Regular.otf" \
    "$HERE/NotoSansTC.ttf" \
    "$HERE/NotoSansTC.otf"; do
    if [[ -f "$cand" ]]; then
      FONT_FILE="$cand"
      break
    fi
  done
fi

if [[ -z "$FONT_TO_PY" || ! -f "$FONT_TO_PY/font_to_py.py" ]]; then
  echo "請設定 FONT_TO_PY=/path/to/micropython-font-to-py 後再執行" >&2
  exit 1
fi

if [[ -z "${FONT_FILE:-}" || ! -f "$FONT_FILE" ]]; then
  echo "找不到字型檔，請把 NotoSansTC-Regular.ttf (或 .otf) 放到 $HERE/" >&2
  echo "或設定 FONT_FILE=/full/path/to/font.ttf" >&2
  exit 1
fi

echo "CJK 字型來源: $FONT_FILE"

PY="${PYTHON:-python3}"

# 去除空白與重複字元（用 Python 處理多 byte UTF-8）
CHAR_STR="$("$PY" -c '
import sys
seen=set(); out=[]
with open(sys.argv[1], encoding="utf-8") as f:
    for ch in f.read():
        if ch in "\n\r\t": continue   # 保留半形空白給 ASCII 句子排版
        if ch in seen: continue
        seen.add(ch); out.append(ch)
sys.stdout.write("".join(out))
' "$CHARS_FILE")"

CHAR_COUNT="$("$PY" -c "import sys; sys.stdout.write(str(len(sys.argv[1])))" "$CHAR_STR")"
echo "字元集 ($CHAR_COUNT 字)"

# font-to-py 不接受路徑型輸出檔名，需切換到目標目錄執行
pushd "$ROOT/writer" >/dev/null

"$PY" "$FONT_TO_PY/font_to_py.py" \
  "$FONT_FILE" 20 noto20.py -c "$CHAR_STR" -x

"$PY" "$FONT_TO_PY/font_to_py.py" \
  "$FONT_FILE" 12 noto12.py -c "$CHAR_STR" -x

# 大字時鐘字型（僅 0–9、冒號、空白）：用 Roboto Mono 或 Courier 之類等寬字
: "${CLOCK_FONT:=$HERE/RobotoMono-Regular.ttf}"
if [[ -f "$CLOCK_FONT" ]]; then
  echo "時鐘字型來源: $CLOCK_FONT"
  # 96 px 在 TIME_RECT(360x250) 會超寬，"HH:MM" 5 字超過 360；縮到 72 px
  "$PY" "$FONT_TO_PY/font_to_py.py" \
    "$CLOCK_FONT" 72 clock_big.py -c "0123456789: " -x
  echo "已產生 writer/clock_big.py"
else
  echo "略過 clock_big.py（找不到 $CLOCK_FONT；大字鐘將 fallback 到 courier20）"
fi

popd >/dev/null

echo "完成：writer/noto20.py, writer/noto12.py"
