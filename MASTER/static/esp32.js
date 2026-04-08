
// nói qua về DOM (document) nó là cánh cổng để liên kết .html với .js, ở .js ta có thể truy cập được cả style của trang web thông qua DOM

// 1. Cấu hình thông số HiveMQ (Khớp với Python và ESP32)
const BROKER = "6419f78d6e5e4affbebe010720192414.s1.eu.hivemq.cloud";
const PORT = 8884;
const CLIENT_ID = "web_client_" + Math.random().toString(16).substr(2, 8);
const USER = "NCKH2026";
const PASS = "Nckh-2026";

const TOPIC_SET = "data";    // Gửi lệnh đi
const TOPIC_STATUS = "data"; // Nhận trạng thái về

// 2. Khởi tạo MQTT Client
const client = new Paho.MQTT.Client(BROKER, PORT, CLIENT_ID);

// 3. Các hàm xử lý sự kiện
client.onConnectionLost = onConnectionLost;
client.onMessageArrived = onMessageArrived;

const options = {
    useSSL: true,
    userName: USER,
    password: PASS,
    onSuccess: onConnect,
    onFailure: onFail
};

client.connect(options);

// 4. Hàm xử lý sự kiện
function onFail() {
    console.log("Không thể kết nối HiveMQ!");
    document.getElementById("connection-status").innerText = "Can't connect to Cloud";
    document.getElementById("connection-status").style.color = "red";
}
function onConnect() {
    console.log("Đã kết nối HiveMQ!");
    document.getElementById("connection-status").innerText = "Cloud Connected";
    document.getElementById("connection-status").style.color = "green";
    // Đăng ký nhận trạng thái từ ESP32
    client.subscribe(TOPIC_STATUS);
    console.log("Đã Subscribe thành công topic: data");
}

function onConnectionLost(responseObject) {
    if (responseObject.errorCode !== 0) {
        console.log("Mất kết nối MQTT: " + responseObject.errorMessage);
        document.getElementById("connection-status").innerText = "Mất kết nối Cloud";
        document.getElementById("connection-status").style.color = "orange";
    }
}


function toggleCamera(isOn) {
        const streamImg = document.getElementById('streamFrame'); //getElementById() :lấy id của tag
        const overlay = document.getElementById('camOverlay'); // overlay offcam
        if (isOn) {
            console.log("Camera: Starting Stream..."); // in thông tin lên console
            // Thay URL IP cua ESP32-CAM
            // streamImg.src = "http://192.168.1.100:81/stream"; 
            streamImg.src = "/video_feed";
            streamImg.style.display = "block"; /* mo hinh anh camera*/
            overlay.style.display = "none"; /*tat overlay offcam */
        } else {
            console.log("Camera: Stopping Stream..."); 
            streamImg.src = ""; //ngat ket noi cam
            streamImg.style.display = "none"; 
            overlay.style.display = "block";
        }
    }

function onMessageArrived(message) {
    console.log("Dữ liệu về: " + message.payloadString);
    try {
        let data = JSON.parse(message.payloadString);
        
        // Cập nhật cho Đèn 1
        if (data.hasOwnProperty('Living_light')) {
            const icon = document.getElementById('icon-light1');
            if (data.Living_light === 1) {
                icon.classList.add('light-on'); // Thêm hiệu ứng sáng
                console.log("Giao diện: Đèn 1 Bật");
            } else {
                icon.classList.remove('light-on'); // Tắt hiệu ứng sáng
                console.log("Giao diện: Đèn 1 Tắt");
            }
        }

        if (data.hasOwnProperty('Kitchen_light')) {
            const icon = document.getElementById('icon-light2');
            if (data.Kitchen_light === 1) {
                icon.classList.add('light-on'); // Thêm hiệu ứng sáng
                console.log("Giao diện: Đèn 2 Bật");
            } else {
                icon.classList.remove('light-on'); // Tắt hiệu ứng sáng
                console.log("Giao diện: Đèn 2 Tắt");
            }
        }

        // Cập nhật cho Cửa (Nếu AI của bạn có điều khiển cửa)
        if (data.hasOwnProperty('Door')) {
            const iconDoor = document.getElementById('icon-door');
            if (data.Door === 1) {
                iconDoor.classList.add('door-open');
                iconDoor.classList.replace('fa-door-closed', 'fa-door-open');
            } else {
                iconDoor.classList.remove('door-open');
                iconDoor.classList.replace('fa-door-open', 'fa-door-closed');
            }
        }
    } catch (e) {
        console.log("Lỗi xử lý dữ liệu giao diện: " + e);
    }
}

// hàm này dùng để gửi lệnh từ web đến ESP32 thông qua MQTT
 function animateDevice(device, action) {
    console.log(`Sending command: ${device} -> ${action}`);

    // 1. Tạo dữ liệu để gửi đi
    let command = {};
    if (device === 'Living_light') command = { Living_light: action === 'ON' ? 1 : 0 };
    if (device === 'Kitchen_light') command = { Kitchen_light: action === 'ON' ? 1 : 0 };
    if (device === 'Door') command = { Door: action === 'OPEN' ? 1 : 0 };

    // 2. Gửi dữ liệu lên MQTT Topic "data"
    const message = new Paho.MQTT.Message(JSON.stringify(command));
    message.destinationName = TOPIC_SET;
    client.send(message);

    // 3. Hiệu ứng giao diện (giữ nguyên logic cũ của bạn)
    if (device === 'Living_light'){
        const icon = document.getElementById('icon-Living_light');
        if (action === 'ON') icon.classList.add('light-on');
        else icon.classList.remove('light-on');
    }
    if (device === 'Kitchen_light'){
        const icon = document.getElementById('icon-Kitchen_light');
        if (action === 'ON') icon.classList.add('light-on');
        else icon.classList.remove('light-on');
    }
    if(device === 'Door'){
        const iconDoor = document.getElementById('icon-Door');
        if (action === 'OPEN') {
            iconDoor.classList.add('door-open');
            iconDoor.classList.replace('fa-door-closed', 'fa-door-open');
        } else {
            iconDoor.classList.remove('door-open');
            iconDoor.classList.replace('fa-door-open', 'fa-door-closed');
        }
        }
}