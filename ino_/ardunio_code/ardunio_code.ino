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
#define ACK_INTERRUPTED       0xF4  // 新增:被中斷

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
#define CMD_PAUSE_LOG         0x20  // 新增:暫停日誌
#define CMD_RESUME_LOG        0x21  // 新增:恢復日誌
#define CMD_CLEAR_QUEUE       0x22  // 新增:清空佇列

// ========== 硬體按鈕設定 ==========
#define INTERRUPT_PIN         2     // 使用支援中斷的 PIN (Arduino Micro: 0,1,2,3,7)
#define BUTTON_DEBOUNCE_MS    50    // 防彈跳時間

// ========== 全域狀態 ==========
volatile bool g_interrupt_flag = false;  // 中斷旗標
volatile bool g_log_enabled = true;      // 日誌啟用狀態
uint32_t last_button_press = 0;          // 防彈跳計時器

// ========== 指令佇列結構 ==========
#define QUEUE_SIZE 16

struct CommandPacket {
    uint8_t cmd;
    uint8_t params[MAX_PACKET_SIZE];
    uint8_t param_len;
    uint32_t timestamp;  // 接收時間戳
};

class CommandQueue {
private:
    CommandPacket queue[QUEUE_SIZE];
    volatile uint8_t head;
    volatile uint8_t tail;
    volatile uint8_t count;

public:
    CommandQueue() : head(0), tail(0), count(0) {}

    bool push(const CommandPacket& packet) {
        if (count >= QUEUE_SIZE) {
            return false;  // 佇列滿了
        }
        queue[tail] = packet;
        tail = (tail + 1) % QUEUE_SIZE;
        count++;
        return true;
    }

    bool pop(CommandPacket& packet) {
        if (count == 0) {
            return false;  // 佇列空了
        }
        packet = queue[head];
        head = (head + 1) % QUEUE_SIZE;
        count--;
        return true;
    }

    void clear() {
        head = tail = count = 0;
    }

    uint8_t size() const { return count; }
    bool isEmpty() const { return count == 0; }
    bool isFull() const { return count >= QUEUE_SIZE; }
};

CommandQueue cmdQueue;

// ========== CRC-8 查找表 ==========
const PROGMEM uint8_t CRC8_TABLE[256] = {
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

// ========== 日誌系統 (改良版) ==========
#define LOG_LEVEL_INFO        0
#define LOG_LEVEL_WARN        1
#define LOG_LEVEL_ERROR       2
#define LOG_LEVEL_DEBUG       3

#define CURRENT_LOG_LEVEL LOG_LEVEL_DEBUG

class Logger {
private:
    uint32_t packet_counter = 0;
    uint32_t error_counter = 0;
    uint32_t success_counter = 0;

    void printTimestamp() {
        if (!g_log_enabled) return;
        Serial1.print("[");
        Serial1.print(millis());
        Serial1.print("ms] ");
    }

    void printLevel(const char* level) {
        if (!g_log_enabled) return;
        Serial1.print("[");
        Serial1.print(level);
        Serial1.print("] ");
    }

public:
    void reset_counter(){
        packet_counter = 0;
        error_counter = 0;
        success_counter = 0;
    }

    void begin(uint32_t baudrate = 115200) {
        Serial1.begin(baudrate);
        Serial1.println("\n==================================");
        Serial1.println("Arduino HID Monitor v2.0 (Queue Mode)");
        Serial1.print("Firmware Time: ");
        Serial1.println(millis());
        Serial1.println("==================================\n");
    }

    void logQueueStatus() {
        if (!g_log_enabled || CURRENT_LOG_LEVEL < LOG_LEVEL_DEBUG) return;
        printTimestamp();
        printLevel("QUEUE");
        Serial1.print("Size: ");
        Serial1.print(cmdQueue.size());
        Serial1.print("/");
        Serial1.println(QUEUE_SIZE);
    }

    void logPacketReceived(uint8_t len) {
        if (!g_log_enabled || CURRENT_LOG_LEVEL < LOG_LEVEL_DEBUG) return;
        packet_counter++;
        printTimestamp();
        printLevel("RECV");
        Serial1.print("Packet #");
        Serial1.print(packet_counter);
        Serial1.print(" | Length: ");
        Serial1.println(len);
    }

    void logPacketData(const uint8_t *data, uint8_t len) {
        if (!g_log_enabled || CURRENT_LOG_LEVEL < LOG_LEVEL_DEBUG) return;
        Serial1.print("    Data: ");
        for (uint8_t i = 0; i < len; i++) {
            if (data[i] < 0x10) Serial1.print("0");
            Serial1.print(data[i], HEX);
            Serial1.print(" ");
        }
        Serial1.println();
    }

    void logCommand(const char* cmd_name, const char* details = nullptr) {
        if (!g_log_enabled) return;
        printTimestamp();
        printLevel("EXEC");
        Serial1.print(cmd_name);
        if (details) {
            Serial1.print(" | ");
            Serial1.print(details);
        }
        Serial1.println();
    }

    void logInterrupt() {
        // 中斷訊息永遠顯示
        printTimestamp();
        printLevel("INT");
        Serial1.println("❌ USER INTERRUPT - Clearing queue");
    }

    void logLogStateChange(bool enabled) {
        // 狀態變更永遠顯示
        Serial1.print("\n[LOG] ");
        Serial1.println(enabled ? "✓ Logging ENABLED" : "✗ Logging PAUSED");
    }

    void logMouseMove(int8_t x, int8_t y, int8_t wheel) {
        if (!g_log_enabled) return;
        char buf[64];
        snprintf(buf, sizeof(buf), "x=%d, y=%d, wheel=%d", x, y, wheel);
        logCommand("MOUSE_MOVE", buf);
    }

    void logMouseButton(const char* action, uint8_t button) {
        if (!g_log_enabled) return;
        char buf[64];
        const char* btn_name = getButtonName(button);
        snprintf(buf, sizeof(buf), "%s (%s)", action, btn_name);
        logCommand("MOUSE", buf);
    }

    void logKeyboard(const char* action, uint8_t key) {
        if (!g_log_enabled) return;
        char buf[80];
        const char* key_name = getKeyName(key);
        snprintf(buf, sizeof(buf), "%s %s (0x%02X)", action, key_name, key);
        logCommand("KEYBOARD", buf);
    }

    void logKeyboardPrint(const uint8_t *text, uint8_t len) {
        if (!g_log_enabled) return;
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

    void logError(const char* error_type, const char* details = nullptr) {
        if (!g_log_enabled) return;
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
        if (!g_log_enabled) return;
        char buf[64];
        snprintf(buf, sizeof(buf), "Expected: 0x%02X, Got: 0x%02X", expected, received);
        logError("CRC_MISMATCH", buf);
    }

    void logInvalidCommand(uint8_t cmd) {
        if (!g_log_enabled) return;
        char buf[32];
        snprintf(buf, sizeof(buf), "Unknown CMD: 0x%02X", cmd);
        logError("INVALID_CMD", buf);
    }

    void logParamError(uint8_t cmd, uint8_t expected, uint8_t received) {
        if (!g_log_enabled) return;
        char buf[64];
        snprintf(buf, sizeof(buf), "CMD 0x%02X needs %d bytes, got %d", cmd, expected, received);
        logError("PARAM_ERROR", buf);
    }

    void logACK(uint8_t ack_code) {
        if (!g_log_enabled || CURRENT_LOG_LEVEL < LOG_LEVEL_DEBUG) return;

        const char* ack_name;
        switch(ack_code) {
            case ACK_SUCCESS:
                ack_name = "SUCCESS";
                success_counter++;
                break;
            case ACK_CRC_ERROR: ack_name = "CRC_ERROR"; break;
            case ACK_INVALID_CMD: ack_name = "INVALID_CMD"; break;
            case ACK_PARAM_ERROR: ack_name = "PARAM_ERROR"; break;
            case ACK_INTERRUPTED: ack_name = "INTERRUPTED"; break;
            default: ack_name = "UNKNOWN"; break;
        }

        printTimestamp();
        printLevel("ACK");
        Serial1.print(ack_name);
        Serial1.print(" (0x");
        Serial1.print(ack_code, HEX);
        Serial1.println(")");
    }

    void logStats() {
        if (!g_log_enabled) return;
        Serial1.println("\n--- Statistics ---");
        Serial1.print("Total Packets: ");
        Serial1.println(packet_counter);
        Serial1.print("Successful: ");
        Serial1.println(success_counter);
        Serial1.print("Errors: ");
        Serial1.println(error_counter);
        Serial1.print("Queue Size: ");
        Serial1.println(cmdQueue.size());
        Serial1.print("Success Rate: ");
        if (packet_counter > 0) {
            Serial1.print((success_counter * 100.0) / packet_counter, 2);
            Serial1.println("%");
        } else {
            Serial1.println("N/A");
        }
        // Time printTimestamp
        unsigned long ms = millis();  // 開機後經過的毫秒
        unsigned long seconds = ms / 1000;
        unsigned long minutes = seconds / 60;
        unsigned long hours = minutes / 60;

        seconds = seconds % 60;
        minutes = minutes % 60;
        hours = hours % 24;  // 若不需要天數，可取 24 小時制

        char buf[20];
        sprintf(buf, "%luh %lumin %lus", hours, minutes, seconds);
        Serial1.println(buf);
        Serial1.println("------------------\n");
        reset_counter();
    }

    const char* getKeyName(uint8_t key) {
        switch(key) {
            case 0x80: return "LEFT_CTRL";
            case 0x81: return "LEFT_SHIFT";
            case 0x82: return "LEFT_ALT";
            case 0x83: return "LEFT_GUI";
            case 0xDA: return "UP_ARROW";
            case 0xD9: return "DOWN_ARROW";
            case 0xD8: return "LEFT_ARROW";
            case 0xD7: return "RIGHT_ARROW";
            case 0xB2: return "BACKSPACE";
            case 0xB3: return "TAB";
            case 0xB0: return "RETURN";
            case 0xB1: return "ESC";
            case 0xD4: return "DELETE";
            default:
                if (key >= 32 && key <= 126) return "ASCII";
                return "SPECIAL";
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

Logger logger;

// ========== 中斷服務例程 (ISR) ==========
void buttonISR() {
    uint32_t current_time = millis();
    
    // 防彈跳
    if (current_time - last_button_press > BUTTON_DEBOUNCE_MS) {
        g_interrupt_flag = true;
        last_button_press = current_time;
    }
}

// ========== CRC 計算 ==========
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

// ========== 非阻塞式指令執行 ==========
struct TimedAction {
    bool active;
    uint8_t action_type;  // 0: mouse, 1: keyboard
    uint8_t button_or_key;
    uint32_t start_time;
    uint16_t duration_ms;
} timedAction = {false, 0, 0, 0, 0};

void executeCommand(const CommandPacket& packet) {
    uint8_t cmd = packet.cmd;
    const uint8_t *params = packet.params;
    uint8_t param_len = packet.param_len;

    // 檢查中斷旗標
    if (g_interrupt_flag) {
        logger.logCommand("CMD_SKIPPED", "Interrupted");
        return;
    }

    switch(cmd) {
        case CMD_MOUSE_MOVE: {
            if (param_len != 3) {
                logger.logParamError(cmd, 3, param_len);
                return;
            }
            int8_t x = (int8_t)params[0];
            int8_t y = (int8_t)params[1];
            int8_t wheel = (int8_t)params[2];
            logger.logMouseMove(x, y, wheel);
            Mouse.move(x, y, wheel);
            break;
        }

        case CMD_MOUSE_PRESS: {
            if (param_len != 1) return;
            logger.logMouseButton("Press", params[0]);
            Mouse.press(params[0]);
            break;
        }

        case CMD_MOUSE_RELEASE: {
            if (param_len != 1) return;
            logger.logMouseButton("Release", params[0]);
            Mouse.release(params[0]);
            break;
        }

        case CMD_MOUSE_CLICK: {
            if (param_len != 1) return;
            logger.logMouseButton("Click", params[0]);
            Mouse.click(params[0]);
            break;
        }

        case CMD_MOUSE_PRESS_TIMED: {
            if (param_len != 3) return;
            uint8_t button = params[0];
            uint16_t duration_ms = (params[1] << 8) | params[2];
            
            // 啟動非阻塞計時器
            timedAction.active = true;
            timedAction.action_type = 0;  // mouse
            timedAction.button_or_key = button;
            timedAction.start_time = millis();
            timedAction.duration_ms = duration_ms;
            
            Mouse.press(button);
            logger.logCommand("MOUSE_TIMED_START");
            break;
        }

        case CMD_KB_PRESS: {
            if (param_len != 1) return;
            logger.logKeyboard("Press", params[0]);
            Keyboard.press(params[0]);
            break;
        }

        case CMD_KB_RELEASE: {
            if (param_len != 1) return;
            logger.logKeyboard("Release", params[0]);
            Keyboard.release(params[0]);
            break;
        }

        case CMD_KB_WRITE: {
            if (param_len != 1) return;
            logger.logKeyboard("Write", params[0]);
            Keyboard.write(params[0]);
            break;
        }

        case CMD_KB_RELEASE_ALL: {
            logger.logCommand("KB_RELEASE_ALL");
            Keyboard.releaseAll();
            break;
        }

        case CMD_KB_PRINT: {
            logger.logCommand("KB_PRINT");
            logger.logKeyboardPrint(params, param_len);
            for (uint8_t i = 0; i < param_len; i++) {
                if (g_interrupt_flag) break;  // 可中斷的輸入
                Keyboard.write(params[i]);
            }
            break;
        }

        case CMD_KB_PRESS_TIMED: {
            if (param_len != 3) return;
            uint8_t key = params[0];
            uint16_t duration_ms = (params[1] << 8) | params[2];
            
            // 啟動非阻塞計時器
            timedAction.active = true;
            timedAction.action_type = 1;  // keyboard
            timedAction.button_or_key = key;
            timedAction.start_time = millis();
            timedAction.duration_ms = duration_ms;
            
            Keyboard.press(key);
            logger.logCommand("KB_TIMED_START");
            break;
        }

        case CMD_PAUSE_LOG: {
            g_log_enabled = false;
            logger.logLogStateChange(false);
            break;
        }

        case CMD_RESUME_LOG: {
            g_log_enabled = true;
            logger.logLogStateChange(true);
            break;
        }

        case CMD_CLEAR_QUEUE: {
            cmdQueue.clear();
            logger.logCommand("QUEUE_CLEARED");
            break;
        }

        default:
            logger.logInvalidCommand(cmd);
            break;
    }
}

void processPacket(const uint8_t *data, uint8_t len) {
    if (len < 1) {
        logger.logError("EMPTY_PACKET");
        sendAck(ACK_PARAM_ERROR);
        return;
    }

    logger.logPacketData(data, len);

    // 封裝成 CommandPacket
    CommandPacket packet;
    packet.cmd = data[0];
    packet.param_len = len - 1;
    memcpy(packet.params, data + 1, packet.param_len);
    packet.timestamp = millis();

    // 立即執行的指令
    if (packet.cmd == CMD_PAUSE_LOG || 
        packet.cmd == CMD_RESUME_LOG || 
        packet.cmd == CMD_CLEAR_QUEUE) {
        executeCommand(packet);
        sendAck(ACK_SUCCESS);
        return;
    }

    // 加入佇列
    if (cmdQueue.push(packet)) {
        logger.logQueueStatus();
        sendAck(ACK_SUCCESS);
    } else {
        logger.logError("QUEUE_FULL");
        sendAck(ACK_PARAM_ERROR);
    }
}

// ========== 統計定時器 ==========
uint32_t last_stats_time = 0;
const uint32_t STATS_INTERVAL = 30000;

void setup() {
    // Serial: 與 Python 通訊
    Serial.begin(115200);
    while (!Serial && millis() < 3000);

    // Serial1: 監控日誌輸出
    logger.begin(115200);

    Keyboard.begin();
    Mouse.begin();

    // 設定中斷按鈕
    pinMode(INTERRUPT_PIN, INPUT_PULLUP);
    attachInterrupt(digitalPinToInterrupt(INTERRUPT_PIN), buttonISR, FALLING);

    // 清空接收緩衝區
    while (Serial.available()) {
        Serial.read();
    }

    logger.logCommand("SYSTEM", "Ready (Queue Mode)");
}

void loop() {
    // === 1. 處理硬體中斷 ===
    if (g_interrupt_flag) {
        logger.logInterrupt();
        
        // 清空佇列
        cmdQueue.clear();
        
        // 釋放所有按鍵/按鈕
        Keyboard.releaseAll();
        Mouse.release(MOUSE_LEFT | MOUSE_RIGHT | MOUSE_MIDDLE);
        
        // 清除計時動作
        if (timedAction.active) {
            if (timedAction.action_type == 0) {
                Mouse.release(timedAction.button_or_key);
            } else {
                Keyboard.release(timedAction.button_or_key);
            }
            timedAction.active = false;
        }
        
        // 通知 Host
        sendAck(ACK_INTERRUPTED);
        
        g_interrupt_flag = false;
    }

    // === 2. 處理計時動作 (非阻塞) ===
    if (timedAction.active) {
        if (millis() - timedAction.start_time >= timedAction.duration_ms) {
            if (timedAction.action_type == 0) {
                Mouse.release(timedAction.button_or_key);
                logger.logCommand("MOUSE_TIMED_END");
            } else {
                Keyboard.release(timedAction.button_or_key);
                logger.logCommand("KB_TIMED_END");
            }
            timedAction.active = false;
        }
    }

    // === 3. 接收新封包 ===
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

    // === 4. 執行佇列中的指令 ===
    if (!timedAction.active && !cmdQueue.isEmpty()) {
        CommandPacket packet;
        if (cmdQueue.pop(packet)) {
            executeCommand(packet);
        }
    }

    // === 5. 定期輸出統計 ===
    if (millis() - last_stats_time > STATS_INTERVAL) {
        logger.logStats();
        last_stats_time = millis();
    }
}
