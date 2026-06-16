"""mDNS 註冊包裝。

依賴 vendored 套件: lib/mdns_client/ (來源 https://github.com/cbrand/micropython-mdns)
若套件尚未引入，所有 API 都會安靜地變成 no-op，並把 _available 設為 False。

使用方式:
    from mdns import MDNSResponder
    r = MDNSResponder()
    await r.start("epaper", ip="192.168.0.1")     # 後續即可 ping epaper.local
    await r.restart(ip="192.168.4.10")             # 切換到 STA 後重新註冊
"""

import uasyncio as asyncio


try:
    from mdns_client import Client as _MDNSClient
    from mdns_client.responder import Responder as _Responder
    from mdns_client.constants import MDNS_PORT as _MDNS_PORT
    _available = True
except Exception as _e:
    _MDNSClient = None
    _Responder = None
    _MDNS_PORT = 5353
    _available = False
    print("mDNS 套件未安裝，將略過 (epaper.local 不會解析)")


def _patch_bind_to_any(client):
    """改寫 client._init_socket：rp2 CYW43 lwIP 不接受 `bind(('224.0.0.251', 5353))`
    (回 ERR_USE → EADDRINUSE)，標準 mDNS 是綁 `0.0.0.0` + IP_ADD_MEMBERSHIP 收
    multicast。Upstream cbrand/micropython-mdns 沿用 ESP32 寫法綁 multicast addr，
    這裡在 instance 上 override 一份。
    """
    def _patched():
        client._close_socket()
        client.socket = client._make_socket()
        client.socket.bind(("0.0.0.0", _MDNS_PORT))
    client._init_socket = _patched


def _builtin_mdns_holds_port():
    """探測 LWIP 內建 mDNS responder 是否已 active（即 5353 port 已被佔）。
    新版 MicroPython rp2（CYW43，1.22+）韌體預設啟用，會在設 `network.hostname()`
    後自動廣播 `<name>.local`，這時 vendored mdns_client 沒辦法再 bind 5353。
    """
    try:
        import socket
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        try:
            s.bind(("0.0.0.0", _MDNS_PORT))
        except OSError:
            return True
        finally:
            try:
                s.close()
            except Exception:
                pass
    except Exception:
        pass
    return False


class MDNSResponder:
    def __init__(self):
        self._client = None
        self._resp = None
        self._consume_task = None
        self._consume_error = None
        self._hostname = None
        self._ip = None

    async def _consume_wrapper(self):
        """包一層 consume，把真正的 exception 存到 instance 上。
        uasyncio Task 在 MicroPython 沒有跨版本一致的 `.exception()` API，
        所以用這招捕捉 _init_socket / bind 的錯誤。"""
        try:
            await self._client.consume()
        except Exception as e:
            self._consume_error = e
            raise

    @property
    def available(self):
        return _available

    async def start(self, hostname, ip):
        if not _available:
            return False
        # 若有殘留的舊 client/task 先 teardown，避免重複 bind
        if self._client is not None or self._consume_task is not None:
            await self._teardown()
        self._hostname = hostname
        self._ip = ip
        return await self._spawn()

    async def restart(self, ip=None, hostname=None):
        if not _available:
            return False
        if ip is not None:
            self._ip = ip
        if hostname is not None:
            self._hostname = hostname
        # IP / 介面變了必須重建 socket，否則仍綁在舊位址上
        await self._teardown()
        return await self._spawn()

    async def stop(self):
        await self._teardown()

    async def _spawn(self):
        if not self._ip or not self._hostname:
            return False
        # 內建 LWIP mDNS responder 已 active → vendored client 無法 bind 5353，
        # 也不需要：epaper.local 已由韌體自動廣播。直接報成功即可。
        if _builtin_mdns_holds_port():
            print("LWIP 內建 mDNS responder 已 active，跳過 vendored client "
                  "(epaper.local 由韌體廣播 @ {})".format(self._ip))
            return True
        last_err = None
        for attempt in range(3):
            try:
                self._consume_error = None
                self._client = _MDNSClient(local_addr=self._ip)
                _patch_bind_to_any(self._client)
                # 預先設 stopped=False，避免 Responder.add_callback 又偷排一個
                # client.start() task；我們自己管理 consume task 才能等它退出。
                self._client.stopped = False
                self._consume_task = asyncio.create_task(self._consume_wrapper())
                # 給 consume 一個 tick 把 _init_socket() / bind() 跑完。
                # bind 失敗會讓 task 立刻結束，下面 done() 就抓得到。
                await asyncio.sleep_ms(50)
                if self._consume_task.done():
                    raise self._consume_error or OSError(
                        "consume task exited unexpectedly")

                self._resp = _Responder(
                    self._client,
                    own_ip=lambda: self._ip,
                    host=lambda: self._hostname,
                )
                self._resp.start()
                print("mDNS 已註冊 {}.local @ {}".format(self._hostname, self._ip))
                return True
            except OSError as e:
                last_err = e
                errno = e.args[0] if e.args else "?"
                print("mDNS bind 失敗 (attempt {}/3, errno={}): {}".format(
                    attempt + 1, errno, e))
                await self._teardown()
                await asyncio.sleep_ms(300 * (attempt + 1))
            except Exception as e:
                last_err = e
                print("mDNS 啟動異常 (attempt {}/3): {}: {}".format(
                    attempt + 1, type(e).__name__, e))
                await self._teardown()
                await asyncio.sleep_ms(300 * (attempt + 1))
        print("mDNS 啟動失敗，放棄: {}".format(last_err))
        return False

    async def _teardown(self):
        # 1. 解除 Responder callback
        try:
            if self._resp is not None:
                self._resp.stop()
        except Exception:
            pass

        # 2. 確保 client.stopped 為 True 並關閉 socket
        if self._client is not None:
            try:
                self._client.stopped = True
            except Exception:
                pass
            try:
                sock = self._client.socket
                if sock is not None:
                    # 主動退出 multicast group 幫 LWIP 早一點釋放 port
                    try:
                        import socket as _socket
                        from mdns_client.util import dotted_ip_to_bytes
                        from mdns_client.constants import MDNS_ADDR
                        mreq = (dotted_ip_to_bytes(MDNS_ADDR)
                                + dotted_ip_to_bytes(self._ip))
                        sock.setsockopt(_socket.IPPROTO_IP,
                                        _socket.IP_DROP_MEMBERSHIP, mreq)
                    except Exception:
                        pass
                    try:
                        sock.close()
                    except Exception:
                        pass
                    try:
                        self._client.socket = None
                    except Exception:
                        pass
            except Exception:
                pass

        # 3. 等舊 consume task 退出，最多 1 秒
        if self._consume_task is not None:
            try:
                await asyncio.wait_for(self._consume_task, 1.0)
            except Exception:
                # TimeoutError 或 task 內部例外都吃掉，避免污染上層
                pass
            self._consume_task = None

        self._client = None
        self._resp = None
