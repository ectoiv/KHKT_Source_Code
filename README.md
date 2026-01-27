# Clearway - INTELLIGENT TRAFFIC CONTROL SYSTEM.
Hệ thống Điều khiển Đèn Giao thông Thích nghi dựa trên Thị giác Máy tính (YOLOv11), Học máy (XGBoost) và Điều khiển Dự báo (MPC)

<div align="center">

![Python](https://img.shields.io/badge/Python-3.13.9-blue)
![YOLO](https://img.shields.io/badge/YOLO-v8-orange)
![Ultralytics](https://img.shields.io/badge/Ultralytics-YOLO-red)
![License](https://img.shields.io/badge/License-MIT-green)
![Status](https://img.shields.io/badge/Status-Active-success)

</div>

## 📖 Giới thiệu (Introduction)

Đây là mã nguồn chính thức cho đề tài Khoa học Kỹ thuật: "Ứng dụng Trí tuệ Nhân tạo trong Điều khiển Đèn Giao thông nhằm Giảm Thiểu Ùn tắc tại Đô thị thông qua YOLOv11m và Gradient Boosting Machines".
Dự án phát triển một hệ thống điều khiển đèn tín hiệu giao thông thông minh hoạt động theo cơ chế vòng lặp khép kín: Nhìn - Dự báo - Tối ưu - Chấp hành. Thay vì sử dụng chu kỳ đèn cố định (Fixed-time), hệ thống phân tích lưu lượng thực tế và dự báo tương lai để điều chỉnh pha đèn linh hoạt, giúp giảm thời gian chờ và giải tỏa ùn tắc.
## 🚀 Tính năng nổi bật (Key Features)

* 👁️ Thị giác máy tính (Computer Vision): Sử dụng mô hình YOLOv11m (được huấn luyện lại) để phát hiện, phân loại phương tiện và đo đếm mật độ giao thông theo thời gian thực từ camera.
+1


* 📈 Dự báo lưu lượng (Traffic Prediction): Tích hợp thuật toán XGBoost (Gradient Boosting) để dự báo lưu lượng và hàng chờ phương tiện trong tương lai gần dựa trên dữ liệu lịch sử.
+1


* 🧠 Điều khiển tối ưu (Optimal Control): Áp dụng thuật toán Model Predictive Control (MPC) để tính toán chiến lược pha đèn tối ưu nhất trong một khoảng thời gian (horizon), cân bằng giữa giảm hàng chờ và làm mượt tín hiệu.
+1


* ⚡ Phần cứng IoT (Edge Computing): Sử dụng vi điều khiển ESP32 với kiến trúc đa luồng (FreeRTOS), giao tiếp qua WebSocket để điều khiển hệ thống đèn vật lý.
+1


* 🛡️ Cơ chế an toàn (Failsafe): Tự động chuyển đổi giữa các chế độ: AI Control (Điều khiển thông minh), Manual (Cố định) và Off (Nháy vàng) khi mất kết nối mạng.
## 🛠️ Kiến trúc hệ thống (System Architecture)
Hệ thống hoạt động theo mô hình Server-Client:
1. Server (PC/Laptop):
* Nhận luồng video từ Camera.

* Chạy pipeline: YOLOv11 (Detect) -> Data Preprocessing -> XGBoost (Predict) -> MPC (Optimize).

* Gửi lệnh điều khiển (JSON) qua giao thức WebSocket.
2. Client (ESP32):
  * Kết nối WiFi.

* Nhận lệnh từ Server.

* Điều khiển trực tiếp các chân GPIO nối với đèn LED (Xanh/Vàng/Đỏ).
## ⚙️ Cài đặt & Hướng dẫn sử dụng (Installation)
1. Phần cứng (Hardware - ESP32):
* Yêu cầu: ESP32 DevKit V1, Đèn LED mô hình, Mạch driver (nếu dùng đèn lớn).
* Cài đăt:
    - Cài đặt PlatformIO hoặc Arduino IDE.
    - Mở thư mục hardware.
    - Cấu hình WiFi và địa chỉ Server trong file include/secrets.h (hoặc tương đương). 
    - Nạp code vào ESP32.
2. Phần mềm (Server - AI Processing):
* Yêu cầu: Python 3.8+, GPU NVIDIA (khuyên dùng để chạy YOLO mượt mà).
* Cài đặt:
  - pip install -r requirements.txt
3. Chạy hệ thống:
* Khởi động sever: python main.py
* Cấp nguồn cho esp32, thiết bị sẽ tự kết nối vào wifi và websocket
* Truy cập UI để theo dõi hệ thống.
## 📊 Kết quả thực nghiệm (Results)
* Nhận diện: YOLOv11m đạt độ chính xác cao trong việc phân loại xe máy, ô tô, xe tải, xe buýt.
* Dự báo: XGBoost cho chỉ số RMSE thấp (~0.2 PCU), dự báo sát với thực tế.

* Mô phỏng: Giảm thiểu đáng kể thời gian chờ trung bình tại nút giao so với chu kỳ cố định trong môi trường giả lập SUMO.
## 👨‍💻 Tác giả (Author)
* Thực hiện: Nguyễn Văn Trọng Tín - Trường THPT Chuyên Thoại Ngọc Hầu.
* Giáo viên hướng dẫn: Th.S Bùi Thị Kim Tuyến
