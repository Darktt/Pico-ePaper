# Pico_ePaper-3.7.py 文件說明

本檔案為 Waveshare 3.7 吋電子紙（e-Paper）顯示器的驅動程式，適用於 Raspberry Pi Pico。主要提供顯示初始化、清除、顯示圖像、局部刷新、進入休眠等功能。

---

## 類別：`EPD_3in7`

### 建構子
```python
def __init__(self)
```
初始化 e-Paper 顯示器，設置 SPI、GPIO 腳位、緩衝區，並自動進行 4 階灰階初始化與清屏。

---

### 主要公開方法

| 方法名稱                             | 功能說明                                                            |
| ------------------------------------ | ------------------------------------------------------------------- |
| `digital_write(pin, value)`          | 對指定的 GPIO 腳位寫入高/低電位。                                   |
| `digital_read(pin)`                  | 讀取指定 GPIO 腳位的電位值。                                        |
| `delay_ms(delaytime)`                | 延遲指定的毫秒數。                                                  |
| `spi_writebyte(data)`                | 透過 SPI 傳送一組位元組資料。                                       |
| `module_exit()`                      | 將重置腳位設為低電位，通常用於模組關閉或釋放資源。                  |
| `reset()`                            | 對 e-Paper 進行硬體重置。                                           |
| `send_command(command)`              | 傳送指令給 e-Paper 控制器。                                         |
| `send_data(data)`                    | 傳送資料給 e-Paper 控制器。                                         |
| `ReadBusy()`                         | 偵測 e-Paper 是否忙碌，等待其完成操作。                             |
| `Load_LUT(lut)`                      | 載入不同的 LUT（查找表），用於不同顯示模式（如 1 灰階、4 灰階等）。 |
| `EPD_3IN7_4Gray_init()`              | 初始化 4 階灰階顯示模式。                                           |
| `EPD_3IN7_1Gray_init()`              | 初始化 1 階灰階（黑白）顯示模式。                                   |
| `EPD_3IN7_4Gray_Clear()`             | 清除 4 階灰階顯示內容（全白）。                                     |
| `EPD_3IN7_1Gray_Clear()`             | 清除 1 階灰階（黑白）顯示內容（全白）。                             |
| `EPD_3IN7_4Gray_Display(Image)`      | 將 4 階灰階影像資料顯示到 e-Paper 上。                              |
| `EPD_3IN7_1Gray_Display(Image)`      | 將 1 階灰階（黑白）影像資料顯示到 e-Paper 上。                      |
| `EPD_3IN7_1Gray_Display_Part(Image)` | 局部刷新顯示（只更新部分畫面，提升速度，適合黑白模式）。            |
| `Sleep()`                            | 讓 e-Paper 進入深度休眠模式，降低功耗。                             |

---

## 其他說明

- `image1Gray`、`image4Gray`：分別為 1 灰階與 4 灰階的 frame buffer，可用於繪圖、顯示文字等。
- `buffer_1Gray`、`buffer_4Gray`：對應的位元組緩衝區。
- LUT（查找表）用於不同顯示刷新模式，影響顯示效果與速度。

---

## 範例（主程式）

主程式示範如何初始化顯示器、繪製文字與圖形、切換顯示模式、局部刷新與進入休眠。

```python
if __name__=='__main__':
    epd = EPD_3in7()
    epd.image1Gray.fill(0xff)
    epd.image4Gray.fill(0xff)
    epd.image4Gray.text("Waveshare", 5, 10, epd.black)
    epd.image4Gray.text("Pico_ePaper-3.7", 5, 40, epd.black)
    epd.image4Gray.text("Raspberry Pico", 5, 70, epd.black)
    epd.EPD_3IN7_4Gray_Display(epd.buffer_4Gray)
    # ... 其餘繪圖與顯示操作 ...
    epd.Sleep()
```

---

如需更詳細的參數或用法，請參考原始碼內的註解或 Waveshare 官方文件。 