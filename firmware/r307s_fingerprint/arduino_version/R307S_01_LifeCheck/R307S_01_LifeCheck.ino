/* =======================================================================
   R307S  --  TEST 1 : LIFE CHECK   (run this one FIRST)
   -----------------------------------------------------------------------
   Answers exactly one question: is the sensor ALIVE and TALKING, or DEAD?
   No libraries. Raw R30x protocol. If this fails, nothing else matters.

   What it does automatically:
     1. Floating-pin test on the touch line (proves Blue/White are real)
     2. Sweeps ALL 12 legal R30x baud rates
     3. Repeats the whole sweep with TX/RX SWAPPED in software
        (R307 cable colours are NOT consistent between sellers -- this
         catches a yellow/green mix-up WITHOUT you rewiring anything)
     4. Dumps every raw byte it hears, so "silence" and "garbage" are
        told apart -- they mean completely different faults
     5. Prints a one-line VERDICT

   WIRING UNDER TEST (yours):
     Red    -> +5V external supply
     Black  -> GND (ESP32 GND, tied to supply GND)
     Yellow -> GPIO18   (expected: sensor TX -> ESP RX)
     Green  -> GPIO17   (expected: sensor RX <- ESP TX)
     Blue   -> GPIO4    (touch / wake-up output)
     White  -> 3V3      (touch-circuit power)
     ESP GND -> external supply GND      <-- MANDATORY common ground

   Board: ESP32-S3 DevKitC-1     Serial Monitor: 115200 baud
   ======================================================================= */

#include <Arduino.h>

#define FP_PIN_A      18      // yellow
#define FP_PIN_B      17      // green
#define FP_TOUCH_PIN  4       // blue
#define MON_BAUD      115200

HardwareSerial FP(1);

// All legal R30x rates: N * 9600, N = 1..12
const uint32_t BAUDS[] = {
  57600,   // factory default -- tried first
  9600, 19200, 28800, 38400, 48000,
  67200, 76800, 86400, 96000, 105600, 115200
};
const int NBAUDS = sizeof(BAUDS) / sizeof(BAUDS[0]);

uint8_t  raw[128];
uint32_t foundBaud   = 0;
bool     foundSwap   = false;
uint8_t  sysPara[32];
uint16_t sysParaLen  = 0;

// ---------------------------------------------------------------- helpers
void hexDump(const uint8_t *b, int n) {
  for (int i = 0; i < n; i++) {
    if (b[i] < 0x10) Serial.print('0');
    Serial.print(b[i], HEX);
    Serial.print(' ');
  }
}

void fpSend(uint8_t pid, const uint8_t *data, uint16_t dlen) {
  uint16_t len = dlen + 2;
  uint16_t sum = pid + (len >> 8) + (len & 0xFF);
  const uint8_t head[] = {0xEF, 0x01, 0xFF, 0xFF, 0xFF, 0xFF};
  FP.write(head, 6);
  FP.write(pid);
  FP.write((uint8_t)(len >> 8));
  FP.write((uint8_t)(len & 0xFF));
  for (uint16_t i = 0; i < dlen; i++) { FP.write(data[i]); sum += data[i]; }
  FP.write((uint8_t)(sum >> 8));
  FP.write((uint8_t)(sum & 0xFF));
  FP.flush();
}

// grab everything for `quiet` ms of silence, or `hard` ms total
int fpSlurp(uint8_t *buf, int maxn, uint32_t quiet, uint32_t hard) {
  uint32_t t0 = millis(), last = millis();
  int n = 0;
  while (millis() - t0 < hard) {
    if (FP.available()) {
      while (FP.available() && n < maxn) { buf[n++] = FP.read(); }
      last = millis();
    }
    if (n > 0 && millis() - last > quiet) break;
    delay(1);
  }
  return n;
}

// find a well-formed EF01 packet inside a raw blob.
// returns confirmation code (>=0), or -1 none, -2 checksum bad
int fpParse(const uint8_t *b, int n, uint8_t *out, uint16_t *outLen) {
  for (int i = 0; i + 11 <= n; i++) {
    if (b[i] != 0xEF || b[i + 1] != 0x01) continue;
    uint16_t len = (b[i + 7] << 8) | b[i + 8];
    if (len < 2 || i + 9 + len > n) continue;
    uint16_t dlen = len - 2;
    uint16_t sum = b[i + 6] + b[i + 7] + b[i + 8];
    for (uint16_t k = 0; k < dlen; k++) sum += b[i + 9 + k];
    uint16_t chk = (b[i + 9 + dlen] << 8) | b[i + 10 + dlen];
    if (chk != sum) return -2;
    if (outLen) *outLen = dlen;
    if (out) for (uint16_t k = 0; k < dlen && k < 32; k++) out[k] = b[i + 9 + k];
    return b[i + 9];
  }
  return -1;
}

const char *codeName(int c) {
  switch (c) {
    case 0x00: return "OK";
    case 0x01: return "packet receive error";
    case 0x02: return "no finger on sensor";
    case 0x03: return "failed to enroll finger";
    case 0x06: return "image too disorderly";
    case 0x07: return "image too small / poor feature";
    case 0x08: return "no match";
    case 0x09: return "not found in library";
    case 0x0A: return "failed to combine templates";
    case 0x0B: return "PageID beyond library";
    case 0x0C: return "invalid template";
    case 0x0D: return "template upload error";
    case 0x0E: return "cannot receive following packets";
    case 0x0F: return "image upload error";
    case 0x10: return "delete failed";
    case 0x11: return "clear library failed";
    case 0x13: return "WRONG PASSWORD (sensor is alive!)";
    case 0x15: return "no valid image in buffer";
    case 0x18: return "FLASH WRITE ERROR";
    case 0x1A: return "invalid register";
    case 0x20: return "address code incorrect";
    case 0x21: return "password must be verified first";
    default:   return "unknown code";
  }
}

// try one (baud, orientation) combo. returns true if a real packet came back
bool probe(uint32_t baud, bool swap) {
  FP.end();
  delay(20);
  // swap=false : RX=18(yellow), TX=17(green)
  // swap=true  : RX=17(green),  TX=18(yellow)
  FP.begin(baud, SERIAL_8N1, swap ? FP_PIN_B : FP_PIN_A,
                             swap ? FP_PIN_A : FP_PIN_B);
  delay(60);
  while (FP.available()) FP.read();

  uint8_t vfy[5] = {0x13, 0x00, 0x00, 0x00, 0x00};   // VfyPwd, password 0
  fpSend(0x01, vfy, 5);

  int n = fpSlurp(raw, sizeof(raw), 40, 700);

  Serial.printf("  %-6lu  %-8s  ", (unsigned long)baud, swap ? "SWAPPED" : "normal");
  if (n == 0) { Serial.println("silence"); return false; }

  Serial.printf("%2d bytes: ", n);
  hexDump(raw, n > 20 ? 20 : n);

  uint8_t d[32]; uint16_t dl = 0;
  int c = fpParse(raw, n, d, &dl);
  if (c == -1) { Serial.println(" <- garbage (wrong baud / noise)"); return false; }
  if (c == -2) { Serial.println(" <- BAD CHECKSUM (marginal wiring)"); return false; }

  Serial.printf(" <- VALID PACKET, code 0x%02X (%s)\n", c, codeName(c));
  return true;
}

// ---------------------------------------------------------------- touch pin
void touchFloatTest() {
  Serial.println(F("\n[1] TOUCH LINE (Blue -> GPIO4) -- floating test"));
  pinMode(FP_TOUCH_PIN, INPUT_PULLDOWN); delay(30);
  int lo = digitalRead(FP_TOUCH_PIN);
  pinMode(FP_TOUCH_PIN, INPUT_PULLUP);   delay(30);
  int hi = digitalRead(FP_TOUCH_PIN);
  pinMode(FP_TOUCH_PIN, INPUT);

  Serial.printf("    with pulldown = %d , with pullup = %d  ->  ", lo, hi);
  if (lo == 0 && hi == 1) {
    Serial.println(F("FLOATING. Nothing is driving GPIO4."));
    Serial.println(F("    Causes: White(3V3) not connected, Blue not connected,"));
    Serial.println(F("            or this R307 unit has no touch-detect circuit."));
    Serial.println(F("    NOT fatal -- UART can still work perfectly."));
  } else {
    Serial.printf("DRIVEN %s. Touch circuit is powered and alive.\n", lo ? "HIGH" : "LOW");
  }

  Serial.println(F("    Now PUT YOUR FINGER on the sensor for 6 seconds..."));
  pinMode(FP_TOUCH_PIN, INPUT);
  int base = digitalRead(FP_TOUCH_PIN);
  bool changed = false;
  uint32_t t0 = millis();
  while (millis() - t0 < 6000) {
    int v = digitalRead(FP_TOUCH_PIN);
    if (v != base) { changed = true; Serial.printf("    GPIO4 changed %d -> %d\n", base, v); base = v; }
    delay(10);
  }
  Serial.println(changed ? F("    RESULT: touch output WORKS.")
                         : F("    RESULT: no change (touch unused/unpowered -- fine for UART use)."));
}

// ---------------------------------------------------------------- sysparams
void decodeSysPara() {
  Serial.println(F("\n[4] SYSTEM PARAMETERS"));
  FP.end(); delay(20);
  FP.begin(foundBaud, SERIAL_8N1, foundSwap ? FP_PIN_B : FP_PIN_A,
                                  foundSwap ? FP_PIN_A : FP_PIN_B);
  delay(60);
  while (FP.available()) FP.read();

  uint8_t vfy[5] = {0x13, 0, 0, 0, 0};
  fpSend(0x01, vfy, 5);
  fpSlurp(raw, sizeof(raw), 40, 600);

  uint8_t cmd = 0x0F;                      // ReadSysPara
  fpSend(0x01, &cmd, 1);
  int n = fpSlurp(raw, sizeof(raw), 40, 900);
  uint8_t d[32]; uint16_t dl = 0;
  int c = fpParse(raw, n, d, &dl);

  if (c != 0x00 || dl < 17) {
    Serial.printf("    ReadSysPara failed (code %d / len %u). Raw: ", c, dl);
    hexDump(raw, n); Serial.println();
    if (c == 0x21) Serial.println(F("    -> sensor has a NON-ZERO PASSWORD set."));
    return;
  }
  uint16_t status = (d[1] << 8) | d[2];
  uint16_t sysid  = (d[3] << 8) | d[4];
  uint16_t cap    = (d[5] << 8) | d[6];
  uint16_t sec    = (d[7] << 8) | d[8];
  uint32_t addr   = ((uint32_t)d[9] << 24) | ((uint32_t)d[10] << 16) | (d[11] << 8) | d[12];
  uint16_t psz    = (d[13] << 8) | d[14];
  uint16_t brate  = (d[15] << 8) | d[16];
  const uint16_t pktBytes[] = {32, 64, 128, 256};

  Serial.printf("    status register : 0x%04X  (busy=%d pass=%d imgBuf=%d)\n",
                status, status & 1, (status >> 1) & 1, (status >> 2) & 1);
  Serial.printf("    system id       : 0x%04X  (expect 0x0009)\n", sysid);
  Serial.printf("    library capacity: %u templates\n", cap);
  Serial.printf("    security level  : %u  (1=loose .. 5=strict, 3 default)\n", sec);
  Serial.printf("    device address  : 0x%08lX\n", (unsigned long)addr);
  Serial.printf("    packet size     : %u bytes\n", psz < 4 ? pktBytes[psz] : 0);
  Serial.printf("    baud setting    : %lu\n", (unsigned long)brate * 9600UL);

  // template count
  uint8_t c2 = 0x1D;
  fpSend(0x01, &c2, 1);
  n = fpSlurp(raw, sizeof(raw), 40, 900);
  dl = 0;
  int cc = fpParse(raw, n, d, &dl);
  if (cc == 0x00 && dl >= 3)
    Serial.printf("    templates stored: %u\n", (uint16_t)((d[1] << 8) | d[2]));
}

// ---------------------------------------------------------------- main
void setup() {
  Serial.begin(MON_BAUD);
  delay(1500);
  Serial.println(F("\n\n==============================================="));
  Serial.println(F("   R307S  LIFE CHECK   (GENIE / ESP32-S3)"));
  Serial.println(F("==============================================="));
  Serial.println(F("Yellow->GPIO18  Green->GPIO17  Blue->GPIO4"));
  Serial.println(F("Red->+5V ext    White->3V3     GNDs common"));

  touchFloatTest();

  Serial.println(F("\n[2] UART SWEEP -- normal orientation (RX=18, TX=17)"));
  Serial.println(F("    baud    pins      response"));
  for (int i = 0; i < NBAUDS && !foundBaud; i++)
    if (probe(BAUDS[i], false)) { foundBaud = BAUDS[i]; foundSwap = false; }

  if (!foundBaud) {
    Serial.println(F("\n[3] UART SWEEP -- SWAPPED orientation (RX=17, TX=18)"));
    for (int i = 0; i < NBAUDS && !foundBaud; i++)
      if (probe(BAUDS[i], true)) { foundBaud = BAUDS[i]; foundSwap = true; }
  } else {
    Serial.println(F("\n[3] swapped sweep skipped -- already talking."));
  }

  Serial.println(F("\n==============================================="));
  if (foundBaud) {
    Serial.println(F("   VERDICT:  SENSOR IS ALIVE"));
    Serial.printf ("   baud = %lu\n", (unsigned long)foundBaud);
    Serial.printf ("   wiring = %s\n", foundSwap
        ? "SWAPPED -> your Yellow is RX and Green is TX."
        : "as documented (Yellow=TX, Green=RX). Correct.");
    if (foundSwap) {
      Serial.println(F("   -> Either physically swap Yellow/Green,"));
      Serial.println(F("      or use RX=17 TX=18 in your GENIE firmware."));
    }
    Serial.println(F("==============================================="));
    decodeSysPara();
    Serial.println(F("\nNEXT: open R307S_02_FullTest and run the full suite."));
  } else {
    Serial.println(F("   VERDICT:  NO RESPONSE ON ANY BAUD, EITHER WAY"));
    Serial.println(F("==============================================="));
    Serial.println(F("Work through these in order:"));
    Serial.println(F(" 1. Measure Red-to-Black with a multimeter AT THE SENSOR"));
    Serial.println(F("    connector while powered. Must be 4.5-6.0 V under load."));
    Serial.println(F(" 2. Is the ESP32 GND actually tied to the external supply GND?"));
    Serial.println(F("    Without that common ground the UART cannot work."));
    Serial.println(F(" 3. Does the sensor glow (red/blue ring) at power-up? No glow"));
    Serial.println(F("    + correct voltage = dead module."));
    Serial.println(F(" 4. Reseat / continuity-test the 6-pin JST. Broken solder on"));
    Serial.println(F("    the flying leads is the #1 cause."));
    Serial.println(F(" 5. Run FullTest option 'L' (UART loopback: jumper 17<->18)"));
    Serial.println(F("    to prove the ESP32 pins themselves are good."));
    Serial.println(F(" 6. Supply current: R307 pulls ~120 mA peaks. A weak 5V rail"));
    Serial.println(F("    browns it out and it never answers."));
  }
}

void loop() { delay(1000); }
