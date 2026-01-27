#pragma once

#ifndef DEVICE_ID
#define DEVICE_ID "xjunction-esp32-01"
#endif

// Cấu hình WebSocket Server
#define WS_HOST "14.237.132.109"  // Thay IP Server của bạn
#define WS_PORT 5000           // Port WebSocket
#define WS_PATH "/ws"    // Đường dẫn socket

// Mất tín hiệu quá lâu thì về MANUAL
#define SERVER_FAIL_TO_MANUAL_MS 10000UL