import os
import framebuf


_cache = []
_CACHE_SIZE = 4


def _read_pbm_header(f):
    """解析 P4 (binary mono) PBM header，回傳 (width, height)。
    格式: P4\\n[# comment ...\\n]<width> <height>\\n<data...>
    """
    magic = f.readline().strip()
    if magic != b"P4":
        raise ValueError("not a P4 PBM: " + repr(magic))
    while True:
        line = f.readline()
        if not line:
            raise ValueError("unexpected EOF in PBM header")
        line = line.strip()
        if line.startswith(b"#"):
            continue
        if not line:
            continue
        parts = line.split()
        if len(parts) >= 2:
            return int(parts[0]), int(parts[1])
        # 寬高可能分行
        w = int(parts[0])
        # 讀下一行高度
        while True:
            line = f.readline()
            if not line:
                raise ValueError("unexpected EOF reading PBM height")
            line = line.strip()
            if line.startswith(b"#") or not line:
                continue
            h = int(line.split()[0])
            return w, h


def load_pbm(path):
    """載入 P4 PBM，回傳 (FrameBuffer MONO_HLSB, width, height)。
    PBM 黑色 bit = 1、白色 bit = 0；framebuf MONO_HLSB 0 = 黑、1 = 白，
    所以讀取時需要逐 byte 反相。
    """
    for entry in _cache:
        if entry[0] == path:
            # LRU bump
            _cache.remove(entry)
            _cache.append(entry)
            return entry[1], entry[2], entry[3]

    with open(path, "rb") as f:
        w, h = _read_pbm_header(f)
        raw = f.read()

    row_bytes = (w + 7) // 8
    expected = row_bytes * h
    if len(raw) < expected:
        raise ValueError("PBM data too short: {} < {}".format(len(raw), expected))
    raw = raw[:expected]

    buf = bytearray(expected)
    for i in range(expected):
        buf[i] = (~raw[i]) & 0xFF

    fb = framebuf.FrameBuffer(buf, w, h, framebuf.MONO_HLSB)

    entry = (path, fb, w, h, buf)  # 保留 buf 防 GC
    _cache.append(entry)
    if len(_cache) > _CACHE_SIZE:
        _cache.pop(0)
    return fb, w, h


def exists(path):
    """判斷 icon 檔案是否存在（不引發例外）。"""
    try:
        parts = path.rsplit("/", 1)
        if len(parts) == 2:
            d, name = parts
            return name in os.listdir(d)
        return path in os.listdir()
    except Exception:
        return False
