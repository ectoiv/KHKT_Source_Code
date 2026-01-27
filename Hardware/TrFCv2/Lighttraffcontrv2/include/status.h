// file: include/status.h
#pragma once
#include <ArduinoJson.h>

// SỬA: Tham số là JsonDocument
void fillStatusDoc(JsonDocument& d, const char* note=nullptr);
void logStatus(const char* note=nullptr);