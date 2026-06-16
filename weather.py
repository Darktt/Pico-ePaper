import os
import utime
import urequests
from machine import RTC


LOG_FILE = "weather.log"
WEATHER_URL = "http://api.openweathermap.org/data/2.5/weather"
MAX_RETRIES = 3  # 1 次原始 + 2 次重試
RETRY_GAP_S = 5
REQUEST_TIMEOUT_S = 60


def _datetime_now(have_ntp=True):
    """回傳 (year, month, day, hour, minute) 與旗標 — 在 NTP 還沒同步時旗標為 False"""
    rtc = RTC()
    d = rtc.datetime()
    year, month, day = d[0], d[1], d[2]
    hour, minute = d[4], d[5]
    # 1970/2000 開機初始化代表還沒 NTP 同步
    valid = have_ntp and year >= 2024
    return year, month, day, hour, minute, valid


def _fmt_timestamp(year, month, day, hour, minute):
    return "{:04d}-{:02d}-{:02d}-{:02d}:{:02d}".format(year, month, day, hour, minute)


def _append_log(line):
    try:
        with open(LOG_FILE, "a") as f:
            f.write(line + "\n")
    except Exception:
        pass


def fetch(config, have_ntp=True):
    """呼叫 OpenWeather API；失敗時重試 2 次，每次間隔 5 秒，timeout 60 秒。
    回傳 dict: {ok, icon, desc, temp} 或 {ok=False, error}.
    每次請求結果都會寫入 weather.log。
    """
    api_key = config.get("weather", "api_key")
    city = config.get("weather", "city") or {}
    is_celsius = bool(config.get("weather", "is_celsius"))
    lat = city.get("lat", 0.0)
    lon = city.get("lon", 0.0)
    units = "metric" if is_celsius else "imperial"
    url = (
        "{base}?lat={lat}&lon={lon}&appid={key}&units={units}&lang=zh_tw"
    ).format(base=WEATHER_URL, lat=lat, lon=lon, key=api_key, units=units)

    last_error = ""
    for attempt in range(MAX_RETRIES):
        resp = None
        try:
            resp = urequests.get(url, timeout=REQUEST_TIMEOUT_S)
            status = resp.status_code
            if status == 200:
                data = resp.json()
                result = {
                    "ok": True,
                    "icon": data["weather"][0]["icon"],
                    "desc": data["weather"][0]["description"],
                    "temp": data["main"]["temp"],
                    "is_celsius": is_celsius,
                }
                # 成功 log 多帶溫度/描述/icon code，方便事後翻查當天天氣狀況
                unit = "C" if is_celsius else "F"
                detail = "{}-{:.1f}{}-{}-{}".format(
                    status, result["temp"], unit,
                    result["desc"], result["icon"])
                _log_result(have_ntp, detail)
                return result
            last_error = "HTTP {}".format(status)
        except Exception as e:
            last_error = str(e) or "request failed"
        finally:
            if resp is not None:
                try:
                    resp.close()
                except Exception:
                    pass
        if attempt < MAX_RETRIES - 1:
            utime.sleep(RETRY_GAP_S)

    _log_result(have_ntp, last_error)
    return {"ok": False, "error": last_error, "is_celsius": is_celsius}


def _log_result(have_ntp, result_text):
    year, month, day, hour, minute, valid = _datetime_now(have_ntp)
    ts = _fmt_timestamp(year, month, day, hour, minute)
    if not valid:
        ts = ts + "[no-ntp]"
    _append_log("{}-{}".format(ts, result_text))


def rotate_if_needed(have_ntp=True):
    """每月 1 號清理 log；以當下日期判斷，僅在當天日期 == 1 時清空。"""
    year, month, day, _, _, valid = _datetime_now(have_ntp)
    if not valid or day != 1:
        return False
    try:
        if LOG_FILE in os.listdir():
            # 清空
            with open(LOG_FILE, "w") as f:
                f.write("")
            return True
    except Exception:
        pass
    return False


def log_exists():
    try:
        return LOG_FILE in os.listdir()
    except Exception:
        return False


def read_log():
    try:
        with open(LOG_FILE, "r") as f:
            return f.read()
    except Exception:
        return ""
