// file: src/status.cpp
#include <Arduino.h>
#include "status.h"
#include "state.h"
#include "config.h"

static const char* modeStr(){
  // SỬA: Đọc từ sharedData.mode thay vì biến mode cũ
  // (Lưu ý: để đơn giản khi log, ta đọc trực tiếp không cần Mutex, chấp nhận sai số nhỏ)
  Mode m = sharedData.mode; 

  switch (m){
    case MODE_MANUAL:  return "manual";
    case MODE_CONTROL: return "control";
    case MODE_OFF:     return "off";
  }
  return "?";
}

static const char* phaseStr(){
  switch (phase){
    case PHASE_A_GREEN:        return "A_GREEN";
    case PHASE_A_YELLOW_3S:    return "A_YELLOW";
    case PHASE_A_RED_WAIT_1S:  return "A_RED_WAIT";
    case PHASE_B_GREEN:        return "B_GREEN";
    case PHASE_B_YELLOW_3S:    return "B_YELLOW";
    case PHASE_B_RED_WAIT_1S:  return "B_RED_WAIT";
  }
  return "?";
}

void fillStatusDoc(JsonDocument& d, const char* note){ // SỬA: JsonDocument
  d["mode"]  = modeStr();
  d["phase"] = phaseStr();
  if (note) d["note"] = note;
  d["uptime_s"] = millis()/1000;
  
  // Giờ biến này đã có nhờ bước sửa số 1
  d["green_s"]  = MAN_GREEN_MS/1000;
  d["red_s"]    = MAN_RED_MS/1000;
  
  d["device"]   = DEVICE_ID;
}

void logStatus(const char* note){
  JsonDocument d; // SỬA: Thay StaticJsonDocument<256> bằng JsonDocument
  fillStatusDoc(d, note);
  String s; serializeJson(d, s);
  Serial.println(s);
}