#include <Arduino.h>
#include "fsm.h"
#include "state.h"
#include "lights.h"
#include "status.h"

//Biến cục bộ để FSM sử dụng
static Mode currentMode = MODE_MANUAL;
static bool currentRedTarget = false;
static bool serverConnected = false;

//Hàm đồng bộ dữ liệu
static void syncState() {
    if (xSemaphoreTake(dataMutex, 0) == pdTRUE) { 
        serverConnected = sharedData.isConnected;
        Mode networkMode = sharedData.mode; 
        //Logic Failsafe
        if (!serverConnected) {
            if (networkMode == MODE_CONTROL) {
                currentMode = MODE_MANUAL;
            } else {
                currentMode = networkMode; 
            }
        } else {
            currentMode = networkMode;
            currentRedTarget = sharedData.redTarget;
        }
        
        xSemaphoreGive(dataMutex);
    }
}

//Hàm Manual FSM
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
      if (now - tPhaseStart >= MAN_RED_MS){ 
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

//Hàm Control Loop
void controlLoop(){
  uint32_t now = millis();
  static bool lastRed = false;
  static bool inited = false;
  if (!inited || (currentRedTarget != lastRed)) {
      if (currentRedTarget) { 
           if(phase == PHASE_A_GREEN) {
               phase = PHASE_A_YELLOW_3S; tPhaseStart = now;
           }
      } else { 
           if(phase == PHASE_B_GREEN) {
               phase = PHASE_B_YELLOW_3S; tPhaseStart = now;
           }
      }
      lastRed = currentRedTarget;
      inited = true;
  }

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
        setLightsB(LED_ON,  LED_OFF, LED_OFF); 
        phase = PHASE_B_GREEN;             
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
        setLightsA(LED_ON,  LED_OFF, LED_OFF);
        phase = PHASE_A_GREEN;          
      }
      break;

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

//Hàm Off Blink Loop
void offBlinkLoop(){
  uint32_t now = millis();
  if (now - tBlinkStart >= 1000){ tBlinkStart = now; blinkState = !blinkState; }
  setLightsA(LED_OFF, blinkState,  LED_OFF);
  setLightsB(LED_OFF, blinkState,  LED_OFF);
}

//Hàm Main
void runFSM() {
    syncState(); 
    
    if (currentMode == MODE_OFF) {
        offBlinkLoop();
    } else if (currentMode == MODE_MANUAL) {
        manualFSM();
    } else if (currentMode == MODE_CONTROL) {
        controlLoop();
    }
}
