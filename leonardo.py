from module.arduinoHID import ArduinoHID, ArduinoHIDException

if __name__ == "__main__":
    try:
        with ArduinoHID() as hid:  # 不指定 port，自動偵測
            hid.mouse_move(10, 10)
            hid.keyboard_type("Hello Auto!")
    except ArduinoHIDException as e:
        print(f"錯誤: {e}")
