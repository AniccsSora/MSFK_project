#include <Keyboard.h>
#include <Mouse.h>

// ========== 協議定義 ==========
#define SYNC_BYTE             0xAA
#define MAX_PACKET_SIZE       32
#define SERIAL_BUFFER_SIZE    128

// ACK 代碼
#define ACK_SUCCESS           0xF0
#define ACK_CRC_ERROR         0xF1
#define ACK_INVALID_CMD       0xF2
#define ACK_PARAM_ERROR       0xF3

// 指令定義
#define CMD_MOUSE_MOVE        0x01
#define CMD_MOUSE_PRESS       0x02
#define CMD_MOUSE_RELEASE     0x03
#define CMD_MOUSE_CLICK       0x04
#define CMD_MOUSE_PRESS_TIMED 0x05
#define CMD_KB_PRESS          0x10
#define CMD_KB_RELEASE        0x11
#define CMD_KB_WRITE          0x12
#define CMD_KB_RELEASE_ALL    0x13
#define CMD_KB_PRINT          0x14
#define CMD_KB_PRESS_TIMED    0x15

// ========== 日誌系統 ==========
#define LOG_LEVEL_INFO        0
#define LOG_LEVEL_WARN        1
#define LOG_LEVEL_ERROR       2
#define LOG_LEVEL_DEBUG       3

// 可以調整日誌級別
#define CURRENT_LOG_LEVEL LOG_LEVEL_DEBUG

class Logger {
private:
    uint32_t packet_counter = 0;
    uint32_t error_counter = 0;
    uint32_t success_counter = 0;

    void printTimestamp() {
        Serial1.print("[");
        Serial1.print(millis());
        Serial1.print("ms] ");
    }

    void printLevel(const char* level) {
        Serial1.print("[");
        Serial1.print(level);
        Serial1.print("] ");
    }

public:
    void begin(uint32_t baudrate = 115200) {
        Serial1.begin(baudrate);
        Serial1.println("\n==================================");
        Serial1.println("Arduino HID Monitor Started");
        Serial1.print("Firmware Version: 1.0.0 | Time: ");
        Serial1.println(millis());
        Serial1.println("==================================\n");
    }

    // === 接收封包日誌 ===
    void logPacketReceived(uint8_t len) {
        if (CURRENT_LOG_LEVEL < LOG_LEVEL_DEBUG) return;

        packet_counter++;
        printTimestamp();
        printLevel("RECV");
        Serial1.print("Packet #");
        Serial1.print(packet_counter);
        Serial1.print(" | Length: ");
        Serial1.println(len);
    }

    void logPacketData(const uint8_t *data, uint8_t len) {
        if (CURRENT_LOG_LEVEL < LOG_LEVEL_DEBUG) return;

        Serial1.print("    Data: ");
        for (uint8_t i = 0; i < len; i++) {
            if (data[i] < 0x10) Serial1.print("0");
            Serial1.print(data[i], HEX);
            Serial1.print(" ");
        }
        Serial1.println();
    }

    // === 指令執行日誌 ===
    void logCommand(const char* cmd_name, const char* details = nullptr) {
        printTimestamp();
        printLevel("EXEC");
        Serial1.print(cmd_name);
        if (details) {
            Serial1.print(" | ");
            Serial1.print(details);
        }
        Serial1.println();
    }

    // === 滑鼠操作日誌 ===
    void logMouseMove(int8_t x, int8_t y, int8_t wheel) {
        char buf[64];
        snprintf(buf, sizeof(buf), "x=%d, y=%d, wheel=%d", x, y, wheel);
        logCommand("MOUSE_MOVE", buf);
    }

    void logMouseButton(const char* action, uint8_t button) {
        char buf[64];
        const char* btn_name = getButtonName(button);
        snprintf(buf, sizeof(buf), "%s (%s)", action, btn_name);
        logCommand("MOUSE", buf);
    }

    void logMouseButtonTimed(uint8_t button, uint16_t duration_ms) {
        char buf[80];
        const char* btn_name = getButtonName(button);
        snprintf(buf, sizeof(buf), "Hold %s for %dms", btn_name, duration_ms);
        logCommand("MOUSE_TIMED", buf);
    }

    // === 鍵盤操作日誌 ===
    void logKeyboard(const char* action, uint8_t key) {
        char buf[80];
        const char* key_name = getKeyName(key);
        snprintf(buf, sizeof(buf), "%s %s (0x%02X)", action, key_name, key);
        logCommand("KEYBOARD", buf);
    }

    void logKeyboardTimed(uint8_t key, uint16_t duration_ms) {
        char buf[96];
        const char* key_name = getKeyName(key);
        snprintf(buf, sizeof(buf), "Hold %s (0x%02X) for %dms", key_name, key, duration_ms);
        logCommand("KB_TIMED", buf);
    }

    void logKeyboardPrint(const uint8_t *text, uint8_t len) {
        char buf[64];
        Serial1.print("    Text: \"");
        for (uint8_t i = 0; i < len && i < 40; i++) {
            if (text[i] >= 32 && text[i] <= 126) {
                Serial1.write(text[i]);
            } else {
                Serial1.print("\\x");
                if (text[i] < 0x10) Serial1.print("0");
                Serial1.print(text[i], HEX);
            }
        }
        if (len > 40) Serial1.print("...");
        Serial1.println("\"");
    }

    // === 錯誤日誌 ===
    void logError(const char* error_type, const char* details = nullptr) {
        error_counter++;
        printTimestamp();
        printLevel("ERROR");
        Serial1.print(error_type);
        if (details) {
            Serial1.print(" | ");
            Serial1.print(details);
        }
        Serial1.print(" | Total Errors: ");
        Serial1.println(error_counter);
    }

    void logCRCError(uint8_t expected, uint8_t received) {
        char buf[64];
        snprintf(buf, sizeof(buf), "Expected: 0x%02X, Got: 0x%02X", expected, received);
        logError("CRC_MISMATCH", buf);
    }

    void logInvalidCommand(uint8_t cmd) {
        char buf[32];
        snprintf(buf, sizeof(buf), "Unknown CMD: 0x%02X", cmd);
        logError("INVALID_CMD", buf);
    }

    void logParamError(uint8_t cmd, uint8_t expected, uint8_t received) {
        char buf[64];
        snprintf(buf, sizeof(buf), "CMD 0x%02X needs %d bytes, got %d", cmd, expected, received);
        logError("PARAM_ERROR", buf);
    }

    // === ACK 日誌 ===
    void logACK(uint8_t ack_code) {
        if (CURRENT_LOG_LEVEL < LOG_LEVEL_DEBUG) return;

        const char* ack_name;
        switch(ack_code) {
            case ACK_SUCCESS:
                ack_name = "SUCCESS";
                success_counter++;
                break;
            case ACK_CRC_ERROR: ack_name = "CRC_ERROR"; break;
            case ACK_INVALID_CMD: ack_name = "INVALID_CMD"; break;
            case ACK_PARAM_ERROR: ack_name = "PARAM_ERROR"; break;
            default: ack_name = "UNKNOWN"; break;
        }

        printTimestamp();
        printLevel("ACK");
        Serial1.print(ack_name);
        Serial1.print(" (0x");
        Serial1.print(ack_code, HEX);
        Serial1.println(")");
    }

    // === 統計資訊 ===
    void logStats() {
        Serial1.println("\n--- Statistics ---");
        Serial1.print("Total Packets: ");
        Serial1.println(packet_counter);
        Serial1.print("Successful: ");
        Serial1.println(success_counter);
        Serial1.print("Errors: ");
        Serial1.println(error_counter);
        Serial1.print("Success Rate: ");
        if (packet_counter > 0) {
            Serial1.print((success_counter * 100.0) / packet_counter, 2);
            Serial1.println("%");
        } else {
            Serial1.println("N/A");
        }
        Serial1.println("------------------\n");
    }

    // === 輔助函數：按鍵名稱 ===
    const char* getKeyName(uint8_t key) {
        switch(key) {
            // 修飾鍵
            case 0x80: return "LEFT_CTRL";
            case 0x81: return "LEFT_SHIFT";
            case 0x82: return "LEFT_ALT";
            case 0x83: return "LEFT_GUI";
            case 0x84: return "RIGHT_CTRL";
            case 0x85: return "RIGHT_SHIFT";
            case 0x86: return "RIGHT_ALT";
            case 0x87: return "RIGHT_GUI";

            // 方向鍵
            case 0xDA: return "UP_ARROW";
            case 0xD9: return "DOWN_ARROW";
            case 0xD8: return "LEFT_ARROW";
            case 0xD7: return "RIGHT_ARROW";

            // 特殊鍵
            case 0xB2: return "BACKSPACE";
            case 0xB3: return "TAB";
            case 0xB0: return "RETURN";
            case 0xB1: return "ESC";
            case 0xD4: return "DELETE";
            case 0xD3: return "PAGE_UP";
            case 0xD6: return "PAGE_DOWN";
            case 0xD2: return "HOME";
            case 0xD5: return "END";
            case 0xD1: return "INSERT";

            // 功能鍵
            case 0xC2: return "F1";
            case 0xC3: return "F2";
            case 0xC4: return "F3";
            case 0xC5: return "F4";
            case 0xC6: return "F5";
            case 0xC7: return "F6";
            case 0xC8: return "F7";
            case 0xC9: return "F8";
            case 0xCA: return "F9";
            case 0xCB: return "F10";
            case 0xCC: return "F11";
            case 0xCD: return "F12";

            // 可見字元
            case 0x20: return "SPACE";
            default:
                if (key >= 32 && key <= 126) {
                    static char buf[2];
                    buf[0] = key;
                    buf[1] = '\0';
                    return buf;
                }
                return "UNKNOWN";
        }
    }

    const char* getButtonName(uint8_t button) {
        switch(button) {
            case 0x01: return "LEFT";
            case 0x02: return "RIGHT";
            case 0x04: return "MIDDLE";
            case 0x07: return "ALL";
            default: return "UNKNOWN";
        }
    }
};

// ========== 全域物件 ==========
Logger logger;

// ========== CRC-8/MAXIM 查找表 ==========
const uint8_t CRC8_TABLE[256] PROGMEM = {
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
};

uint8_t crc8(const uint8_t *data, uint8_t len) {
    uint8_t crc = 0x00;
    for (uint8_t i = 0; i < len; i++) {
        crc = pgm_read_byte(&CRC8_TABLE[crc ^ data[i]]);
    }
    return crc;
}

// ========== 封包處理 ==========
uint8_t rx_buffer[MAX_PACKET_SIZE];
uint8_t rx_state = 0;
uint8_t rx_len = 0;
uint8_t rx_idx = 0;

void sendAck(uint8_t ack_code) {
    Serial.write(ack_code);
    logger.logACK(ack_code);
}

void processPacket(const uint8_t *data, uint8_t len) {
    if (len < 1) {
        logger.logError("EMPTY_PACKET");
        sendAck(ACK_PARAM_ERROR);
        return;
    }

    logger.logPacketData(data, len);

    uint8_t cmd = data[0];
    const uint8_t *params = data + 1;
    uint8_t param_len = len - 1;

    switch(cmd) {
        case CMD_MOUSE_MOVE: {
            if (param_len != 3) {
                logger.logParamError(cmd, 3, param_len);
                sendAck(ACK_PARAM_ERROR);
                return;
            }
            int8_t x = (int8_t)params[0];
            int8_t y = (int8_t)params[1];
            int8_t wheel = (int8_t)params[2];

            logger.logMouseMove(x, y, wheel);
            Mouse.move(x, y, wheel);
            sendAck(ACK_SUCCESS);
            break;
        }

        case CMD_MOUSE_PRESS: {
            if (param_len != 1) {
                logger.logParamError(cmd, 1, param_len);
                sendAck(ACK_PARAM_ERROR);
                return;
            }
            logger.logMouseButton("Press", params[0]);
            Mouse.press(params[0]);
            sendAck(ACK_SUCCESS);
            break;
        }

        case CMD_MOUSE_RELEASE: {
            if (param_len != 1) {
                logger.logParamError(cmd, 1, param_len);
                sendAck(ACK_PARAM_ERROR);
                return;
            }
            logger.logMouseButton("Release", params[0]);
            Mouse.release(params[0]);
            sendAck(ACK_SUCCESS);
            break;
        }

        case CMD_MOUSE_CLICK: {
            if (param_len != 1) {
                logger.logParamError(cmd, 1, param_len);
                sendAck(ACK_PARAM_ERROR);
                return;
            }
            logger.logMouseButton("Click", params[0]);
            Mouse.click(params[0]);
            sendAck(ACK_SUCCESS);
            break;
        }

        case CMD_MOUSE_PRESS_TIMED: {
            if (param_len != 3) {
                logger.logParamError(cmd, 3, param_len);
                sendAck(ACK_PARAM_ERROR);
                return;
            }
            uint8_t button = params[0];
            uint16_t duration_ms = (params[1] << 8) | params[2];

            logger.logMouseButtonTimed(button, duration_ms);
            Mouse.press(button);
            delay(duration_ms);
            Mouse.release(button);
            sendAck(ACK_SUCCESS);
            break;
        }

        case CMD_KB_PRESS: {
            if (param_len != 1) {
                logger.logParamError(cmd, 1, param_len);
                sendAck(ACK_PARAM_ERROR);
                return;
            }
            logger.logKeyboard("Press", params[0]);
            Keyboard.press(params[0]);
            sendAck(ACK_SUCCESS);
            break;
        }

        case CMD_KB_RELEASE: {
            if (param_len != 1) {
                logger.logParamError(cmd, 1, param_len);
                sendAck(ACK_PARAM_ERROR);
                return;
            }
            logger.logKeyboard("Release", params[0]);
            Keyboard.release(params[0]);
            sendAck(ACK_SUCCESS);
            break;
        }

        case CMD_KB_WRITE: {
            if (param_len != 1) {
                logger.logParamError(cmd, 1, param_len);
                sendAck(ACK_PARAM_ERROR);
                return;
            }
            logger.logKeyboard("Write", params[0]);
            Keyboard.write(params[0]);
            sendAck(ACK_SUCCESS);
            break;
        }

        case CMD_KB_RELEASE_ALL: {
            if (param_len != 0) {
                logger.logParamError(cmd, 0, param_len);
                sendAck(ACK_PARAM_ERROR);
                return;
            }
            logger.logCommand("KB_RELEASE_ALL", "All keys released");
            Keyboard.releaseAll();
            sendAck(ACK_SUCCESS);
            break;
        }

        case CMD_KB_PRINT: {
            logger.logCommand("KB_PRINT");
            logger.logKeyboardPrint(params, param_len);
            for (uint8_t i = 0; i < param_len; i++) {
                Keyboard.write(params[i]);
            }
            sendAck(ACK_SUCCESS);
            break;
        }

        case CMD_KB_PRESS_TIMED: {
            if (param_len != 3) {
                logger.logParamError(cmd, 3, param_len);
                sendAck(ACK_PARAM_ERROR);
                return;
            }
            uint8_t key = params[0];
            uint16_t duration_ms = (params[1] << 8) | params[2];

            logger.logKeyboardTimed(key, duration_ms);
            Keyboard.press(key);
            delay(duration_ms);
            Keyboard.release(key);
            sendAck(ACK_SUCCESS);
            break;
        }

        default:
            logger.logInvalidCommand(cmd);
            sendAck(ACK_INVALID_CMD);
            break;
    }
}

// ========== 統計定時器 ==========
uint32_t last_stats_time = 0;
const uint32_t STATS_INTERVAL = 30000; // 30 秒

void setup() {
    // Serial: 與 Python 通訊
    Serial.begin(230400);
    while (!Serial && millis() < 3000);

    // Serial1: 監控日誌輸出
    logger.begin(115200);

    Keyboard.begin();
    Mouse.begin();

    // 清空接收緩衝區
    while (Serial.available()) {
        Serial.read();
    }

    logger.logCommand("SYSTEM", "Ready for commands");
}

void loop() {
    // 處理命令
    while (Serial.available() > 0) {
        uint8_t byte_in = Serial.read();

        switch(rx_state) {
            case 0:    // 等待 SYNC
                if (byte_in == SYNC_BYTE) {
                    rx_state = 1;
                    rx_idx = 0;
                }
                break;

            case 1:    // 讀取 LEN
                rx_len = byte_in;
                if (rx_len == 0 || rx_len > MAX_PACKET_SIZE - 1) {
                    logger.logError("INVALID_LENGTH");
                    sendAck(ACK_PARAM_ERROR);
                    rx_state = 0;
                } else {
                    logger.logPacketReceived(rx_len);
                    rx_state = 2;
                    rx_idx = 0;
                }
                break;

            case 2:    // 讀取資料 + CRC
                rx_buffer[rx_idx++] = byte_in;

                if (rx_idx == rx_len + 1) {
                    uint8_t received_crc = rx_buffer[rx_len];
                    uint8_t calculated_crc = crc8(rx_buffer, rx_len);

                    if (received_crc == calculated_crc) {
                        processPacket(rx_buffer, rx_len);
                    } else {
                        logger.logCRCError(calculated_crc, received_crc);
                        sendAck(ACK_CRC_ERROR);
                    }

                    rx_state = 0;
                    rx_idx = 0;
                }
                break;
        }
    }

    // 定期輸出統計資訊
    if (millis() - last_stats_time > STATS_INTERVAL) {
        logger.logStats();
        last_stats_time = millis();
    }
}