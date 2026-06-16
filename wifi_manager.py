import network
import time


AP_DEFAULT_SSID = "ePaper"
AP_DEFAULT_PASSWORD = "paper1234"
# MicroPython rp2 (CYW43) 的 AP DHCP server 子網被硬碼成 192.168.4.0/24，
# `WLAN(AP_IF).ifconfig()` setter 雖然回報成功但 DHCP pool 不會跟著改
# (micropython/micropython#17401, #17977，至 2025-06 仍 open)。
# 因此這裡採用平台真實值；start_ap() 也會讀回實際 IP 以防未來修好。
AP_DEFAULT_IP = "192.168.4.1"
AP_DEFAULT_DOMAIN = "epaper.local"


def rssi_to_level(rssi):
    """將 RSSI (dBm) 轉成 0–4 的等級用於 wifi_icon/levelN.pbm"""
    if rssi is None:
        return 0
    if rssi >= -55:
        return 4
    if rssi >= -65:
        return 3
    if rssi >= -75:
        return 2
    if rssi >= -85:
        return 1
    return 0


class WiFiManager:
    def __init__(self):
        self.ap = network.WLAN(network.AP_IF)
        self.sta = network.WLAN(network.STA_IF)
        self._ap_info = None
        # 新版 MicroPython rp2 (CYW43, 1.22+) lwIP 預設啟用 mDNS responder，
        # 設了 hostname 就會自動廣播 `<name>.local`，不需要使用者 socket 程式。
        # 若這版韌體沒這功能，呼叫 hostname() 只是設 DHCP client hostname，無害；
        # vendored mdns_client 會接手 (mdns.MDNSResponder)。
        try:
            network.hostname("epaper")
            print("network.hostname 設為 'epaper'（若韌體支援內建 mDNS 即可用 epaper.local）")
        except Exception as e:
            print("network.hostname 設定失敗:", e)

    def start_ap(self, ssid=AP_DEFAULT_SSID, password=AP_DEFAULT_PASSWORD,
                 ip=AP_DEFAULT_IP, domain=AP_DEFAULT_DOMAIN):
        # 不關掉 STA — 規格要求 STA 連線後 web 服務不停止；AP 與 STA 並存
        self.ap.active(True)
        self.ap.config(ssid=ssid, key=password)
        try:
            self.ap.ifconfig((ip, "255.255.255.0", ip, ip))
        except Exception:
            pass
        # 讀回介面真正掛上的 IP；若 setter 在 rp2 CYW43 被忽略，
        # 這裡會拿到 DHCP 預設的 192.168.4.1，避免 guide 畫面與
        # mDNS local_addr 用到不存在於任何介面的位址。
        try:
            actual_ip = self.ap.ifconfig()[0]
        except Exception:
            actual_ip = ip
        info = {
            "mode": "AP",
            "ssid": ssid,
            "password": password,
            "ip": actual_ip,
            "domain": domain,
        }
        self._ap_info = info
        return info

    def stop_ap(self):
        self.ap.active(False)
        self._ap_info = None

    def ap_info(self):
        return self._ap_info

    def connect_sta(self, ssid, password, timeout=15):
        if not ssid:
            return None
        self.sta.active(True)
        # 若已連線到不同 SSID 需先斷線；否則 connect() 會被忽略
        if self.sta.isconnected():
            try:
                cur = self.sta.config("essid")
            except Exception:
                cur = None
            if cur != ssid:
                try:
                    self.sta.disconnect()
                except Exception:
                    pass
                time.sleep(0.3)
        if not self.sta.isconnected():
            self.sta.connect(ssid, password)
        t0 = time.time()
        while not self.sta.isconnected():
            if time.time() - t0 > timeout:
                return None
            time.sleep(0.5)
        ip = self.sta.ifconfig()[0]
        return {
            "mode": "STA",
            "ssid": ssid,
            "ip": ip,
        }

    def disconnect_sta(self):
        try:
            self.sta.disconnect()
        except Exception:
            pass
        self.sta.active(False)

    def is_connected(self):
        return self.sta.isconnected()

    def current_rssi(self):
        try:
            if self.sta.isconnected():
                return self.sta.status("rssi")
        except Exception:
            pass
        return None

    def current_level(self):
        return rssi_to_level(self.current_rssi())

    def sta_ip(self):
        if self.sta.isconnected():
            try:
                return self.sta.ifconfig()[0]
            except Exception:
                pass
        return None

    def scan(self):
        """回傳已去重的可見 SSID 清單 [{ssid, rssi, security}, ...]，依強度排序"""
        try:
            self.sta.active(True)
            raw = self.sta.scan()
        except Exception:
            return []
        results = {}
        for entry in raw:
            try:
                ssid = entry[0].decode("utf-8")
            except Exception:
                continue
            if not ssid:
                continue
            rssi = entry[3] if len(entry) > 3 else None
            sec = entry[4] if len(entry) > 4 else 0
            prev = results.get(ssid)
            if prev is None or (rssi is not None and rssi > prev["rssi"]):
                results[ssid] = {"ssid": ssid, "rssi": rssi, "security": sec}
        return sorted(results.values(), key=lambda x: x["rssi"] or -127, reverse=True)
