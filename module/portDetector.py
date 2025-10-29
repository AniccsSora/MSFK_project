import serial
import serial.tools.list_ports
from typing import Optional

class PortDetector:
    """串列埠自動偵測工具"""

    @staticmethod
    def find_arduino() -> Optional[str]:
        """
        自動尋找 Arduino 裝置

        Returns:
            找到的 COM Port 名稱，如果沒找到則返回 None
        """
        ports = serial.tools.list_ports.comports()

        # 常見的 Arduino VID:PID
        arduino_ids = [
            (0x2341, None),  # Arduino Official
            (0x1B4F, None),  # SparkFun
            (0x10C4, None),  # Silicon Labs (CP210x)
            (0x0403, None),  # FTDI
            (0x16C0, None),  # Teensy
            (0x2A03, None),  # Arduino.org
        ]

        for port in ports:
            # 檢查 VID
            if port.vid:
                for vid, pid in arduino_ids:
                    if port.vid == vid:
                        if pid is None or port.pid == pid:
                            print(f"✓ 找到 Arduino: {port.device} - {port.description}")
                            return port.device

            # 檢查描述中是否包含 Arduino
            if port.description and 'Arduino' in port.description:
                print(f"✓ 找到 Arduino (描述匹配): {port.device} - {port.description}")
                return port.device

        return None

    @staticmethod
    def print_all_ports():
        """列印所有可用的 COM Port"""
        ports = serial.tools.list_ports.comports()

        if not ports:
            print("沒有找到任何 COM Port")
            return

        print("\n可用的 COM Port:")
        print("-" * 70)
        for port in ports:
            print(f"Port: {port.device}")
            print(f"  描述: {port.description}")
            print(f"  VID:PID: {port.vid:04X}:{port.pid:04X}" if port.vid and port.pid else "  VID:PID: N/A")
            print(f"  製造商: {port.manufacturer if port.manufacturer else 'N/A'}")
            print("-" * 70)

