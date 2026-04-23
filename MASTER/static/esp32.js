
// nói qua về DOM (document) nó là cánh cổng để liên kết .html với .js, ở .js ta có thể truy cập được cả style của trang web thông qua DOM

// 1. Cấu hình thông số HiveMQ (Khớp với Python và ESP32)
const BROKER = "6419f78d6e5e4affbebe010720192414.s1.eu.hivemq.cloud";
const PORT = 8884;
const CLIENT_ID = "web_client_" + Math.random().toString(16).substr(2, 8);
const USER = "NCKH2026";
const PASS = "Nckh-2026";


const TOPIC_COMMAND = "home/commands"; // Gửi lệnh lẻ xuống ESP32
const TOPIC_STATE = "home/state";     // Nhận trạng thái gộp từ ESP32
const TOPIC_HEARTBEAT = "home/heartbeat"; // Theo dõi sức khỏe thiết bị

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
    
    // Đăng ký nhận trạng thái gộp và heartbeat
    client.subscribe(TOPIC_STATE);
    client.subscribe(TOPIC_HEARTBEAT);
    
    console.log("Đã Subscribe thành công các topic đồng bộ.");
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
    const payload = message.payloadString;
    const topic   = message.destinationName;

    if (topic === TOPIC_HEARTBEAT) {
        console.log("Heartbeat từ ESP32: " + payload + "s");
        const el = document.getElementById("connection-status");
        if (el) {
            el.innerText = "Device Online";
            el.style.color = "green";
        }
        return;
    }

    if (topic !== TOPIC_STATE) return;

    try {
        const data = JSON.parse(payload);
        console.log("[SYNC] State:", data);

        // ── Cập nhật trạng thái thiết bị ──────────────────────
        updateDeviceIcon('icon-Living_light', data.Living_light,
            'light-on', null, null);

        updateDeviceIcon('icon-Kitchen_light', data.Kitchen_light,
            'light-on', null, null);

        updateDeviceIcon('icon-Door', data.Door,
            'door-open', 'fa-door-closed', 'fa-door-open');

        // ── Cập nhật đồng hồ ESP32 ────────────────────────────
        if (data.esp_time) {
            const clockEl = document.getElementById('esp-clock');
            if (clockEl) clockEl.innerText = "Device Time: " + data.esp_time;
        }

        // ── Cập nhật đếm ngược từ ESP32 ───────────────────────
        // ESP32 là nguồn thật — mọi tab/máy đều nhận cùng giá trị
        const device = document.getElementById('timerDevice').value;
        syncCountdownFromESP32(device, data);

    } catch (e) {
        console.error("[ERROR] Parse state:", e);
    }
}

// ============================================================
// HÀM MỚI: syncCountdownFromESP32(device, data)
// Nhận giây còn lại từ ESP32 thay vì tự tính trong JS
// → Mọi tab/máy đều hiển thị đúng giá trị như nhau
// ============================================================
function syncCountdownFromESP32(device, data) {
    // Map tên thiết bị → prefix field trong JSON
    const prefixMap = {
        'Living_light':  'll',
        'Kitchen_light': 'kl',
        'Door':          'dr'
    };
    const p = prefixMap[device];
    if (!p) return;

    const isActive   = data[p + '_active'];
    const remStart   = data[p + '_rem_start']; // giây còn lại đến khi BẬT
    const remEnd     = data[p + '_rem_end'];   // giây còn lại đến khi TẮT

    const countdownEl  = document.getElementById('countdown');
    const statusEl     = document.getElementById('timerStatus');
    const cancelBtn    = document.getElementById('cancelTimerBtn');

    if (!isActive) {
        // Nếu ESP32 báo không còn lịch trình → reset UI
        if (!deviceSchedules[device]?.interval) {
            countdownEl.innerText  = "00:00:00";
            statusEl.innerText     = "Chưa có lịch trình nào được thiết lập";
            cancelBtn.classList.add('d-none');
        }
        return;
    }

    // Lịch đang chạy — hiển thị nút Hủy
    cancelBtn.classList.remove('d-none');

    if (remStart > 0) {
        // Chưa đến giờ bật
        countdownEl.innerText = formatSeconds(remStart);
        statusEl.innerText    = `Chờ đến giờ bật ${device.replace('_', ' ')}`;
    } else if (remEnd > 0) {
        // Đang trong khoảng hoạt động
        countdownEl.innerText = formatSeconds(remEnd);
        statusEl.innerText    = `${device.replace('_', ' ')} đang bật – còn lại đến khi tắt`;
    } else {
        countdownEl.innerText = "00:00:00";
        statusEl.innerText    = "Lịch trình vừa kết thúc";
    }
}

// Hàm bổ trợ: đổi giây → chuỗi "HH:MM:SS"
function formatSeconds(totalSec) {
    const h = Math.floor(totalSec / 3600);
    const m = Math.floor((totalSec % 3600) / 60);
    const s = totalSec % 60;
    return [h, m, s].map(v => String(v).padStart(2, '0')).join(':');
}

function updateDeviceIcon(iconId, value, activeClass, classOff, classOn) {
    const el = document.getElementById(iconId);
    if (!el) return;
    const isOn = (value == 1 || value === true);
    if (isOn) {
        el.classList.add(activeClass);
        if (classOff && classOn) {
            el.classList.replace(classOff, classOn);
        }
    } else {
        el.classList.remove(activeClass);
        if (classOff && classOn) {
            el.classList.replace(classOn, classOff);
        }
    }
}

// ============================================================
// HÀM CŨ: animateDevice() — GIỮ NGUYÊN LOGIC
// Gửi lệnh tức thời, UI cập nhật qua home/state (không tự update)
// ============================================================
function animateDevice(device, action) {
    const val = (action === 'ON' || action === 'OPEN') ? 1 : 0;
    const command = {};
    command[device] = val;

    console.log(`[CMD] ${device} → ${val}`);
    const message = new Paho.MQTT.Message(JSON.stringify(command));
    message.destinationName = TOPIC_COMMAND;
    client.send(message);
    // Không tự add/remove class — chờ ESP32 phản hồi qua home/state
}


let deviceSchedules = {
    'Living_light': { interval: null, startTime: null, endTime: null, isStarted: false },
    'Kitchen_light': { interval: null, startTime: null, endTime: null, isStarted: false },
    'Door': { interval: null, startTime: null, endTime: null, isStarted: false }
};


// Hàm này để đảm bảo khi bạn chuyển sang thiết bị khác, 
// nếu thiết bị đó chưa có lịch thì nút Hủy phải ẩn đi
function onDeviceChange() {
    const device = document.getElementById('timerDevice').value;
    const schedule = deviceSchedules[device];

    document.getElementById('startTime').value = schedule.startTime || "";
    document.getElementById('endTime').value = schedule.endTime || "";

    if (schedule.interval) {
        document.getElementById('cancelTimerBtn').classList.remove('d-none');
        // Cập nhật lại câu thông báo nếu cần
        if (schedule.isStarted) {
            document.getElementById('timerStatus').innerText = `Đang chạy lịch trình cho ${device}`;
        } else {
            document.getElementById('timerStatus').innerText = `Đã đặt lịch chờ cho ${device}`;
        }
    } else {
        document.getElementById('countdown').innerText = "00:00:00";
        document.getElementById('timerStatus').innerText = "Chưa có lịch trình nào được thiết lập";
        document.getElementById('cancelTimerBtn').classList.add('d-none');
    }
}

// ============================================================
// HÀM CŨ: setSchedule() — SỬA ĐỔI
// Gửi đúng format JSON có "device", "start_time", "end_time"
// ESP32 xử lý lịch trình — JS chỉ gửi lệnh và chờ phản hồi
// KHÔNG còn setInterval đếm ngược trong JS
// ============================================================
function setSchedule() {
    const device   = document.getElementById('timerDevice').value;
    const startStr = document.getElementById('startTime').value;
    const endStr   = document.getElementById('endTime').value;

    if (!startStr || !endStr) {
        alert("Vui lòng nhập đầy đủ thời gian!");
        return;
    }

    // Gửi lệnh đặt lịch — ESP32 sẽ xử lý và gửi lại rem_start/rem_end
    const command = {
        device:     device,
        start_time: startStr,  // format "HH:MM"
        end_time:   endStr
    };

    console.log(`[SCHEDULE] Gửi lịch trình cho ${device}:`, command);

    const message = new Paho.MQTT.Message(JSON.stringify(command));
    message.destinationName = TOPIC_COMMAND;
    client.send(message);

    // Cập nhật bộ nhớ local để nút Hủy biết thiết bị nào đang có lịch
    deviceSchedules[device].startTime  = startStr;
    deviceSchedules[device].endTime    = endStr;
    // KHÔNG dùng setInterval nữa — đếm ngược đến từ ESP32 qua home/state

    document.getElementById('timerStatus').innerText =
        `Đã gửi lịch trình cho ${device.replace('_', ' ')} – đang chờ xác nhận từ thiết bị...`;
    document.getElementById('cancelTimerBtn').classList.remove('d-none');
}

function stopDeviceSchedule(device) {
    if (deviceSchedules[device].interval) {
        clearInterval(deviceSchedules[device].interval);
        deviceSchedules[device].interval = null;
        deviceSchedules[device].startTime = null;
        deviceSchedules[device].endTime = null;
        
        // Nếu đang nhìn đúng thiết bị này thì reset màn hình
        if (document.getElementById('timerDevice').value === device) {
            cancelTimerUI();
        }
    }
}

// Hàm bổ trợ xóa giao diện
// Hàm reset giao diện hiển thị đếm ngược
function cancelTimerUI() {
    document.getElementById('countdown').innerText = "00:00:00";
    document.getElementById('timerStatus').innerText = "Chưa có lịch trình nào được thiết lập";
    document.getElementById('cancelTimerBtn').classList.add('d-none');
}

// ============================================================
// HÀM CŨ: cancelCurrentTimer() — SỬA ĐỔI
// Gửi lệnh cancel_schedule về ESP32 thay vì chỉ clearInterval
// ============================================================
function cancelCurrentTimer() {
    const device   = document.getElementById('timerDevice').value;
    const schedule = deviceSchedules[device];

    // Gửi lệnh hủy lịch về ESP32
    const command = {
        action: "cancel_schedule",
        device: device
    };
    const message = new Paho.MQTT.Message(JSON.stringify(command));
    message.destinationName = TOPIC_COMMAND;
    client.send(message);
    console.log(`[SCHEDULE] Hủy lịch trình: ${device}`);

    // Nếu có setInterval cũ còn sót lại thì xóa
    if (schedule.interval) {
        clearInterval(schedule.interval);
        schedule.interval = null;
    }

    // Reset dữ liệu local
    schedule.startTime = null;
    schedule.endTime   = null;

    document.getElementById('startTime').value  = "";
    document.getElementById('endTime').value    = "";

    // UI sẽ tự reset khi nhận phản hồi từ ESP32 qua home/state
    document.getElementById('timerStatus').innerText =
        "Đang hủy – chờ xác nhận từ thiết bị...";
}

// Hàm hiển thị thời gian đếm ngược lên màn hình
function displayTime(diffMs, statusText) {
    if (diffMs < 0) return;
    const h = Math.floor(diffMs / 3600000).toString().padStart(2, '0');
    const m = Math.floor((diffMs % 3600000) / 60000).toString().padStart(2, '0');
    const s = Math.floor((diffMs % 60000) / 1000).toString().padStart(2, '0');

    document.getElementById('countdown').innerText = `${h}:${m}:${s}`;
    document.getElementById('timerStatus').innerText = statusText;
}