#!/usr/bin/env bash
# 把 OpenWeather 官方圖示轉成 96×96 的 PBM P4 (1-bit) 給電子紙使用。
#
# 與 `tools/fetch_weather_icons.py` (Pillow) 等價，純 ImageMagick 流程：
#   level (8%,92%)：對比拉伸（OpenWeather 原圖灰階偏窄，不拉很淡）
#   unsharp     ：銳化邊緣
#   FS dither   ：保留漸層 + 1-bit
#
# 前置作業：
#   brew install imagemagick
#
# 執行:
#   bash weather_icon/build_icons.sh

set -euo pipefail
HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$HERE"

if command -v magick >/dev/null 2>&1; then
  MAGICK="magick"
elif command -v convert >/dev/null 2>&1; then
  MAGICK="convert"
else
  echo "找不到 ImageMagick，請先 brew install imagemagick" >&2
  exit 1
fi

SIZE="${SIZE:-96}"
CODES=(01d 01n 02d 02n 03d 03n 04d 04n 09d 09n 10d 10n 11d 11n 13d 13n 50d 50n)

ensure_p4() {
  # ImageMagick 預設 PBM 輸出可能是 P1 (ASCII)；強制轉成 P4 (raw binary)
  local f="$1"
  if head -c 2 "$f" | grep -q '^P1'; then
    $MAGICK "$f" -compress none -define pbm:raw=true "$f"
  fi
}

for code in "${CODES[@]}"; do
  url="https://openweathermap.org/img/wn/${code}@2x.png"
  echo "下載 $url"
  curl -fsSL "$url" -o "/tmp/${code}.png"
  $MAGICK "/tmp/${code}.png" \n    -background white -alpha remove -alpha off \n    -filter Lanczos -resize "${SIZE}x${SIZE}" \n    -level 8%,92% \n    -unsharp 0x1+1.2+0.02 \n    -dither FloydSteinberg \n    -monochrome \n    -compress none \n    "${code}.pbm"
  ensure_p4 "${code}.pbm"
done

# 失敗用 icon — 三角警告 + 中央驚嘆號
$MAGICK -size "${SIZE}x${SIZE}" xc:white \n  -fill black -draw "polygon $((SIZE/2)),6 $((SIZE-6)),$((SIZE-6)) 6,$((SIZE-6))" \n  -fill white \n  -draw "rectangle $((SIZE/2-3)),24 $((SIZE/2+3)),$((SIZE-26))" \n  -draw "rectangle $((SIZE/2-3)),$((SIZE-20)) $((SIZE/2+3)),$((SIZE-12))" \n  -threshold 50% \n  -compress none \n  weather_failed.pbm
ensure_p4 weather_failed.pbm

echo "完成：$(ls -1 *.pbm | wc -l | tr -d ' ') 個 PBM 圖示已建立（${SIZE}×${SIZE}）"
