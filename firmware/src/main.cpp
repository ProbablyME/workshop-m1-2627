/**
 * SENTINEL-X — firmware ESP8266 (Groupe 1, AetherCorp Industrial Solutions)
 *
 * Capteurs  : DHT22 (D5), MQ-2 (A0 via diviseur), PIR HC-SR501 (D6)
 * Sorties   : OLED I2C 0x3C (D1/D2), buzzer actif (D7), LED bicolore (D0 rouge, D8 verte)
 * Réseau    : Wi-Fi + MQTT(S) vers le PC Serveur Local. Interfaces : docs/CONTRAT_DONNEES.md
 *
 * Boucle non bloquante (millis) : lecture capteurs 2 s, télémétrie 5 s, alertes sur
 * franchissement de seuil avec hystérésis, commandes reçues sur <prefix>/cmd.
 */
#include <Arduino.h>
#include <ESP8266WiFi.h>
#include <WiFiClientSecure.h>
#include <PubSubClient.h>
#include <ArduinoJson.h>
#include <Wire.h>
#include <Adafruit_GFX.h>
#include <Adafruit_SSD1306.h>
#include <DHT.h>
#include <sys/time.h>
#include <time.h>

#include "config.h"
#include "secrets.h"

// Courant de démarrage : l'ESP8266 calibre sa radio au boot (pic 300-400 mA) avant setup().
// RF_DISABLED (mode banc) : radio jamais initialisée, boot le plus sobre possible.
// RF_NO_CAL (mode normal) : radio active sans recalibration au boot, pic réduit.
#ifdef BENCH_NO_WIFI
RF_MODE(RF_DISABLED)
#else
RF_MODE(RF_NO_CAL)
#endif

// ----------------------------------------------------------------------------- objets
DHT dht(PIN_DHT, DHT_TYPE);
Adafruit_SSD1306 oled(OLED_W, OLED_H, &Wire, -1);
#if TLS_ENABLED
BearSSL::WiFiClientSecure net;
#ifdef MQTT_CA_CERT
BearSSL::X509List caList(MQTT_CA_CERT);
#endif
#else
WiFiClient net;
#endif
PubSubClient mqtt(net);

// ----------------------------------------------------------------------------- état
struct Readings {
  float temp = NAN, hum = NAN;   // dernières valeurs valides du DHT22
  uint8_t dhtFails = 0;          // lectures ratées consécutives (>= 3 → panne)
  int gasRaw = 0;
  float gasPpm = 0;
  bool motion = false;
  bool pirSeenLow = false;       // le PIR a été vu au niveau bas au moins une fois : capteur réellement branché
} rd;

struct Alerts {
  bool motion = false;
  bool gas = false, gasCrit = false;
  bool temp = false, tempCrit = false;
  bool hum = false, humCrit = false;
  bool fault = false;
  bool camera = false;   // intrusion vue par l'IA (commande "camera" envoyée par le serveur)
  bool any() const { return motion || gas || temp || hum || fault || camera; }
} al;

struct Actuator {
  uint8_t pin;
  bool manual = false;      // true : piloté par une commande ; false : mode automatique
  bool level = false;
  bool blink = false;
  unsigned long until = 0;  // fin du mode manuel (0 = jusqu'à la prochaine commande)
  unsigned long lastToggle = 0;
};
Actuator buzzer{PIN_BUZZER}, ledR{PIN_LED_RED}, ledG{PIN_LED_GREEN};
unsigned long buzzerAutoUntil = 0;

// ---- Mélodie d'alarme : Doom E1M1 "At Doom's Gate", extraite du lump D_E1M1 de doom1.wad ----
// Piste guitare (canal 1), 71 notes, 10.8 s, transposée de 3 octaves pour le buzzer.
// Triplets (fréquence Hz, créneau ms, durée sonnée ms). MELODY_SPEED_PCT dans config.h ralentit/accélère.
static const uint16_t MELODY[] PROGMEM = {
  659,136,43, 659,136,136, 1319,143,136, 659,136,43, 659,136,136, 1175,136,121, 659,136,43, 659,136,136,
  1047,136,129, 659,136,43, 659,136,136, 932,136,136, 659,136,57, 659,143,143, 988,136,129, 1047,136,121,
  659,136,29, 659,136,136, 1319,136,121, 659,136,43, 659,136,136, 1175,136,136, 659,136,43, 659,136,136,
  1047,143,114, 659,136,50, 659,136,136, 932,679,679, 659,136,50, 659,136,136, 1319,136,136, 659,143,50,
  659,136,136, 1175,136,136, 659,136,57, 659,136,136, 1047,136,129, 659,136,43, 659,136,136, 932,136,136,
  659,136,43, 659,136,136, 988,143,136, 1047,136,129, 659,136,43, 659,136,136, 1319,136,136, 659,136,50,
  659,136,136, 1175,136,136, 659,136,43, 659,136,136, 1047,136,136, 659,143,50, 659,136,136, 932,679,679,
  659,136,36, 659,136,136, 1319,136,136, 659,136,43, 659,143,143, 1175,136,121, 659,136,43, 659,136,136,
  1047,136,129, 659,136,43, 659,136,136, 932,136,129, 659,136,57, 659,136,136, 988,136,136 };
static const uint8_t MELODY_LEN = sizeof(MELODY) / sizeof(MELODY[0]) / 3;   // nombre de notes

struct Melody {
  bool playing = false;
  uint8_t idx = 0;
  unsigned long nextAt = 0;
} melody;

static void melodyStop() {
  noTone(PIN_BUZZER);
  melody.playing = false;
}

static void melodyStart(unsigned long now) {
  melody.playing = true;
  melody.idx = 0;
  melody.nextAt = now;           // la première note part au prochain tick
}

// Avance la mélodie sans bloquer ; la rejoue en boucle tant qu'on ne l'arrête pas.
static void melodyTick(unsigned long now) {
  if (!melody.playing || now < melody.nextAt) return;
  if (melody.idx >= MELODY_LEN) melody.idx = 0;
  uint16_t f    = pgm_read_word(&MELODY[melody.idx * 3]);
  uint32_t slot = (uint32_t)pgm_read_word(&MELODY[melody.idx * 3 + 1]) * MELODY_SPEED_PCT / 100;
  uint32_t snd  = (uint32_t)pgm_read_word(&MELODY[melody.idx * 3 + 2]) * MELODY_SPEED_PCT / 100;
  if (f) tone(PIN_BUZZER, f, snd); else noTone(PIN_BUZZER);
  melody.nextAt = now + slot;
  melody.idx++;
}

bool oledOk = false;
uint8_t oledAddr = OLED_ADDR;
unsigned long oledProbeAt = 0;

// Cherche l'écran aux adresses 0x3C puis 0x3D ; appelé au boot puis toutes les 10 s tant qu'il manque.
static bool oledProbe() {
  for (uint8_t a : {(uint8_t)0x3C, (uint8_t)0x3D}) {
    Wire.beginTransmission(a);
    if (Wire.endTransmission() == 0 && oled.begin(SSD1306_SWITCHCAPVCC, a)) { oledAddr = a; return true; }
  }
  return false;
}
float mq2R0 = 0;   // résistance du MQ-2 en air propre, calibrée après la chauffe
float gasBase = -1;   // ligne de base du MQ-2 (valeur brute en air propre), fixée après la chauffe
unsigned long tSensor = 0, tTelemetry = 0, tOled = 0, tMqttRetry = 0, bootMs = 0;

static String topic(const char* suffix) { return String(TOPIC_PREFIX) + "/" + suffix; }
static bool dhtFault() { return rd.dhtFails >= 3; }
static bool dhtValid() { return !isnan(rd.temp) && !dhtFault(); }

// ----------------------------------------------------------------------------- OLED
// Interface en pages (128x64) : bandeau titre, pictogrammes, gros chiffres, jauge, courbe,
// pagination en bas. Les pages défilent toutes les OLED_PAGE_MS ; une alerte prend l'écran et clignote.
static const uint8_t ICON_THERMO[] PROGMEM = { 0x03,0xC0, 0x04,0x20, 0x05,0xA0, 0x05,0xA0, 0x05,0xA0, 0x05,0xA0, 0x05,0xA0, 0x05,0xA0, 0x05,0xA0, 0x09,0x90, 0x13,0xC8, 0x17,0xE8, 0x17,0xE8, 0x0B,0xD0, 0x04,0x20, 0x03,0xC0 };
static const uint8_t ICON_DROP[] PROGMEM = { 0x01,0x00, 0x01,0x00, 0x03,0x80, 0x03,0x80, 0x07,0xC0, 0x07,0xC0, 0x0F,0xE0, 0x0F,0xE0, 0x1F,0xF0, 0x1F,0xF0, 0x1F,0xF0, 0x1E,0xF0, 0x0E,0xE0, 0x0F,0xE0, 0x07,0xC0, 0x03,0x80 };
static const uint8_t ICON_FLAME[] PROGMEM = { 0x01,0x00, 0x03,0x00, 0x03,0x80, 0x07,0x80, 0x07,0xC0, 0x0F,0xC0, 0x0F,0xE0, 0x1F,0xE0, 0x1F,0xF0, 0x1E,0xF0, 0x3C,0x78, 0x3C,0x78, 0x3E,0xF8, 0x1F,0xF0, 0x0F,0xE0, 0x07,0xC0 };
static const uint8_t ICON_PERSON[] PROGMEM = { 0x03,0xC0, 0x07,0xE0, 0x07,0xE0, 0x07,0xE0, 0x03,0xC0, 0x01,0x80, 0x0F,0xF0, 0x1F,0xF8, 0x3F,0xFC, 0x3B,0xDC, 0x3B,0xDC, 0x3B,0xDC, 0x03,0xC0, 0x03,0xC0, 0x07,0xE0, 0x07,0xE0 };
static const uint8_t ICON_CAMERA[] PROGMEM = { 0x00,0x00, 0x07,0x80, 0x0F,0xC0, 0x7F,0xF0, 0x7F,0xFC, 0x60,0x0C, 0x67,0xCC, 0x6F,0xEC, 0x6C,0x6C, 0x6C,0x6C, 0x6F,0xEC, 0x67,0xCC, 0x60,0x0C, 0x7F,0xFC, 0x3F,0xF8, 0x00,0x00 };
static const uint8_t ICON_SHIELD[] PROGMEM = { 0x01,0x80, 0x07,0xE0, 0x1F,0xF8, 0x3F,0xFC, 0x39,0x9C, 0x3B,0xDC, 0x3B,0xDC, 0x3B,0xDC, 0x38,0x1C, 0x3B,0xDC, 0x3F,0xFC, 0x1F,0xF8, 0x0F,0xF0, 0x07,0xE0, 0x03,0xC0, 0x01,0x80 };
static const uint8_t ICON_WARN[] PROGMEM = { 0x01,0x80, 0x01,0x80, 0x03,0xC0, 0x03,0xC0, 0x06,0x60, 0x06,0x60, 0x0E,0x70, 0x0E,0x70, 0x1E,0x78, 0x1E,0x78, 0x3E,0x7C, 0x3F,0xFC, 0x7E,0x7E, 0x7E,0x7E, 0xFF,0xFF, 0x00,0x00 };

#define OLED_PAGE_MS 7000
#define TEMP_HIST_N 48
float tempHist[TEMP_HIST_N];
uint8_t tempHistN = 0, tempHistHead = 0;
uint8_t oledPage = 0;
unsigned long oledPageSince = 0;
bool oledInverted = false;

static void histPush(float v) {
  tempHist[tempHistHead] = v;
  tempHistHead = (tempHistHead + 1) % TEMP_HIST_N;
  if (tempHistN < TEMP_HIST_N) tempHistN++;
}

static void drawHeader(const char* title) {
  oled.fillRoundRect(0, 0, 128, 11, 2, SSD1306_WHITE);
  oled.setTextSize(1);
  oled.setTextColor(SSD1306_BLACK);
  oled.setCursor(3, 2);
  oled.print(title);
  // Wi-Fi : 4 barres selon le RSSI
  int bars = !WiFi.isConnected() ? 0 : (WiFi.RSSI() > -55 ? 4 : WiFi.RSSI() > -65 ? 3 : WiFi.RSSI() > -75 ? 2 : 1);
  for (int i = 0; i < 4; i++) {
    int h = 2 + i * 2, x = 104 + i * 3;
    if (i < bars) oled.fillRect(x, 9 - h, 2, h, SSD1306_BLACK);
    else oled.drawRect(x, 9 - h, 2, h, SSD1306_BLACK);
  }
  // MQTT : point plein si connecté, vide sinon
  if (mqtt.connected()) oled.fillCircle(122, 5, 3, SSD1306_BLACK); else oled.drawCircle(122, 5, 3, SSD1306_BLACK);
  oled.setTextColor(SSD1306_WHITE);
}

static void drawFooter(uint8_t n, uint8_t current) {
  int x0 = 64 - (n * 6) / 2;
  for (uint8_t i = 0; i < n; i++) {
    if (i == current) oled.fillCircle(x0 + i * 6 + 2, 61, 2, SSD1306_WHITE);
    else oled.drawPixel(x0 + i * 6 + 2, 61, SSD1306_WHITE);
  }
}

static void bigValue(int x, int y, const String& v, const char* unit) {
  oled.setTextSize(2); oled.setCursor(x, y); oled.print(v);
  oled.setTextSize(1); oled.setCursor(x + v.length() * 12 + 2, y + 7); oled.print(unit);
}

static void pageStatus() {
  drawHeader("SENTINEL-X");
  oled.drawBitmap(4, 16, ICON_SHIELD, 16, 16, SSD1306_WHITE);
  oled.setTextSize(2); oled.setCursor(26, 16); oled.print("SX-G1-01");
  oled.setTextSize(1);
  oled.setCursor(4, 36); oled.print(WiFi.isConnected() ? "IP " + WiFi.localIP().toString() : String("WiFi: connexion..."));
  oled.setCursor(4, 47);
  oled.print(mqtt.connected() ? (TLS_ENABLED ? "MQTT TLS OK" : "MQTT OK") : "MQTT: OFF");
  oled.setCursor(86, 47); oled.print("fw "); oled.print(FW_VERSION);
}

static void pageClimate() {
  drawHeader("CLIMAT");
  oled.drawBitmap(2, 15, ICON_THERMO, 16, 16, SSD1306_WHITE);
  oled.drawBitmap(77, 15, ICON_DROP, 16, 16, SSD1306_WHITE);
  if (dhtValid()) {
    bigValue(18, 16, String(rd.temp, 1), "C");
    bigValue(95, 16, String((int)rd.hum), "%");
  } else {
    oled.setTextSize(1); oled.setCursor(18, 20); oled.print("--.-"); oled.setCursor(95, 20); oled.print("--");
  }
  // courbe de température des 4 dernières minutes
  const int gx = 2, gy = 36, gw = 124, gh = 18;
  oled.drawFastHLine(gx, gy + gh, gw, SSD1306_WHITE);
  if (tempHistN >= 2) {
    float lo = 1e9, hi = -1e9;
    for (uint8_t i = 0; i < tempHistN; i++) { float v = tempHist[i]; if (v < lo) lo = v; if (v > hi) hi = v; }
    if (hi - lo < 1.0f) { float c = (hi + lo) / 2; lo = c - 0.5f; hi = c + 0.5f; }
    int px = -1, py = -1;
    for (uint8_t i = 0; i < tempHistN; i++) {
      uint8_t idx = (tempHistHead + TEMP_HIST_N - tempHistN + i) % TEMP_HIST_N;
      int x = gx + (int)((long)i * (gw - 1) / (TEMP_HIST_N - 1));
      int y = gy + gh - 1 - (int)((tempHist[idx] - lo) / (hi - lo) * (gh - 2));
      if (px >= 0) oled.drawLine(px, py, x, y, SSD1306_WHITE);
      px = x; py = y;
    }
    oled.fillCircle(px, py, 2, SSD1306_WHITE);
  }
}

static void pageGas() {
  drawHeader("GAZ / FUMEE");
  oled.drawBitmap(2, 15, ICON_FLAME, 16, 16, SSD1306_WHITE);
  bigValue(22, 16, String(rd.gasRaw), "raw");
  oled.setTextSize(1); oled.setCursor(2, 36);
  if (gasBase < 0) {
    oled.print("chauffe du capteur...");
  } else {
    int delta = (int)(rd.gasRaw - gasBase);
    oled.print("base "); oled.print((int)gasBase); oled.print("  ecart "); if (delta >= 0) oled.print("+"); oled.print(delta);
    // jauge : 0 .. +GAS_DELTA_CRIT, repères attention / critique
    const int bx = 2, by = 47, bw = 124, bh = 8;
    oled.drawRect(bx, by, bw, bh, SSD1306_WHITE);
    float frac = delta <= 0 ? 0 : (delta >= GAS_DELTA_CRIT ? 1.0f : (float)delta / GAS_DELTA_CRIT);
    if (frac > 0) oled.fillRect(bx + 1, by + 1, (int)((bw - 2) * frac), bh - 2, SSD1306_WHITE);
    int xw = bx + (int)((bw - 2) * (float)GAS_DELTA_WARN / GAS_DELTA_CRIT);
    oled.drawFastVLine(xw, by - 2, bh + 4, SSD1306_WHITE);
    oled.drawFastVLine(bx + bw - 1, by - 2, bh + 4, SSD1306_WHITE);
  }
}

static void pageSecurity() {
  drawHeader("SECURITE");
  oled.drawBitmap(4, 15, ICON_PERSON, 16, 16, SSD1306_WHITE);
  oled.setTextSize(1);
  oled.setCursor(26, 16); oled.print("Mouvement PIR");
  oled.setCursor(26, 25); oled.print(!rd.pirSeenLow ? "> non branche" : rd.motion ? "> PRESENCE" : "> zone libre");
  oled.drawBitmap(4, 36, ICON_CAMERA, 16, 16, SSD1306_WHITE);
  oled.setCursor(26, 37); oled.print("Camera IA");
  oled.setCursor(26, 46); oled.print(al.camera ? "> INTRUSION" : "> zone libre");
  oled.setCursor(96, 46); oled.print(melody.playing ? "SON" : "   ");
}

static void pageAlert() {
  drawHeader("!! ALERTE !!");
  oled.drawBitmap(4, 18, ICON_WARN, 16, 16, SSD1306_WHITE);
  oled.setTextSize(2); oled.setCursor(26, 18);
  if (al.camera && al.motion) oled.print("CAM+PIR");
  else if (al.camera) oled.print("CAMERA");
  else if (al.motion) oled.print("PIR");
  else if (al.gas) oled.print(al.gasCrit ? "GAZ !!" : "GAZ");
  else if (al.temp) oled.print("TEMP");
  else if (al.hum) oled.print("HUMID.");
  else oled.print("CAPTEUR");
  oled.setTextSize(1); oled.setCursor(4, 40);
  if (al.camera) oled.print("Intrus vu par camera");
  else if (al.motion) oled.print("Mouvement detecte");
  else if (al.gas) { oled.print("Gaz : "); oled.print(rd.gasRaw); oled.print(" (+"); oled.print((int)(rd.gasRaw - gasBase)); oled.print(")"); }
  else if (al.temp) { oled.print("Temperature "); oled.print(rd.temp, 1); oled.print(" C"); }
  else if (al.hum) { oled.print("Humidite "); oled.print((int)rd.hum); oled.print(" %"); }
  else oled.print("DHT22 sans reponse");
  oled.setCursor(4, 51); oled.print(melody.playing ? "Sirene active" : "Sirene terminee");
}

static void drawOled() {
  if (!oledOk) return;
  unsigned long now = millis();
  if (now - oledPageSince >= OLED_PAGE_MS) { oledPage = (oledPage + 1) % 4; oledPageSince = now; }
  oled.clearDisplay();
  oled.setTextColor(SSD1306_WHITE);
  if (al.any()) {
    pageAlert();
    bool inv = (now / 500) % 2 == 0;             // clignotement par inversion matérielle
    if (inv != oledInverted) { oled.invertDisplay(inv); oledInverted = inv; }
  } else {
    if (oledInverted) { oled.invertDisplay(false); oledInverted = false; }
    switch (oledPage) {
      case 0: pageStatus(); break;
      case 1: pageClimate(); break;
      case 2: pageGas(); break;
      default: pageSecurity(); break;
    }
    drawFooter(4, oledPage);
  }
  oled.display();
}

// ----------------------------------------------------------------------------- actionneurs
static void tickActuators(unsigned long now) {
  bool online = WiFi.isConnected() && mqtt.connected();
  Actuator* acts[] = {&buzzer, &ledR, &ledG};
  for (Actuator* a : acts) {
    if (a->manual && a->until && now >= a->until) {   // fin de pulse / blink / on temporisé
      a->manual = false; a->blink = false; a->level = false;
    }
    if (a->manual && a->blink && now - a->lastToggle >= BLINK_PERIOD_MS) {
      a->level = !a->level; a->lastToggle = now;
    }
  }
  if (!buzzer.manual) buzzer.level = now < buzzerAutoUntil;
  if (!ledR.manual) ledR.level = al.any() || !online;
  if (!ledG.manual) ledG.level = online && !al.any();
  if (buzzer.level && !melody.playing) melodyStart(now);     // alarme : mélodie (en boucle tant que demandée)
  if (!buzzer.level && melody.playing) melodyStop();
  melodyTick(now);
  digitalWrite(ledR.pin, ledR.level ? HIGH : LOW);
  digitalWrite(ledG.pin, ledG.level ? HIGH : LOW);
}

// "off" rend la main au mode automatique (et coupe la sirène auto pour le buzzer).
// "on" sans durée reste manuel jusqu'à la prochaine commande.
static void applyCommand(Actuator& a, const char* action, unsigned long duration, unsigned long now) {
  if (!strcmp(action, "off")) {
    a.manual = false; a.blink = false; a.level = false; a.until = 0;
    if (&a == &buzzer) buzzerAutoUntil = 0;
    return;
  }
  a.manual = true;
  a.lastToggle = now;
  a.level = true;
  a.blink = !strcmp(action, "blink");
  if (!strcmp(action, "pulse"))  a.until = now + (duration ? duration : (&a == &buzzer ? BUZZER_AUTO_MS : 1000));
  else if (a.blink)              a.until = now + (duration ? duration : 3000);
  else                           a.until = duration ? now + duration : 0;   // "on"
}

static void handleCommand(const JsonDocument& doc) {
  const char* actuator = doc["actuator"] | "";
  const char* action   = doc["action"]   | "";
  unsigned long duration = doc["duration_ms"] | 0UL;
  unsigned long now = millis();
  if      (!strcmp(actuator, "buzzer"))    applyCommand(buzzer, action, duration, now);
  else if (!strcmp(actuator, "led_red"))   applyCommand(ledR, action, duration, now);
  else if (!strcmp(actuator, "led_green")) applyCommand(ledG, action, duration, now);
  else if (!strcmp(actuator, "led")) { applyCommand(ledR, action, duration, now); applyCommand(ledG, action, duration, now); }
  else if (!strcmp(actuator, "camera")) {          // intrusion détectée par la vision IA : écran, LED rouge, bip
    bool on = !strcmp(action, "on");
    if (on && !al.camera) buzzerAutoUntil = now + BUZZER_AUTO_MS;
    al.camera = on;
  }
  else { Serial.printf("[cmd] actionneur inconnu: %s\n", actuator); return; }
  Serial.printf("[cmd] %s %s %lu ms (%s)\n", actuator, action, duration, doc["cmd_id"] | "-");
}

// ----------------------------------------------------------------------------- MQTT
static void publishJson(const char* suffix, JsonDocument& doc, bool retain = false) {
  char buf[512];
  size_t n = serializeJson(doc, buf, sizeof(buf));
  if (!mqtt.publish(topic(suffix).c_str(), reinterpret_cast<const uint8_t*>(buf), n, retain))
    Serial.printf("[mqtt] publication %s echouee (%u octets)\n", suffix, (unsigned)n);
}

static void publishStatus(bool online) {
  JsonDocument doc;
  doc["device_id"] = DEVICE_ID;
  doc["online"] = online;
  if (online) { doc["ip"] = WiFi.localIP().toString(); doc["fw"] = FW_VERSION; }
  publishJson("status", doc, true);
}

#ifndef BENCH_NO_WIFI
static void publishTelemetry() {
  JsonDocument doc;
  doc["device_id"] = DEVICE_ID;
  doc["uptime_ms"] = millis();
  if (dhtValid()) {
    doc["temperature"] = roundf(rd.temp * 10) / 10;
    doc["humidity"]    = roundf(rd.hum * 10) / 10;
  }
  doc["gas_raw"]   = rd.gasRaw;
  doc["gas_ppm"]   = roundf(rd.gasPpm * 10) / 10;
  doc["motion"]    = rd.motion;
  doc["rssi"]      = WiFi.RSSI();
  doc["heap_free"] = ESP.getFreeHeap();
  publishJson("telemetry", doc);
}
#endif

static void publishAlert(const char* type, bool on, float value, const char* severity) {
  JsonDocument doc;
  doc["device_id"] = DEVICE_ID;
  doc["uptime_ms"] = millis();
  doc["type"]      = type;
  doc["state"]     = on ? "on" : "off";
  doc["value"]     = value;
  doc["severity"]  = severity;
  publishJson("alerts", doc);
  Serial.printf("[alert] %s %s (%.1f) %s\n", type, on ? "ON" : "OFF", value, severity);
  if (on && (!strcmp(severity, "critical") || !strcmp(type, "motion")))
    buzzerAutoUntil = millis() + BUZZER_AUTO_MS;
}

static void onMqttMessage(char* t, uint8_t* payload, unsigned int len) {
  JsonDocument doc;
  DeserializationError err = deserializeJson(doc, payload, len);
  if (err) { Serial.printf("[mqtt] JSON invalide sur %s : %s\n", t, err.c_str()); return; }
  if (topic("cmd") == t) handleCommand(doc);
}

#if TLS_ENABLED && defined(MQTT_CA_CERT)
static void syncTime() {
  configTime(0, 0, "pool.ntp.org", "time.nist.gov");
  Serial.print("[time] NTP");
  unsigned long t0 = millis();
  while (time(nullptr) < 1700000000UL && millis() - t0 < 5000) { delay(200); Serial.print("."); }
  if (time(nullptr) < 1700000000UL) {
    timeval tv = { (time_t)BUILD_EPOCH, 0 };   // réseau isolé : date de compilation
    settimeofday(&tv, nullptr);
    Serial.println(" absent, date de compilation utilisee");
  } else {
    Serial.println(" OK");
  }
}
#endif

static bool mqttConnect() {
  String willTopic = topic("status");
  char will[96];
  snprintf(will, sizeof(will), "{\"device_id\":\"%s\",\"online\":false}", DEVICE_ID);
  Serial.printf("[mqtt] connexion %s:%d%s... ", MQTT_HOST, MQTT_PORT, TLS_ENABLED ? " (TLS)" : "");
  bool ok = mqtt.connect(DEVICE_ID, MQTT_USER, MQTT_PASS, willTopic.c_str(), 1, true, will);
  if (!ok) {
    Serial.printf("echec rc=%d", mqtt.state());
#if TLS_ENABLED
    char sslErr[96];
    int code = net.getLastSSLError(sslErr, sizeof(sslErr));
    if (code) Serial.printf(" ssl=%d %s", code, sslErr);
#endif
    Serial.printf(" (heap %u)\n", ESP.getFreeHeap());
    return false;
  }
  Serial.println("OK");
  Serial.printf("[oled] %s | heap %u\n", oledOk ? "detecte a 0x3C" : "ABSENT (verifier SDA=D2 SCL=D1 3V G)", ESP.getFreeHeap());
  mqtt.subscribe(topic("cmd").c_str(), 1);
  publishStatus(true);
  return true;
}

// ----------------------------------------------------------------------------- capteurs
static float mq2Rs(int raw) {
  float v = raw / 1023.0f * 3.3f * MQ2_DIVIDER_RATIO;   // tension en sortie AO du capteur
  if (v < 0.01f) v = 0.01f;
  return MQ2_RL_KOHM * (MQ2_VCC - v) / v;                // Rs en kΩ
}

static void readSensors(unsigned long now) {
  float t = dht.readTemperature();
  float h = dht.readHumidity();
  // Trame corrompue ayant passé le checksum par hasard (contact douteux) : valeurs hors plage physique
  if (!isnan(t) && (t < -40 || t > 80 || h < 0 || h > 100)) { t = NAN; h = NAN; }
  if (isnan(t) || isnan(h)) {
    if (rd.dhtFails < 255) rd.dhtFails++;
  } else {
    rd.temp = t; rd.hum = h; rd.dhtFails = 0;
    static uint8_t histTick = 0;
    if (++histTick >= 3) { histTick = 0; histPush(t); }   // un point toutes les ~6 s → 48 points ≈ 5 min
  }

  // Médiane de 8 lectures : l'ADC de l'ESP8266 glitche pendant les émissions Wi-Fi
  int samples[8];
  for (int i = 0; i < 8; i++) { samples[i] = analogRead(PIN_GAS); delayMicroseconds(300); }
  for (int i = 1; i < 8; i++) { int v = samples[i], j = i - 1; while (j >= 0 && samples[j] > v) { samples[j + 1] = samples[j]; j--; } samples[j + 1] = v; }
  rd.gasRaw = (samples[3] + samples[4]) / 2;
  if (now - bootMs > MQ2_WARMUP_MS) {
    // Ligne de base : suit immédiatement vers le bas (le capteur continue de se "nettoyer"),
    // très lentement vers le haut (une hausse lente est précisément ce que l'IA doit voir).
    static int baseCount = 0; static float baseAcc = 0;
    if (gasBase < 0) {                       // ligne de base initiale : moyenne des 10 premières lectures (20 s)
      baseAcc += rd.gasRaw;
      if (++baseCount >= 10) { gasBase = baseAcc / baseCount; Serial.printf("[mq2] ligne de base = %.0f\n", gasBase); }
    } else if (rd.gasRaw < gasBase) gasBase += 0.1f * (rd.gasRaw - gasBase);    // descente : suivi en ~20 s
    else gasBase += 0.005f * (rd.gasRaw - gasBase);                             // montée : suivi en ~7 min
    float rs = mq2Rs(rd.gasRaw);
    if (mq2R0 <= 0) { mq2R0 = rs / MQ2_CLEAN_AIR_RATIO; Serial.printf("[mq2] R0 calibre = %.2f kOhm\n", mq2R0); }
    float ratio = rs / mq2R0;
    float ppm = ratio > 0 ? 574.25f * powf(ratio, -2.222f) : 0;   // estimation GPL, datasheet MQ-2
    rd.gasPpm = ppm < 0 ? 0 : (ppm > 10000 ? 10000 : ppm);          // borné : l'estimation n'a de sens qu'en ordre de grandeur
  }

  // Une broche en l'air se lit au niveau haut : on ne croit le PIR qu'après l'avoir vu bas une fois.
  bool pirHigh = digitalRead(PIN_PIR) == HIGH;
  if (!pirHigh) rd.pirSeenLow = true;
  rd.motion = rd.pirSeenLow && pirHigh;
}

// Seuils avec hystérésis : on publie à l'entrée, à l'escalade (warning → critical) et à la sortie.
static void evalThreshold(bool& active, bool& crit, float value, float warn, float critT, float hyst, const char* type) {
  if (!active && value > warn) {
    active = true; crit = value > critT;
    publishAlert(type, true, value, crit ? "critical" : "warning");
  } else if (active && !crit && value > critT) {
    crit = true;
    publishAlert(type, true, value, "critical");
  } else if (active && value < warn - hyst) {
    active = false; crit = false;
    publishAlert(type, false, value, "info");
  }
}

static void evalAlerts() {
  if (rd.motion != al.motion) {
    al.motion = rd.motion;
    publishAlert("motion", al.motion, al.motion ? 1 : 0, "warning");
  }
  if (gasBase >= 0)   // après la chauffe seulement : seuils relatifs à la ligne de base
    evalThreshold(al.gas, al.gasCrit, rd.gasRaw, gasBase + GAS_DELTA_WARN, gasBase + GAS_DELTA_CRIT, HYST_GAS, "gas");
  if (dhtValid()) {
    evalThreshold(al.temp, al.tempCrit, rd.temp, TEMP_WARN, TEMP_CRIT, HYST_TEMP, "temperature");
    evalThreshold(al.hum,  al.humCrit,  rd.hum,  HUM_WARN,  HUM_CRIT,  HYST_HUM,  "humidity");
  }
  if (dhtFault() != al.fault) {
    al.fault = dhtFault();
    publishAlert("sensor_fault", al.fault, 0, "warning");
  }
}

// ----------------------------------------------------------------------------- setup / loop
void setup() {
  Serial.begin(115200);
  delay(100);
  Serial.printf("\n\nSENTINEL-X %s  fw %s\n", DEVICE_ID, FW_VERSION);
  bootMs = millis();

  pinMode(PIN_PIR, INPUT);
  pinMode(PIN_BUZZER, OUTPUT);
  pinMode(PIN_LED_RED, OUTPUT);
  pinMode(PIN_LED_GREEN, OUTPUT);
  digitalWrite(PIN_BUZZER, LOW);
  digitalWrite(PIN_LED_RED, LOW);
  digitalWrite(PIN_LED_GREEN, LOW);
  dht.begin();

  Wire.begin(PIN_OLED_SDA, PIN_OLED_SCL);
  oledOk = oledProbe();
  if (!oledOk) {
    Serial.println("[oled] introuvable en 0x3C/0x3D (verifier SDA=D2, SCL=D1, 3V, G) : nouvel essai toutes les 10 s");
  } else {
    Serial.printf("[oled] detecte a 0x%02X\n", oledAddr);
    oled.clearDisplay();
    oled.drawBitmap(56, 8, ICON_SHIELD, 16, 16, SSD1306_WHITE);
    oled.setTextSize(2);
    oled.setTextColor(SSD1306_WHITE);
    oled.setCursor(4, 30);
    oled.print("SENTINEL-X");
    oled.setTextSize(1);
    oled.setCursor(22, 50);
    oled.print("AetherCorp  Groupe 1");
    oled.display();
  }

#ifdef BENCH_NO_WIFI
  // Mode banc d'essai : radio coupée (~70 mA) pour tester carte, OLED et capteurs sur un port
  // USB ou un hub qui ne fournit pas assez de courant pour le Wi-Fi.
  WiFi.mode(WIFI_OFF);
  WiFi.forceSleepBegin();
  Serial.println("[wifi] MODE BANC : radio coupee, pas de MQTT (build -e bench)");
#else
  WiFi.mode(WIFI_STA);
  WiFi.persistent(false);
  WiFi.setAutoReconnect(true);
  WiFi.setOutputPower(WIFI_TX_DBM);
  WiFi.hostname(DEVICE_ID);
  WiFi.begin(WIFI_SSID, WIFI_PASS);
  Serial.printf("[wifi] connexion a %s (tx %.1f dBm)", WIFI_SSID, (double)WIFI_TX_DBM);
  unsigned long t0 = millis();
  while (!WiFi.isConnected() && millis() - t0 < 20000) { delay(250); Serial.print("."); }
  if (WiFi.isConnected()) Serial.println(" OK " + WiFi.localIP().toString());
  else Serial.println(" echec, nouvelles tentatives en arriere-plan");
#endif

#if TLS_ENABLED
#ifdef MQTT_CA_CERT
  net.setTrustAnchors(&caList);
  syncTime();
#else
  net.setFingerprint(MQTT_FINGERPRINT);
#endif
#endif
  mqtt.setServer(MQTT_HOST, MQTT_PORT);
  mqtt.setCallback(onMqttMessage);
  mqtt.setBufferSize(512);
  mqtt.setKeepAlive(30);
}

void loop() {
  unsigned long now = millis();

  if (WiFi.isConnected()) {
    if (!mqtt.connected()) {
      if (now - tMqttRetry >= MQTT_RETRY_MS) { tMqttRetry = now; mqttConnect(); }
    } else {
      mqtt.loop();
    }
  }

  if (now - tSensor >= SENSOR_PERIOD_MS) {
    tSensor = now;
    readSensors(now);
    evalAlerts();
  }
  if (now - tTelemetry >= TELEMETRY_PERIOD_MS) {
    tTelemetry = now;
#ifdef BENCH_NO_WIFI
    Serial.printf("[banc] T=%s H=%s gaz=%d pir=%d heap=%u\n",
                  dhtValid() ? String(rd.temp, 1).c_str() : "--", dhtValid() ? String(rd.hum, 0).c_str() : "--",
                  rd.gasRaw, rd.motion ? 1 : 0, ESP.getFreeHeap());
#else
    if (mqtt.connected()) publishTelemetry();
#endif
  }
  if (!oledOk && now - oledProbeAt >= 10000) {        // écran branché après coup, ou fil remis en place
    oledProbeAt = now;
    if ((oledOk = oledProbe())) Serial.printf("[oled] detecte a 0x%02X (branchement tardif)\n", oledAddr);
  }
  if (now - tOled >= OLED_PERIOD_MS) {
    tOled = now;
    drawOled();
  }
  tickActuators(now);
  yield();
}
