import time
from module.arduino_hid import ArduinoHID, ArduinoHIDException

# ========== 使用範例 ==========
if __name__ == "__main__":
    try:
        with ArduinoHID() as hid:
            print("\n=== Arduino HID 改良版測試 ===")
            print("提示: 按下硬體按鈕可以中斷執行中的指令\n")

            # 暫停日誌(減少 Serial1 輸出)
            print("1. 暫停日誌...")
            hid.pause_logging()
            time.sleep(0.5)

            # 測試基本輸入
            print("2. 打開記事本...")
            hid.win_r()
            time.sleep(1)
            hid.keyboard_print("notepad")
            time.sleep(0.5)
            hid.enter()
            time.sleep(1)

            # 恢復日誌
            print("3. 恢復日誌...")
            hid.resume_logging()
            time.sleep(0.5)

            # 測試可中斷的長文字輸入
            print("4. 開始輸入長文字 (可按硬體按鈕中斷)...")
            hid.reset_interrupt_flag()

            long_text = "This is a very long text that can be interrupted by pressing the hardware button. " * 100

            try:
                hid.keyboard_type(long_text, delay=0.05, check_interrupt=True)
                print("✓ 文字輸入完成")
            except ArduinoHIDException as e:
                print(f"✗ {e}")
                hid.reset_interrupt_flag()

            time.sleep(1)

            # 清理
            print("5. 關閉記事本...")
            hid.alt_f4()
            time.sleep(0.5)
            hid.keyboard_write(hid.KEY_RIGHT_ARROW)
            time.sleep(0.3)
            hid.enter()

            print("\n✓ 測試完成!")

    except ArduinoHIDException as e:
        print(f"❌ 錯誤: {e}")
    except KeyboardInterrupt:
        print("\n⚠️ 被使用者中斷")
