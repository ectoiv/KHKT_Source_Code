#include <Arduino.h>
#include "fsm.h"
#include "state.h"
#include "lights.h"
#include "status.h"

// Biến cục bộ để FSM sử dụng (được copy từ sharedData sang)
static Mode currentMode = MODE_MANUAL;
static bool currentRedTarget = false;
static bool serverConnected = false;

// Hàm đồng bộ dữ liệu từ Task Network sang Task Logic an toàn
static void syncState() {
    // Chỉ mượn Mutex trong tích tắc để copy dữ liệu
    if (xSemaphoreTake(dataMutex, 0) == pdTRUE) { // 0 = Không chờ nếu đang bận
        serverConnected = sharedData.isConnected;
        Mode networkMode = sharedData.mode; // Lấy mode nhận được từ server
        // Logic Failsafe: Mất mạng -> Về Manual
        if (!serverConnected) {
            // Mất mạng: Chỉ chuyển về MANUAL nếu mode hiện tại yêu cầu mạng (CONTROL)
            if (networkMode == MODE_CONTROL) {
                currentMode = MODE_MANUAL;
            } else {
                // Nếu đang là OFF (hoặc MANUAL), thì giữ nguyên trạng thái đó
                currentMode = networkMode; 
            }
        } else {
            // Có mạng: Luôn nghe theo server
            currentMode = networkMode;
            currentRedTarget = sharedData.redTarget;
        }
        
        xSemaphoreGive(dataMutex);
    }
}

// --- 1. Hàm Manual FSM (Code cũ của bạn) ---
void manualFSM(){
  uint32_t now = millis();
  switch (phase){
    case PHASE_A_GREEN:
      setLightsA(LED_ON,  LED_OFF, LED_OFF);
      setLightsB(LED_OFF, LED_OFF, LED_ON);
      if (now - tPhaseStart >= MAN_GREEN_MS){
        phase = PHASE_A_YELLOW_3S; tPhaseStart = now;
      }
      break;

    case PHASE_A_YELLOW_3S:
      setLightsA(LED_OFF, LED_ON,  LED_OFF);
      setLightsB(LED_OFF, LED_OFF, LED_ON);
      if (now - tPhaseStart >= 5000){
        setLightsA(LED_OFF, LED_OFF,  LED_ON);
        phase = PHASE_A_RED_WAIT_1S; tPhaseStart = now;
      }
      break;

    case PHASE_A_RED_WAIT_1S:
      setLightsA(LED_OFF, LED_OFF,  LED_ON);
      setLightsB(LED_OFF, LED_OFF,  LED_ON);
      if (now - tPhaseStart >= 1000){
        phase = PHASE_B_GREEN; tPhaseStart = now;
      }
      break;

    case PHASE_B_GREEN:
      setLightsB(LED_ON,  LED_OFF, LED_OFF);
      setLightsA(LED_OFF, LED_OFF,  LED_ON);
      if (now - tPhaseStart >= MAN_RED_MS){ // Dùng MAN_RED_MS cho pha B xanh
        phase = PHASE_B_YELLOW_3S; tPhaseStart = now;
      }
      break;

    case PHASE_B_YELLOW_3S:
      setLightsB(LED_OFF, LED_ON,  LED_OFF);
      setLightsA(LED_OFF, LED_OFF, LED_ON);
      if (now - tPhaseStart >= 5000){
        setLightsB(LED_OFF, LED_OFF,  LED_ON);
        phase = PHASE_B_RED_WAIT_1S; tPhaseStart = now;
      }
      break;

    case PHASE_B_RED_WAIT_1S:
      setLightsA(LED_OFF, LED_OFF,  LED_ON);
      setLightsB(LED_OFF, LED_OFF,  LED_ON);
      if (now - tPhaseStart >= 1000){
        phase = PHASE_A_GREEN; tPhaseStart = now;
      }
      break;
  }
}

// --- 2. Hàm Control Loop (Cập nhật logic Red Target) ---
void controlLoop(){
  uint32_t now = millis();
  
  // Detect edge (sườn xung) để chuyển trạng thái dựa trên biến currentRedTarget
  static bool lastRed = false;
  static bool inited = false;

  // Nếu lệnh đổi (Red thay đổi) hoặc mới khởi động Control Mode
  if (!inited || (currentRedTarget != lastRed)) {
      if (currentRedTarget) { 
           // Server yêu cầu: A Đỏ (tức là B sẽ Xanh)
           // Nếu A đang xanh -> chuyển sang quy trình vàng -> đỏ
           if(phase == PHASE_A_GREEN) {
               phase = PHASE_A_YELLOW_3S; tPhaseStart = now;
           }
      } else { 
           // Server yêu cầu: B Đỏ (tức là A sẽ Xanh)
           // Nếu B đang xanh -> chuyển sang quy trình vàng -> đỏ
           if(phase == PHASE_B_GREEN) {
               phase = PHASE_B_YELLOW_3S; tPhaseStart = now;
           }
      }
      lastRed = currentRedTarget;
      inited = true;
  }
  
  // Máy trạng thái xử lý chuyển pha
  switch (phase){
    case PHASE_A_YELLOW_3S:
      setLightsA(LED_OFF, LED_ON,  LED_OFF);
      setLightsB(LED_OFF, LED_OFF, LED_ON);
      if (now - tPhaseStart >= 5000){
        setLightsA(LED_OFF, LED_OFF,  LED_ON);
        phase = PHASE_A_RED_WAIT_1S; tPhaseStart = now;
      }
      break;

    case PHASE_A_RED_WAIT_1S:
      setLightsA(LED_OFF, LED_OFF,  LED_ON);
      setLightsB(LED_OFF, LED_OFF,  LED_ON);
      if (now - tPhaseStart >= 1000){
        setLightsB(LED_ON,  LED_OFF, LED_OFF);   // B xanh
        phase = PHASE_B_GREEN;             // Đứng yên ở B Xanh chờ lệnh
      }
      break;

    case PHASE_B_YELLOW_3S:
      setLightsB(LED_OFF, LED_ON,  LED_OFF);
      setLightsA(LED_OFF, LED_OFF,  LED_ON);
      if (now - tPhaseStart >= 5000){
        setLightsB(LED_OFF, LED_OFF,  LED_ON);
        phase = PHASE_B_RED_WAIT_1S; tPhaseStart = now;
      }
      break;

    case PHASE_B_RED_WAIT_1S:
      setLightsB(LED_OFF, LED_OFF,  LED_ON);
      setLightsA(LED_OFF, LED_OFF,  LED_ON);
      if (now - tPhaseStart >= 1000){
        setLightsA(LED_ON,  LED_OFF, LED_OFF);   // A xanh
        phase = PHASE_A_GREEN;             // Đứng yên ở A Xanh chờ lệnh
      }
      break;

    // Các trạng thái tĩnh, giữ nguyên đèn
    case PHASE_A_GREEN:
        setLightsA(LED_ON,  LED_OFF, LED_OFF);
        setLightsB(LED_OFF, LED_OFF, LED_ON);
        break;
        
    case PHASE_B_GREEN:
        setLightsB(LED_ON,  LED_OFF, LED_OFF);
        setLightsA(LED_OFF, LED_OFF,  LED_ON);
        break;
  }
}

// --- 3. Hàm Off Blink Loop (Code cũ của bạn) ---
void offBlinkLoop(){
  uint32_t now = millis();
  if (now - tBlinkStart >= 1000){ tBlinkStart = now; blinkState = !blinkState; }
  setLightsA(LED_OFF, blinkState,  LED_OFF);
  setLightsB(LED_OFF, blinkState,  LED_OFF);
}

// --- 4. Hàm Main RUN ---
void runFSM() {
    syncState(); // Bước 1: Đồng bộ dữ liệu
    
    if (currentMode == MODE_OFF) {
        offBlinkLoop();
    } else if (currentMode == MODE_MANUAL) {
        manualFSM();
    } else if (currentMode == MODE_CONTROL) {
        controlLoop();
    }
}