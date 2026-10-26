# E-Paper 天氣月曆鐘

Raspberry Pi Pico 2 W + Waveshare 3.7" 電子紙的桌面型時間 / 天氣 / 月曆顯示器，MicroPython 撰寫，初次設定走自架 Wi-Fi 熱點 + Web UI，不需綁雲端 app。

## 硬體

| 元件 | 型號 |
|---|---|
| MCU | Raspberry Pi Pico 2 W (RP2350 + CYW43439) |
| 顯示 | Waveshare 3.7" e-Paper HAT，480 × 280，4 階灰 / 1-bit |
| 電源 | 18650 鋰電池 × 1 |

電子紙接腳（與 `Pico_ePaper_3_7.py` 一致）：

| Signal | GPIO |
|---|---|
| RST  | 12 |
| DC   | 8  |
| CS   | 9  |
| BUSY | 13 |
| SCK  | SPI1 default |
| MOSI | SPI1 default |

SPI baudrate 4 MHz。

## 功能

- 大字時鐘（12/24 小時切換）+ AM/PM，每分鐘部分刷新一次、不閃爍
- OpenWeather 當日天氣（圖示 + 溫度 + 中文描述），每天 11:00 / 23:00 全幀更新
- 月曆，今天日期反白；可選週日 / 週一為一週起始
- 右上角 Wi-Fi 強度圖示（5 級）
- 每天 23:59 透過 `time.apple.com` NTP 校時，支援時區 offset
- 初次設定的 AP + Web UI（RWD），mDNS 廣播 `epaper.local`
- 跨日自動重畫月曆、每月 1 號清空天氣 log

## 部署

不用 build，直接用 [MicroPico (paulober.pico-w-go)](https://marketplace.visualstudio.com/items?itemName=paulober.pico-w-go) VSCode extension 上傳：

1. 在 Pico 上燒 MicroPython 1.22+（rp2 / RPI_PICO2_W build）
2. 用 USB 連接，VSCode 開本專案
3. 右鍵專案根 → **Upload project to Pico**（會自動讀 `.vscode/settings.json` 裡的 `micropico.pyIgnore`，跳過 `*.md`、`fonts/`、`tools/`、`API/` 等開發用檔案）
4. **MicroPico: Soft reset Pico**（macOS 上 vREPL 的 `Ctrl-D` 會被終端機吃掉，改用 Command Palette）

第一次啟動沒有 `config.json` → 自動進入 AP 模式：

```
連線 Wi-Fi：ePaper
密碼：paper1234
用瀏覽器連線：
  http://192.168.4.1
  或 http://epaper.local
```

> AP 子網被 MicroPython rp2 CYW43 韌體硬碼成 `192.168.4.0/24`，無視 `ifconfig()` 設值（micropython/micropython#17401、#17977）；目前不可繞過。

進設定頁完成 Wi-Fi / 時區 / OpenWeather API Key + 城市選擇後存檔，裝置自動切到 STA、跑 NTP → 抓天氣 → 顯示主畫面；確認成功進入主畫面後，設定用 AP 會自動關閉以節省電力。Web Server 仍透過家中 Wi-Fi 的 STA 介面提供服務，可用 `http://epaper.local` 或 Pico 的 LAN IP 隨時修改設定。

## 設定（config.json）

```json
{
  "wifi":    { "ssid": "", "password": "" },
  "time":    { "is_24h": true, "week_start": 1, "tz_offset_min": 480 },
  "weather": {
    "api_key": "",
    "city": { "name": "Taipei", "lat": 25.04, "lon": 121.5 },
    "is_celsius": true
  }
}
```

- `week_start`：1 = 週一、7 = 週日
- `tz_offset_min`：UTC 偏移分鐘，預設 480（UTC+8）；NTP 拿 UTC 後加上 offset 寫入 RTC
- `is_celsius`：true = °C / false = °F

設定儲存後 Web Server 不停服務，可隨時改。

## 檔案地圖

```
main.py                    入口
app.py                     狀態機 / event loop 黏合層
scheduler.py               EV_MINUTE / EV_DAY / EV_NTP / EV_WEATHER / EV_WIFI_LEVEL 事件
config.py                  ConfigManager：載入 / 儲存 / 區段存取
wifi_manager.py            AP / STA 切換、scan、RSSI → 等級
web_server.py              Port 80 HTTP server (RWD 設定頁、城市清單、log 下載)
weather.py                 OpenWeather API + weather.log 寫入
ntp.py                     time.apple.com NTP 校時 + 時區 offset
mdns.py                    epaper.local 廣播（先試 LWIP 內建 responder，fallback 到 vendored mdns_client）
Pico_ePaper_3_7.py         Waveshare 3.7" 驅動（SPI、4 階 / 1-bit、partial refresh）
taiwan_cities.json         22 個台灣城市座標

display/
  canvas.py                FrameBuffer 包裝層 + commit_full / commit_part
  fonts.py                 字型 alias（FONT_BODY / FONT_SMALL / FONT_MONO / FONT_CLOCK / FONT_LABEL）
  icons.py                 PBM 載入
  screens/
    guide.py               初次設定導引畫面
    message.py             單行訊息畫面（初始化中、失敗 ...）
    calendar.py            月曆繪製
    main_screen.py         主畫面：時鐘 + 天氣 + 月曆 + WiFi

writer/                    peterhinch/micropython-font-to-py 的 Writer / CWriter
  noto12.py, noto20.py     從 NotoSansTC 產出，218 chars
  clock_big.py             大字時鐘用
  freesans20.py, font10.py, font6.py, courier20.py

wifi_icon/                 level0.pbm ~ level4.pbm
weather_icon/              OpenWeather code（01d-50n）96×96 PBM + weather_failed.pbm

lib/mdns_client/           vendored cbrand/micropython-mdns

API/                       Bruno API collection（dev only，不上 Pico）
fonts/                     字型 build 環境（dev only）
tools/                     host 端工具（dev only）
```

## 字型重 build

加新字到 `fonts/chars_used.txt` 後：

```bash
cd fonts
./build_fonts.sh   # 用 micropython-font-to-py + freetype-py
```

產出 `writer/noto12.py` 和 `writer/noto20.py`，重新上傳即可。`build_fonts.sh` 會自動建 `.venv` 裝 freetype-py。

## 天氣圖示重 build

來源是 OpenWeather 官方 PNG，轉成 96×96 PBM (P4)：

```bash
bash weather_icon/build_icons.sh    # 純 ImageMagick
# 或
python tools/fetch_weather_icons.py # Pillow 版
```

兩條流程都會做 autocontrast → unsharp → Floyd-Steinberg dither → 1-bit 二值化。

## 開發小技巧

- **觀察 REPL**：MicroPico extension → vREPL（VSCode 內建終端）
- **跳過 NTP 測跨日**：在 Pico 根目錄建空檔 `/.skip_ntp`，啟動時會跳過 NTP，可手動撥 RTC 測時間相關邏輯（記得測完刪掉）
- **mDNS 不通**：MicroPython rp2 1.22+ 韌體啟用 LWIP 內建 mDNS responder，呼叫 `network.hostname("epaper")` 就會廣播。若 `ping epaper.local` 仍失敗，先用 `sudo tcpdump -i en0 -nn udp port 5353` 確認封包有沒有發出
- **天氣 log 看歷史**：Web UI 直接下載 `weather.log`，格式見 `ProjectDetail.md`

## 參考文件

- `ProjectDetail.md` — 功能規格 / log 格式 / 流程
- `Pico-ePaper-3.7.md` — 電子紙驅動筆記
- `plant.md` — 實作進度與已知風險
- `CLAUDE.md` — Claude Code agent 提示
- `writer/WRITER.md` / `writer/DRIVERS.md` — Writer 套件文件

## 致謝

- [peterhinch/micropython-font-to-py](https://github.com/peterhinch/micropython-font-to-py) — Writer / 字型轉檔
- [cbrand/micropython-mdns](https://github.com/cbrand/micropython-mdns) — vendored mDNS client fallback
- Waveshare 3.7" e-Paper [driver 原始碼](https://github.com/waveshareteam/Pico_ePaper_Code)
- [OpenWeatherMap](https://openweathermap.org/) — 天氣資料與圖示
