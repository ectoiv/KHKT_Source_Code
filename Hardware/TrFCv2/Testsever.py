from flask import Flask, request, jsonify
#from flask_cors import CORS
app = Flask(__name__)
# CORS(app)
# Dữ liệu từ ESP32 gửi lên
esp_data = {
    "DoAmDat": None,
    "NhietDo": None,
    "DoAm": None,
    "AnhSang": None
}

# Dữ liệu cấu hình gửi xuống ESP32 từ app
control_data = {
    "auto": 0,  # 0: thủ công, 1: tự động
    "tmpDoAmDat": None,
    "tmpNhietDo": None,
    "tmpDoAm": None,
    "tmpAnhSang": None
}
#route esp32
@app.route("/sensor", methods=["POST"])
def handle_sensor():
    global esp_data
    data = request.get_json()

    # Cập nhật dữ liệu từ ESP32
    esp_data["DoAmDat"] = data.get("DoAmDat")
    esp_data["NhietDo"] = data.get("NhietDo")
    esp_data["DoAm"] = data.get("DoAm")
    esp_data["AnhSang"] = data.get("AnhSang")

    print("[ESP32 -> Flask] Sensor:", esp_data)

    # Trả lại lệnh điều khiển ngay sau khi nhận xong sensor
    response = {
        "auto": control_data["auto"],
        "tmpDoAmDat": control_data["tmpDoAmDat"],
        "tmpNhietDo": control_data["tmpNhietDo"],
        "tmpDoAm": control_data["tmpDoAm"],
        "tmpAnhSang": control_data["tmpAnhSang"]
    }

    print("[Flask -> ESP32] Return Command:", response)
    return jsonify(response)
#route app
@app.route("/app/data", methods=["GET"])
def send_to_app():
    # Ứng dụng yêu cầu đọc dữ liệu sensor
    response = {
        "DoAmDat": esp_data["DoAmDat"],
        "NhietDo": esp_data["NhietDo"],
        "DoAm": esp_data["DoAm"],
        "AnhSang": esp_data["AnhSang"]
    }

    print("[Flask -> App] Sensor:", response)
    return jsonify(response)

@app.route("/app/control", methods=["POST"])    
def receive_from_app():
    global control_data
    data = request.get_json()

    # Cập nhật dữ liệu điều khiển
    control_data["auto"] = data.get("auto", 0)
    control_data["tmpDoAmDat"] = data.get("soil")
    control_data["tmpNhietDo"] = data.get("temperature")
    control_data["tmpDoAm"] = data.get("humidity")
    control_data["tmpAnhSang"] = data.get("light")

    print("[App -> Flask] Control:", control_data)
    return "OK", 200

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000)