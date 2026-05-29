/*
 * CardioMonitor - ESP32 + MAX30100 firmware
 * ----------------------------------------------------------------------------
 * Streams heart-beat events as newline-delimited JSON over USB serial.
 * Each detected beat emits:
 *     {"bpm": 75.3, "ibi": 820, "ts_ms": 12345, "spo2": 97.4, "ir": 51234}
 *
 *  Hardware wiring (MAX30100 breakout <-> ESP32 DevKit v1):
 *      VIN  -> 3V3
 *      GND  -> GND
 *      SCL  -> GPIO 22
 *      SDA  -> GPIO 21
 *      INT  -> GPIO 19    (optional, not used by the PulseOximeter library)
 *
 *  Arduino IDE setup:
 *      Board   : "ESP32 Dev Module"
 *      Library : "MAX30100lib" by OXullo Intersecans  (Library Manager)
 *      Baud    : 115200 (must match Streamlit dashboard)
 *
 *  The MAX30100_PulseOximeter helper handles peak detection and exposes BPM.
 *  IBI (inter-beat interval in ms) is computed from successive beats.
 * ----------------------------------------------------------------------------
 */

#include <Wire.h>
#include "MAX30100_PulseOximeter.h"

#define REPORTING_PERIOD_MS 1000     // fallback periodic status line
#define LED_STATUS_PIN      2        // on-board LED (most ESP32 dev boards)

PulseOximeter pox;
uint32_t lastReport = 0;
uint32_t lastBeatMs = 0;
bool      firstBeat = true;

// ----------------------------------------------------------- beat callback --
void onBeatDetected() {
    uint32_t now = millis();
    uint32_t ibi = 0;
    if (!firstBeat) {
        ibi = now - lastBeatMs;
    }
    lastBeatMs = now;
    firstBeat  = false;

    float bpm  = pox.getHeartRate();
    float spo2 = pox.getSpO2();
    float ir   = pox.getIR();

    // Emit JSON line. IBI is 0 on the very first beat (no previous reference).
    Serial.print("{\"bpm\":");
    Serial.print(bpm, 1);
    Serial.print(",\"ibi\":");
    Serial.print(ibi);
    Serial.print(",\"ts_ms\":");
    Serial.print(now);
    Serial.print(",\"spo2\":");
    Serial.print(spo2, 1);
    Serial.print(",\"ir\":");
    Serial.print(ir, 0);
    Serial.println("}");

    digitalWrite(LED_STATUS_PIN, HIGH);
}

// --------------------------------------------------------------------- setup -
void setup() {
    Serial.begin(115200);
    delay(200);
    pinMode(LED_STATUS_PIN, OUTPUT);
    digitalWrite(LED_STATUS_PIN, LOW);

    Serial.println("{\"event\":\"boot\",\"firmware\":\"CardioMonitor/ESP32/MAX30100\"}");

    Wire.begin(21, 22);                     // SDA=21, SCL=22
    if (!pox.begin()) {
        Serial.println("{\"event\":\"error\",\"msg\":\"MAX30100 not detected\"}");
        while (true) {                      // blink SOS-style and halt
            digitalWrite(LED_STATUS_PIN, HIGH); delay(120);
            digitalWrite(LED_STATUS_PIN, LOW);  delay(120);
        }
    }
    pox.setIRLedCurrent(MAX30100_LED_CURR_7_6MA);
    pox.setOnBeatDetectedCallback(onBeatDetected);

    Serial.println("{\"event\":\"ready\"}");
}

// ---------------------------------------------------------------------- loop -
void loop() {
    pox.update();

    if (millis() - lastReport > REPORTING_PERIOD_MS) {
        // Heartbeat "keepalive" line - lets the dashboard detect disconnects.
        Serial.print("{\"event\":\"status\",\"bpm\":");
        Serial.print(pox.getHeartRate(), 1);
        Serial.print(",\"spo2\":");
        Serial.print(pox.getSpO2(), 1);
        Serial.println("}");
        lastReport = millis();
        digitalWrite(LED_STATUS_PIN, LOW);
    }
}
