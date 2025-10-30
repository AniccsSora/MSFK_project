import serial
import serial.tools.list_ports
from typing import Optional

class PortDetector:
    """串列埠自動偵測工具"""
    @staticmethod
    def dump_all_serials(dump=False):
        ports = serial.tools.list_ports.comports()
        if dump:
            # 列出所有裝置訊息
            print("偵測到的 COM Port 列表:")
            print("-" * 40)
            for port in ports:
                print(f"  device:{port.device}, \n"
                      f"  description:{port.description}, \n"
                      f"  hwid:{port.hwid}, vid:{port.vid}, pid:{port.pid}, \n"
                      f"  serial_number:{port.serial_number}, location:{port.location}, \n"
                      f"  manufacturer:{port.manufacturer}, \n"
                      f"  product:{port.product}, \n"
                      f"  interface:{port.interface}")
                print("-" * 40)
            print("")
        return ports

    @staticmethod
    def find_arduino(dump=False) -> Optional[str]:
        """
        自動尋找 Arduino 裝置

        Returns:
            找到的 COM Port 名稱，如果沒找到則返回 None
        """

        ports = PortDetector.dump_all_serials(dump=dump)

        # 常見的 Arduino VID:PID
        arduino_ids = [
            (0x2341, None),  # Arduino Official
            # (0x1B4F, None),  # SparkFun
            # (0x10C4, None),  # Silicon Labs (CP210x)
            # (0x0403, None),  # FTDI
            # (0x16C0, None),  # Teensy
            # (0x2A03, None),  # Arduino.org
        ]

        for port in ports:
            # 檢查 VID
            if port.vid:
                for vid, pid in arduino_ids:
                    if port.vid == vid:
                        if pid is None or port.pid == pid:
                            print("  pid:", port.pid)
                            print("  vid:", port.vid)
                            print(f"  ✓ 找到 Arduino: {port.device} - {port.description}")
                            return port.device

            # 檢查描述中是否包含 Arduino
            if port.description and 'Arduino' in port.description:
                print(f"  ✓ 找到 Arduino (描述匹配): {port.device} - {port.description}")
                return port.device
        return None

    @staticmethod
    def print_all_ports():
        """列印所有可用的 COM Port"""
        ports = serial.tools.list_ports.comports()
        if not ports:
            print("沒有找到任何 COM Port")
            return

        PortDetector.dump_all_serials(dump=True)


if __name__ == "__main__":

    if True:
        detector = PortDetector()
        detector.print_all_ports()
        arduino_port = detector.find_arduino()
        print("arduino_port =", arduino_port)

        if arduino_port:
            print(f"找到的 Arduino COM Port: {arduino_port}")
        else:
            print("沒有找到 Arduino 裝置")
