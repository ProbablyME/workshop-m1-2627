#pragma once
// Configuration matérielle et fonctionnelle du boîtier. Les secrets sont dans secrets.h.

// ---- Identité (docs/CONTRAT_DONNEES.md §1) ----
#define DEVICE_ID     "SX-G1-01"
#define FW_VERSION    "0.1.0"
#define TOPIC_PREFIX  "sentinel/g1"

// ---- Broches (docs/CABLAGE.md §1) ----
#define PIN_OLED_SCL   D1   // GPIO5
#define PIN_OLED_SDA   D2   // GPIO4
#define PIN_DHT        D5   // GPIO14
#define DHT_TYPE       DHT22 // DHT11 si le capteur est le modèle bleu
#define PIN_PIR        D6   // GPIO12
#define PIN_BUZZER     D7   // GPIO13 (via transistor NPN)
#define PIN_LED_RED    D0   // GPIO16
#define PIN_LED_GREEN  D8   // GPIO15 (doit être bas au boot : LED vers masse = OK)
#define PIN_GAS        A0   // ADC via pont diviseur 10k/20k

// ---- Wi-Fi ----
// Puissance d'émission en dBm (max 20.5). 17 suffit largement sur une table et réduit le
// courant de pointe, utile quand l'ESP est alimenté par un port USB ou un hub faiblard.
#define WIFI_TX_DBM  17.0f

// ---- Cadences (ms) ----
#define SENSOR_PERIOD_MS     2000   // DHT22 : 2 s minimum entre deux lectures
#define TELEMETRY_PERIOD_MS  5000   // contrat §2
#define OLED_PERIOD_MS        500
#define MQTT_RETRY_MS        5000
#define MQ2_WARMUP_MS      180000   // chauffe du MQ-2 : pas d'alerte gaz ni de ppm avant 3 min

// ---- Seuils locaux "réflexe" (contrat §6) ----
#define TEMP_WARN  35.0f
#define TEMP_CRIT  45.0f
#define HUM_WARN   80.0f
#define HUM_CRIT   90.0f
// Gaz : seuils RELATIFS à la ligne de base mesurée après la chauffe (robuste au 3,3 V / 5 V et à la dérive)
#define GAS_DELTA_WARN   80
#define GAS_DELTA_CRIT  200
#define HYST_TEMP   2.0f
#define HYST_HUM    3.0f
#define HYST_GAS   30

// ---- MQ-2 : estimation ppm (courbe GPL de la datasheet, indicative) ----
#define MQ2_DIVIDER_RATIO  1.0f    // montage minimal : MQ-2 en 3,3 V, AO direct sur A0 (1.5f avec diviseur 10k/20k)
#define MQ2_VCC            3.3f    // 5.0f si le MQ-2 est alimenté en 5 V
#define MQ2_RL_KOHM        5.0f    // résistance de charge du module (1k sur certains modules)
#define MQ2_CLEAN_AIR_RATIO 9.83f  // Rs/R0 en air propre (datasheet)

// ---- Actionneurs ----
// Buzzer PASSIF (module 3 broches, signal sur D7) : le firmware joue une mélodie par PWM (tone()).
// BUZZER_AUTO_MS = durée de la sirène automatique sur alerte (≈ la mélodie à 100 %).
#define BUZZER_AUTO_MS  10991
#define MELODY_SPEED_PCT 100   // 100 = tempo du jeu ; 150 = une fois et demie plus lent
#define BLINK_PERIOD_MS  200

// ---- OLED ----
#define OLED_ADDR  0x3C
#define OLED_W     128
#define OLED_H     64
