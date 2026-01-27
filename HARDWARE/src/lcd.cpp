#include "LCD.h"
#include <Wire.h>
#include <LiquidCrystal_I2C.h>
#include "state.h"

// --- CẤU HÌNH CHÂN ---
struct LCD_Config {
    int sda;
    int scl;
    int addr;
};

LCD_Config lcd_configs[] = {
    {32, 33, 0x27}, // LCD 1
    {18, 19, 0x27}, // LCD 2 
    {14, 13, 0x27}, // LCD 3
    {21, 22, 0x27}  // LCD 4
};

LiquidCrystal_I2C lcd_driver(0x27, 16, 2);

// --- HÀM CHUYỂN BUS I2C (ĐÃ FIX LỖI) ---
void switchBus(int lcdIndex) {
    // 1. Ngắt I2C hiện tại
    Wire.end();
    
    // 2. [QUAN TRỌNG] Reset TẤT CẢ các chân I2C về trạng thái INPUT 
    // Để đảm bảo không có chân nào bị "dính" tín hiệu
    for(int i=0; i<4; i++) {
        pinMode(lcd_configs[i].sda, INPUT);
        pinMode(lcd_configs[i].scl, INPUT);
    }
    
    // 3. Delay nhỏ để xả điện dung trên dây (quan trọng khi dây dài)
    delayMicroseconds(50); 

    // 4. Khởi tạo lại với chân mới
    Wire.begin(lcd_configs[lcdIndex].sda, lcd_configs[lcdIndex].scl);
    Wire.setClock(100000); // 100kHz là chuẩn cho LCD 1602
}

// --- HÀM KHỞI TẠO ---
void lcd_init_system() {
    for(int i = 0; i < 4; i++) {
        switchBus(i);
        // Cần init lại mỗi khi chuyển bus lần đầu để PCF8574 đồng bộ
        lcd_driver.init(); 
        lcd_driver.backlight();
        lcd_driver.setCursor(0, 0);
        lcd_driver.print("LCD" + String(i + 1) + ": Ready");
        delay(100); 
    }
}

// --- TASK HIỂN THỊ ---
void TaskLCDDisplay(void *pvParameters) {
    TickType_t lastWakeTime = xTaskGetTickCount();
    
    // SỬA LỖI TIMING: Bạn comment là 1 giây nhưng code để 100ms
    // Nếu quét 4 màn hình quá nhanh (100ms), I2C sẽ không kịp đáp ứng -> lỗi hiển thị
    // Hãy để ít nhất 500ms hoặc 1000ms
    const TickType_t frequency = 1000 / portTICK_PERIOD_MS; 
    
    String localTime;
    float localPcu[4];
    float localPpcu[4];

    for (;;) {
        // 1. COPY DỮ LIỆU
        if (xSemaphoreTake(dataMutex, 100)) {
            localTime = sharedData.timeStr;
            for(int k=0; k<4; k++){
                localPcu[k] = sharedData.pcu[k];
                localPpcu[k] = sharedData.ppcu[k];
            }
            xSemaphoreGive(dataMutex);
        }
        
        // 2. CẬP NHẬT HIỂN THỊ
        // LCD 1
        switchBus(0);
        lcd_driver.setCursor(0, 0); 
        lcd_driver.print(localTime + " - Z1   "); // Thêm khoảng trắng để xóa ký tự thừa
        lcd_driver.setCursor(0, 1); 
        lcd_driver.print("P:" + String(localPcu[0], 1) + " PP:" + String(localPpcu[0], 1) + "   ");

        // LCD 2
        switchBus(1);
        lcd_driver.setCursor(0, 0); 
        lcd_driver.print(localTime + " - Z2   ");
        lcd_driver.setCursor(0, 1); 
        lcd_driver.print("P:" + String(localPcu[1], 1) + " PP:"+String(localPpcu[1], 1) + "   ");

        // LCD 3
        switchBus(2);
        lcd_driver.setCursor(0, 0); 
        lcd_driver.print(localTime + " - Z3   ");
        lcd_driver.setCursor(0, 1); 
        lcd_driver.print("P:" + String(localPcu[2], 1) + " PP:"+String(localPpcu[2], 1) + "   ");

        // LCD 4
        switchBus(3);
        lcd_driver.setCursor(0, 0); 
        lcd_driver.print(localTime + " - Z4   ");
        lcd_driver.setCursor(0, 1); 
        lcd_driver.print("P:" + String(localPcu[3], 1) + " PP:"+String(localPpcu[3], 1) + "   ");

        vTaskDelayUntil(&lastWakeTime, frequency);
    }
}