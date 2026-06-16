import ntptime
import utime
from machine import RTC


NTP_HOST = "time.apple.com"
DEFAULT_TIMEOUT = 30


def sync(timeout=DEFAULT_TIMEOUT, host=NTP_HOST, tz_offset_minutes=0):
    """嘗試與 NTP 伺服器同步時間，timeout 秒內不斷重試；成功回傳 True。

    ntptime.settime() 寫進 RTC 的是 UTC，但 LandscapeCanvas 顯示用的
    RTC().datetime() 我們不希望多算 offset，直接把 UTC + tz_offset 寫回
    RTC，後續所有 `RTC().datetime()` 自然是本地時間。
    """
    ntptime.host = host
    t0 = utime.time()
    while True:
        try:
            ntptime.settime()
            # 加上時區偏移後再寫一次 RTC
            secs = utime.time() + int(tz_offset_minutes) * 60
            tm = utime.localtime(secs)
            rtc = RTC()
            rtc.datetime((tm[0], tm[1], tm[2], tm[6] + 1,
                          tm[3], tm[4], tm[5], 0))
            return True
        except Exception:
            if utime.time() - t0 > timeout:
                return False
            utime.sleep(1)
