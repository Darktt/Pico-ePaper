import ujson
import os


DEFAULT_CONFIG = {
    "wifi": {
        "ssid": "",
        "password": ""
    },
    "time": {
        "is_24h": True,
        "week_start": 1,  # 1: 週一, 7: 週日
        "tz_offset_minutes": 480  # UTC+8（台灣）；±分鐘
    },
    "weather": {
        "api_key": "",
        "city": {
            "name": "",
            "lat": 0.0,
            "lon": 0.0
        },
        "is_celsius": True
    }
}


class ConfigManager:
    def __init__(self, filename="config.json"):
        self.filename = filename
        self.config = None
        self._batch_depth = 0
        self._dirty = False
        self.load()

    def load(self):
        try:
            if self.filename in os.listdir():
                with open(self.filename, "r") as f:
                    self.config = ujson.load(f)
            else:
                self.config = ujson.loads(ujson.dumps(DEFAULT_CONFIG))
                self.save()
        except Exception:
            self.config = ujson.loads(ujson.dumps(DEFAULT_CONFIG))
            self.save()

    def save(self):
        if self.config is None:
            return
        if self._batch_depth > 0:
            self._dirty = True
            return
        with open(self.filename, "w") as f:
            ujson.dump(self.config, f)

    def batch(self):
        return _Batch(self)

    def _enter_batch(self):
        self._batch_depth += 1

    def _exit_batch(self):
        self._batch_depth -= 1
        if self._batch_depth == 0 and self._dirty:
            self._dirty = False
            self.save()

    def get(self, section, key=None):
        if not isinstance(self.config, dict):
            self.load()
        if not isinstance(self.config, dict):
            return None
        if key is not None:
            return self.config.get(section, {}).get(key)
        return self.config.get(section)

    def set(self, section, key, value):
        if not isinstance(self.config, dict):
            self.load()
        if not isinstance(self.config, dict):
            return
        if section not in self.config:
            self.config[section] = {}
        self.config[section][key] = value
        self.save()

    def set_weather_city(self, name, lat, lon):
        if not isinstance(self.config, dict):
            self.load()
        if not isinstance(self.config, dict):
            return
        self.config["weather"]["city"] = {"name": name, "lat": lat, "lon": lon}
        self.save()

    def is_wifi_configured(self):
        ssid = self.get("wifi", "ssid")
        return bool(ssid)

    def is_weather_configured(self):
        api_key = self.get("weather", "api_key")
        city = self.get("weather", "city") or {}
        return bool(api_key) and bool(city.get("name"))


class _Batch:
    def __init__(self, manager):
        self.manager = manager

    def __enter__(self):
        self.manager._enter_batch()
        return self.manager

    def __exit__(self, exc_type, exc, tb):
        self.manager._exit_batch()
        return False
