import ctypes
import sys
from module.logger import logger
from typing import Dict, List, Optional, Tuple
from dataclasses import dataclass
from enum import Enum
from pathlib import Path

import pygetwindow as gw
import mss
import mss.tools


class WindowCaptureException(Exception):
    pass


class WindowNotFoundError(WindowCaptureException):
    pass


class WindowNotForegroundError(WindowCaptureException):
    pass


class DPIDetectionError(WindowCaptureException):
    pass


@dataclass
class MonitorInfo:
    index: int  # Monitor index (1-based)
    name: str
    width: int
    height: int
    x: int
    y: int
    dpi_x: int
    dpi_y: int
    scale_factor: float
    is_primary: bool

    @property
    def orientation(self) -> str:
        return "Vertical" if self.height > self.width else "Horizontal"

    @property
    def position_desc(self) -> str:
        if self.is_primary:
            return "Primary"
        elif self.x < 0 and self.y < 0:
            return "Left Top"
        elif self.x < 0:
            return "Left"
        elif self.y < 0:
            return "Upper"
        else:
            return f"Position (x, y) = ({self.x}, {self.y})"

    def __str__(self) -> str:
        return (f"Monitor {self.index}: {self.width}x{self.height} ({self.orientation})\n"
                f"  Position Desc: {self.position_desc}\n"
                f"  DPI: {self.dpi_x}x{self.dpi_y} (Scale: {self.scale_factor:.2f}x)\n"
                f"  Pos: x={self.x}, y={self.y}")


@dataclass
class WindowPosition:
    left: int
    top: int
    width: int
    height: int
    title: str

    @property
    def right(self) -> int:
        return self.left + self.width

    @property
    def bottom(self) -> int:
        return self.top + self.height


@dataclass
class CaptureRegion:
    left: int
    top: int
    width: int
    height: int

    def to_mss_monitor(self) -> Dict[str, int]:
        """ Transfer to mss's Monitor dict format. """
        return {
            'left': self.left,
            'top': self.top,
            'width': self.width,
            'height': self.height
        }


# ==================== Windows API ====================
class RECT(ctypes.Structure):
    """Windows RECT Strct """
    _fields_ = [
        ('left', ctypes.c_long),
        ('top', ctypes.c_long),
        ('right', ctypes.c_long),
        ('bottom', ctypes.c_long)
    ]

    @property
    def width(self):
        return self.right - self.left

    @property
    def height(self):
        return self.bottom - self.top


class MONITORINFO(ctypes.Structure):
    """Windows MONITORINFO  Strct
    typedef struct tagMONITORINFO {
      DWORD cbSize;
      RECT  rcMonitor;
      RECT  rcWork;
      DWORD dwFlags;
    } MONITORINFO, *LPMONITORINFO;
    """
    _fields_ = [
        ('cbSize', ctypes.c_ulong),
        ('rcMonitor', RECT),
        ('rcWork', RECT),
        ('dwFlags', ctypes.c_ulong),
        ('szDevice', ctypes.c_wchar * 32)
    ]


# ==================== DPI ====================
class DPIAwareness(Enum):
    """ DPI Aware """
    UNAWARE = 0
    SYSTEM_AWARE = 1
    PER_MONITOR_AWARE = 2


class DPIManager:
    """DPI Manger & Detect """

    # Windows API Constants
    MDT_EFFECTIVE_DPI = 0
    MONITOR_DEFAULTTONEAREST = 2

    @staticmethod
    def set_dpi_awareness(mode: DPIAwareness = DPIAwareness.PER_MONITOR_AWARE) -> bool:
        """
        Args:
            mode: DPI Awareness Mode

        Returns:
            True for success setting, False for failure
        """
        try:
            if sys.platform != 'win32':
                logger.warning("Non-Windows, Skip DPI Setting")
                return True

            # Try Windows 10+  API
            try:
                ctypes.windll.shcore.SetProcessDpiAwareness(mode.value)
                logger.info(f"DPI Awareness setting on: {mode.name}")
                return True
            except AttributeError:
                # Windows 8.1
                ctypes.windll.user32.SetProcessDPIAware()
                logger.info("Use DPI Awareness API (Windows 8.1 Below)")
                return True

        except Exception as e:
            logger.error(f"Setting DPI Awareness failed: {e}")
            raise DPIDetectionError(f"Can't setting DPI Awareness Mode: {e}")

    @staticmethod
    def get_monitor_dpi(hmonitor) -> Tuple[int, int]:
        """
        Get target monitor DPI

        Args:
            hmonitor: Windows HMONITOR handle

        Returns:
            (dpi_x, dpi_y)
        """
        l_DEFAULT_DPI = (96, 96)

        try:
            if sys.platform != 'win32':
                logger.warning("Non-Windows Use DPI 96")
                return l_DEFAULT_DPI

            dpi_x = ctypes.c_uint()
            dpi_y = ctypes.c_uint()

            result = ctypes.windll.shcore.GetDpiForMonitor(
                hmonitor,
                DPIManager.MDT_EFFECTIVE_DPI,
                ctypes.byref(dpi_x),
                ctypes.byref(dpi_y)
            )

            if result == 0:  # S_OK
                return (dpi_x.value, dpi_y.value)
            else:
                logger.warning(f"GetDpiForMonitor return: {result}, use default DPI {l_DEFAULT_DPI}")
                return l_DEFAULT_DPI

        except Exception as e:
            logger.error(f"Get DPI failed: {e}")
            return l_DEFAULT_DPI

    @staticmethod
    def calculate_scale_factor(dpi: int) -> float:
        """
        Calc scale ratio

        Args:
            dpi: DPI

        Returns:
            (1.0 = 100%, 1.5 = 150%)
        """
        return dpi / 96.0


# ==================== Monitor Manager ====================
class MonitorManager:

    def __init__(self):
        self.monitors: List[MonitorInfo] = []
        self._detect_monitors()

    def _detect_monitors(self) -> None:
        """Detect all screens and their DPI information (using Windows API) """
        logger.info("Start detecting screen information...")

        try:
            if sys.platform != 'win32':
                logger.warning("For non-Windows systems, use the screen information provided by MSS.")
                self._detect_monitors_mss()
                return

            def callback(hmonitor, hdc, lprect, lparam):
                info = MONITORINFO()
                info.cbSize = ctypes.sizeof(MONITORINFO)

                if ctypes.windll.user32.GetMonitorInfoW(hmonitor, ctypes.byref(info)):
                    rect = info.rcMonitor

                    # Get DPI
                    dpi_x, dpi_y = DPIManager.get_monitor_dpi(hmonitor)
                    scale_factor = DPIManager.calculate_scale_factor(dpi_x)

                    is_primary = bool(info.dwFlags & 1)  # MONITORINFOF_PRIMARY = 1

                    monitor_info = MonitorInfo(
                        index=len(self.monitors) + 1,
                        name=info.szDevice,
                        width=rect.width,
                        height=rect.height,
                        x=rect.left,
                        y=rect.top,
                        dpi_x=dpi_x,
                        dpi_y=dpi_y,
                        scale_factor=scale_factor,
                        is_primary=is_primary
                    )

                    self.monitors.append(monitor_info)
                    logger.debug(f"Detected: {monitor_info}")

                return True  # Continue enumeration

            MonitorEnumProc = ctypes.WINFUNCTYPE(
                ctypes.c_int,
                ctypes.c_ulong,
                ctypes.c_ulong,
                ctypes.POINTER(RECT),
                ctypes.c_double
            )

            ctypes.windll.user32.EnumDisplayMonitors(
                None, None, MonitorEnumProc(callback), 0
            )

            logger.info(f"Total Detected {len(self.monitors)} Monitors")

        except Exception as e:
            logger.error(f"Screen detection failed. Try using the MSS alternative: {e}")
            self._detect_monitors_mss()

    def _detect_monitors_mss(self) -> None:
        """Use the MSS alternative solution to detect the screen (DPI detection is not supported)."""
        logger.info("Detecting the screen using an MSS alternative…")

        try:
            with mss.mss() as sct:
                for idx, monitor in enumerate(sct.monitors[1:], 1):
                    # MSS cannot detect DPI; use the default value.
                    monitor_info = MonitorInfo(
                        index=idx,
                        name=f"Monitor {idx}",
                        width=monitor['width'],
                        height=monitor['height'],
                        x=monitor['left'],
                        y=monitor['top'],
                        dpi_x=96,
                        dpi_y=96,
                        scale_factor=1.0,
                        is_primary=(monitor['left'] == 0 and monitor['top'] == 0)
                    )

                    self.monitors.append(monitor_info)
                    logger.debug(f"Detected: {monitor_info}")

            logger.info(f"A total of {len(self.monitors)} screen (no DPI information)")

        except Exception as e:
            logger.error(f"mss screen detection also failed.: {e}")
            raise DPIDetectionError(f"Unable to detect screen information: {e}")

    def get_monitor_at_point(self, x: int, y: int) -> Optional[MonitorInfo]:
        """
        Get the screen where the specified coordinates are located

        Args:
            x, y: logic

        Returns:
            MonitorInfo / None
        """
        for monitor in self.monitors:
            if (monitor.x <= x < monitor.x + monitor.width and
                monitor.y <= y < monitor.y + monitor.height):
                return monitor

        logger.warning(f"Pos ({x}, {y}) not within the range of any known screen")
        return None

    def get_primary_monitor(self) -> MonitorInfo:
        for monitor in self.monitors:
            if monitor.is_primary:
                return monitor

        logger.warning("Primary screen not found, using first screen")
        return self.monitors[0]

    def print_all_monitors(self) -> None:
        logger.hr("Available monitor [Start]", level=1)


        for monitor in self.monitors:
            logger.info(f"\n{monitor}")

        logger.hr("Available monitor [Done]", level=1)

    def select_monitor_interactive(self) -> Optional[MonitorInfo]:
        self.print_all_monitors()

        while True:
            try:
                choice = input(f"\nSelect monitor index (1-{len(self.monitors)}，q to cancel): ").strip()

                if choice.lower() == 'q':
                    logger.info("User cancelled monitor selection")
                    return None

                choice = int(choice)
                if 1 <= choice <= len(self.monitors):
                    selected = self.monitors[choice - 1]
                    logger.info(f" ✓ Selected {choice}: {selected.name}")
                    logger.info(f"User select: {selected}")
                    return selected
                else:
                    logger.error(f"❌ Please use 1 ~ {len(self.monitors)} number")

            except ValueError:
                logger.error("❌ Please enter a valid number (or enter 'q' to cancel).")
            except KeyboardInterrupt:
                logger.info("\n\nThe operation has been cancelled.")
                logger.info("User interruption selection")
                return None


class WindowCapture:
    # Viewport coordinate anomaly threshold.
    COORDINATE_THRESHOLD = 10000

    def __init__(self, window_title: str = "MapleStory", auto_init_dpi: bool = True):
        """

        Args:
            window_title: target window title
            auto_init_dpi:
        """
        self.window_title = window_title
        self.window: Optional[gw.Win32Window] = None
        self.monitor_manager: Optional[MonitorManager] = None

        if auto_init_dpi:
            self._initialize_dpi()

        logger.info(f"WindowCapture init done，target title: '{window_title}'")

    def _initialize_dpi(self) -> None:
        try:
            DPIManager.set_dpi_awareness(DPIAwareness.PER_MONITOR_AWARE)
            self.monitor_manager = MonitorManager()
        except Exception as e:
            logger.error(f"DPI init failed: {e}")
            raise

    def list_available_windows(self, ignore_empty: bool = True) -> List[str]:
        """
        list all available window titles

        Args:
            ignore_empty: default True to ignore empty titles

        Returns:
            List[str]: window titles
        """
        titles = gw.getAllTitles()

        if ignore_empty:
            titles = [title for title in titles if title.strip()]

        logger.debug(f"Found {len(titles)} windows")
        return titles

    def find_window(self, title: Optional[str] = None) -> bool:
        """
        Search for the target window by title

        Args:
            title: window title, if None use self.window_title

        Returns:
            True for success
        """
        search_title = title or self.window_title

        try:
            windows = gw.getWindowsWithTitle(search_title)

            if not windows:
                logger.error(f"Not found named '{search_title}' window")
                self._print_available_windows()
                raise WindowNotFoundError(f"Not found window named: '{search_title}'")

            self.window = windows[0]
            logger.info(f"Found window: '{self.window.title}'")
            return True

        except IndexError:
            logger.error(f"Not found '{search_title}' windows")
            self._print_available_windows()
            raise WindowNotFoundError(f"Not found window name: '{search_title}'")

    def _print_available_windows(self) -> None:
        logger.info("List all available windows:")
        for title in self.list_available_windows():
            logger.info(f"  - {title}")
        logger.info()

    def get_window_position(self) -> WindowPosition:
        """
        Logic coordinate of the target window

        Returns:
            WindowPosition Object
        """
        if self.window is None:
            raise WindowNotFoundError("Call find_window() first.")

        if (abs(self.window.top) > self.COORDINATE_THRESHOLD or
            abs(self.window.left) > self.COORDINATE_THRESHOLD):
            error_msg = (
                f"Window '{self.window.title}' abnormal, not in frontend\n"
                f"  Pos: x={self.window.left}, y={self.window.top}\n"
                f"  Please check if the window is minimized or obscured."
            )
            logger.error(error_msg)
            raise WindowNotForegroundError(error_msg)

        position = WindowPosition(
            left=self.window.left,
            top=self.window.top,
            width=self.window.width,
            height=self.window.height,
            title=self.window.title
        )

        logger.info(f"Win pos: x={position.left}, y={position.top}, "
                   f"w={position.width}, h={position.height}")

        return position

    def calculate_capture_region(self,
                                 position: Optional[WindowPosition] = None,
                                 use_manual_scale: Optional[float] = None) -> CaptureRegion:
        """
        Calculate the screenshot area (entity pixel coordinates).

        Args:
            position: The window position will be automatically obtained if it is set to None.
            use_manual_scale: Manually specify the scaling ratio; if set to None, it will be automatically detected.

        Returns:
            CaptureRegion Object
        """
        if position is None:
            position = self.get_window_position()

        if use_manual_scale is not None:
            scale = use_manual_scale
            logger.info(f"Use manual scaling: {scale:.2f}x")
        else:
            if self.monitor_manager is None:
                logger.warning("MonitorManager is not initialized; use the default scaling of 1.0x.")
                scale = 1.0
            else:
                # Use the center point of the window to determine the current screen.
                center_x = position.left + position.width // 2
                center_y = position.top + position.height // 2

                monitor = self.monitor_manager.get_monitor_at_point(center_x, center_y)

                if monitor:
                    scale = monitor.scale_factor
                    logger.info(f"The viewport is located at {monitor.name}, DPI scaling is: {scale:.2f}x")
                else:
                    scale = 1.0
                    logger.warning("Unable to determine the screen size of the window, using the default scaling 1.0x")

        region = CaptureRegion(
            left=int(position.left * scale),
            top=int(position.top * scale),
            width=int(position.width * scale),
            height=int(position.height * scale)
        )

        logger.info(f"Screenshot area (entity pixels): "
                   f"left={region.left}, top={region.top}, "
                   f"width={region.width}, height={region.height}")

        return region

    def capture(self,
                output_path: str = "screenshot.png",
                manual_scale: Optional[float] = None) -> str:
        """
        Capture the window screen

        Args:
            output_path: Output file path
            manual_scale: Manually specify the scaling ratio

        Returns:
            Output file path
        """
        logger.info(f"Start taking screenshots and outputting the path.: {output_path}")

        if self.window is None:
            self.find_window()

        # Calculate the screenshot area
        region = self.calculate_capture_region(use_manual_scale=manual_scale)

        try:
            with mss.mss() as sct:
                screenshot = sct.grab(region.to_mss_monitor())
                mss.tools.to_png(screenshot.rgb, screenshot.size, output=output_path)

            logger.info(f"Screenshot successful: {output_path}")
            return output_path

        except Exception as e:
            logger.error(f"Screenshot failed: {e}")
            raise WindowCaptureException(f"Screenshot failed: {e}")

    def capture_full_monitor(self,
                            monitor_index: int = 1,
                            output_path: Optional[str] = None) -> str:
        """
        Capture the entire screen

        Args:
            monitor_index: Screen numbering (starting from 1)
            output_path: Output path; if None, it will be automatically named.

        Returns:
            Output file path
        """
        if self.monitor_manager is None:
            raise DPIDetectionError("MonitorManager Uninitialized")

        if monitor_index < 1 or monitor_index > len(self.monitor_manager.monitors):
            raise ValueError(f"Invalid screen number: {monitor_index}")

        monitor = self.monitor_manager.monitors[monitor_index - 1]

        if output_path is None:
            output_path = (f"monitor_{monitor_index}_"
                          f"{monitor.width}x{monitor.height}_"
                          f"scale{monitor.scale_factor:.2f}.png")
            output_path = logger.LOG_DIR_SCREENSHOT / output_path

        logger.info(f"Capture screen {monitor_index}: {monitor.name}")

        try:
            with mss.mss() as sct:
                # The monitors index in MSS starts from 1.
                screenshot = sct.grab(sct.monitors[monitor_index])
                mss.tools.to_png(screenshot.rgb, screenshot.size, output=output_path)

            logger.info(f"Screenshot successful: {output_path}")
            return output_path

        except Exception as e:
            logger.error(f"Screenshot failed: {e}")
            raise WindowCaptureException(f"Screenshot failed: {e}")

    def get_window_monitor(self) -> MonitorInfo:
        position = self.get_window_position()
        center_x = position.left + position.width // 2
        center_y = position.top + position.height // 2
        return self.monitor_manager.get_monitor_at_point(center_x, center_y)

def quick_capture(window_title: str = "MapleStory",
                 output_path: str = "screenshot.png",
                 manual_scale: Optional[float] = None) -> str:
    """
    Quick screenshot convenience function

    Args:
        window_title: Window title
        output_path: Output path
        manual_scale: Manual scaling
    Returns:
        Output file path
    """
    capture = WindowCapture(window_title)
    capture.find_window()
    return capture.capture(output_path, manual_scale)


# ==================== 測試與範例 ====================
def test_monitor_detection():
    logger.hr("Test 1: Monitor Detection", level=1)


    try:
        DPIManager.set_dpi_awareness()
        manager = MonitorManager()
        manager.print_all_monitors()

        primary = manager.get_primary_monitor()
        logger.hr(f"Primary monitor: {primary.name} (scale: {primary.scale_factor:.2f}x)", level=1)

    except Exception as e:
        logger.error(f"Screen detection test failed: {e}")
        raise

def test_window_capture(window_title: str = "MapleStory"):
    logger.hr(f"Test 2: window capture - '{window_title}'", level=1)


    try:
        capture = WindowCapture(window_title)

        logger.info("Available windows:")
        for title in capture.list_available_windows()[:10]:
            logger.info(f"  - {title}")

        logger.info(f"Find window '{window_title}'...")
        capture.find_window()

        position = capture.get_window_position()
        logger.info(f"Window position (logical coordinates):")
        logger.info(f"  x={position.left}, y={position.top}")
        logger.info(f"  w={position.width}, h={position.height}")

        region_auto = capture.calculate_capture_region()
        logger.info(f"Screenshot area (auto DPI):")
        logger.info(f"  left={region_auto.left}, top={region_auto.top}")
        logger.info(f"  width={region_auto.width}, height={region_auto.height}")

        output = capture.capture(logger.LOG_DIR_SCREENSHOT / "test_auto_dpi.png")
        logger.info(f" ✓ Screenshot successful: {output}")

        logger.warning(" Testing manual scaling 1.0x...")
        region_manual = capture.calculate_capture_region(use_manual_scale=1.0)
        at_monitor = capture.get_window_monitor().index
        output_manual = capture.capture(logger.LOG_DIR_SCREENSHOT / "test_manual_scale_1x_mon_{}.png".format(at_monitor), manual_scale=1.0)
        logger.info(f"✓ Manually zoomed screenshot successful: {output_manual}")

    except WindowNotFoundError as e:
        logger.error(f"❌ Window not found: {e}")
    except WindowNotForegroundError as e:
        logger.error(f"❌ Window status error: {e}")
    except Exception as e:
        logger.error(f"Screenshot test failed: {e}")
        raise


def test_full_monitor_capture():
    logger.hr("Test 3: Full-screen screenshot", level=1)

    try:
        capture = WindowCapture("dummy")

        monitor = capture.monitor_manager.select_monitor_interactive()

        if monitor:
            output = capture.capture_full_monitor(monitor.index)
            logger.info(f"✓ Screenshot successful: {output}", level=1)
        else:
            logger.warning("Cancel screenshot", level=1)

    except Exception as e:
        logger.error(f"Full-screen screenshot test failed: {e}")
        raise


def main():
    global logger_debug
    logger_debug = True
    logger.hr("Multi-screen DPI-sensing window screenshot tool", level=1)

    logger.debug("舒服 debug")

    try:
        # Test 1: Screen Detection
        test_monitor_detection()

        # Test 2: Screenshot
        logger.hr("Test 2: Go to find MapleStory Window Screenshot [Start]", level=1)
        test_window_capture("MapleStory")
        logger.hr("Test 2: Go to find MapleStory Window Screenshot [Done]", level=1)

        # Test 3: Full-screen screenshot (optional)
        # choice = input("\nShould we test full-screen screenshot? (y/N): ").strip().lower()
        choice = 'N'
        if choice == 'y':
            test_full_monitor_capture()


        logger.hr("All done", level=1)


    except Exception as e:
        logger.error(f"Program execution failed: {e}")
        logger.error(f" ❌ Error: {e}")
        return 1

    return 0

def main2():
    capture = WindowCapture("MapleStory")
    capture.find_window()
    monitor = capture.get_window_monitor()  # 自動知道在哪個螢幕
    logger.info(f"Window in {monitor.name}, scale {monitor.scale_factor}x")
    # save
    output = capture.capture("screenshot_enhanced.png")
    logger.info(f"Capture successfully: {output}")

if __name__ == "__main__":
    # logger.set_debug(True)

    # Run:
    #    python -m module.screenshot.window_capture
    sys.exit(main())
    # sys.exit(main2())
