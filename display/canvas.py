import framebuf

try:
    import micropython
except Exception:
    micropython = None


# landscape (使用者邏輯): 480 (寬) × 280 (高)
# native (面板實際): 280 (寬) × 480 (高)
LANDSCAPE_W = 480
LANDSCAPE_H = 280
NATIVE_W = 280
NATIVE_H = 480

# landscape stride (bytes per row): 480 / 8 = 60
# native stride (bytes per row): 280 / 8 = 35
_SRC_STRIDE = LANDSCAPE_W >> 3
_DST_STRIDE = NATIVE_W >> 3


# viper 加速：MicroPython 編譯期決定能不能用。
# 不用 hasattr() 偵測，因為 micropython.viper 是 compile-time directive 而非
# runtime attribute；直接 exec def，失敗就 fallback。
_transpose_cw_viper = None
if micropython is not None:
    try:
        @micropython.viper
        def _transpose_cw_viper(src: ptr8, dst: ptr8,
                                lx0: int, ly0: int,
                                lw: int, lh: int):
            """ROTATE_CW: nx = ly, ny = LANDSCAPE_W - 1 - lx
            src = landscape buf MONO_HLSB, dst = native buf MONO_HLSB。
            """
            LW: int = 480
            src_stride: int = 60   # LANDSCAPE_W >> 3
            dst_stride: int = 35   # NATIVE_W >> 3
            ly: int = ly0
            ly_end: int = ly0 + lh
            lx_end: int = lx0 + lw
            while ly < ly_end:
                lx: int = lx0
                row_off: int = ly * src_stride
                # nx 在這個 ly 是固定的
                nx: int = ly
                nx_byte: int = nx >> 3
                nx_bit: int = 7 - (nx & 7)
                nx_mask: int = 1 << nx_bit
                nx_mask_inv: int = 0xFF ^ nx_mask
                while lx < lx_end:
                    sb: int = src[row_off + (lx >> 3)]
                    bit: int = (sb >> (7 - (lx & 7))) & 1
                    ny: int = LW - 1 - lx
                    di: int = ny * dst_stride + nx_byte
                    if bit != 0:
                        dst[di] = (dst[di] | nx_mask) & 0xFF
                    else:
                        dst[di] = dst[di] & nx_mask_inv
                    lx += 1
                ly += 1
    except Exception as _e:
        print("[canvas] viper compile 失敗: {}".format(_e))
        _transpose_cw_viper = None


# native 加速：比 viper 寬鬆，做不到 viper 那麼快但仍然比解譯快 5–10×。
_transpose_cw_native = None
if micropython is not None:
    try:
        @micropython.native
        def _transpose_cw_native(src, dst, lx0, ly0, lw, lh):
            LW = 480
            src_stride = 60
            dst_stride = 35
            ly = ly0
            ly_end = ly0 + lh
            lx_end = lx0 + lw
            while ly < ly_end:
                lx = lx0
                row_off = ly * src_stride
                nx_byte = ly >> 3
                nx_mask = 1 << (7 - (ly & 7))
                nx_mask_inv = 0xFF ^ nx_mask
                while lx < lx_end:
                    sb = src[row_off + (lx >> 3)]
                    bit = (sb >> (7 - (lx & 7))) & 1
                    ny = LW - 1 - lx
                    di = ny * dst_stride + nx_byte
                    if bit:
                        dst[di] = dst[di] | nx_mask
                    else:
                        dst[di] = dst[di] & nx_mask_inv
                    lx += 1
                ly += 1
    except Exception as _e:
        print("[canvas] native compile 失敗: {}".format(_e))
        _transpose_cw_native = None


class LandscapeCanvas(framebuf.FrameBuffer):
    """
    480×280 橫向座標 → 內部維護一塊獨立的 framebuffer，
    commit 時轉置到 EPD 的 280×480 native framebuffer。

    座標約定（向右旋轉 90 度後使用者看到的方向）：
      landscape (0, 0)      → 左上
      landscape (479, 0)    → 右上
      landscape (0, 279)    → 左下
      landscape (479, 279)  → 右下

    Native 映射:
      native_x = landscape_y
      native_y = (LANDSCAPE_W - 1) - landscape_x
    （等價於原始 framebuffer 向右旋轉 90° 後顯示。如方向不對請翻轉 ROTATE_CW 旗標。）

    為了讓 writer.Writer 能直接使用，本類別繼承 framebuf.FrameBuffer 並暴露
    width / height 屬性。
    """

    ROTATE_CW = True

    def __init__(self, epd):
        self.epd = epd
        self.width = LANDSCAPE_W
        self.height = LANDSCAPE_H
        self.buf = bytearray(LANDSCAPE_W * LANDSCAPE_H // 8)
        # 0xFF = 白底（EPD 1Gray: 0 = 黑、1 = 白）
        for i in range(len(self.buf)):
            self.buf[i] = 0xFF
        super().__init__(self.buf, LANDSCAPE_W, LANDSCAPE_H, framebuf.MONO_HLSB)
        # 追蹤 EPD controller 是否仍在 active 狀態（內部 0x26 舊框 RAM 是否有效）。
        # 每次 commit 完成後不 Sleep，下次 partial refresh 的 DU LUT 才能用正確的舊框
        # 狀態算 transition；只有 shutdown() 才會真的把 EPD 送進 deep sleep。
        self._awake = False

    # ----- 額外便利方法 -----
    def clear(self):
        for i in range(len(self.buf)):
            self.buf[i] = 0xFF

    def blit_pbm(self, x, y, pbm_fb, w, h, invert=False):
        """把 PBM FrameBuffer 貼到指定座標。"""
        if invert:
            # 反相版本：把 1 變 0、0 變 1
            for ly in range(h):
                for lx in range(w):
                    self.pixel(x + lx, y + ly, 1 - pbm_fb.pixel(lx, ly))
        else:
            self.blit(pbm_fb, x, y)

    # ----- 轉置到 native framebuffer -----
    def _transpose_pixel(self, lx, ly):
        if self.ROTATE_CW:
            nx = ly
            ny = (LANDSCAPE_W - 1) - lx
        else:
            nx = (LANDSCAPE_H - 1) - ly
            ny = lx
        return nx, ny

    def _transpose_into(self, native_fb, rect=None):
        if rect is None:
            lx0, ly0, lw, lh = 0, 0, LANDSCAPE_W, LANDSCAPE_H
        else:
            lx0, ly0, lw, lh = rect
        # 加速版（要求 ROTATE_CW + native_fb 是 epd.image1Gray）
        if self.ROTATE_CW and native_fb is self.epd.image1Gray:
            if _transpose_cw_viper is not None:
                _transpose_cw_viper(self.buf, self.epd.buffer_1Gray,
                                    lx0, ly0, lw, lh)
                return
            if _transpose_cw_native is not None:
                _transpose_cw_native(self.buf, self.epd.buffer_1Gray,
                                     lx0, ly0, lw, lh)
                return
        # Fallback: 純 Python（慢，僅供 debug）
        for ly in range(ly0, ly0 + lh):
            for lx in range(lx0, lx0 + lw):
                c = self.pixel(lx, ly)
                nx, ny = self._transpose_pixel(lx, ly)
                native_fb.pixel(nx, ny, c)

    # ----- 對外 commit -----
    def commit_full(self):
        """全幀刷新（init → GC LUT display）。

        完成後 *不* Sleep。Sleep (0x10) 會讓 controller 進深度睡眠並失去內部 0x26
        舊框 RAM；下次 partial refresh 的 DU LUT 會用 undefined 算 transition，
        導致 ghosting。改成只在 shutdown() 才真正 Sleep。
        """
        self.epd.EPD_3IN7_1Gray_init()
        self._transpose_into(self.epd.image1Gray, None)
        self.epd.EPD_3IN7_1Gray_Display(self.epd.buffer_1Gray)
        self._awake = True

    def _native_rect(self, rect):
        """把 landscape rect 換算成 native (portrait) rect。"""
        x, y, w, h = rect
        if self.ROTATE_CW:
            # (lx, ly) → (ly, LANDSCAPE_W-1-lx)；rect 對應的 native:
            nx = y
            ny = LANDSCAPE_W - x - w
            return nx, ny, h, w
        nx = LANDSCAPE_H - y - h
        ny = x
        return nx, ny, h, w

    def commit_part(self, rect):
        """部分刷新；rect 為 landscape 座標 (x, y, w, h)。

        DU LUT 是 (old_pixel, new_pixel) → waveform 的對照表，需要 controller
        內部 0x26 舊框 RAM 寫有目前面板真實狀態才能算對 transition。
        Waveshare driver 的 `EPD_3IN7_1Gray_Display_Part` 只寫 0x24 (new)，
        0x26 (old) 由 controller 在每次 display update 後自動拷貝 0x24→0x26。
        所以只要 commit 之間不再呼叫 init/reset/Sleep，0x26 自然會保留正確狀態，
        DU LUT 就能把舊像素乾淨擦掉，不再需要兩階段擦白 + 重畫。

        若 EPD 尚未建立 baseline（剛開機 / shutdown 後第一次），fallback 走全幀。
        """
        if not self._awake:
            self.commit_full()
            return
        self._transpose_into(self.epd.image1Gray, rect)
        self.epd.EPD_3IN7_1Gray_Display_Part(self.epd.buffer_1Gray)

    def shutdown(self):
        """讓 EPD 進深度睡眠；下一次 commit_part 會自動先做一次 commit_full 重建 baseline。"""
        if self._awake:
            self.epd.Sleep()
            self._awake = False
