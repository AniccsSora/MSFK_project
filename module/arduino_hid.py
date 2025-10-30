import serial
import serial.tools.list_ports
import struct
import time
from typing import Optional, List, Tuple
from module.com_port_detector import PortDetector

class ArduinoHIDException(Exception):
    """Arduino HID 異常"""
    pass


class ArduinoHID:
    # Protocol
    SYNC_BYTE = 0xAA
    ACK_SUCCESS = 0xF0
    ACK_CRC_ERROR = 0xF1
    ACK_INVALID_CMD = 0xF2
    ACK_PARAM_ERROR = 0xF3

    # Command
    CMD_MOUSE_MOVE = 0x01
    CMD_MOUSE_PRESS = 0x02
    CMD_MOUSE_RELEASE = 0x03
    CMD_MOUSE_CLICK = 0x04
    CMD_MOUSE_PRESS_TIMED = 0x05
    CMD_KB_PRESS = 0x10
    CMD_KB_RELEASE = 0x11
    CMD_KB_WRITE = 0x12
    CMD_KB_RELEASE_ALL = 0x13
    CMD_KB_PRINT = 0x14
    CMD_KB_PRESS_TIMED = 0x15

    # Mouse
    MOUSE_LEFT = 0x01
    MOUSE_RIGHT = 0x02
    MOUSE_MIDDLE = 0x04
    MOUSE_ALL = 0x07

    # Keyboard
    KEY_LEFT_CTRL = 0x80
    KEY_LEFT_SHIFT = 0x81
    KEY_LEFT_ALT = 0x82
    KEY_LEFT_GUI = 0x83
    KEY_RIGHT_CTRL = 0x84
    KEY_RIGHT_SHIFT = 0x85
    KEY_RIGHT_ALT = 0x86
    KEY_RIGHT_GUI = 0x87

    KEY_UP_ARROW = 0xDA
    KEY_DOWN_ARROW = 0xD9
    KEY_LEFT_ARROW = 0xD8
    KEY_RIGHT_ARROW = 0xD7
    KEY_BACKSPACE = 0xB2
    KEY_TAB = 0xB3
    KEY_RETURN = 0xB0
    KEY_ESC = 0xB1
    KEY_DELETE = 0xD4
    KEY_PAGE_UP = 0xD3
    KEY_PAGE_DOWN = 0xD6
    KEY_HOME = 0xD2
    KEY_END = 0xD5

    KEY_F1 = 0xC2
    KEY_F2 = 0xC3
    KEY_F3 = 0xC4
    KEY_F4 = 0xC5
    KEY_F5 = 0xC6
    KEY_F6 = 0xC7
    KEY_F7 = 0xC8
    KEY_F8 = 0xC9
    KEY_F9 = 0xCA
    KEY_F10 = 0xCB
    KEY_F11 = 0xCC
    KEY_F12 = 0xCD

    # CRC-8/MAXIM lookup table
    CRC8_TABLE = [
        0x00, 0x5E, 0xBC, 0xE2, 0x61, 0x3F, 0xDD, 0x83,
        0xC2, 0x9C, 0x7E, 0x20, 0xA3, 0xFD, 0x1F, 0x41,
        0x9D, 0xC3, 0x21, 0x7F, 0xFC, 0xA2, 0x40, 0x1E,
        0x5F, 0x01, 0xE3, 0xBD, 0x3E, 0x60, 0x82, 0xDC,
        0x23, 0x7D, 0x9F, 0xC1, 0x42, 0x1C, 0xFE, 0xA0,
        0xE1, 0xBF, 0x5D, 0x03, 0x80, 0xDE, 0x3C, 0x62,
        0xBE, 0xE0, 0x02, 0x5C, 0xDF, 0x81, 0x63, 0x3D,
        0x7C, 0x22, 0xC0, 0x9E, 0x1D, 0x43, 0xA1, 0xFF,
        0x46, 0x18, 0xFA, 0xA4, 0x27, 0x79, 0x9B, 0xC5,
        0x84, 0xDA, 0x38, 0x66, 0xE5, 0xBB, 0x59, 0x07,
        0xDB, 0x85, 0x67, 0x39, 0xBA, 0xE4, 0x06, 0x58,
        0x19, 0x47, 0xA5, 0xFB, 0x78, 0x26, 0xC4, 0x9A,
        0x65, 0x3B, 0xD9, 0x87, 0x04, 0x5A, 0xB8, 0xE6,
        0xA7, 0xF9, 0x1B, 0x45, 0xC6, 0x98, 0x7A, 0x24,
        0xF8, 0xA6, 0x44, 0x1A, 0x99, 0xC7, 0x25, 0x7B,
        0x3A, 0x64, 0x86, 0xD8, 0x5B, 0x05, 0xE7, 0xB9,
        0x8C, 0xD2, 0x30, 0x6E, 0xED, 0xB3, 0x51, 0x0F,
        0x4E, 0x10, 0xF2, 0xAC, 0x2F, 0x71, 0x93, 0xCD,
        0x11, 0x4F, 0xAD, 0xF3, 0x70, 0x2E, 0xCC, 0x92,
        0xD3, 0x8D, 0x6F, 0x31, 0xB2, 0xEC, 0x0E, 0x50,
        0xAF, 0xF1, 0x13, 0x4D, 0xCE, 0x90, 0x72, 0x2C,
        0x6D, 0x33, 0xD1, 0x8F, 0x0C, 0x52, 0xB0, 0xEE,
        0x32, 0x6C, 0x8E, 0xD0, 0x53, 0x0D, 0xEF, 0xB1,
        0xF0, 0xAE, 0x4C, 0x12, 0x91, 0xCF, 0x2D, 0x73,
        0xCA, 0x94, 0x76, 0x28, 0xAB, 0xF5, 0x17, 0x49,
        0x08, 0x56, 0xB4, 0xEA, 0x69, 0x37, 0xD5, 0x8B,
        0x57, 0x09, 0xEB, 0xB5, 0x36, 0x68, 0x8A, 0xD4,
        0x95, 0xCB, 0x29, 0x77, 0xF4, 0xAA, 0x48, 0x16,
        0xE9, 0xB7, 0x55, 0x0B, 0x88, 0xD6, 0x34, 0x6A,
        0x2B, 0x75, 0x97, 0xC9, 0x4A, 0x14, 0xF6, 0xA8,
        0x74, 0x2A, 0xC8, 0x96, 0x15, 0x4B, 0xA9, 0xF7,
        0xB6, 0xE8, 0x0A, 0x54, 0xD7, 0x89, 0x6B, 0x35
    ]

    def __init__(self, port: Optional[str] = None, baudrate: int = 230400,
                 timeout: float = 0.1, retries: int = 3, auto_detect: bool = True):
        """
        Init Arduino HID

        Args:
            port: `COMx` string, if None go auto-detect
            baudrate: bardrate (default: 230400)
            timeout: timeout
            retries: retry
            auto_detect: True.
        """
        if port is None and auto_detect:
            print("🔍 正在自動偵測 Arduino 裝置...")
            port = PortDetector.find_arduino()

            if port is None:
                print("\n❌ 自動偵測失敗,顯示所有可用 COM Port:")
                PortDetector.print_all_ports()
                raise ArduinoHIDException("找不到 Arduino 裝置,請手動指定 port 參數")

        if port is None:
            raise ArduinoHIDException("必須指定 port 參數或啟用 auto_detect")

        try:
            self.ser = serial.Serial(port, baudrate, timeout=timeout)
            self.retries = retries
            print(f"✓ 已連接到: {port} @ {baudrate} bps")
            time.sleep(2)  # 等待 Arduino 初始化

            # 清空接收緩衝區
            self.ser.reset_input_buffer()
            self.ser.reset_output_buffer()

        except serial.SerialException as e:
            raise ArduinoHIDException(f"無法開啟 {port}: {e}")

    def _crc8(self, data: bytes) -> int:
        """計算 CRC-8/MAXIM"""
        crc = 0x00
        for byte in data:
            crc = self.CRC8_TABLE[crc ^ byte]
        return crc

    def _send_packet(self, cmd: int, params: bytes = b'') -> bool:
        """發送封包並等待 ACK"""
        data = bytes([cmd]) + params
        data_len = len(data)
        crc = self._crc8(data)
        packet = bytes([self.SYNC_BYTE, data_len]) + data + bytes([crc])

        for attempt in range(self.retries):
            try:
                self.ser.write(packet)
                ack = self.ser.read(1)

                if len(ack) == 0:
                    if attempt < self.retries - 1:
                        time.sleep(0.01)
                        continue
                    raise ArduinoHIDException("No ACK received")

                ack_code = ack[0]

                if ack_code == self.ACK_SUCCESS:
                    return True
                elif ack_code == self.ACK_CRC_ERROR:
                    if attempt < self.retries - 1:
                        time.sleep(0.01)
                        continue
                    raise ArduinoHIDException("CRC error")
                elif ack_code == self.ACK_INVALID_CMD:
                    raise ArduinoHIDException(f"Invalid command: 0x{cmd:02X}")
                elif ack_code == self.ACK_PARAM_ERROR:
                    raise ArduinoHIDException(f"Parameter error for command: 0x{cmd:02X}")
                else:
                    raise ArduinoHIDException(f"Unknown ACK code: 0x{ack_code:02X}")

            except serial.SerialException as e:
                raise ArduinoHIDException(f"Serial error: {e}")

        return False

    # ========== 滑鼠方法 ==========

    def mouse_move(self, x: int, y: int, wheel: int = 0) -> bool:
        """移動滑鼠"""
        x = max(-127, min(127, x))
        y = max(-127, min(127, y))
        wheel = max(-127, min(127, wheel))
        params = struct.pack('bbb', x, y, wheel)
        return self._send_packet(self.CMD_MOUSE_MOVE, params)

    def mouse_press(self, button: int = MOUSE_LEFT) -> bool:
        """按下滑鼠按鍵"""
        return self._send_packet(self.CMD_MOUSE_PRESS, bytes([button]))

    def mouse_release(self, button: int = MOUSE_LEFT) -> bool:
        """釋放滑鼠按鍵"""
        return self._send_packet(self.CMD_MOUSE_RELEASE, bytes([button]))

    def mouse_click(self, button: int = MOUSE_LEFT) -> bool:
        """點擊滑鼠"""
        return self._send_packet(self.CMD_MOUSE_CLICK, bytes([button]))

    def mouse_press_for(self, button: int = MOUSE_LEFT, duration: float = 0.2) -> bool:
        """按住滑鼠按鍵指定時間後釋放"""
        if not self.mouse_press(button):
            return False
        time.sleep(duration)
        return self.mouse_release(button)

    def mouse_press_timed(self, button: int = MOUSE_LEFT, duration_ms: int = 200) -> bool:
        """按住滑鼠按鍵指定時間後釋放(Arduino 端控制)"""
        duration_ms = max(1, min(65535, duration_ms))
        params = struct.pack('>BH', button, duration_ms)
        return self._send_packet(self.CMD_MOUSE_PRESS_TIMED, params)

    # ========== 鍵盤方法 ==========
    def keyboard_press(self, key: int) -> bool:
        """按下按鍵"""
        return self._send_packet(self.CMD_KB_PRESS, bytes([key]))

    def keyboard_release(self, key: int) -> bool:
        """釋放按鍵"""
        return self._send_packet(self.CMD_KB_RELEASE, bytes([key]))

    def keyboard_write(self, key: int) -> bool:
        """按下並釋放按鍵"""
        return self._send_packet(self.CMD_KB_WRITE, bytes([key]))

    def keyboard_release_all(self) -> bool:
        """釋放所有按鍵"""
        return self._send_packet(self.CMD_KB_RELEASE_ALL)

    def keyboard_press_for(self, key: int, duration: float) -> bool:
        """按住按鍵指定時間後釋放"""
        if not self.keyboard_press(key):
            return False
        time.sleep(duration)
        return self.keyboard_release(key)

    def keyboard_press_timed(self, key: int, duration_ms: int) -> bool:
        """按住按鍵指定時間後釋放(Arduino 端控制)"""
        duration_ms = max(1, min(65535, duration_ms))
        params = struct.pack('>BH', key, duration_ms)
        return self._send_packet(self.CMD_KB_PRESS_TIMED, params)

    def keyboard_print(self, text: str) -> bool:
        """輸入字串(一次性發送)"""
        if len(text) > 30:
            for i in range(0, len(text), 30):
                chunk = text[i:i + 30]
                if not self._send_packet(self.CMD_KB_PRINT, chunk.encode('ascii', errors='ignore')):
                    return False
            return True
        else:
            return self._send_packet(self.CMD_KB_PRINT, text.encode('ascii', errors='ignore'))

    def keyboard_execute_sequence(self, *actions, delay: float = 0.01) -> bool:
        """
        執行複雜的鍵盤操作序列

        Args:
            *actions: 動作序列，可以是字串（輸入文字）或整數（按鍵代碼）
            delay: 延遲時間

        Example:
            # 輸入 ">>>" 然後輸入 "<<<" 再向左移動3次
            keyboard_execute_sequence(">>>", "<<<",
                                     KEY_LEFT_ARROW, KEY_LEFT_ARROW, KEY_LEFT_ARROW,
                                     [KEY_LEFT_ARROW]*3 )
        Returns:
            bool: 執行是否成功
        """
        for action in actions:
            if isinstance(action, str):
                # 字串：輸入文字
                if not self.keyboard_type(action, delay=delay):
                    return False
            elif isinstance(action, int):
                # 整數：按鍵代碼
                if not self.keyboard_write(action):
                    return False
                time.sleep(delay)
            elif isinstance(action, list):
                # 列表：多個按鍵代碼
                for key in action:
                    if not isinstance(key, int):
                        raise ValueError(f"列表中的元素必須是整數按鍵代碼: {key}")
                    if not self.keyboard_write(key):
                        return False
                    time.sleep(delay)
            else:
                raise ValueError(f"不支援的動作類型: {type(action)}")

        return True

    def keyboard_type(self, text: str, delay: float = 0.01) -> bool:
        """輸入文字(逐字元發送)"""
        for char in text:
            if not self.keyboard_write(ord(char)):
                return False
            if delay > 0:
                time.sleep(delay)
        return True

    def hotkey(self, *keys: int, hold_time: float = 0.05) -> bool:
        """執行快捷鍵組合"""
        for key in keys:
            if not self.keyboard_press(key):
                return False
        time.sleep(hold_time)
        for key in reversed(keys):
            if not self.keyboard_release(key):
                return False
        return True

    # ========== 常用快捷鍵 ==========
    def backspace(self) -> bool:
        """ Backspace """
        return self.keyboard_write(self.KEY_BACKSPACE)

    def enter(self) -> bool:
        """ Enter """
        return self.keyboard_write(self.KEY_RETURN)
    def alt_f4(self) -> bool:
        """ Alt+F4 """
        return self.hotkey(self.KEY_LEFT_ALT, self.KEY_F4)

    def win_r(self) -> bool:
        """ Win+R """
        return self.hotkey(self.KEY_LEFT_GUI, ord('r'))

    def ctrl_c(self) -> bool:
        """Ctrl+C"""
        return self.hotkey(self.KEY_LEFT_CTRL, ord('c'))

    def ctrl_v(self) -> bool:
        """Ctrl+V"""
        return self.hotkey(self.KEY_LEFT_CTRL, ord('v'))

    def ctrl_x(self) -> bool:
        """Ctrl+X"""
        return self.hotkey(self.KEY_LEFT_CTRL, ord('x'))

    def ctrl_z(self) -> bool:
        """Ctrl+Z"""
        return self.hotkey(self.KEY_LEFT_CTRL, ord('z'))

    def ctrl_a(self) -> bool:
        """Ctrl+A"""
        return self.hotkey(self.KEY_LEFT_CTRL, ord('a'))

    def close(self):
        """關閉連接"""
        if self.ser.is_open:
            self.ser.close()
            print("✓ 連接已關閉")

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.close()

if __name__ == "__main__":

    with ArduinoHID() as presser:
        presser.win_r()
        time.sleep(1)
        presser.keyboard_print("notepad")
        time.sleep(1)
        presser.enter()
        time.sleep(1)
        #
        presser.keyboard_execute_sequence(">>>", "<<<", [presser.KEY_LEFT_ARROW]*3, delay=0.25 )

        with open("../asset/test_text_sample/123.txt", "r", encoding="utf-8") as f:
            content = f.read()
            for c in content:
                presser.keyboard_type(c, delay=0.035)
                presser.backspace()

        presser.alt_f4()
        presser.keyboard_execute_sequence(presser.KEY_LEFT_ARROW,
                                          presser.KEY_RETURN, delay=0.5)


        print("done")
