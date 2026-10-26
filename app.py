import os
import uasyncio as asyncio

from config import ConfigManager
from wifi_manager import WiFiManager
from web_server import WebConfigServer
from scheduler import (
    Scheduler, EV_MINUTE, EV_DAY, EV_WEATHER, EV_NTP, EV_LOG_ROTATE, EV_WIFI_LEVEL,
)
from Pico_ePaper_3_7 import EPD_3in7
from display.canvas import LandscapeCanvas
from display.screens import guide, message, main_screen
from mdns import MDNSResponder
import weather as weather_mod
import ntp


def _print_disk_usage():
    """開機印一份檔案系統用量與根目錄前幾大檔案 / 資料夾。"""
    try:
        s = os.statvfs("/")
        block = s[0]
        total = block * s[2]
        free = block * s[3]
        used = total - free
        print("[FS] total {:>4} KB  used {:>4} KB  free {:>4} KB".format(
            total // 1024, used // 1024, free // 1024))
    except Exception as e:
        print("[FS] statvfs 失敗: {}".format(e))
        return

    def _dir_size(path):
        """遞迴算資料夾總大小；只加實際檔案，跳過子目錄的 metadata 值。"""
        total = 0
        try:
            for f in os.listdir(path):
                sub = "{}/{}".format(path, f)
                try:
                    sst = os.stat(sub)
                except Exception:
                    continue
                if sst[0] & 0x4000:
                    total += _dir_size(sub)
                else:
                    total += sst[6]
        except Exception:
            pass
        return total

    try:
        entries = []
        for name in os.listdir("/"):
            try:
                st = os.stat("/" + name)
                if st[0] & 0x4000:
                    entries.append((_dir_size("/" + name), name + "/"))
                else:
                    entries.append((st[6], name))
            except Exception:
                pass
        entries.sort(reverse=True)
        for sz, name in entries:
            print("[FS]   {:>6} KB  {}".format(sz // 1024, name))
    except Exception as e:
        print("[FS] 掃描根目錄失敗: {}".format(e))

    # 關鍵 icon 目錄存在性提示
    for d in ("wifi_icon", "weather_icon"):
        try:
            n = len(os.listdir(d))
            print("[FS] {}/ 含 {} 個檔案".format(d, n))
        except Exception:
            print("[FS] !! {}/ 不存在，icon 將 fallback 成文字".format(d))


STATE_BOOT = "BOOT"
STATE_AP = "AP_CONFIG"
STATE_STA_TRY = "STA_TRY"
STATE_INIT = "INIT"
STATE_RUN = "RUN"
STATE_HALT = "HALT"


class App:
    def __init__(self):
        self.config = ConfigManager()
        self.wifi = WiFiManager()
        self.epd = EPD_3in7()
        self.canvas = LandscapeCanvas(self.epd)
        self.scheduler = Scheduler()
        self.web = WebConfigServer(self.config, self.wifi, self, port=80)

        self.mdns = MDNSResponder()

        self.state = STATE_BOOT
        self.weather_data = None
        self.have_ntp = False
        self._reinit_event = asyncio.Event()

    def state_name(self):
        return self.state

    def _bench_canvas(self):
        """量整片 transpose + 各區部分 transpose 時間，方便看 viper 是否生效。"""
        try:
            from display.canvas import (
                _transpose_cw_viper, _transpose_cw_native,
            )
            if _transpose_cw_viper is not None:
                accel = "viper"
            elif _transpose_cw_native is not None:
                accel = "native"
            else:
                accel = "pure-python (slow)"
            print("[BENCH] canvas accel: {}".format(accel))
        except Exception as e:
            print("[BENCH] accel 狀態檢查失敗: {}".format(e))
        try:
            import time
            t0 = time.ticks_ms()
            self.canvas._transpose_into(self.epd.image1Gray, None)
            t1 = time.ticks_ms()
            print("[BENCH] transpose full (480x280): {} ms".format(
                time.ticks_diff(t1, t0)))
            t0 = time.ticks_ms()
            self.canvas._transpose_into(self.epd.image1Gray, (0, 30, 360, 250))
            t1 = time.ticks_ms()
            print("[BENCH] transpose TIME_RECT (360x250): {} ms".format(
                time.ticks_diff(t1, t0)))
        except Exception as e:
            print("[BENCH] transpose 量測失敗: {}".format(e))

    # ---------------- 入口 ---------------- #

    async def run(self):
        _print_disk_usage()
        self._bench_canvas()
        await self.web.start()
        asyncio.create_task(self._main_loop())
        # 註冊 scheduler handler
        self.scheduler.on(EV_MINUTE, self._on_minute)
        self.scheduler.on(EV_DAY, self._on_day)
        self.scheduler.on(EV_WEATHER, self._on_weather_tick)
        self.scheduler.on(EV_NTP, self._on_ntp_tick)
        self.scheduler.on(EV_LOG_ROTATE, self._on_log_rotate)
        asyncio.create_task(self.scheduler.run())

        # 永遠不結束
        while True:
            await asyncio.sleep(3600)

    async def _main_loop(self):
        # 進入點：依目前 config 決定要不要進 STA_TRY
        if self.config.is_wifi_configured():
            await self._enter_sta_try(initial=True)
        else:
            await self._enter_ap()

        # 之後等待 web POST /weather 觸發 re-init
        while True:
            await self._reinit_event.wait()
            self._reinit_event.clear()
            await self._enter_init()

    # ---------------- 狀態轉換 ---------------- #

    async def _enter_ap(self):
        self.state = STATE_AP
        info = self.wifi.start_ap()
        # 啟動 mDNS（規格要求 epaper.local 在 AP 模式下可解析）
        await self.mdns.start("epaper", info["ip"])
        guide.show(self.canvas, info)
        # 待著等 /wifi POST → try_connect_wifi

    async def _enter_sta_try(self, initial=False):
        self.state = STATE_STA_TRY
        ssid = self.config.get("wifi", "ssid")
        pwd = self.config.get("wifi", "password") or ""
        if not ssid:
            await self._enter_ap()
            return
        message.show(self.canvas, "連線 Wi-Fi 中⋯⋯")
        result = self.wifi.connect_sta(ssid, pwd)
        if result is None:
            message.show(self.canvas, "連線失敗，回到 AP")
            await asyncio.sleep(1)
            await self._enter_ap()
            return
        # 連線成功；不關 AP，讓 web 仍可從 AP 存取
        if initial:
            self.wifi.stop_ap()
        await self.mdns.start("epaper", result["ip"])
        await self._enter_init()

    async def _enter_init(self):
        self.state = STATE_INIT
        message.show(self.canvas, "初始化準備中⋯⋯")
        await asyncio.sleep(0)

        # NTP（呼叫會 block 事件圈最多 30 秒；UI 已先顯示 INIT 訊息可接受）
        # 測試旁路：filesystem 根目錄存在 `.skip_ntp` 就跳過 NTP，
        # 用於在 REPL 撥 RTC 後 soft-reset 觀察跨日事件而不被覆寫。
        try:
            _skip_ntp = ".skip_ntp" in os.listdir("/")
        except Exception:
            _skip_ntp = False
        if _skip_ntp:
            print("[INIT] 偵測到 /.skip_ntp，跳過 NTP（測試用，記得刪檔還原）")
            self.have_ntp = True
        else:
            message.show(self.canvas, "初始化 NTP 中")
            tz = self.config.get("time", "tz_offset_minutes")
            if tz is None:
                tz = 480
            self.have_ntp = ntp.sync(30, tz_offset_minutes=tz)
            if not self.have_ntp:
                message.show(self.canvas, "初始化 NTP 失敗")
                self.state = STATE_HALT
                return

        # 月曆刷新（規格 6.4：NTP 後一律更新；INIT 期間以全幀渲染處理）
        # 因為主畫面尚未渲染，月曆會在 render_full 一起畫，此處不需單獨重繪

        # Weather
        if not self.config.is_weather_configured():
            # 還沒設定天氣，先暫停在 INIT，web /weather POST 會再觸發
            message.show(self.canvas, "請完成天氣設定（http://{}）".format(
                self.wifi.sta_ip() or ""))
            self.state = STATE_HALT
            return

        message.show(self.canvas, "取得天氣資訊中")
        self.weather_data = await weather_mod.fetch_async(
            self.config, have_ntp=self.have_ntp)
        if not self.weather_data.get("ok"):
            message.show(self.canvas, "取得天氣資訊失敗")
            self.state = STATE_HALT
            return

        await self._enter_run()

    async def _enter_run(self):
        self.state = STATE_RUN
        main_screen.render_full(self.canvas, self.config, self.weather_data,
                                self.wifi.current_level())
        # 初次設定時 AP 與 STA 會暫時並存，方便手機不必先切回家中 Wi-Fi。
        # 所有初始化都成功、主畫面已完成顯示後，才關掉 AP；Web server 仍綁在
        # STA 的 LAN IP / epaper.local，因此日後設定不受影響。若 NTP 或天氣
        # 初始化失敗則不會到這裡，AP 會保留給使用者修正設定。
        if self.wifi.ap_info() is not None:
            print("[Wi-Fi] 初始化完成，關閉設定用 AP（Web server 保留於 STA）")
            self.wifi.stop_ap()

    # ---------------- Web callback ---------------- #

    async def try_connect_wifi(self, ssid, pwd):
        """由 /wifi POST 呼叫；嘗試連線，回傳 True/False。"""
        message.show(self.canvas, "連線 Wi-Fi 中⋯⋯")
        result = self.wifi.connect_sta(ssid, pwd)
        if result is None:
            message.show(self.canvas, "Wi-Fi 連線失敗")
            return False
        # 連線成功；保持 AP 直到使用者完成全部設定（規格不強制，但較友善）
        await self.mdns.restart(ip=result["ip"])
        message.show(self.canvas, "已連線：{}".format(result["ip"]))
        return True

    async def request_reinit(self, delay_ms=0):
        """由 /weather POST 呼叫 — 觸發重新 INIT。

        初次設定時，呼叫端仍透過 AP 收取 HTTP 回應。可選的短暫延遲確保
        redirect 已送達，再開始可能會關閉 AP 的初始化流程。
        """
        if delay_ms > 0:
            asyncio.create_task(self._request_reinit_after(delay_ms))
        else:
            self._reinit_event.set()

    async def _request_reinit_after(self, delay_ms):
        await asyncio.sleep_ms(delay_ms)
        self._reinit_event.set()

    # ---------------- Scheduler handlers ---------------- #

    async def _on_minute(self, event, now):
        if self.state == STATE_RUN:
            main_screen.render_time(self.canvas, self.config)

    async def _on_day(self, event, now):
        """跨日（含跨月）— 重畫月曆，把 today 的反白移到新日期。"""
        if self.state == STATE_RUN:
            main_screen.render_calendar(self.canvas, self.config)

    async def _on_weather_tick(self, event, now):
        if self.state != STATE_RUN:
            return
        message.show(self.canvas, "更新天氣中⋯⋯")
        self.weather_data = await weather_mod.fetch_async(
            self.config, have_ntp=self.have_ntp)
        main_screen.render_full(self.canvas, self.config, self.weather_data,
                                self.wifi.current_level())

    async def _on_ntp_tick(self, event, now):
        if self.state != STATE_RUN:
            return
        try:
            _skip_ntp = ".skip_ntp" in os.listdir("/")
        except Exception:
            _skip_ntp = False
        if _skip_ntp:
            print("[NTP] 偵測到 /.skip_ntp，跳過 23:59 resync（測試用）")
            ok = True
        else:
            tz = self.config.get("time", "tz_offset_minutes")
            if tz is None:
                tz = 480
            ok = ntp.sync(30, tz_offset_minutes=tz)
        self.have_ntp = self.have_ntp or ok
        # 規格 6.4：無論 NTP 成功與否都要更新月曆
        main_screen.render_calendar(self.canvas, self.config)

    async def _on_log_rotate(self, event, now):
        weather_mod.rotate_if_needed(have_ntp=self.have_ntp)

