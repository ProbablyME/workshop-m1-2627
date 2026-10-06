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
// Piste guitare (canal 0), 15 notes, 2.2 s, transposée de 3 octaves pour le buzzer.
// Triplets (fréquence Hz, créneau ms, durée sonnée ms). MELODY_SPEED_PCT dans config.h ralentit/accélère.
static const uint16_t MELODY[] PROGMEM = {
  659,136,43, 659,143,143, 1319,136,129, 659,136,43, 659,136,136, 1175,136,121, 659,136,43, 659,136,136,
  1047,136,129, 659,136,43, 659,136,136, 932,136,136, 659,143,57, 659,136,136, 988,329,129 };
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
float mq2R0 = 0;   // résistance du MQ-2 en air propre, calibrée après la chauffe
float gasBase = -1;   // ligne de base du MQ-2 (valeur brute en air propre), fixée après la chauffe
unsigned long tSensor = 0, tTelemetry = 0, tOled = 0, tMqttRetry = 0, bootMs = 0;

static String topic(const char* suffix) { return String(TOPIC_PREFIX) + "/" + suffix; }
static bool dhtFault() { return rd.dhtFails >= 3; }
static bool dhtValid() { return !isnan(rd.temp) && !dhtFault(); }

// ----------------------------------------------------------------------------- OLED
static void oledLine(uint8_t row, const String& s) {
  oled.setCursor(0, row * 10);
  oled.print(s);
}

static void drawOled() {
  if (!oledOk) return;
  oled.clearDisplay();
  oled.setTextSize(1);
  oled.setTextColor(SSD1306_WHITE);
  oledLine(0, String("SENTINEL-X ") + DEVICE_ID);
#ifdef BENCH_NO_WIFI
  oledLine(1, String("MODE BANC (sans WiFi)"));
#else
  oledLine(1, WiFi.isConnected() ? "IP " + WiFi.localIP().toString() : String("WiFi: connexion..."));
#endif
  oledLine(2, String("MQTT ") + (mqtt.connected() ? "OK" : "--") + (TLS_ENABLED ? " TLS " : " ") +
                  String(WiFi.RSSI()) + "dBm");
  oledLine(3, dhtValid() ? "T " + String(rd.temp, 1) + "C  H " + String(rd.hum, 0) + "%"
                         : String("DHT22: pas de donnee"));
  oledLine(4, "Gaz " + String(rd.gasRaw) + (gasBase < 0 ? " chauffe" : " +" + String((int)(rd.gasRaw - gasBase))) +
                  "  PIR " + (rd.motion ? "!!" : "--"));
  String st = "Statut: nominal";
  if (al.any()) {
    st = "ALERTE";
    if (al.camera && al.motion) st += " CAM+PIR";
    else if (al.camera) st += " CAMERA";
    else if (al.motion) st += " PIR";
    if (al.gas) st += al.gasCrit ? " GAZ!" : " gaz";
    if (al.temp) st += al.tempCrit ? " TEMP!" : " temp";
    if (al.hum) st += " hum";
    if (al.fault) st += " capteur";
  }
  oledLine(5, st);
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

  rd.motion = digitalRead(PIN_PIR) == HIGH;
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
  oledOk = oled.begin(SSD1306_SWITCHCAPVCC, OLED_ADDR);
  if (!oledOk) {
    Serial.println("[oled] introuvable a 0x3C (verifier SDA=D2, SCL=D1, 3V, G)");
  } else {
    oled.clearDisplay();
    oled.setTextSize(2);
    oled.setTextColor(SSD1306_WHITE);
    oled.setCursor(4, 24);
    oled.print("SENTINEL-X");
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
  if (now - tOled >= OLED_PERIOD_MS) {
    tOled = now;
    drawOled();
  }
  tickActuators(now);
  yield();
}
