#include <Arduino.h>
#include <WiFi.h>
#include <PubSubClient.h>
#include <ArduinoJson.h>
#include "secrets.h"   // Wi‑Fi & MQTT

#ifndef DEVICE_ID
#define DEVICE_ID "xjunction-esp32-01"
#endif

#ifndef SERVER_TIMEOUT_MS
#define SERVER_TIMEOUT_MS 30000UL
#endif

/*********** PINS (đổi theo dây của bạn) ***********/
// Hướng A
const int PIN_A_G = 17;
const int PIN_A_Y = 16;
const int PIN_A_R = 4;
// Hướng B
const int PIN_B_G = 27;
const int PIN_B_Y = 26;
const int PIN_B_R = 25;

/*********** DEFAULTS ***********/
uint32_t MAN_GREEN_MS = 30000UL;  // 30s xanh
uint32_t MAN_RED_MS   = 30000UL;  // 30s đỏ

/*********** STATES ***********/
enum Mode { MODE_MANUAL, MODE_REMOTE, MODE_SUSPEND };
Mode mode = MODE_MANUAL;

enum Phase { PHASE_A_GREEN, PHASE_A_TO_RED_BLINKY, PHASE_B_GREEN, PHASE_B_TO_RED_BLINKY };
Phase phase = PHASE_A_GREEN;

uint32_t tPhaseStart = 0;
uint32_t tBlinkStart = 0;
bool blinkState = false;
uint32_t suspendUntil = 0;
uint32_t tLastServer = 0;

WiFiClient wifi;
PubSubClient mqtt(wifi);

/*********** GPIO helpers ***********/
static inline void setLightsA(bool g, bool y, bool r){ digitalWrite(PIN_A_G,g); digitalWrite(PIN_A_Y,y); digitalWrite(PIN_A_R,r);} 
static inline void setLightsB(bool g, bool y, bool r){ digitalWrite(PIN_B_G,g); digitalWrite(PIN_B_Y,y); digitalWrite(PIN_B_R,r);} 
static inline void allOff(){ setLightsA(false,false,false); setLightsB(false,false,false);} 
static inline void safeAllRed(){ setLightsA(false,false,true); setLightsB(false,false,true);} 

void publishStatus(const char* note){
  StaticJsonDocument<256> d;
  d["device"] = DEVICE_ID;
  d["mode"] = (mode==MODE_MANUAL?"manual":(mode==MODE_REMOTE?"remote":"suspend"));
  d["phase"] = (phase==PHASE_A_GREEN?"A_GREEN":phase==PHASE_A_TO_RED_BLINKY?"A_Y_BLINK":phase==PHASE_B_GREEN?"B_GREEN":"B_Y_BLINK");
  d["note"] = note;
  char buf[256]; size_t n = serializeJson(d, buf);
  String topic = String("status/") + DEVICE_ID;
  mqtt.publish(topic.c_str(), buf, n);
}

/*********** Wi‑Fi + MQTT ***********/
void connectWiFi(){
  WiFi.mode(WIFI_STA);
  WiFi.begin(WIFI_SSID, WIFI_PASSWORD);
  Serial.print("WiFi connecting");
  while (WiFi.status()!=WL_CONNECTED){ Serial.print('.'); delay(400);} 
  Serial.printf("\nWiFi OK: %s\n", WiFi.localIP().toString().c_str());
}

void onMqttMessage(char* topic, byte* payload, unsigned int len){
  tLastServer = millis();
  StaticJsonDocument<384> doc;
  if (deserializeJson(doc, payload, len)) return;
  const char* op = doc["op"] | "";

  if (!strcmp(op,"hb")) return; // heartbeat

  if (!strcmp(op,"mode")){
    const char* v = doc["val"] | "manual";
    mode = (!strcmp(v,"remote")) ? MODE_REMOTE : MODE_MANUAL;
    publishStatus("mode change");
    return;
  }

  if (!strcmp(op,"set_times")){
    uint32_t g = doc["green"] | (MAN_GREEN_MS/1000);
    uint32_t r = doc["red"]   | (MAN_RED_MS/1000);
    MAN_GREEN_MS = max<uint32_t>(5, g) * 1000UL;
    MAN_RED_MS   = max<uint32_t>(5, r) * 1000UL;
    publishStatus("times updated");
    return;
  }

  if (!strcmp(op,"suspend")){
    uint32_t secs = doc["seconds"] | 0;
    if (secs>0){ mode = MODE_SUSPEND; suspendUntil = millis() + secs*1000UL; tBlinkStart = millis(); blinkState=false; publishStatus("suspend start"); }
    return;
  }

  if (!strcmp(op,"set_color") && mode==MODE_REMOTE){
    const char* dir = doc["dir"] | "A";
    const char* val = doc["val"] | "red";

    if (!strcmp(dir,"A")){
      if (!strcmp(val,"green")){
        setLightsB(false,false,true);
        setLightsA(true,false,false);
        publishStatus("remote A=green, B=red");
      } else {
        phase = PHASE_A_TO_RED_BLINKY; tBlinkStart = millis(); blinkState=false;
      }
    } else {
      if (!strcmp(val,"green")){
        setLightsA(false,false,true);
        setLightsB(true,false,false);
        publishStatus("remote B=green, A=red");
      } else {
        phase = PHASE_B_TO_RED_BLINKY; tBlinkStart = millis(); blinkState=false;
      }
    }
  }
}

void ensureMqtt(){
  if (mqtt.connected()) return;
  mqtt.setServer(MQTT_HOST, MQTT_PORT);
  mqtt.setCallback(onMqttMessage);

  String clientId = String("tl-") + DEVICE_ID + "-" + String((uint32_t)ESP.getEfuseMac(), HEX);
  String lwtTopic = String("status/") + DEVICE_ID + "/lwt";
  while(!mqtt.connected()){
    Serial.print("MQTT connecting...");
    if (mqtt.connect(clientId.c_str(), MQTT_USER, MQTT_PASS, lwtTopic.c_str(), 0, true, "offline")){
      Serial.println("OK");
      mqtt.publish(lwtTopic.c_str(), "online", true);
      String sub = String("cmd/") + DEVICE_ID; mqtt.subscribe(sub.c_str());
      publishStatus("boot"); tLastServer = millis();
    } else { Serial.printf("fail rc=%d\n", mqtt.state()); delay(1000);} 
  }
}

/*********** Blink helpers ***********/
bool doYellowBlinkToRedA(){
  uint32_t now = millis();
  if (now - tBlinkStart >= 2000){ setLightsA(false,false,true); return true; }
  if (now - tBlinkStart >= 500){ tBlinkStart += 500; blinkState=!blinkState; setLightsA(false, blinkState, false);} 
  return false;
}

bool doYellowBlinkToRedB(){
  uint32_t now = millis();
  if (now - tBlinkStart >= 2000){ setLightsB(false,false,true); return true; }
  if (now - tBlinkStart >= 500){ tBlinkStart += 500; blinkState=!blinkState; setLightsB(false, blinkState, false);} 
  return false;
}

void doSuspendBlink(){
  uint32_t now = millis();
  if (now - tBlinkStart >= 1000){ tBlinkStart += 1000; blinkState=!blinkState; }
  setLightsA(false, blinkState, false); setLightsB(false, blinkState, false);
}

/*********** Manual FSM ***********/
void manualFSM(){
  uint32_t now = millis();
  switch(phase){
    case PHASE_A_GREEN:
      setLightsA(true,false,false); setLightsB(false,false,true);
      if (now - tPhaseStart >= MAN_GREEN_MS){ phase = PHASE_A_TO_RED_BLINKY; tBlinkStart = now; blinkState=false; }
      break;
    case PHASE_A_TO_RED_BLINKY:
      if (doYellowBlinkToRedA()){ phase = PHASE_B_GREEN; tPhaseStart = now; }
      break;
    case PHASE_B_GREEN:
      setLightsB(true,false,false); setLightsA(false,false,true);
      if (now - tPhaseStart >= MAN_RED_MS){ phase = PHASE_B_TO_RED_BLINKY; tBlinkStart = now; blinkState=false; }
      break;
    case PHASE_B_TO_RED_BLINKY:
      if (doYellowBlinkToRedB()){ phase = PHASE_A_GREEN; tPhaseStart = now; }
      break;
  }
}

/*********** Setup & Loop ***********/
void setup(){
  Serial.begin(115200);
  pinMode(PIN_A_G,OUTPUT); pinMode(PIN_A_Y,OUTPUT); pinMode(PIN_A_R,OUTPUT);
  pinMode(PIN_B_G,OUTPUT); pinMode(PIN_B_Y,OUTPUT); pinMode(PIN_B_R,OUTPUT);
  allOff();

  connectWiFi();
  ensureMqtt();

  mode = MODE_MANUAL; phase = PHASE_A_GREEN; tPhaseStart = millis();
}

void loop(){
  if (WiFi.status()!=WL_CONNECTED) connectWiFi();
  ensureMqtt();
  mqtt.loop();
  uint32_t now = millis();

  if (mode==MODE_SUSPEND){
    if (now >= suspendUntil){ mode = MODE_REMOTE; publishStatus("suspend end"); safeAllRed(); }
    else { doSuspendBlink(); return; }
  }

  if (mode==MODE_MANUAL) manualFSM();
  else if (mode==MODE_REMOTE){
    if (phase==PHASE_A_TO_RED_BLINKY){ if (doYellowBlinkToRedA()) publishStatus("A->red done"); }
    else if (phase==PHASE_B_TO_RED_BLINKY){ if (doYellowBlinkToRedB()) publishStatus("B->red done"); }

    if (now - tLastServer > SERVER_TIMEOUT_MS){
      mode = MODE_MANUAL; publishStatus("server timeout -> manual");
      safeAllRed(); phase = PHASE_A_GREEN; tPhaseStart = millis();
    }
  }
}