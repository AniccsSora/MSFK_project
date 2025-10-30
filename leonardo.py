from module.arduino_hid import ArduinoHID, ArduinoHIDException

if __name__ == "__main__":
    try:
        with ArduinoHID() as hid:  # 不指定 port，自動偵測
            hid.hotkey()
            hid.mouse_press()
            #hid.keyboard_type("Hello Auto!")
    except ArduinoHIDException as e:
        print(f"錯誤: {e}")
