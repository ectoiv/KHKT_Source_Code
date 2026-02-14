#include "LCD.h"
#include <Wire.h>
#include <LiquidCrystal_I2C.h>
#include "state.h"

//config
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
    Wire.end();
    for(int i=0; i<4; i++) {
        pinMode(lcd_configs[i].sda, INPUT);
        pinMode(lcd_configs[i].scl, INPUT);
    }
    
    // xả điện dung
    delayMicroseconds(50); 
    Wire.begin(lcd_configs[lcdIndex].sda, lcd_configs[lcdIndex].scl);
    Wire.setClock(100000);
}

void lcd_init_system() {
    for(int i = 0; i < 4; i++) {
        switchBus(i);
        lcd_driver.init(); 
        lcd_driver.backlight();
        lcd_driver.setCursor(0, 0);
        lcd_driver.print("LCD" + String(i + 1) + ": Ready");
        delay(100); 
    }
}

//HIỂN THỊ
void TaskLCDDisplay(void *pvParameters) {
    TickType_t lastWakeTime = xTaskGetTickCount();

    const TickType_t frequency = 1000 / portTICK_PERIOD_MS; 
    
    String localTime;
    float localPcu[4];
    float localPpcu[4];

    for (;;) {

        if (xSemaphoreTake(dataMutex, 100)) {
            localTime = sharedData.timeStr;
            for(int k=0; k<4; k++){
                localPcu[k] = sharedData.pcu[k];
                localPpcu[k] = sharedData.ppcu[k];
            }
            xSemaphoreGive(dataMutex);
        }
        
        //LCD 1
        switchBus(0);
        lcd_driver.setCursor(0, 0); 
        lcd_driver.print(localTime + " - Z1   "); 
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
