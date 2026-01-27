
#include "state.h"

SharedState sharedData = { 
    false,          // 1. isConnected (Mặc định chưa kết nối)
    MODE_MANUAL,    // 2. mode (Mặc định Manual)
    false,          // 3. redTarget (Mặc định không đỏ)
    "",             // 4. timeStr (Chuỗi rỗng)
    {0.0, 0.0, 0.0, 0.0},      // 5. pcu (Mảng 0)
    {0.0, 0.0, 0.0, 0.0}       // 6. ppcu (Mảng 0)
};
SemaphoreHandle_t dataMutex;

Phase phase = PHASE_A_GREEN;
uint32_t tPhaseStart = 0;
uint32_t tBlinkStart = 0;
bool blinkState = false;

// --- THÊM LẠI CÁC DÒNG NÀY ---
uint32_t MAN_GREEN_MS = 30000UL; // 30 giây
uint32_t MAN_RED_MS   = 30000UL;