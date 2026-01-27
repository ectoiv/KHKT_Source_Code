const WebSocket = require('ws');
const ip = require('ip');

// Tạo Server tại port 8080
const wss = new WebSocket.Server({ port: 8080 });

console.log('------------------------------------------------');
console.log(`✅ WebSocket Server đang chạy!`);
console.log(`👉 ĐỊA CHỈ SERVER (WS_HOST): "${ip.address()}"`); // Đây là IP máy bạn
console.log(`👉 PORT (WS_PORT): 8080`);
console.log('------------------------------------------------');

wss.on('connection', function connection(ws) {
  console.log('🔌 [ESP32] Đã kết nối thành công!');

  ws.on('message', function incoming(message) {
    console.log('📩 Nhận từ ESP32: %s', message);
  });

  ws.on('close', () => {
    console.log('❌ [ESP32] Đã ngắt kết nối');
  });

  // Gửi lệnh chào mừng
  ws.send(JSON.stringify({ message: "Hello ESP32 from Node.js Server" }));
});

// Cho phép bạn gõ lệnh từ bàn phím để gửi xuống ESP32
const readline = require('readline');
const rl = readline.createInterface({
  input: process.stdin,
  output: process.stdout
});

console.log('💡 Gõ lệnh dưới đây để gửi (vd: 1=A đỏ, 2=B đỏ, 3=Manual):');

rl.on('line', (input) => {
  let command = {};
  
  // Tạo phím tắt cho nhanh
  if (input === '1') {
      console.log(">> Gửi lệnh: A ĐỎ (Control Mode)");
      command = { Control: true, Red: true }; // Red=true là A đỏ
  } 
  else if (input === '2') {
      console.log(">> Gửi lệnh: B ĐỎ (Control Mode)");
      command = { Control: true, Red: false }; // Red=false là B đỏ
  }
  else if (input === '3') {
      console.log(">> Gửi lệnh: Về MANUAL");
      command = { Manual: true };
  }
  else if (input === '0') {
      console.log(">> Gửi lệnh: OFF (Nháy vàng)");
      command = { OFF: true };
  }
  else {
      // Gửi JSON tùy ý nếu gõ tay
      try {
        command = JSON.parse(input);
      } catch (e) {
        console.log("Lỗi: Phải nhập đúng định dạng JSON hoặc dùng phím tắt 1,2,3");
        return;
      }
  }

  // Gửi cho tất cả client đang kết nối (ESP32)
  wss.clients.forEach(function each(client) {
    if (client.readyState === WebSocket.OPEN) {
      client.send(JSON.stringify(command));
    }
  });
});