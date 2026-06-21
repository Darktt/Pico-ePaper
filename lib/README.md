# lib/ — vendored 第三方模組

## mdns_client (規格要求 epaper.local)

來源：https://github.com/cbrand/micropython-mdns

### 安裝

```sh
# 在 host 上執行
cd /tmp
git clone https://github.com/cbrand/micropython-mdns.git
mkdir -p /Users/darktt/Documents/Raspberry-Pico/E-Paper/lib/mdns_client
cp -R /tmp/micropython-mdns/src/mdns_client/. \
      /Users/darktt/Documents/Raspberry-Pico/E-Paper/lib/mdns_client/
```

### 上傳到 Pico

把 `lib/mdns_client/` 整個資料夾用 MicroPico 上傳到裝置。

### 確認 sys.path

裝置上必須能 `from mdns_client import Client`，因此 `lib/` 需要在 `sys.path` 中。
若 MicroPico 上傳沒有自動處理，可在 `boot.py` 加入：

```python
import sys
if "/lib" not in sys.path:
    sys.path.append("/lib")
```

### 如果不安裝

`mdns.py` 會偵測 import 失敗，所有 API 都會變成 no-op，不影響其他功能；只是 `epaper.local`
無法解析，使用者必須改用 IP 連線。
