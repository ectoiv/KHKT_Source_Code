#include <WebSocketsClient.h>
#include <ArduinoJson.h>
#include "socket_client.h"
#include "state.h"
#include "config.h"

WebSocketsClient webSocket;
unsigned long lastMsgTime = 0;

void hexdump(const void *mem, uint32_t len, uint8_t cols = 16) {
  const uint8_t* src = (const uint8_t*) mem;
  Serial.printf("\n[HEXDUMP] Address: 0x%08X len: 0x%X (%d)", (ptrdiff_t)src, len, len);
  for(uint32_t i = 0; i < len; i++) {
    if(i % cols == 0) Serial.printf("\n[0x%08X] 0x%08X: ", (ptrdiff_t)src, i);
    Serial.printf("%02X ", *src); src++;
  }
  Serial.printf("\n");
}

void webSocketEvent(WStype_t type, uint8_t * payload, size_t length) {
    switch(type) {
        case WStype_DISCONNECTED:
            Serial.printf("[WSc] Disconnected!\n");
            // Cập nhật trạng thái mất kết nối an toàn
            if (xSemaphoreTake(dataMutex, pdMS_TO_TICKS(10)) == pdTRUE) {
                sharedData.isConnected = false;
                xSemaphoreGive(dataMutex);
            }
            break;

        case WStype_CONNECTED:
            Serial.printf("[WSc] Connected to url: %s\n", payload);
            // Gửi message chào hỏi nếu cần
            webSocket.sendTXT("{\"type\":\"hello\", \"device\":\"" DEVICE_ID "\"}");
            break;

        case WStype_TEXT:
            Serial.printf("[WSc] get text: %s\n", payload);
            lastMsgTime = millis();
            
            // Parse JSON ngay tại đây
           JsonDocument doc;
            DeserializationError error = deserializeJson(doc, payload);
            if (error) {
                Serial.print(F("deserializeJson() failed: "));
                Serial.println(error.c_str());
                return;
            }
                
            // --- QUAN TRỌNG: Cập nhật Shared Data với Mutex ---
            // Chỉ giữ Mutex trong thời gian cực ngắn để copy dữ liệu
            if (!error && xSemaphoreTake(dataMutex, pdMS_TO_TICKS(10)) == pdTRUE) {
                sharedData.isConnected = true;

                // 1. XỬ LÝ TRẠNG THÁI (STATE)
                JsonObject state = doc["state"];
                if (state["OFF"]) sharedData.mode = MODE_OFF;
                else if (state["Manual"]) sharedData.mode = MODE_MANUAL;
                else if (state["Control"]) sharedData.mode = MODE_CONTROL;
                
                sharedData.redTarget = state["Red"];

                // 2. XỬ LÝ DỮ LIỆU PCU (PCU) - THÊM MỚI
                JsonObject pcuObj = doc["pcu"];
                if (!pcuObj.isNull()) {
                    // Lưu thời gian
                    sharedData.timeStr = pcuObj["Time"].as<String>();
                    
                    // Lưu dữ liệu các Zone vào mảng (để dễ hiển thị vòng lặp)
                    sharedData.pcu[0] = pcuObj["zone1pcu"];
                    sharedData.ppcu[0] = pcuObj["zone1ppcu"];
                    
                    sharedData.pcu[1] = pcuObj["zone2pcu"];
                    sharedData.ppcu[1] = pcuObj["zone2ppcu"];
                    
                    sharedData.pcu[2] = pcuObj["zone3pcu"];
                    sharedData.ppcu[2] = pcuObj["zone3ppcu"];
                    
                    sharedData.pcu[3] = pcuObj["zone4pcu"];
                    sharedData.ppcu[3] = pcuObj["zone4ppcu"];
                }

                xSemaphoreGive(dataMutex);
            }
            break;
    }
}

void socket_setup() {
    // Server address, port and URL
    webSocket.begin(WS_HOST, WS_PORT, WS_PATH);
    // webSocket.setAuthorization("user", "Password"); // Nếu cần auth
    webSocket.onEvent(webSocketEvent);
    webSocket.setReconnectInterval(5000);
}

void socket_loop() {
    webSocket.loop();
    // Watchdog: Nếu lâu không nhận được tin -> Báo mất kết nối
    // // if (millis() - lastMsgTime > SERVER_FAIL_TO_MANUAL_MS) {
    // //      if (xSemaphoreTake(dataMutex, pdMS_TO_TICKS(10)) == pdTRUE) {
    // //          // Chỉ đánh dấu là mất kết nối, logic chuyển Manual sẽ nằm ở FSM
    // //          sharedData.isConnected = false; 
    // //          xSemaphoreGive(dataMutex);
    // //      }
    // }
}