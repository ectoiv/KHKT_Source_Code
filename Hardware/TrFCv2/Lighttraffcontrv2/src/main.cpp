#include <Arduino.h>
#include "state.h"
#include "lights.h"
#include "net_wifi.h"
#include "socket_client.h" 
#include "fsm.h"
#include "lcd.h" // <--- THÊM FILE HEAD

// Task Handles
TaskHandle_t TaskNetwork; 
TaskHandle_t TaskLCD; // <--- Handle cho Task LCD

// Semaphore toàn cục (nếu cần dùng chung)
// SemaphoreHandle_t dataMutex; 

// --- TASK 0: NETWORK & WIFI (Chạy trên Core 0) ---
void TaskNetworkCode( void * pvParameters ){
  Serial.print("Network Task running on core ");
  Serial.println(xPortGetCoreID());

  wifi_connect_blocking(); 
  socket_setup();

  for(;;){
    wifi_ensure();
    socket_loop();
    vTaskDelay(10 / portTICK_PERIOD_MS); 
  }
}

void setup() {
  Serial.begin(115200);
  
  // 1. Khởi tạo phần cứng cơ bản
  lights_init();
  
  // 2. Khởi tạo LCDs (Làm trước khi tạo task để tránh tranh chấp I2C lúc đầu)
  lcd_init_system(); // <--- GỌI INIT LCD
  
  // 3. Tạo Mutex
  dataMutex = xSemaphoreCreateMutex();
  if(dataMutex == NULL) {
      Serial.println("Error: Could not create Mutex");
      while(1);
  }

  // 4. Khởi tạo Task Network trên Core 0
  xTaskCreatePinnedToCore(
                    TaskNetworkCode,   
                    "NetworkTask",     
                    10000,             
                    NULL,              
                    0,                 
                    &TaskNetwork,      
                    0);                

  // 5. Khởi tạo Task LCD (Core 1 hoặc 0 đều được, ở đây để Core 1)
  // Stack size 4096 là đủ cho việc in ấn I2C
  xTaskCreatePinnedToCore(
                    TaskLCDDisplay,    /* Hàm từ LCD.cpp */
                    "LCDTask",         
                    4096,              
                    NULL,              
                    1,                 /* Priority 1 (bằng mức loop mặc định) */
                    &TaskLCD,          
                    1);                /* Pin to Core 1 */

  // 6. Reset trạng thái ban đầu
  // sharedData.mode = MODE_MANUAL; // (Giả sử bạn có struct sharedData)
}

// --- TASK 1: LOGIC ĐÈN (Mặc định Loop chạy Core 1) ---
void loop() {
  // Loop này chạy logic đèn FSM
  // Task LCD sẽ xen kẽ chạy với loop này nhờ FreeRTOS quản lý
  runFSM(); 
  
  // Quan trọng: Thêm delay cực nhỏ để nhường CPU cho TaskLCD nếu FSM chạy quá nhanh
  vTaskDelay(1 / portTICK_PERIOD_MS); 
}