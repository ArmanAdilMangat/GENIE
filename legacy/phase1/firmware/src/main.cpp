/**
 * GENIE — Generate, Engage, Navigate Intelligent Environments
 * Phase 1 Firmware — ESP32-S3 voice capture client
 *
 * Hardware:
 *   - ESP32-S3 DevKitC-1 (N16R8 recommended for PSRAM)
 *   - INMP441 I2S MEMS microphone on GPIO 5/6/7
 *   - Built-in BOOT button (GPIO 0) for push-to-talk
 *
 * Flow:
 *   BOOT pressed → record 7s mono 16kHz WAV →
 *   HTTP POST /audio to Flask server → server pipes through
 *   Whisper (STT) → Mistral 7B (LLM) → pyttsx3 (TTS on laptop speakers)
 *
 * In Phase 2 the on-device MAX98357A + 3W speaker take over playback.
 *
 * Author: Arman Adil Mangat
 * Repo:   https://github.com/ArmanAdilMangat/GENIE
 */

#include <Arduino.h>
#include <driver/i2s.h>
#include <WiFi.h>

#include "secrets.h"   // WIFI_SSID, WIFI_PASS, FLASK_IP, FLASK_PORT

// ===== PINS =====
#define MIC_SCK   7
#define MIC_WS    6
#define MIC_SD    5
#define BOOT_BTN  0   // built-in BOOT button

// ===== AUDIO =====
#define SAMPLE_RATE    16000
#define REC_SECONDS    7
#define TOTAL_SAMPLES  (SAMPLE_RATE * REC_SECONDS)  // 7 sec = 224KB — fits in S3

int16_t audioBuf[TOTAL_SAMPLES];

// ===== STATE =====
enum State { IDLE, RECORDING, SENDING, WAITING };
State state = IDLE;
bool stopRequested = false;   // stop recording mid-way
bool paused = false;          // pause auto-loop

// ===== WAV HEADER =====
void makeWavHeader(uint8_t* h, int dataBytes) {
    auto w32 = [&](int p, uint32_t v){ h[p]=v;h[p+1]=v>>8;h[p+2]=v>>16;h[p+3]=v>>24; };
    auto w16 = [&](int p, uint16_t v){ h[p]=v;h[p+1]=v>>8; };
    memcpy(h,    "RIFF", 4); w32(4, dataBytes+36);
    memcpy(h+8,  "WAVE", 4);
    memcpy(h+12, "fmt ", 4); w32(16,16);
    w16(20,1); w16(22,1);
    w32(24,SAMPLE_RATE); w32(28,SAMPLE_RATE*2);
    w16(32,2); w16(34,16);
    memcpy(h+36,"data",4); w32(40,dataBytes);
}

// ===== MIC SETUP =====
void setupMic() {
    i2s_config_t cfg = {
        .mode = (i2s_mode_t)(I2S_MODE_MASTER | I2S_MODE_RX),
        .sample_rate = SAMPLE_RATE,
        .bits_per_sample = I2S_BITS_PER_SAMPLE_32BIT,
        .channel_format = I2S_CHANNEL_FMT_ONLY_RIGHT,
        .communication_format = I2S_COMM_FORMAT_STAND_I2S,
        .intr_alloc_flags = ESP_INTR_FLAG_LEVEL1,
        .dma_buf_count = 4,
        .dma_buf_len = 256,
        .use_apll = false,
        .tx_desc_auto_clear = false,
        .fixed_mclk = 0
    };
    i2s_pin_config_t pins = {
        .bck_io_num = MIC_SCK, .ws_io_num = MIC_WS,
        .data_out_num = I2S_PIN_NO_CHANGE, .data_in_num = MIC_SD
    };
    i2s_driver_install(I2S_NUM_0, &cfg, 0, NULL);
    i2s_set_pin(I2S_NUM_0, &pins);
    i2s_zero_dma_buffer(I2S_NUM_0);
}

// ===== COMPONENT TESTS =====
void testMic() {
    Serial.println("\n🔬 MIC TEST — speak for 3 sec...");
    int32_t buf[256];
    size_t bytes;
    int32_t maxVal = 0;
    long end = millis() + 3000;
    while (millis() < end) {
        i2s_read(I2S_NUM_0, buf, sizeof(buf), &bytes, 100);
        int n = bytes / sizeof(int32_t);
        for (int i = 0; i < n; i++) {
            int32_t v = abs(buf[i] >> 14);
            if (v > maxVal) maxVal = v;
        }
    }
    Serial.printf("   Peak level: %d\n", maxVal);
    if      (maxVal > 2000) Serial.println("   ✅ Mic EXCELLENT!");
    else if (maxVal > 500)  Serial.println("   ✅ Mic working (speak louder for best results)");
    else                    Serial.println("   ❌ Mic weak — check wiring on GPIO 5,6,7");
}

void testWifi() {
    Serial.println("\n🔬 WIFI TEST...");
    if (WiFi.status() == WL_CONNECTED) {
        Serial.println("   ✅ Connected: " + WiFi.localIP().toString());
        Serial.printf("   Signal: %d dBm\n", WiFi.RSSI());
    } else {
        Serial.println("   ❌ Disconnected! Reconnecting...");
        WiFi.begin(WIFI_SSID, WIFI_PASS);
        int t = 0;
        while (WiFi.status() != WL_CONNECTED && t++ < 20) { delay(500); Serial.print("."); }
        Serial.println(WiFi.status() == WL_CONNECTED ? "\n   ✅ Reconnected!" : "\n   ❌ Failed!");
    }
}

void testFlask() {
    Serial.println("\n🔬 FLASK SERVER TEST...");
    WiFiClient client;
    if (client.connect(FLASK_IP, FLASK_PORT)) {
        client.println("GET / HTTP/1.1");
        client.println("Host: " + String(FLASK_IP));
        client.println("Connection: close");
        client.println();
        delay(500);
        Serial.println(client.available() ? "   ✅ Flask server is UP!" : "   ❌ Flask not responding!");
        client.stop();
    } else {
        Serial.println("   ❌ Cannot reach Flask — is app.py running?");
    }
}

void testOllama() {
    Serial.println("\n🔬 GENIE AI TEST...");
    WiFiClient client;
    // Ollama runs on laptop at port 11434
    if (client.connect(FLASK_IP, 11434)) {
        Serial.println("   ✅ Genie AI (Ollama/Mistral) is reachable!");
        client.stop();
    } else {
        Serial.println("   ❌ Genie AI not reachable — run: ollama run mistral");
    }
}

// ===== RECORD =====
// Returns actual samples recorded (may be less if stopped early)
int recordAudio() {
    state = RECORDING;
    stopRequested = false;
    Serial.println("\n━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━");
    Serial.printf( "🎤 GENIE listening... (%d sec max)\n", REC_SECONDS);
    Serial.println("   Press 's' to stop early");
    Serial.println("━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━");

    int32_t buf[256];
    size_t bytes;
    int idx = 0, lastPrint = 0;

    while (idx < TOTAL_SAMPLES && !stopRequested) {
        // Check for stop command while recording
        if (Serial.available()) {
            char c = Serial.read();
            if (c == 's' || c == 'S') {
                Serial.println("\n⏹️  Recording stopped early!");
                stopRequested = true;
                break;
            }
        }
        i2s_read(I2S_NUM_0, buf, sizeof(buf), &bytes, portMAX_DELAY);
        int n = bytes / sizeof(int32_t);
        for (int i = 0; i < n && idx < TOTAL_SAMPLES; i++)
            audioBuf[idx++] = (int16_t)(buf[i] >> 16);
        if (idx / SAMPLE_RATE > lastPrint) {
            lastPrint = idx / SAMPLE_RATE;
            Serial.printf("  ⏱  %d sec\n", lastPrint);
        }
    }

    Serial.printf("✅ Recorded %d sec of audio\n", idx / SAMPLE_RATE);
    return idx;  // return actual recorded samples
}

// ===== SEND =====
void sendToFlask(int samplesRecorded) {
    state = SENDING;
    Serial.println("📤 Sending to Genie AI...");

    WiFiClient client;
    if (!client.connect(FLASK_IP, FLASK_PORT)) {
        Serial.println("❌ Cannot connect to Flask!");
        state = IDLE;
        return;
    }

    int dataBytes  = samplesRecorded * sizeof(int16_t);
    int totalBytes = 44 + dataBytes;

    client.println("POST /audio HTTP/1.1");
    client.println("Host: " + String(FLASK_IP));
    client.println("Content-Type: audio/wav");
    client.println("Content-Length: " + String(totalBytes));
    client.println("Connection: close");
    client.println();

    uint8_t wavHeader[44];
    makeWavHeader(wavHeader, dataBytes);
    client.write(wavHeader, 44);

    int sent = 0;
    Serial.print("📡 ");
    while (sent < samplesRecorded) {
        int chunk = min(256, samplesRecorded - sent);
        client.write((uint8_t*)(audioBuf + sent), chunk * sizeof(int16_t));
        sent += chunk;
        if (sent % SAMPLE_RATE == 0) Serial.print("█");
    }
    Serial.println();

    state = WAITING;
    Serial.println("⏳ Genie is thinking... (laptop will speak)");

    long timeout = millis() + 90000;
    while (client.available() == 0 && millis() < timeout) delay(100);

    String response = "";
    while (client.available()) response += (char)client.read();
    client.stop();

    if (response.indexOf("success") >= 0) {
        Serial.println("\n🔊 Genie replied!");
        // JSON key is "genie_reply":"...", offset = 11 chars + ":\"" = 14
        int s = response.indexOf("genie_reply") + 14;
        int e = response.indexOf("\"", s);
        if (s > 13 && e > s)
            Serial.println("🤖 Genie: " + response.substring(s, e));
    } else {
        Serial.println("❌ Error: " + response.substring(0, 200));
    }
    state = IDLE;
}

// ===== MENU =====
void printMenu() {
    Serial.println("\n╔════════════════════════════════════╗");
    Serial.println("║         GENIE Voice Assistant      ║");
    Serial.println("╠════════════════════════════════════╣");
    Serial.println("║  🎤 BOOT btn / 'r' → Start record  ║");
    Serial.println("║  ⏹️  's'           → Stop recording ║");
    Serial.println("║  ⏸️  'p'           → Pause / Resume ║");
    Serial.println("╠════════════════════════════════════╣");
    Serial.println("║  🔬 COMPONENT TESTS:               ║");
    Serial.println("║  'm' → Test Mic                    ║");
    Serial.println("║  'w' → Test WiFi                   ║");
    Serial.println("║  'f' → Test Flask server           ║");
    Serial.println("║  'g' → Test Genie AI (Ollama)      ║");
    Serial.println("║  'a' → Test ALL components         ║");
    Serial.println("╠════════════════════════════════════╣");
    Serial.println("║  'h' → Show this menu              ║");
    Serial.println("╚════════════════════════════════════╝");
    if (paused)
        Serial.println("⚠️  System is PAUSED — press 'p' to resume\n");
    else
        Serial.println("✅ Ready — press BOOT or 'r' to talk to Genie!\n");
}

// ===== SETUP =====
void setup() {
    Serial.begin(115200);
    delay(1000);
    pinMode(BOOT_BTN, INPUT_PULLUP);

    Serial.println("\n╔════════════════════════════════════╗");
    Serial.println("║     GENIE FYP Phase 1 - Booting   ║");
    Serial.println("╚════════════════════════════════════╝");
    Serial.printf("Free heap: %d bytes\n", ESP.getFreeHeap());

    WiFi.begin(WIFI_SSID, WIFI_PASS);
    Serial.print("Connecting to WiFi");
    while (WiFi.status() != WL_CONNECTED) { delay(500); Serial.print("."); }
    Serial.println("\n✅ WiFi: " + WiFi.localIP().toString());

    setupMic();
    Serial.println("✅ Mic ready (GPIO 5,6,7)");
    Serial.printf("Free heap after init: %d bytes\n", ESP.getFreeHeap());

    printMenu();
}

// ===== LOOP =====
void loop() {
    // BOOT button → start recording
    if (digitalRead(BOOT_BTN) == LOW) {
        delay(50);
        if (digitalRead(BOOT_BTN) == LOW && state == IDLE && !paused) {
            int recorded = recordAudio();
            if (recorded > SAMPLE_RATE) {  // at least 1 sec of audio
                sendToFlask(recorded);
            } else {
                Serial.println("⚠️  Too short — speak longer!");
            }
            printMenu();
            delay(500);
        }
    }

    // Serial keyboard commands
    if (Serial.available()) {
        char cmd = tolower(Serial.read());

        // These work even when busy
        if (cmd == 's' && state == RECORDING) {
            stopRequested = true;
            return;
        }
        if (cmd == 'p') {
            paused = !paused;
            Serial.println(paused ? "\n⏸️  PAUSED — press 'p' to resume" : "\n▶️  RESUMED!");
            printMenu();
            return;
        }
        if (cmd == 'h') { printMenu(); return; }

        // These only work when idle and not paused
        if (state != IDLE) { Serial.println("⚠️  Busy! Wait or press 's' to stop."); return; }
        if (paused && cmd != 'p') { Serial.println("⚠️  Paused! Press 'p' to resume first."); return; }

        switch (cmd) {
            case 'r': {
                int recorded = recordAudio();
                if (recorded > SAMPLE_RATE) sendToFlask(recorded);
                else Serial.println("⚠️  Too short!");
                printMenu();
                break;
            }
            case 'm': testMic();   printMenu(); break;
            case 'w': testWifi();  printMenu(); break;
            case 'f': testFlask(); printMenu(); break;
            case 'g': testOllama(); printMenu(); break;
            case 'a':
                Serial.println("\n🔬 TESTING ALL COMPONENTS...");
                testWifi();
                testMic();
                testFlask();
                testOllama();
                Serial.println("\n✅ All tests complete!");
                printMenu();
                break;
        }
    }
}
