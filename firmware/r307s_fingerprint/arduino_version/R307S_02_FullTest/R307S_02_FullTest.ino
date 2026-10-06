/* =======================================================================
   R307S  --  TEST 2 : FULL DIAGNOSTIC SUITE
   -----------------------------------------------------------------------
   Menu-driven. No external libraries -- raw R30x protocol, so nothing
   can break because of an Adafruit_Fingerprint version difference.

   Run R307S_01_LifeCheck FIRST. It tells you the BAUD and whether the
   Yellow/Green pair is swapped. Put those two answers in CONFIG below.

   WIRING (yours):
     Red -> +5V ext | Black -> GND | Yellow -> GPIO18 | Green -> GPIO17
     Blue -> GPIO4  | White -> 3V3 | ESP GND -> supply GND

   Serial Monitor: 115200 baud, line ending = Newline
   ======================================================================= */

#include <Arduino.h>

// ------------------------------------------------------------ CONFIG ----
#define FP_BAUD        57600    // <-- from LifeCheck ("baud = ...")
#define FP_SWAPPED     false    // <-- true if LifeCheck said SWAPPED
#define FP_PIN_YELLOW  18
#define FP_PIN_GREEN   17
#define FP_TOUCH_PIN   4
// ------------------------------------------------------------------------

#define FP_RX (FP_SWAPPED ? FP_PIN_GREEN  : FP_PIN_YELLOW)
#define FP_TX (FP_SWAPPED ? FP_PIN_YELLOW : FP_PIN_GREEN)

HardwareSerial FP(1);

uint8_t  rsp[64];
uint16_t rspLen = 0;

// ------------------------------------------------------------- protocol --
void fpSend(const uint8_t *data, uint16_t dlen) {
  uint16_t len = dlen + 2;
  uint16_t sum = 0x01 + (len >> 8) + (len & 0xFF);
  const uint8_t head[] = {0xEF, 0x01, 0xFF, 0xFF, 0xFF, 0xFF, 0x01};
  FP.write(head, 7);
  FP.write((uint8_t)(len >> 8));
  FP.write((uint8_t)(len & 0xFF));
  for (uint16_t i = 0; i < dlen; i++) { FP.write(data[i]); sum += data[i]; }
  FP.write((uint8_t)(sum >> 8));
  FP.write((uint8_t)(sum & 0xFF));
  FP.flush();
}

int rdByte(uint32_t tmo) {
  uint32_t t0 = millis();
  while (millis() - t0 < tmo) { if (FP.available()) return FP.read(); }
  return -1;
}

// returns confirmation code >=0, or -1 timeout, -2 checksum, -3 length
int fpRecv(uint32_t tmo) {
  uint32_t t0 = millis();
  int b;
  rspLen = 0;
  while (true) {
    if (millis() - t0 > tmo) return -1;
    b = rdByte(tmo);
    if (b < 0) return -1;
    if (b != 0xEF) continue;
    b = rdByte(120);
    if (b == 0x01) break;
  }
  uint8_t h[7];
  for (int i = 0; i < 7; i++) { b = rdByte(400); if (b < 0) return -1; h[i] = b; }
  uint16_t len = ((uint16_t)h[5] << 8) | h[6];
  if (len < 2 || len > sizeof(rsp) + 2) return -3;
  uint16_t dlen = len - 2;
  uint16_t sum = h[4] + h[5] + h[6];
  for (uint16_t i = 0; i < dlen; i++) {
    b = rdByte(400); if (b < 0) return -1;
    rsp[i] = b; sum += b;
  }
  int hi = rdByte(400), lo = rdByte(400);
  if (hi < 0 || lo < 0) return -1;
  if (((uint16_t)(hi << 8) | lo) != sum) return -2;
  rspLen = dlen;
  return rsp[0];
}

int fpCmd(const uint8_t *data, uint16_t dlen, uint32_t tmo = 2000) {
  while (FP.available()) FP.read();
  fpSend(data, dlen);
  return fpRecv(tmo);
}

const char *codeName(int c) {
  switch (c) {
    case  0x00: return "OK";
    case  0x01: return "packet receive error";
    case  0x02: return "no finger on sensor";
    case  0x03: return "failed to capture image";
    case  0x06: return "image too disorderly (smudged/wet)";
    case  0x07: return "too few feature points (light touch/dry)";
    case  0x08: return "no match";
    case  0x09: return "not found in library";
    case  0x0A: return "the two scans did not combine (different fingers?)";
    case  0x0B: return "PageID beyond library capacity";
    case  0x0C: return "invalid/corrupt template";
    case  0x0D: return "template upload error";
    case  0x0E: return "cannot receive following packets";
    case  0x0F: return "image upload error";
    case  0x10: return "delete failed";
    case  0x11: return "clear library failed";
    case  0x13: return "wrong password";
    case  0x15: return "no valid image in buffer";
    case  0x18: return "FLASH READ/WRITE ERROR";
    case  0x1A: return "invalid register";
    case  0x20: return "address code incorrect";
    case  0x21: return "password must be verified first";
    case -1:    return "NO RESPONSE (timeout)";
    case -2:    return "CHECKSUM ERROR (marginal wiring/baud)";
    case -3:    return "malformed packet length";
    default:    return "unknown";
  }
}
void say(const char *what, int c) {
  Serial.printf("    %s -> 0x%02X %s\n", what, c & 0xFF, codeName(c));
}

// ------------------------------------------------------------- commands --
bool verifyPwd() {
  uint8_t d[5] = {0x13, 0, 0, 0, 0};
  int c = fpCmd(d, 5);
  return c == 0x00;
}

void cmdSysPara() {
  Serial.println(F("\n-- SYSTEM PARAMETERS --"));
  uint8_t d = 0x0F;
  int c = fpCmd(&d, 1);
  if (c != 0x00 || rspLen < 17) { say("ReadSysPara", c); return; }
  uint16_t status = (rsp[1] << 8) | rsp[2];
  uint16_t sysid  = (rsp[3] << 8) | rsp[4];
  uint16_t cap    = (rsp[5] << 8) | rsp[6];
  uint16_t sec    = (rsp[7] << 8) | rsp[8];
  uint32_t addr   = ((uint32_t)rsp[9] << 24) | ((uint32_t)rsp[10] << 16) |
                    ((uint32_t)rsp[11] << 8) | rsp[12];
  uint16_t psz    = (rsp[13] << 8) | rsp[14];
  uint16_t br     = (rsp[15] << 8) | rsp[16];
  const uint16_t pk[] = {32, 64, 128, 256};
  Serial.printf("    status 0x%04X  busy=%d pwdOK=%d imgBuf=%d\n",
                status, status & 1, (status >> 1) & 1, (status >> 2) & 1);
  Serial.printf("    system id      : 0x%04X %s\n", sysid,
                sysid == 0x0009 ? "(genuine R30x)" : "(UNEXPECTED)");
  Serial.printf("    capacity       : %u templates\n", cap);
  Serial.printf("    security level : %u (1 loose .. 5 strict)\n", sec);
  Serial.printf("    device address : 0x%08lX\n", (unsigned long)addr);
  Serial.printf("    packet size    : %u bytes\n", psz < 4 ? pk[psz] : 0);
  Serial.printf("    baud setting   : %lu\n", (unsigned long)br * 9600UL);
}

int cmdCount(bool quiet = false) {
  uint8_t d = 0x1D;
  int c = fpCmd(&d, 1);
  if (c != 0x00 || rspLen < 3) { if (!quiet) say("TemplateNum", c); return -1; }
  int n = (rsp[1] << 8) | rsp[2];
  if (!quiet) Serial.printf("    templates stored: %d\n", n);
  return n;
}

void cmdIndex() {
  Serial.println(F("\n-- ENROLLED IDs (index table, page 0 = ID 0-255) --"));
  uint8_t d[2] = {0x1F, 0x00};
  int c = fpCmd(d, 2);
  if (c != 0x00 || rspLen < 33) { say("ReadIndexTable", c);
    Serial.println(F("    (some R307 firmwares do not support 0x1F -- not a fault)"));
    return; }
  int found = 0;
  Serial.print(F("    IDs: "));
  for (int byteIdx = 0; byteIdx < 32; byteIdx++)
    for (int bit = 0; bit < 8; bit++)
      if (rsp[1 + byteIdx] & (1 << bit)) { Serial.printf("%d ", byteIdx * 8 + bit); found++; }
  if (!found) Serial.print(F("(none)"));
  Serial.printf("\n    total = %d\n", found);
}

bool waitFinger(const char *msg, uint32_t tmo = 12000) {
  Serial.printf("    %s\n", msg);
  uint32_t t0 = millis();
  uint8_t g = 0x01;
  while (millis() - t0 < tmo) {
    int c = fpCmd(&g, 1, 1200);
    if (c == 0x00) { Serial.println(F("    image captured.")); return true; }
    if (c == 0x02) { delay(60); continue; }          // no finger yet
    say("GetImage", c);
    if (c < 0) return false;
    delay(120);
  }
  Serial.println(F("    timeout waiting for finger."));
  return false;
}

void waitRemove() {
  Serial.println(F("    remove finger..."));
  uint8_t g = 0x01;
  uint32_t t0 = millis();
  while (millis() - t0 < 8000) {
    if (fpCmd(&g, 1, 1000) == 0x02) { delay(300); return; }
    delay(100);
  }
}

void cmdEnroll(uint16_t id) {
  Serial.printf("\n-- ENROLL to slot #%u --\n", id);
  if (!waitFinger("place finger (1st of 2)...")) return;
  uint8_t t1[2] = {0x02, 0x01};
  int c = fpCmd(t1, 2, 3000);  say("Img2Tz buf1", c);  if (c != 0x00) return;
  waitRemove();
  if (!waitFinger("place the SAME finger again (2nd of 2)...")) return;
  uint8_t t2[2] = {0x02, 0x02};
  c = fpCmd(t2, 2, 3000);      say("Img2Tz buf2", c);  if (c != 0x00) return;
  uint8_t rm = 0x05;
  c = fpCmd(&rm, 1, 3000);     say("RegModel", c);     if (c != 0x00) return;
  uint8_t st[4] = {0x06, 0x01, (uint8_t)(id >> 8), (uint8_t)(id & 0xFF)};
  c = fpCmd(st, 4, 3000);      say("Store (flash write)", c);
  if (c == 0x00) {
    Serial.println(F("    ENROLL OK -- and this proves the flash writes."));
    cmdCount();
  }
}

void cmdSearch() {
  Serial.println(F("\n-- 1:N SEARCH --"));
  if (!waitFinger("place any enrolled finger...")) return;
  uint8_t t1[2] = {0x02, 0x01};
  int c = fpCmd(t1, 2, 3000);  say("Img2Tz buf1", c);  if (c != 0x00) return;
  uint8_t s[6] = {0x04, 0x01, 0x00, 0x00, 0x03, 0xE8};   // buf1, page0, 1000
  c = fpCmd(s, 6, 4000);
  if (c == 0x00 && rspLen >= 5) {
    uint16_t pid = (rsp[1] << 8) | rsp[2];
    uint16_t sc  = (rsp[3] << 8) | rsp[4];
    Serial.printf("    MATCH  id=%u  confidence=%u\n", pid, sc);
  } else say("Search", c);
}

void cmdMatchId(uint16_t id) {
  Serial.printf("\n-- 1:1 VERIFY against slot #%u --\n", id);
  uint8_t ld[4] = {0x07, 0x02, (uint8_t)(id >> 8), (uint8_t)(id & 0xFF)};
  int c = fpCmd(ld, 4, 3000);  say("LoadChar->buf2", c); if (c != 0x00) return;
  if (!waitFinger("place finger...")) return;
  uint8_t t1[2] = {0x02, 0x01};
  c = fpCmd(t1, 2, 3000);      say("Img2Tz buf1", c);   if (c != 0x00) return;
  uint8_t mt = 0x03;
  c = fpCmd(&mt, 1, 3000);
  if (c == 0x00 && rspLen >= 3)
    Serial.printf("    MATCH confidence=%u\n", (uint16_t)((rsp[1] << 8) | rsp[2]));
  else say("Match", c);
}

void cmdDelete(uint16_t id) {
  uint8_t d[6] = {0x0C, (uint8_t)(id >> 8), (uint8_t)(id & 0xFF), 0x00, 0x01, 0x00};
  // DeletChar: pageID(2) + number(2)
  uint8_t p[5] = {0x0C, (uint8_t)(id >> 8), (uint8_t)(id & 0xFF), 0x00, 0x01};
  (void)d;
  int c = fpCmd(p, 5, 3000);
  Serial.printf("\n-- DELETE #%u --\n", id);
  say("DeletChar", c);
  cmdCount();
}

void cmdEmpty() {
  Serial.println(F("\n!! This ERASES ALL fingerprints. Type ERASE to confirm:"));
  uint32_t t0 = millis(); String s = "";
  while (millis() - t0 < 15000) {
    if (Serial.available()) { s = Serial.readStringUntil('\n'); s.trim(); break; }
    delay(10);
  }
  if (s != "ERASE") { Serial.println(F("    cancelled.")); return; }
  uint8_t e = 0x0D;
  int c = fpCmd(&e, 1, 4000);
  say("Empty", c);
  cmdCount();
}

void cmdImageQuality() {
  Serial.println(F("\n-- IMAGE QUALITY (10 captures) --"));
  Serial.println(F("    keep one finger on the sensor the whole time."));
  int ok = 0, feat = 0;
  for (int i = 0; i < 10; i++) {
    uint8_t g = 0x01;
    int c = fpCmd(&g, 1, 1500);
    if (c == 0x00) {
      ok++;
      uint8_t t[2] = {0x02, 0x01};
      int f = fpCmd(t, 2, 3000);
      if (f == 0x00) feat++;
      Serial.printf("    %2d: image OK, feature 0x%02X %s\n", i + 1, f & 0xFF, codeName(f));
    } else {
      Serial.printf("    %2d: 0x%02X %s\n", i + 1, c & 0xFF, codeName(c));
    }
    delay(200);
  }
  Serial.printf("    images %d/10, usable features %d/10\n", ok, feat);
  if (ok >= 8 && feat >= 7) Serial.println(F("    OPTICS + DSP: GOOD"));
  else if (ok >= 8)         Serial.println(F("    optics fine, features poor -> dry/dirty finger or dirty glass"));
  else                      Serial.println(F("    poor capture -> clean the glass, check 5V rail"));
}

void cmdSoak(int n) {
  Serial.printf("\n-- LINK SOAK TEST (%d packets) --\n", n);
  int good = 0, tmo = 0, chk = 0;
  uint32_t t0 = millis();
  for (int i = 0; i < n; i++) {
    uint8_t d = 0x0F;
    int c = fpCmd(&d, 1, 800);
    if (c == 0x00) good++;
    else if (c == -1) tmo++;
    else if (c == -2) chk++;
  }
  uint32_t ms = millis() - t0;
  Serial.printf("    good=%d  timeouts=%d  checksum-errors=%d  (%lu ms)\n",
                good, tmo, chk, (unsigned long)ms);
  if (good == n)       Serial.println(F("    LINK: ROCK SOLID."));
  else if (good > n * 0.95) Serial.println(F("    LINK: usable but not clean -- shorten wires, add 100nF at sensor."));
  else                 Serial.println(F("    LINK: UNRELIABLE -- power rail sag or bad joint. Fix before trusting it."));
}

void cmdFlashTest() {
  Serial.println(F("\n-- FLASH READ/WRITE TEST (notepad page 15) --"));
  Serial.println(F("    non-destructive to fingerprints; overwrites notepad page 15 only."));
  uint8_t w[34];
  w[0] = 0x18; w[1] = 15;
  for (int i = 0; i < 32; i++) w[2 + i] = (uint8_t)(0xA5 ^ i);
  int c = fpCmd(w, 34, 3000);
  say("WriteNotepad", c);
  if (c != 0x00) { Serial.println(F("    -> flash write path FAILED (enrollment will not persist).")); return; }
  uint8_t r[2] = {0x19, 15};
  c = fpCmd(r, 2, 3000);
  say("ReadNotepad", c);
  if (c != 0x00 || rspLen < 33) return;
  bool same = true;
  for (int i = 0; i < 32; i++) if (rsp[1 + i] != (uint8_t)(0xA5 ^ i)) same = false;
  Serial.println(same ? F("    FLASH VERIFY OK -- non-volatile memory is healthy.")
                      : F("    FLASH VERIFY MISMATCH -- suspect module."));
}

void cmdLed() {
  Serial.println(F("\n-- LED / BACKLIGHT --"));
  uint8_t on  = 0x50, off = 0x51;
  int c = fpCmd(&on, 1, 1500);  say("LED on  (0x50)", c);
  delay(1200);
  c = fpCmd(&off, 1, 1500);     say("LED off (0x51)", c);
  delay(600);
  uint8_t aura[5] = {0x35, 0x02, 0x30, 0x01, 0x05};   // breathing, red, 5x
  c = fpCmd(aura, 5, 1500);     say("AuraLed (0x35)", c);
  Serial.println(F("    0x01/0x1A here just means this firmware lacks the command."));
  Serial.println(F("    Did the ring actually light? That is the real answer."));
}

void cmdTouch() {
  Serial.println(F("\n-- TOUCH PIN MONITOR (GPIO4), 10 s --"));
  pinMode(FP_TOUCH_PIN, INPUT);
  int last = digitalRead(FP_TOUCH_PIN), ch = 0;
  Serial.printf("    idle level = %d. Touch and release a few times.\n", last);
  uint32_t t0 = millis();
  while (millis() - t0 < 10000) {
    int v = digitalRead(FP_TOUCH_PIN);
    if (v != last) { Serial.printf("    %5lu ms: %d -> %d\n", (unsigned long)(millis() - t0), last, v); last = v; ch++; }
    delay(5);
  }
  Serial.printf("    transitions = %d %s\n", ch,
                ch ? "-> touch line WORKS" : "-> no activity (unpowered White, or no touch circuit)");
}

void cmdLoopback() {
  Serial.println(F("\n-- ESP32 UART LOOPBACK --"));
  Serial.printf("    UNPLUG the sensor. Jumper GPIO%d <-> GPIO%d. Then press ENTER.\n", FP_PIN_YELLOW, FP_PIN_GREEN);
  uint32_t t0 = millis();
  while (millis() - t0 < 30000) { if (Serial.available()) { Serial.readStringUntil('\n'); break; } delay(10); }
  FP.end(); delay(20);
  FP.begin(FP_BAUD, SERIAL_8N1, FP_RX, FP_TX);
  delay(50);
  while (FP.available()) FP.read();
  const char *pat = "GENIE-R307S-LOOPBACK";
  FP.print(pat); FP.flush();
  delay(150);
  String got = "";
  while (FP.available()) got += (char)FP.read();
  Serial.printf("    sent: %s\n    got : %s\n", pat, got.c_str());
  Serial.println(got == String(pat)
    ? F("    ESP32 UART pins are GOOD -> any failure is the sensor/wiring.")
    : F("    ESP32 UART pins FAILED -> wrong pins, damaged GPIO, or pin conflict."));
  Serial.println(F("    Reconnect the sensor before other tests."));
}

void cmdMonitor() {
  Serial.println(F("\n-- CONTINUOUS ALIVE MONITOR -- send any key to stop --"));
  int fails = 0, polls = 0;
  while (!Serial.available()) {
    int n = cmdCount(true);
    polls++;
    if (n < 0) { fails++; Serial.printf("    %4d: LINK DROP\n", polls); }
    else Serial.printf("    %4d: alive, %d templates\n", polls, n);
    delay(1000);
  }
  while (Serial.available()) Serial.read();
  Serial.printf("    polls=%d drops=%d\n", polls, fails);
}

// ---------------------------------------------------------------- menu --
void help() {
  Serial.println(F("\n=========== R307S FULL TEST ==========="));
  Serial.println(F("  p  system parameters"));
  Serial.println(F("  t  template count"));
  Serial.println(F("  i  list enrolled IDs"));
  Serial.println(F("  e  enroll  (e5 = enroll to slot 5)"));
  Serial.println(F("  s  1:N search"));
  Serial.println(F("  v  1:1 verify (v5 = against slot 5)"));
  Serial.println(F("  d  delete   (d5)"));
  Serial.println(F("  x  ERASE ALL templates"));
  Serial.println(F("  q  image quality x10"));
  Serial.println(F("  k  link soak test (200 packets)"));
  Serial.println(F("  f  flash read/write test"));
  Serial.println(F("  g  LED / aura test"));
  Serial.println(F("  b  touch pin monitor"));
  Serial.println(F("  L  ESP32 UART loopback (sensor unplugged)"));
  Serial.println(F("  r  continuous alive monitor"));
  Serial.println(F("  a  RUN ALL non-destructive tests"));
  Serial.println(F("  h  this menu"));
  Serial.println(F("======================================="));
  Serial.print(F("> "));
}

void runAll() {
  Serial.println(F("\n########## FULL NON-DESTRUCTIVE SWEEP ##########"));
  Serial.printf("link: baud %d, RX=GPIO%d TX=GPIO%d\n", FP_BAUD, FP_RX, FP_TX);
  Serial.printf("password verify -> %s\n", verifyPwd() ? "OK" : "FAILED");
  cmdSysPara();
  cmdCount();
  cmdIndex();
  cmdSoak(200);
  cmdFlashTest();
  cmdLed();
  cmdImageQuality();
  Serial.println(F("\n########## SWEEP DONE ##########"));
  Serial.println(F("If sysparams read, soak = 200/200, flash verified and"));
  Serial.println(F("images 8+/10 -> the sensor is fully healthy."));
  Serial.println(F("Then do 'e1' and 's' to prove the biometric path end to end."));
}

void setup() {
  Serial.begin(115200);
  delay(1500);
  pinMode(FP_TOUCH_PIN, INPUT);
  FP.begin(FP_BAUD, SERIAL_8N1, FP_RX, FP_TX);
  delay(100);
  Serial.println(F("\n\nR307S full diagnostic (GENIE / ESP32-S3)"));
  Serial.printf("baud %d  RX=GPIO%d  TX=GPIO%d  touch=GPIO%d\n",
                FP_BAUD, FP_RX, FP_TX, FP_TOUCH_PIN);
  if (!verifyPwd())
    Serial.println(F("WARNING: handshake failed. Run R307S_01_LifeCheck first."));
  else
    Serial.println(F("handshake OK."));
  help();
}

void loop() {
  if (!Serial.available()) return;
  String line = Serial.readStringUntil('\n');
  line.trim();
  if (!line.length()) return;
  char c = line.charAt(0);
  uint16_t arg = (line.length() > 1) ? (uint16_t)line.substring(1).toInt() : 1;

  switch (c) {
    case 'p': cmdSysPara();      break;
    case 't': cmdCount();        break;
    case 'i': cmdIndex();        break;
    case 'e': cmdEnroll(arg);    break;
    case 's': cmdSearch();       break;
    case 'v': cmdMatchId(arg);   break;
    case 'd': cmdDelete(arg);    break;
    case 'x': cmdEmpty();        break;
    case 'q': cmdImageQuality(); break;
    case 'k': cmdSoak(200);      break;
    case 'f': cmdFlashTest();    break;
    case 'g': cmdLed();          break;
    case 'b': cmdTouch();        break;
    case 'L': cmdLoopback();     break;
    case 'r': cmdMonitor();      break;
    case 'a': runAll();          break;
    default:  help();            return;
  }
  Serial.print(F("\n> "));
}
