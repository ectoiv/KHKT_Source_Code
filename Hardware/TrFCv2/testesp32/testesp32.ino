#include <WiFi.h>
#include <HTTPClient.h>
#include <ArduinoJson.h>
#include <HardwareSerial.h>
// WiFi credentials
const char* ssid = "Bacxiuduong";
const char* password = "12345678";
HardwareSerial mSerial(2);
// Flask server URL
const char* serverURL = "http://123.31.55.148:5000/sensor";

void setup() {
  Serial.begin(115200);
  mSerial.begin(9600, SERIAL_8N1, 16, 17); //Rx16, Tx17.
  WiFi.begin(ssid, password);

  Serial.print("Connecting to WiFi...");
  while (WiFi.status() != WL_CONNECTED) {
    delay(500);
    Serial.print(".");
  }
  Serial.println("\nWiFi connected");
}
void loop() {
  static String incomingLines[4];
  static int lineIndex = 0;

  if (mSerial.available()) {
    String line = mSerial.readStringUntil('\n');
    line.trim();
    if (line.length() > 0) {
      incomingLines[lineIndex] = line;
      lineIndex++;
      if (lineIndex == 4) {
        float doAmDat = incomingLines[0].toFloat();
        float nhietDo = incomingLines[1].toFloat();
        float doAm = incomingLines[2].toFloat();
        float anhSang = incomingLines[3].toFloat();

        Serial.println("== Dữ liệu từ Arduino ==");
        Serial.printf("Độ ẩm đất: %.2f\n", doAmDat);
        Serial.printf("Nhiệt độ: %.2f\n", nhietDo);
        Serial.printf("Độ ẩm không khí: %.2f\n", doAm);
        Serial.printf("Ánh sáng: %.2f\n", anhSang);
        Serial.println("==========================");

        // Chỉ gửi khi WiFi đã kết nối
        if (WiFi.status() == WL_CONNECTED) {
          HTTPClient http;
          http.begin(serverURL);
          http.addHeader("Content-Type", "application/json");

          StaticJsonDocument<200> sendDoc;
          sendDoc["DoAmDat"] = doAmDat;
          sendDoc["NhietDo"] = nhietDo;
          sendDoc["DoAm"] = doAm;
          sendDoc["AnhSang"] = anhSang;

          String requestBody;
          serializeJson(sendDoc, requestBody);

          int httpResponseCode = http.POST(requestBody);
          if (httpResponseCode > 0) {
            String response = http.getString();
            Serial.print("Server response: ");
            Serial.println(response);

            StaticJsonDocument<200> recvDoc;
            DeserializationError error = deserializeJson(recvDoc, response);
            if (!error) {
              int autoMode = recvDoc["auto"];
              float tmpDoAmDat = recvDoc["tmpDoAmDat"];
              float tmpNhietDo = recvDoc["tmpNhietDo"];
              float tmpDoAm = recvDoc["tmpDoAm"];
              float tmpAnhSang = recvDoc["tmpAnhSang"];
              mSerial.print(autoMode);
              mSerial.print('\n');
              mSerial.print(tmpDoAmDat);
              mSerial.print('\n');
              mSerial.print(tmpNhietDo);
              mSerial.print('\n');
              mSerial.print(tmpDoAm);
              mSerial.print('\n');
              mSerial.print(tmpAnhSang);
              mSerial.print('\n');
              //---------------------------------send test
              Serial.println("Nhận từ Flask:");
              Serial.printf("auto: %d\n", autoMode);
              Serial.printf("tmpDoAmDat: %.2f\n", tmpDoAmDat);
              Serial.printf("tmpNhietDo: %.2f\n", tmpNhietDo);
              Serial.printf("tmpDoAm: %.2f\n", tmpDoAm);
              Serial.printf("tmpAnhSang: %.2f\n", tmpAnhSang);
              //============================================
            } else {
              Serial.println("Lỗi parse JSON từ Flask");
            } b 
          } else {
            Serial.print("Error POST: ");
            Serial.println(httpResponseCode);
          }

          http.end();
        } else {
          Serial.println("WiFi disconnected");
        }

        lineIndex = 0;
      }
    }
  }
  //mSerial.print("TEST!");
  delay(100);
}