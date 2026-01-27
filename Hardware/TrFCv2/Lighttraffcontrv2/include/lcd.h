#ifndef LCD_MODULE_H
#define LCD_MODULE_H

#include <Arduino.h>

// Hàm khởi tạo các màn hình (gọi trong setup)
void lcd_init_system();

// Task FreeRTOS quản lý hiển thị (đưa vào xTaskCreate)
void TaskLCDDisplay(void *pvParameters);

#endif