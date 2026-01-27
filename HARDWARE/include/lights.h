#pragma once
#include <Arduino.h>

// Giá trị bật/tắt theo yêu cầu
#define LED_ON   0x01   // HIGH
#define LED_OFF  0x00   // LOW

void lights_init();
void setLightsA(uint8_t g, uint8_t y, uint8_t r);
void setLightsB(uint8_t g, uint8_t y, uint8_t r);
void allOff();
void safeAllRed();