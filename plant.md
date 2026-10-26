# E-Paper 天氣顯示專案 — ProjectDetail.md 對齊計畫

## 實作進度 (2026-10-26)

> 此區為現況快照；下方各章為原始設計細節，供細節參考。

### 已完成 ✅

**程式碼模組 (13 個，全部通過 `python3 -m ast` 語法檢查)**

| 檔案 | 行數 / 大小 | 功能 |
|---|---|---|
| `main.py` | 11 行 | bootstrap → `App().run()` |
| `app.py` | 12 KB | FSM 主控 (BOOT → AP → STA_TRY → INIT → RUN)；`_enter_run` 主畫面畫完後若 AP 仍開就 `stop_ap()`；`request_reinit(delay_ms)` 可延遲觸發 INIT |
| `config.py` | 3 KB | ConfigManager + `batch()`；`time.tz_offset_minutes` (預設 480 = UTC+8) |
| `wifi_manager.py` | 3.9 KB | AP/STA + `scan()` + `rssi_to_level()`；`__init__` 設 `network.hostname("epaper")` 觸發 LWIP 內建 mDNS（若韌體支援）|
| `weather.py` | 3.7 KB | OpenWeather fetch + log + 月初 rotate |
| `ntp.py` | 0.8 KB | NTP sync time.apple.com (30s timeout)；套用 `tz_offset_minutes` 寫入本地時間 |
| `scheduler.py` | 2 KB | 1Hz poll RTC，5 種事件（含 `EV_DAY`：跨日 / 跨月 / 跨年偵測）|
| `web_server.py` | 17 KB | uasyncio + 多頁 `/wifi/scan/time/weather/done/weather.log` + RWD；`/time` 加時區下拉（UTC−12～+14，含半小時時區）；POST `/weather` 以 `delay_ms=1500` 觸發 reinit，確保 `/done` redirect 先經 AP 送達 |
| `mdns.py` | 4.6 KB | 偵測 LWIP 內建 mDNS（Pico W 1.22+）有沒有 active；有就讓韌體廣播，沒有才退回 vendored mdns_client + 把 `_init_socket` monkey-patch 成綁 `0.0.0.0` 而非 multicast addr；IP 切換重建、顯式追蹤 consume task、`wait_for` 退出、3 次退避重試 |
| `display/canvas.py` | 5 KB | 480×280 landscape FB + 轉置到 280×480 native；`@micropython.viper` 加速 `_transpose_cw_viper` 直接 bit-pack 操作底層 buffer；`commit_full` / `commit_part` 之間不 `init/Sleep`，讓 controller 內部 0x26 舊框 RAM 自然追蹤面板狀態，DU LUT 才能算對 transition 把舊像素擦乾淨 |
| `display/icons.py` | 2.4 KB | PBM P4 載入 + LRU cache |
| `display/fonts.py` | 1.3 KB | 字型集中匯出 + fallback |
| `display/screens/{guide,message,calendar,main_screen}.py` | 0.9–5.7 KB | 四個畫面；render 入口呼叫 `log_display()` 把文字鏡像到 REPL（`[EPD] ...`）|
| `display/screens/__init__.py` | <1 KB | `log_display()` + `make_writer()`（wrap `printstring` 預設 invert，解 Writer 不吃 bg/fg 的反白）|

**資產（已產出且驗證）**

| 類別 | 內容 | 來源 |
|---|---|---|
| CJK 字型 | `writer/noto20.py` (55 KB)、`writer/noto12.py` (29 KB) | NotoSansTC-Regular.ttf，218 字（ASCII printable + `：，⋯（）` 全形標點 + `月年` 月曆 + 天氣描述補字 `小中大暴陣凍毛細夾薄煙霾沙塵土火山灰颮龍捲風少散朗強烈`）|
| 時鐘字型 | `writer/clock_big.py` | RobotoMono-Regular.ttf, 72 px（96 px 時 `HH:MM` 295 → 395 px 會超出 TIME_RECT.w=360）|
| Wi-Fi icons | `wifi_icon/level0..4.pbm` | `tools/gen_wifi_icons.py` |
| 天氣 icons | `weather_icon/01d..50n.pbm` (18 個) + `weather_failed.pbm` | OpenWeather @2x → autocontrast + UnsharpMask + Floyd-Steinberg dither，輸出 96×96 P4（黑像素 15–21%）|
| mDNS 套件 | `lib/mdns_client/` | github.com/cbrand/micropython-mdns |
| Build 腳本 | `fonts/build_fonts.sh`, `tools/gen_*.py`, `tools/fetch_weather_icons.py` | — |
| 上傳忽略清單 | `.gitignore` (含 mDns/, fonts/, tools/, API/, *.md, *.sh) | — |

### 待辦 ⏳

1. **實機驗證初次設定後自動關 AP** — 手機經 AP 完成 `/weather` 設定 → 應收到 `/done` → NTP + 天氣成功進 RUN 後 AP 消失；之後 `http://epaper.local` / LAN IP 仍可開設定頁。另測 NTP / 天氣失敗時 AP 保留

### 近期實測通過 ✅

- **部分刷新殘影** — `commit_full` / `commit_part` 之間移除 `init()` + `Sleep()` 後，DU LUT 正確算 transition，時鐘區跨分鐘乾淨換字、無 ghosting
- **跨日 / 跨月月曆刷新** — `scheduler.EV_DAY` 在 `_last_day != now[2]` 時 emit；`app._on_day` → `render_calendar` → `commit_part(CAL_RECT)`；以 `/.skip_ntp` 旗標 + REPL 撥 RTC 驗證 2026-06-14 → 06-15、06-30 → 07-01 切換正常
- **月份標頭字型** — `chars_used.txt` 補「月年」後重 build，noto12 / noto20 出字正常
- **mDNS `epaper.local` 解析** — 韌體內建 lwIP mDNS responder + `network.hostname("epaper")` 即可廣播；`mdns.py` 偵測到 5353 已被佔即跳過 vendored client。mac 端 `ping epaper.local` / `dns-sd -G v4v6 epaper.local` 可解到 STA IP
- **`weather.fetch` 不阻塞 event loop** — `weather.fetch_async` 用 `_thread.start_new_thread` 把 sync `fetch` 丟到 RP2350 第二核心跑，主核心每 200 ms `await asyncio.sleep_ms` poll 完成旗標。最壞 190 s (3 × 60 s timeout + 2 × 5 s gap) 期間 web / scheduler / 部分刷新照常運作；`_thread_busy` flag 防重入；不可用時 fallback 回同步 `fetch`

### 測試輔助

- `/.skip_ntp` 旗標檔：`app._enter_init` 與 `_on_ntp_tick` 都會檢查，存在時跳過 NTP 不蓋 RTC。production build 不會夾帶此檔；測試完用 `os.remove('/.skip_ntp')` 還原。

### 已知風險

| 風險 | 影響 | 緩解 |
|---|---|---|
| `connect_sta` (~15 s) / `ntp.sync` (30 s) 阻塞 event loop | web / 時鐘 tick 短暫凍住 | `connect_sta` 使用者主動觸發、可接受；`ntp.sync` 23:59 觸發、無互動 |
| `/scan` 會短暫斷 STA | 重新掃描時連線可能中斷 | 實測後決定是否 cache |
| 同時開 AP + STA 的 mDNS | 只能綁一個介面 | 開機 `_enter_sta_try(initial=True)` 會關 AP；初次設定期間 AP + STA 暫時並存（mDNS 綁 STA IP），進 RUN 後 `_enter_run` 關 AP |
| 1500 ms 延遲是經驗值 | 手機慢時 `/done` 可能在 AP 關閉前沒收完 | 實際 AP 要到 NTP + 天氣都成功才關（通常數秒以上），風險低；實測再調 |
| AP 子網 DHCP 硬碼 `192.168.4.0/24`（micropython#17401, #17977） | 規格 `ProjectDetail.md` 寫的 `192.168.0.1` 在現行 rp2 CYW43 韌體不可達 | `wifi_manager.AP_DEFAULT_IP = "192.168.4.1"`；`start_ap()` 讀回 `ifconfig()[0]` 真實 IP 供 guide / mDNS 使用 |

---

## Context

`ProjectDetail.md` 詳細描述了一台 Raspberry Pi Pico 2 W + Waveshare 3.7" 電子紙的中文天氣顯示裝置應有的行為（Wi-Fi 熱點導引、網頁設定、NTP 同步、OpenWeather 天氣抓取、月曆、最小化部分刷新等）。

現在的 `main.py` 是 534 行的單檔骨架版本，僅完成了基本的 ConfigManager / WiFiManager / WebConfigServer / 一次性畫面繪製，但與規格有以下主要落差：

1. 沒有 main loop — 一次性畫完即結束，無法每分鐘部分刷新時間
2. 沒有 11:00 / 23:00 天氣排程、23:59 NTP 排程、月初 log 清理
3. Web server 是 blocking socket，完成設定後會永遠卡住，且無法與 STA 模式共存
4. 網頁缺少 SSID 掃描下拉、重新掃描、RWD、多頁逐步引導
5. 所有字型只支援 ASCII，無法顯示「連線、密碼、初始化、一/二/三」等中文
6. `weather_icon/` 與 `wifi_icon/` 資料夾是空的；目前的繪圖把檔名當文字 print 出來
7. 沒有 mDNS（`epaper.local`）
8. 12 小時制換算邏輯錯誤（00:00 → 0:00，應為 12:00）
9. Wi-Fi 強度寫死 `level3`，沒有依 RSSI 換算

目標：把專案重構成符合規格、可長期運行的多模組架構，補上所有缺失功能。

## 關鍵決策（使用者已確認）

| 項目 | 採用方案 |
| --- | --- |
| 中文字型 | NotoSansTC 子集，用 `font-to-py` 產生 20px / 12px 兩個版本（~10 KB） |
| mDNS | Vendor `github.com/cbrand/micropython-mdns` 至 `lib/mdns_client/` |
| 程式結構 | 拆成多模組（`config.py`, `wifi_manager.py`, `web_server.py`, `weather.py`, `scheduler.py`, `app.py`, `display/*`） |
| 網頁流程 | 多頁逐步引導：`/wifi` → `/time` → `/weather` → `/done`，未連線 Wi-Fi 不能進入後續頁 |
| Icon 格式 | PBM P4（1-bit raw），直接 `framebuf.FrameBuffer(buf, w, h, MONO_HLSB)` 載入 |
| 並行模型 | `uasyncio`，web server / scheduler / state task 為 cooperative task |
| 橫向座標 | 在 `display/canvas.py` 提供 480×280 landscape 包裝層，內部用第二個 framebuffer 並在 commit 時轉置到 280×480 native portrait（多 16.8 KB RAM） |

## 目標架構

```
main.py                      # 5–10 行：import app; uasyncio.run(app.run())
app.py                       # FSM 主控（BOOT → AP_CONFIG → STA_TRY → INIT → RUN）
config.py                    # ConfigManager（沿用現有 + batch 模式）
wifi_manager.py              # WiFiManager + scan() + rssi_to_level()
mdns.py                      # 包裝 mdns_client，註冊 epaper.local
weather.py                   # OpenWeather client + retry + log writer + 月初 rotate
scheduler.py                 # uasyncio task：每秒 poll RTC，產生 MinuteTick/WeatherRefresh/NtpResync/LogRotate
web_server.py                # uasyncio HTTP server，多頁路由 / RWD
display/
    canvas.py                # LandscapeCanvas：(x∈[0,480), y∈[0,280)) → 內部 280×480 fb，commit_full / commit_part
    icons.py                 # load_pbm(path) → (FrameBuffer, w, h)，含 LRU cache
    fonts.py                 # 集中暴露 noto20 / noto12 / freesans20 / courier_big
    screens/
        guide.py             # 初次設定導引畫面
        message.py           # 居中單行訊息
        main_screen.py       # 主畫面（時間 + Wi-Fi icon + 天氣 + 月曆）
        calendar.py          # 月曆繪製
lib/mdns_client/             # vendored
wifi_icon/level0..4.pbm
weather_icon/01d..50n.pbm, weather_failed.pbm
fonts/                       # 字型生成腳本與字元清單（host 端）
    chars_used.txt
    build_fonts.sh
```

## FSM 行為

```
BOOT
  └─ config.is_configured() → no  → AP_CONFIG
                            → yes → STA_TRY

AP_CONFIG
  ├─ wifi.start_ap()
  ├─ mdns.start("epaper")
  ├─ guide.show(canvas, wifi_info)
  └─ web server task 持續服務 /wifi /scan

STA_TRY  （從 AP_CONFIG 收到 POST /wifi 後進入）
  ├─ wifi.connect_sta() with 15s timeout
  ├─ success → mdns 重新註冊新 IP → message.show("連線成功") → INIT
  └─ fail    → message.show("連線失敗，回到 AP") → AP_CONFIG

INIT  （已連線成功，第一次進入或收到 POST /weather 完成）
  ├─ message.show("初始化準備中⋯⋯")
  ├─ message.show("初始化 NTP 中") → ntp_sync(timeout=30)
  │    └─ fail → message.show("初始化 NTP 失敗") → halt（web server 仍開）
  ├─ message.show("取得天氣資訊中") → weather.fetch()
  │    └─ fail (2 retries × 5s) → message.show("取得天氣資訊失敗") → halt
  └─ all good → RUN

RUN
  ├─ main_screen.render_full(canvas, ctx)
  ├─ scheduler task 持續每秒 poll：
  │    • minute changed         → render_time（部分刷新時間區）
  │    • 11:00:00 / 23:00:00    → weather.fetch() + render_full（全刷）
  │    • 23:59:00               → ntp.sync(); 一律 render_calendar（部分刷新月曆區）
  │    • day == 1 & 00:00:00    → weather.rotate_log()
  └─ 收到新的 POST /weather → 重新 INIT（不重啟）
```

Web server 整個生命週期都不關閉；STA 連線後仍綁 `0.0.0.0:80`，使用者隨時可重新編輯設定。

## 網頁多頁路由

| 路徑 | 方法 | 行為 |
| --- | --- | --- |
| `/` | GET | 依目前 state 重導向（未連線 → `/wifi`，已連線未設定天氣 → `/time` 或 `/weather`，全部完成 → `/done`） |
| `/wifi` | GET | 顯示 SSID 下拉（含 `[重新掃描]`）+ 密碼欄 |
| `/wifi` | POST | 儲存到 config → 觸發 STA_TRY → 回應 `{ok, ip}` JSON；前端依結果跳轉 `/time` 或顯示錯誤 |
| `/scan` | GET | 回傳 `WLAN.scan()` JSON 給前端動態更新下拉 |
| `/time` | GET | 12/24 小時制 radio、週起始日 select（未連線時 302 → `/wifi`） |
| `/time` | POST | 儲存後跳 `/weather` |
| `/weather` | GET | API Key、城市 select（從 `taiwan_cities.json`）、°C/°F radio、log 下載連結 |
| `/weather` | POST | 儲存後觸發 INIT；回應 `/done` |
| `/done` | GET | 顯示「設定完成，裝置正在套用」；後續可從這頁連回 `/wifi` 等修改 |
| `/weather.log` | GET | 下載 `weather.log` |

所有頁面共用模板（header / nav / footer / RWD CSS），CSS 用 inline `<style>` 約 40 行 flexbox + viewport meta。

## 字型與 Icon 資產

### 字型

用 `font-to-py` 從 NotoSansTC-Regular 產生：

- `writer/noto20.py` — 20 px，包含 `chars_used.txt` 中所有中文 + ASCII
- `writer/noto12.py` — 12 px，用於月曆

`fonts/chars_used.txt` 初步清單：
```
連線WiFi密碼用瀏覽器到以下網址完成初次設定或
初始化準備中
初始化 NTP 中
初始化 NTP 失敗
取得天氣資訊中
取得天氣資訊失敗
設定已儲存套用中
一二三四五六日
台北新桃中南高基隆嘉義雲林彰化苗栗屏東宜蘭花蓮東澎湖金門連江市縣
晴多雲陰雨雪雷霧
時間日曆天氣
℃℉
```

時間區用較大的 ASCII-only 字（例如 `font-to-py` 產生 60 px Courier 數字字型），不需 CJK 範圍。

### Icon

PBM P4 (1-bit raw, MSB first) — 直接接 `FrameBuffer(buf, w, h, MONO_HLSB)`：

| 路徑 | 尺寸 | 來源 |
| --- | --- | --- |
| `wifi_icon/level0..4.pbm` | 32×20 | 自繪或 Feather wifi 圖示 |
| `weather_icon/01d..50n.pbm`（18 種） | 80×80 | OpenWeather `https://openweathermap.org/img/wn/<code>@2x.png` |
| `weather_icon/weather_failed.pbm` | 80×80 | 自繪驚嘆號三角 |

`fonts/build_fonts.sh` + `weather_icon/build_icons.sh` 放在專案內並寫進 README，重現性命令：

```sh
for code in 01d 01n 02d 02n 03d 03n 04d 04n 09d 09n 10d 10n 11d 11n 13d 13n 50d 50n; do
  curl -sL "https://openweathermap.org/img/wn/${code}@2x.png" -o "/tmp/${code}.png"
  magick "/tmp/${code}.png" -resize 80x80 -background white -alpha remove \
         -threshold 50% -compress none "weather_icon/${code}.pbm"
done
```

`display/icons.py` 提供：

```python
def load_pbm(path):
    # 解析 "P4\n<w> <h>\n" 後直接 FrameBuffer(remaining, w, h, framebuf.MONO_HLSB)
    ...
```

附加 LRU cache（最多 4 張）以節省 heap。

## Canvas 抽象（橫向座標系）

`display/canvas.py`：

```python
class LandscapeCanvas:
    """480×280 landscape 給呼叫端，內部映射到 280×480 native portrait fb。"""

    def __init__(self, epd):
        self.epd = epd
        self.buf = bytearray(480 * 280 // 8)
        self.fb = framebuf.FrameBuffer(self.buf, 480, 280, framebuf.MONO_HLSB)

    def text(self, x, y, font, s, invert=False): ...
    def blit_pbm(self, x, y, fb, w, h, invert=False): ...
    def fill_rect(self, x, y, w, h, color): ...
    def commit_full(self):
        self._transpose_to(self.epd.image1Gray)
        self.epd.EPD_3IN7_1Gray_init()
        self.epd.EPD_3IN7_1Gray_Display(self.epd.buffer_1Gray)
        self.epd.Sleep()
    def commit_part(self, rect):
        # rect=(x,y,w,h) in landscape coords；轉成 portrait 範圍後呼叫 Display_Part
        ...
```

時間區、Wi-Fi icon 區、月曆區各自有固定 rect（時間：`(0,30,360,250)`，Wi-Fi：`(440,0,40,28)`，天氣：`(360,30,120,140)`，月曆：`(360,170,120,110)`），讓部分刷新只影響對應區域。

## 排版（landscape 480×280）

```
+--------------------------------------------------+
|                                       [Wi-Fi]    |  y: 0–28
+------------------------------------+-------------+
|                                    |  天氣 icon  |
|                                    | (80×80)     |
|         時間 HH:MM                  |  20°C       |  y: 30–170
|         (140px tall digits)        |  晴         |
|                                    |             |
|                                    +-------------+
|                                    |  一二三...   |
|                                    |  月曆        |  y: 170–280
|                                    |             |
+------------------------------------+-------------+
   x: 0                              360           480
```

時間佔左 360 px × 250 px，右側 120 px 上半為天氣、下半為迷你月曆。Wi-Fi icon 縮在右上角頂部。

## 重點 bug 與既有程式碼問題（重構時一併修）

1. `WiFiManager.connect_sta` 失敗回 `False`、成功回 dict → 統一改回 `None | dict`。
2. `ConfigManager.set()` 每個 key 都會 save → 加入 `with config.batch(): ...` 延遲寫檔。
3. 12 小時換算：`if not is_24h and hour > 12: hour -= 12` 漏掉 00:00 與 12:00。改成 `hour = hour % 12 or 12`，並補上 AM/PM。
4. `ntp_sync` 寫 RTC 時 `tm[6]+1` 假設 `localtime` weekday 0=Mon，確實如此；保留並加註釋。
5. `draw_main_screen` 用 `wri10.printstring(f"Wi-Fi: {wifi_icon}")` 把檔名印成文字 → 改用 `canvas.blit_pbm(...)`。
6. 失敗時 `display.Sleep()` 後下一次 partial refresh 需要 `EPD_3IN7_1Gray_init()` → scheduler 在每次 partial 前都重新 init。
7. Weather log timestamp NTP 同步前用 `utime.localtime()` 會是開機後相對時間 → 統一改用 `RTC.datetime()`，且在 NTP 失敗時不要產生誤導日期（log 行可加 `[no-ntp]` 標記）。
8. `WebConfigServer.start()` 是 blocking → 改寫為 `async def serve()` 用 `asyncio.start_server`。
9. `EPD_3in7.__init__` 會做一次 4Gray init+clear（很慢且未使用），可從 ctor 移除，改成第一次需要時才 init。

## 規格對應檢查表

| 規格條目 | 實作位置 |
| --- | --- |
| 1.1–1.5 AP SSID/pwd/IP/mDNS/顯示 | `wifi_manager.start_ap`, `mdns.start`, `display/screens/guide.py` |
| 1.* 只在沒 config 時 | `app.run()` 先檢查 `config.is_configured()` |
| 2.1.* SSID 下拉 + 掃描 + 重新掃描 | `web_server.py` `/wifi` + `/scan` 路由 |
| 2.2.* 12/24h + 週起始 | `/time` 路由 |
| 2.3.* API key / 城市 / 攝氏華氏 / log | `/weather` 路由 + `/weather.log` |
| 2.* 不停止服務 | web server task 整個 app 生命週期都在 |
| 2.* RWD | viewport meta + flexbox CSS |
| 2.* 自動套用 | `/weather` POST 完直接觸發 FSM re-INIT，不需 reboot |
| 3.* Wi-Fi 強度 icon | `wifi_manager.rssi_to_level` → `wifi_icon/level{n}.pbm` |
| 4.1–4.3 時間（無秒、每分鐘部分刷新、12/24h） | `scheduler.MinuteTick` → `main_screen.render_time` → `canvas.commit_part` |
| 4.4 NTP（23:59、time.apple.com、30s、不重試） | `scheduler.NtpResync` → `ntp.sync` |
| 5.1–5.8 天氣 | `weather.fetch` + `scheduler.WeatherRefresh` |
| 6.1–6.4 月曆 | `display/screens/calendar.py` + NTP 後一律 render |
| Log 規格 | `weather.append_log` + `weather.rotate_if_needed` |
| 流程 §1–6 | `app.py` FSM |

## 實作順序（建議分階段，避免一次性大改後難 debug）

1. ✅ **資產準備**（host 端）：noto20/noto12/clock_big 字型、Wi-Fi icon、weather icon、`lib/mdns_client/`
2. ✅ **Canvas + Icon + Fonts**：`display/canvas.py`, `display/icons.py`, `display/fonts.py`
3. ✅ **模組拆分**：從原 main.py 抽出 `config.py`, `wifi_manager.py`, `weather.py`
4. ✅ **Async 化 web server**：`asyncio.start_server` + 多頁路由
5. ✅ **FSM (`app.py`)**：BOOT → AP_CONFIG → STA_TRY → INIT → RUN
6. ✅ **Scheduler**：1Hz poll RTC + MinuteTick partial refresh
7. ✅ **進階排程**：WeatherRefresh (11:00/23:00) / NtpResync (23:59) / LogRotate (每月 1 號)
8. ✅ **mDNS**：vendored + `mdns.py` wrapper
9. ⏳ **Polishing**：上 Pico 後依實測調整（12h AM/PM 邊界、Wi-Fi RSSI level、log rotate 邊界、AP+STA 同網段）

## 關鍵需修改 / 新增檔案

- `/Users/darktt/Documents/Raspberry-Pico/E-Paper/main.py` — 削減成 5–10 行 bootstrap
- `/Users/darktt/Documents/Raspberry-Pico/E-Paper/app.py`（新）— FSM 主控
- `/Users/darktt/Documents/Raspberry-Pico/E-Paper/config.py`（新）— 從 main.py 抽出 ConfigManager，加 batch 模式
- `/Users/darktt/Documents/Raspberry-Pico/E-Paper/wifi_manager.py`（新）— `scan()`, `rssi_to_level()`
- `/Users/darktt/Documents/Raspberry-Pico/E-Paper/web_server.py`（新）— async 多頁路由
- `/Users/darktt/Documents/Raspberry-Pico/E-Paper/weather.py`（新）— fetch + log + rotate
- `/Users/darktt/Documents/Raspberry-Pico/E-Paper/scheduler.py`（新）— 1Hz poll RTC
- `/Users/darktt/Documents/Raspberry-Pico/E-Paper/mdns.py`（新）— mdns_client 包裝
- `/Users/darktt/Documents/Raspberry-Pico/E-Paper/display/canvas.py`（新）— landscape 包裝
- `/Users/darktt/Documents/Raspberry-Pico/E-Paper/display/icons.py`（新）— PBM 載入
- `/Users/darktt/Documents/Raspberry-Pico/E-Paper/display/fonts.py`（新）— 字型集中匯出
- `/Users/darktt/Documents/Raspberry-Pico/E-Paper/display/screens/guide.py`（新）
- `/Users/darktt/Documents/Raspberry-Pico/E-Paper/display/screens/message.py`（新）
- `/Users/darktt/Documents/Raspberry-Pico/E-Paper/display/screens/main_screen.py`（新）
- `/Users/darktt/Documents/Raspberry-Pico/E-Paper/display/screens/calendar.py`（新）
- `/Users/darktt/Documents/Raspberry-Pico/E-Paper/lib/mdns_client/*` — 從 upstream 引入
- `/Users/darktt/Documents/Raspberry-Pico/E-Paper/writer/noto20.py`, `noto12.py` — 新字型
- `/Users/darktt/Documents/Raspberry-Pico/E-Paper/wifi_icon/level{0..4}.pbm` — 5 個檔
- `/Users/darktt/Documents/Raspberry-Pico/E-Paper/weather_icon/*.pbm` — 19 個檔
- `/Users/darktt/Documents/Raspberry-Pico/E-Paper/fonts/chars_used.txt` + `build_fonts.sh`（host 端腳本）

## Verification 計畫（待 Pico 上線後逐項跑）

裝置端（MicroPico 上傳後 REPL 觀察）：

1. ⏳ **匯入 smoke test**：REPL `import config; import app; import display.canvas; import mdns_client` — 確認沒有 ImportError
2. ⏳ **AP_CONFIG 視覺**：刪除 `config.json` → 重啟 → e-paper 應顯示置中橫向「連線 Wi-Fi：ePaper / 密碼：paper1234 / http://192.168.4.1 / http://epaper.local」。手機連 `ePaper` SSID，瀏覽器開 `http://192.168.4.1` 與 `http://epaper.local` 確認 RWD
3. ⏳ **多頁流程**：`/wifi` 掃描下拉、重新掃描按鈕。POST 成功 → 跳 `/time`。直接造訪 `/time` 在未連線時應 302 回 `/wifi`
4. ⏳ **NTP 失敗路徑**：拔掉 router 再儲存 → e-paper 顯示「初始化 NTP 失敗」、web server 仍可從 STA IP 連得到
5. ⏳ **分鐘 tick**：觀察 `:59` → `:00` 切換，只有時間區閃刷，其他區不動
6. ⏳ **排程 mock**：（尚未實作）`/dev/fire?event=weather|ntp|log` debug route — 若實測等到 11:00 太久可考慮加
7. ⏳ **Log rotate**：把 RTC 設到 `2026-01-31 23:59:30`，等過午夜，確認 `weather.log` 清空
8. ⏳ **重新設定**：RUN 階段改城市 → POST `/weather` → FSM 重新 INIT、抓新天氣、全刷主畫面；期間 web server 持續可達（用 `curl` 在另一台機器持續打）
9. ⏳ **12h 邊界**：手動把 RTC 設 00:00 / 11:59 / 12:00 / 23:59，觀察顯示分別為 `12:00 AM / 11:59 AM / 12:00 PM / 11:59 PM`

## 待後續確認的次要決策

- ⏳ Minute tick 之間 `machine.lightsleep(900)` 省電 — 等實測續航再決定
- ⏳ `EPD_3in7.__init__` 的 4Gray init+clear 是否移除以加速冷啟 — 建議實測後移除
- ✅ `/scan` 在 STA 模式對外開放 — 規格「不停止服務」，採開放
- ⏳ Canvas 轉置效能優化（viper / byte 對齊）— 等實測再決定

## 部署流程 (MicroPico)

1. **連線**：USB 插 Pico → VSCode 狀態列出現「Pico Connected」(綠)
2. **首次上傳**：Explorer 樹專案根目錄右鍵 → **Upload project to Pico**（30–60 秒）
3. **驗證檔案**：REPL 跑 `os.listdir()`, `os.listdir('lib')`, `os.listdir('writer')` 確認都到位
4. **執行**：REPL 按 Ctrl-D soft reset（或 `import main; main.main()`）
5. **後續迭代**：改的單檔右鍵 → **Upload file to Pico**；Ctrl-C 中止程式、Ctrl-D 重啟

`.gitignore` 已設定，MicroPico Upload Project 不會夾帶 `mDns/`, `fonts/`, `tools/`, `API/`, `*.md`, `*.sh` 等 host-only 內容。
