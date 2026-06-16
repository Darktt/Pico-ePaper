import uasyncio as asyncio
from machine import RTC


# 事件代碼
EV_MINUTE = "minute"
EV_DAY = "day"
EV_WEATHER = "weather"
EV_NTP = "ntp"
EV_LOG_ROTATE = "log_rotate"
EV_WIFI_LEVEL = "wifi_level"


class Scheduler:
    """每秒 poll RTC，根據時間變化派發事件給註冊的 handler（coroutine）。"""

    def __init__(self):
        self._handlers = {}
        self._last_minute = None
        self._last_day = None
        self._last_dispatched = {}
        self._task = None
        self._stop = False

    def on(self, event, handler):
        """註冊事件處理函式（async coroutine 接受 event_name 與 datetime tuple）。"""
        self._handlers.setdefault(event, []).append(handler)

    async def _emit(self, event, now):
        key = (event, now[0], now[1], now[2], now[4], now[5], now[6])
        if self._last_dispatched.get(event) == key:
            return
        self._last_dispatched[event] = key
        for h in self._handlers.get(event, []):
            try:
                await h(event, now)
            except Exception as e:
                print("scheduler handler error ({}): {}".format(event, e))

    async def run(self):
        rtc = RTC()
        self._stop = False
        while not self._stop:
            now = rtc.datetime()
            day = now[2]
            hour, minute, second = now[4], now[5], now[6]

            # 日期變化（跨日，含跨月跨年）→ 月曆刷新
            # 規格 6.* 只指定 NTP 後刷新，但 23:59 那次仍是「昨天」，過 00:00 後
            # today 已變但沒事件再戳一次；多開這條獨立事件比把邏輯塞進 minute 乾淨。
            if self._last_day is None:
                self._last_day = day
            elif day != self._last_day:
                self._last_day = day
                await self._emit(EV_DAY, now)

            # 分鐘變化
            if self._last_minute is None or minute != self._last_minute:
                self._last_minute = minute
                await self._emit(EV_MINUTE, now)

            # 11:00:00 / 23:00:00 → 天氣重抓
            if (hour, minute, second) in ((11, 0, 0), (23, 0, 0)):
                await self._emit(EV_WEATHER, now)

            # 23:59:00 → NTP 同步
            if (hour, minute, second) == (23, 59, 0):
                await self._emit(EV_NTP, now)

            # 每月 1 號 00:00:00 → log rotate
            if (now[2], hour, minute, second) == (1, 0, 0, 0):
                await self._emit(EV_LOG_ROTATE, now)

            await asyncio.sleep_ms(1000)

    def stop(self):
        self._stop = True
