#include <WiFi.h>
#include "net_wifi.h"
#include "secrets.h"  // WIFI_SSID, WIFI_PASSWORD

void wifi_connect_blocking(unsigned long timeout_ms){
  if (WiFi.status()==WL_CONNECTED) return;
  WiFi.mode(WIFI_STA);
  WiFi.begin(WIFI_SSID, WIFI_PASSWORD);
  Serial.print("WiFi connecting");
  unsigned long t0 = millis();
  while (WiFi.status()!=WL_CONNECTED && millis()-t0 < timeout_ms){ Serial.print('.'); delay(400);} 
  if (WiFi.status()==WL_CONNECTED) Serial.printf("WiFi OK: %s", WiFi.localIP().toString().c_str());
  else Serial.println("WiFi failed, will retry in loop");
}

void wifi_ensure(){
  if (WiFi.status()!=WL_CONNECTED) wifi_connect_blocking(5000);
}