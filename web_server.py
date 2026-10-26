import os
import ujson
import uasyncio as asyncio


CITIES_FILE = "taiwan_cities.json"


def _load_cities():
    try:
        with open(CITIES_FILE, "r") as f:
            return ujson.load(f)
    except Exception:
        return []


def _url_decode(s):
    res = ""
    i = 0
    while i < len(s):
        ch = s[i]
        if ch == "+":
            res += " "
            i += 1
        elif ch == "%" and i + 2 < len(s):
            try:
                res += chr(int(s[i + 1:i + 3], 16))
                i += 3
            except Exception:
                res += ch
                i += 1
        else:
            res += ch
            i += 1
    return res


def _parse_form(body):
    params = {}
    for pair in body.split("&"):
        if "=" in pair:
            k, v = pair.split("=", 1)
            params[_url_decode(k)] = _url_decode(v)
        elif pair:
            params[_url_decode(pair)] = ""
    return params


def _parse_query(path):
    if "?" not in path:
        return path, {}
    p, q = path.split("?", 1)
    return p, _parse_form(q)


# ---------------- HTML 模板 ---------------- #

CSS = """
<style>
*{box-sizing:border-box}
body{font-family:-apple-system,BlinkMacSystemFont,'Segoe UI',sans-serif;
  max-width:480px;margin:0 auto;padding:16px;background:#f7f7f7;color:#222}
h1{font-size:1.3rem;margin:0 0 12px}
h2{font-size:1.05rem;margin:16px 0 8px}
nav{display:flex;gap:8px;margin:8px 0 16px;flex-wrap:wrap}
nav a{padding:6px 10px;border-radius:999px;background:#e0e0e0;color:#333;
  text-decoration:none;font-size:.85rem}
nav a.active{background:#0066cc;color:#fff}
form{background:#fff;padding:14px;border-radius:10px;
  box-shadow:0 1px 3px rgba(0,0,0,.06)}
label{display:block;margin:10px 0 4px;font-size:.9rem;color:#444}
input[type=text],input[type=password],select{
  width:100%;padding:10px;border:1px solid #ccc;border-radius:6px;
  font-size:1rem;min-height:44px}
.radio-row{display:flex;gap:16px;margin:8px 0}
.radio-row label{display:flex;align-items:center;gap:6px;margin:0}
button,input[type=submit]{
  width:100%;padding:12px;background:#0066cc;color:#fff;border:0;
  border-radius:8px;font-size:1rem;min-height:48px;margin-top:14px;cursor:pointer}
button.secondary{background:#888;margin-top:8px}
.notice{padding:10px;border-radius:8px;background:#fff8d6;
  border:1px solid #e6d97a;font-size:.9rem;margin:12px 0}
.error{padding:10px;border-radius:8px;background:#ffe0e0;
  border:1px solid #e69a9a;font-size:.9rem;margin:12px 0}
.ok{padding:10px;border-radius:8px;background:#e0ffe5;
  border:1px solid #87cf94;font-size:.9rem;margin:12px 0}
a.dl{display:inline-block;margin-top:14px;color:#0066cc}
</style>
"""


def _page(title, body, active=""):
    nav = ""
    for key, label in (("wifi", "Wi-Fi"), ("time", "時間"), ("weather", "天氣"), ("done", "完成")):
        cls = "active" if active == key else ""
        nav += "<a class='{cls}' href='/{key}'>{label}</a>".format(cls=cls, key=key, label=label)
    return (
        "<!doctype html><html lang='zh-TW'><head>"
        "<meta charset='utf-8'>"
        "<meta name='viewport' content='width=device-width,initial-scale=1'>"
        "<title>{title}</title>{css}"
        "</head><body>"
        "<h1>ePaper 設定</h1>"
        "<nav>{nav}</nav>"
        "{body}"
        "</body></html>"
    ).format(title=title, css=CSS, nav=nav, body=body)


def _wifi_page(scan_list, current_ssid, msg=""):
    options = ""
    seen = set()
    if current_ssid and current_ssid not in [x.get("ssid") for x in scan_list]:
        options += "<option value='{0}' selected>{0}（已儲存）</option>".format(current_ssid)
        seen.add(current_ssid)
    for x in scan_list:
        ssid = x.get("ssid", "")
        if not ssid or ssid in seen:
            continue
        seen.add(ssid)
        sel = " selected" if ssid == current_ssid else ""
        rssi = x.get("rssi", "")
        options += "<option value='{0}'{1}>{0}（{2}dBm）</option>".format(ssid, sel, rssi)

    msg_html = "<div class='notice'>{}</div>".format(msg) if msg else ""

    body = (
        "{msg}"
        "<form method='POST' action='/wifi'>"
        "<h2>Wi-Fi 設定</h2>"
        "<label>SSID</label>"
        "<select name='ssid'>{options}</select>"
        "<button type='button' class='secondary' onclick='rescan()'>重新掃描</button>"
        "<label>密碼</label>"
        "<input type='password' name='password' autocomplete='off'>"
        "<input type='submit' value='儲存並連線'>"
        "</form>"
        "<script>"
        "function rescan(){{"
          "var b=event.target;b.disabled=true;b.textContent='掃描中…';"
          "fetch('/scan').then(r=>r.json()).then(j=>{{"
            "var sel=document.querySelector('select[name=ssid]');"
            "sel.innerHTML='';"
            "j.forEach(x=>{{"
              "var o=document.createElement('option');"
              "o.value=x.ssid;o.textContent=x.ssid+'（'+x.rssi+'dBm）';"
              "sel.appendChild(o);}});"
            "b.disabled=false;b.textContent='重新掃描';"
          "}}).catch(e=>{{b.disabled=false;b.textContent='重新掃描';alert(e);}});"
        "}}"
        "</script>"
    ).format(msg=msg_html, options=options)
    return _page("Wi-Fi 設定", body, active="wifi")


TZ_OPTIONS = [
    (-720, "UTC−12"), (-660, "UTC−11"), (-600, "UTC−10"),
    (-540, "UTC−9"), (-480, "UTC−8 (LA)"), (-420, "UTC−7"),
    (-360, "UTC−6"), (-300, "UTC−5 (NY)"), (-240, "UTC−4"),
    (-180, "UTC−3"), (-120, "UTC−2"), (-60, "UTC−1"),
    (0, "UTC±0 (London)"), (60, "UTC+1 (Berlin)"), (120, "UTC+2"),
    (180, "UTC+3"), (210, "UTC+3:30 (Tehran)"), (240, "UTC+4"),
    (270, "UTC+4:30 (Kabul)"), (300, "UTC+5"), (330, "UTC+5:30 (India)"),
    (360, "UTC+6"), (420, "UTC+7"), (480, "UTC+8 (Taipei)"),
    (540, "UTC+9 (Tokyo)"), (570, "UTC+9:30 (Adelaide)"),
    (600, "UTC+10 (Sydney)"), (660, "UTC+11"), (720, "UTC+12"),
    (780, "UTC+13"), (840, "UTC+14"),
]


def _time_page(timecfg, msg=""):
    is_24h = bool(timecfg.get("is_24h", True))
    week_start = timecfg.get("week_start", 1)
    tz_min = timecfg.get("tz_offset_minutes")
    if tz_min is None:
        tz_min = 480
    msg_html = "<div class='ok'>{}</div>".format(msg) if msg else ""

    tz_html = "".join(
        "<option value='{v}' {s}>{l}</option>".format(
            v=v, l=l, s="selected" if v == tz_min else "")
        for v, l in TZ_OPTIONS
    )

    body = (
        "{msg}"
        "<form method='POST' action='/time'>"
        "<h2>時間 / 日曆</h2>"
        "<label>時制</label>"
        "<div class='radio-row'>"
        "<label><input type='radio' name='is_24h' value='1' {c24}/>24 小時制</label>"
        "<label><input type='radio' name='is_24h' value='0' {c12}/>12 小時制</label>"
        "</div>"
        "<label>一週起始日</label>"
        "<select name='week_start'>"
        "<option value='1' {w1}>週一</option>"
        "<option value='7' {w7}>週日</option>"
        "</select>"
        "<label>時區</label>"
        "<select name='tz_offset_minutes'>{tz_html}</select>"
        "<input type='submit' value='儲存'>"
        "</form>"
    ).format(
        msg=msg_html,
        c24="checked" if is_24h else "",
        c12="" if is_24h else "checked",
        w1="selected" if week_start == 1 else "",
        w7="selected" if week_start == 7 else "",
        tz_html=tz_html,
    )
    return _page("時間設定", body, active="time")


def _weather_page(weather_cfg, cities, msg=""):
    api_key = weather_cfg.get("api_key", "")
    is_celsius = bool(weather_cfg.get("is_celsius", True))
    city = weather_cfg.get("city") or {}
    current_name = city.get("name", "")

    options = ""
    for idx, c in enumerate(cities):
        sel = "selected" if c.get("name") == current_name else ""
        options += "<option value='{}' {}>{}</option>".format(idx, sel, c.get("name", ""))

    log_link = ""
    try:
        if "weather.log" in os.listdir():
            log_link = "<a class='dl' href='/weather.log' download>下載 weather.log</a>"
    except Exception:
        pass

    msg_html = "<div class='ok'>{}</div>".format(msg) if msg else ""

    body = (
        "{msg}"
        "<form method='POST' action='/weather'>"
        "<h2>天氣設定</h2>"
        "<label>OpenWeather API Key</label>"
        "<input type='text' name='api_key' value='{api}' autocomplete='off'>"
        "<label>城市</label>"
        "<select name='city_idx'>{options}</select>"
        "<label>溫度單位</label>"
        "<div class='radio-row'>"
        "<label><input type='radio' name='is_celsius' value='1' {cc}/>攝氏 ℃</label>"
        "<label><input type='radio' name='is_celsius' value='0' {cf}/>華氏 ℉</label>"
        "</div>"
        "<input type='submit' value='儲存並套用'>"
        "</form>"
        "{log}"
    ).format(
        msg=msg_html,
        api=api_key,
        options=options,
        cc="checked" if is_celsius else "",
        cf="" if is_celsius else "checked",
        log=log_link,
    )
    return _page("天氣設定", body, active="weather")


def _done_page(state):
    body = (
        "<div class='ok'>裝置運作中 — 設定已套用</div>"
        "<p>目前狀態：{state}</p>"
        "<p>你可以隨時回到上方的分頁修改設定。</p>"
    ).format(state=state)
    return _page("完成", body, active="done")


# ---------------- 路由器 ---------------- #

class WebConfigServer:
    def __init__(self, config, wifi, app, port=80):
        self.config = config
        self.wifi = wifi
        self.app = app  # 提供事件介面
        self.port = port
        self.cities = _load_cities()
        self._server = None

    async def start(self):
        self._server = await asyncio.start_server(self._handle, "0.0.0.0", self.port)
        print("Web server listening on :{}".format(self.port))

    async def _handle(self, reader, writer):
        try:
            request_line = await reader.readline()
            if not request_line:
                return
            parts = request_line.decode().split()
            if len(parts) < 2:
                return
            method, path = parts[0], parts[1]

            headers = {}
            while True:
                line = await reader.readline()
                if not line or line == b"\r\n":
                    break
                try:
                    k, v = line.decode().split(":", 1)
                    headers[k.strip().lower()] = v.strip()
                except Exception:
                    pass

            body = b""
            content_length = int(headers.get("content-length", "0") or 0)
            if content_length > 0:
                body = await reader.readexactly(content_length)

            await self._route(writer, method, path, body, headers)
        except Exception as e:
            print("web handler error: {}".format(e))
            try:
                await self._send(writer, 500, "text/plain", "Server error: {}".format(e))
            except Exception:
                pass
        finally:
            try:
                await writer.aclose()
            except Exception:
                pass

    async def _send(self, writer, status, content_type, body, extra_headers=None):
        if isinstance(body, str):
            body = body.encode("utf-8")
        status_text = {200: "OK", 302: "Found", 404: "Not Found",
                       400: "Bad Request", 500: "Server Error"}.get(status, "OK")
        head = "HTTP/1.0 {} {}\r\nContent-Type: {}\r\nContent-Length: {}\r\nConnection: close\r\n".format(
            status, status_text, content_type, len(body))
        if extra_headers:
            for k, v in extra_headers.items():
                head += "{}: {}\r\n".format(k, v)
        head += "\r\n"
        writer.write(head.encode())
        writer.write(body)
        await writer.drain()

    async def _redirect(self, writer, location):
        await self._send(writer, 302, "text/plain", "redirecting", {"Location": location})

    async def _route(self, writer, method, path, body, headers):
        p, query = _parse_query(path)

        if p == "/":
            # 依目前狀態 302
            if not self.wifi.is_connected():
                return await self._redirect(writer, "/wifi")
            if not self.config.is_weather_configured():
                return await self._redirect(writer, "/time" if not self._time_seen() else "/weather")
            return await self._redirect(writer, "/done")

        if p == "/wifi" and method == "GET":
            scan = self.wifi.scan()
            return await self._send(writer, 200, "text/html; charset=utf-8",
                                    _wifi_page(scan, self.config.get("wifi", "ssid") or ""))

        if p == "/wifi" and method == "POST":
            form = _parse_form(body.decode())
            ssid = form.get("ssid", "").strip()
            pwd = form.get("password", "").strip()
            with self.config.batch():
                self.config.set("wifi", "ssid", ssid)
                self.config.set("wifi", "password", pwd)
            # 觸發 STA_TRY；await 結果
            ok = await self.app.try_connect_wifi(ssid, pwd)
            if ok:
                return await self._redirect(writer, "/time")
            scan = self.wifi.scan()
            return await self._send(writer, 200, "text/html; charset=utf-8",
                                    _wifi_page(scan, ssid, msg="連線失敗，請檢查 SSID / 密碼"))

        if p == "/scan" and method == "GET":
            scan = self.wifi.scan()
            return await self._send(writer, 200, "application/json", ujson.dumps(scan))

        if p == "/time" and method == "GET":
            if not self.wifi.is_connected():
                return await self._redirect(writer, "/wifi")
            return await self._send(writer, 200, "text/html; charset=utf-8",
                                    _time_page(self.config.get("time") or {}))

        if p == "/time" and method == "POST":
            if not self.wifi.is_connected():
                return await self._redirect(writer, "/wifi")
            form = _parse_form(body.decode())
            is_24h = form.get("is_24h", "1") == "1"
            try:
                week_start = int(form.get("week_start", "1"))
            except Exception:
                week_start = 1
            try:
                tz_min = int(form.get("tz_offset_minutes", "480"))
            except Exception:
                tz_min = 480
            # clamp 到合理範圍
            if tz_min < -720:
                tz_min = -720
            elif tz_min > 840:
                tz_min = 840
            with self.config.batch():
                self.config.set("time", "is_24h", is_24h)
                self.config.set("time", "week_start", week_start)
                self.config.set("time", "tz_offset_minutes", tz_min)
            return await self._redirect(writer, "/weather")

        if p == "/weather" and method == "GET":
            if not self.wifi.is_connected():
                return await self._redirect(writer, "/wifi")
            return await self._send(writer, 200, "text/html; charset=utf-8",
                                    _weather_page(self.config.get("weather") or {}, self.cities))

        if p == "/weather" and method == "POST":
            if not self.wifi.is_connected():
                return await self._redirect(writer, "/wifi")
            form = _parse_form(body.decode())
            api_key = form.get("api_key", "").strip()
            try:
                idx = int(form.get("city_idx", "0"))
            except Exception:
                idx = 0
            is_celsius = form.get("is_celsius", "1") == "1"
            with self.config.batch():
                self.config.set("weather", "api_key", api_key)
                self.config.set("weather", "is_celsius", is_celsius)
                if 0 <= idx < len(self.cities):
                    city = self.cities[idx]
                    self.config.set_weather_city(
                        city.get("name", ""),
                        city.get("latitude", 0.0),
                        city.get("longitude", 0.0),
                    )
            # 初次設定仍透過 AP 回傳這個 redirect；稍候再開始初始化，避免
            # 成功進入 RUN 後關閉 AP 時中斷目前這個 HTTP 回應。
            await self.app.request_reinit(delay_ms=1500)
            return await self._redirect(writer, "/done")

        if p == "/done" and method == "GET":
            return await self._send(writer, 200, "text/html; charset=utf-8",
                                    _done_page(self.app.state_name()))

        if p == "/weather.log" and method == "GET":
            try:
                if "weather.log" in os.listdir():
                    with open("weather.log", "r") as f:
                        log_data = f.read()
                    return await self._send(writer, 200, "text/plain; charset=utf-8", log_data,
                                            {"Content-Disposition": "attachment; filename=weather.log"})
            except Exception:
                pass
            return await self._send(writer, 404, "text/plain", "no log")

        return await self._send(writer, 404, "text/plain", "not found")

    def _time_seen(self):
        # 時間設定一律會有預設值，所以以 weather 是否設定為主要判斷依據；
        # 預留 helper 給將來擴充。
        return False
