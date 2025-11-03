import sys
import serial
import serial.tools.list_ports
from typing import Optional
from module.logger import logger


class PortDetector:
    @staticmethod
    def dump_all_serials(dump=False):
        ports = serial.tools.list_ports.comports()
        if dump:
            logger.info("Detect COM Port List:")
            logger.info("-" * 40)
            for port in ports:
                logger.info(f"  device:{port.device}, \n"
                            f"  description:{port.description}, \n"
                            f"  hwid:{port.hwid}, vid:{port.vid}, pid:{port.pid}, \n"
                            f"  serial_number:{port.serial_number}, location:{port.location}, \n"
                            f"  manufacturer:{port.manufacturer}, \n"
                            f"  product:{port.product}, \n"
                            f"  interface:{port.interface}",
                            )  # ??? fail  extra={"highlighter": logger.console_highlighter}
                logger.info("-" * 40)
            logger.info("")
        return ports

    @staticmethod
    def find_arduino(dump=False) -> Optional[str]:
        """
        Auto-detect Arduino device

        Returns:
            Found COM Port name，if not found return None
        """

        ports = PortDetector.dump_all_serials(dump=dump)

        # Common Arduino VID:PID
        arduino_ids = [
            (0x2341, None),  # Arduino Official
            # (0x1B4F, None),  # SparkFun
            # (0x10C4, None),  # Silicon Labs (CP210x)
            # (0x0403, None),  # FTDI
            # (0x16C0, None),  # Teensy
            # (0x2A03, None),  # Arduino.org
        ]

        for port in ports:
            if port.vid:
                for vid, pid in arduino_ids:
                    if port.vid == vid:
                        if pid is None or port.pid == pid:
                            logger.info("  pid/vid:", port.pid, "/", port.vid)
                            logger.info(f"  ✓ Found Arduino: {port.device} - {port.description}")
                            return port.device

            if port.description and 'Arduino' in port.description:
                logger.info(f"  ✓ Found Arduino (Desc matched): {port.device} - {port.description}")
                return port.device
        return None

    @staticmethod
    def print_all_ports():
        ports = serial.tools.list_ports.comports()
        if not ports:
            logger.error("No any available COM Ports")
            return

        PortDetector.dump_all_serials(dump=True)


def main():
    detector = PortDetector()
    detector.print_all_ports()
    arduino_port = detector.find_arduino()
    logger.info(f"arduino_port = {arduino_port}")

    if arduino_port:
        logger.info(f"Found Arduino COM Port: {arduino_port}")
    else:
        logger.info("Not found Arduino device.")


if __name__ == "__main__":
    # Run:
    #     python -m module.com.port_detector
    try:
        sys.exit(main())
    except Exception as e:
        logger.exception("Un-handle excpetion: %s", e)
        sys.exit(1)
