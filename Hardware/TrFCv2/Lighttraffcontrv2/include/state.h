#pragma once
#include <Arduino.h>
#include <freertos/semphr.h> 

enum Mode  { MODE_MANUAL, MODE_CONTROL, MODE_OFF };
enum Phase {
  PHASE_A_GREEN, PHASE_A_YELLOW_3S, PHASE_A_RED_WAIT_1S,
  PHASE_B_GREEN, PHASE_B_YELLOW_3S, PHASE_B_RED_WAIT_1S
};

struct SharedState {
  bool isConnected;
  Mode mode;       // 0: OFF, 1: MANUAL, 2: CONTROL
  bool redTarget;
  
  // --- THÊM MỚI ---
  String timeStr;     // Lưu chuỗi thời gian "06:06:10 PM"
  float pcu[4];       // Lưu giá trị PCU cho 4 zone
  float ppcu[4];      // Lưu giá trị PPCU cho 4 zone
};

extern SharedState sharedData;      
extern SemaphoreHandle_t dataMutex; 

extern Phase phase;
extern uint32_t tPhaseStart;
extern uint32_t tBlinkStart;
extern bool blinkState;

// --- THÊM LẠI CÁC DÒNG NÀY ---
extern uint32_t MAN_GREEN_MS;
extern uint32_t MAN_RED_MS;