#include <Arduino.h>
#include "pins.h"
#include "lights.h"

// KHÔNG đảo mức: 0x01 = HIGH (bật), 0x00 = LOW (tắt)
void lights_init() {
  pinMode(PIN_A_G, OUTPUT); pinMode(PIN_A_Y, OUTPUT); pinMode(PIN_A_R, OUTPUT);
  pinMode(PIN_B_G, OUTPUT); pinMode(PIN_B_Y, OUTPUT); pinMode(PIN_B_R, OUTPUT);

  digitalWrite(PIN_A_G, LED_OFF); digitalWrite(PIN_A_Y, LED_OFF); digitalWrite(PIN_A_R, LED_OFF);
  digitalWrite(PIN_B_G, LED_OFF); digitalWrite(PIN_B_Y, LED_OFF); digitalWrite(PIN_B_R, LED_OFF);
}

void setLightsA(uint8_t g, uint8_t y, uint8_t r) {
  digitalWrite(PIN_A_G, g); digitalWrite(PIN_A_Y, y); digitalWrite(PIN_A_R, r);
}
void setLightsB(uint8_t g, uint8_t y, uint8_t r) {
  digitalWrite(PIN_B_G, g); digitalWrite(PIN_B_Y, y); digitalWrite(PIN_B_R, r);
}
void allOff() {
  setLightsA(LED_OFF, LED_OFF, LED_OFF);
  setLightsB(LED_OFF, LED_OFF, LED_OFF);
}
void safeAllRed() {
  setLightsA(LED_OFF, LED_OFF, LED_ON);
  setLightsB(LED_OFF, LED_OFF, LED_ON);
}