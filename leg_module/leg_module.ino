#include <WiFi.h>
#include <PubSubClient.h>
#include <Wire.h>
#include <Adafruit_MPU6050.h>
#include <Adafruit_Sensor.h>
#include <math.h>

Adafruit_MPU6050 mpu;

// ================== WiFi / MQTT ==================
WiFiClient   espClient;
PubSubClient client(espClient);

const char* ssid        = "VLY";
const char* password    = "14122550";

const char* mqtt_broker = "broker.emqx.io";
const int   mqtt_port   = 1883;

const char* PUB_TOPIC   = "gyro/test";      // publish ค่าทุกครั้งที่มีผลลัพธ์
const char* CLIENT_PREF = "esp32-client-";  // prefix client id

// ================== Sampling / Detection ==================
// เก็บที่ ~100 Hz → หน้าต่าง 1s และประเมินทุก 500ms (overlap 50%)
const uint16_t SAMPLE_PERIOD_MS = 10;       // ~100Hz
const uint32_t WINDOW_MS        = 1000;     // หน้าต่าง 1 วินาที
const uint16_t WINDOW_SAMPLES   = WINDOW_MS / SAMPLE_PERIOD_MS; // = 100
const uint16_t HOP_MS           = 1000;      // อัปเดตผลทุก 500 ms

// —— Peak detection guard —— 
const uint16_t MIN_PEAK_GAP_MS  = 180;      // ระยะห่างขั้นต่ำระหว่างยอด (กันยอดปลอมเร็วๆ)
const uint16_t MIN_PEAK_GAP_SAMPLES = MIN_PEAK_GAP_MS / SAMPLE_PERIOD_MS;

// บัฟเฟอร์วน
float az_buf[WINDOW_SAMPLES];
float amag_buf[WINDOW_SAMPLES];
float gmag_buf[WINDOW_SAMPLES];             // |gyro| magnitude (rad/s)
uint16_t buf_idx = 0;
uint32_t last_sample_ms = 0;
uint32_t last_eval_ms   = 0;

// ================== เกณฑ์ (ปรับเทียบได้) ==================
// ยืน: ความแปรปรวนของ magnitude ต่ำ
const float VAR_STAND_MAX    = 0.20f;

// นับ peak ที่แกน Z โดยเทียบกับ meanZ + thresh (หน่วย m/s^2)
const float PEAK_THRESH_Z    = 0.80f;       // เข้มขึ้นเพื่อตัดยอดเล็กๆ จากการขยับเบาๆ
const float SCHMITT_REL_FALL = 0.5f;        // ลงต่ำกว่า 50% ของ thresh เพื่อ re-arm

// ความถี่ท่าต่างๆ (Hz)
const float FREQ_SQ_MIN_HZ   = 0.20f;
const float FREQ_SQ_MAX_HZ   = 1.25f;       // ขยายให้ Squat ครอบคลุมท่าเร็วขึ้นนิด
const float FREQ_JOG_MIN_HZ  = 1.60f;       // ยกเกณฑ์ Jogging ให้พ้นการขยับเร็วๆ
const float FREQ_GAP_MARGIN  = 0.05f;       // กันเด้งที่ขอบเขต

// เกณฑ์ "แรง" สำหรับ Jogging (ผ่านอย่างน้อย 2 ใน 4)
const float AZ_PP_JOG_MIN      = 4.0f;      // ช่วงสวิง Z (max-min) ขั้นต่ำ (m/s^2)
const float STDZ_JOG_MIN       = 1.10f;     // ส่วนเบี่ยงเบนมาตรฐาน Z ขั้นต่ำ (m/s^2)
const float MAG_RANGE_JOG_MIN  = 2.5f;      // ช่วงสวิง magnitude ขั้นต่ำ (m/s^2)
const float GYRO_STD_JOG_MIN   = 0.60f;     // ส่วนเบี่ยงเบนมาตรฐาน |gyro| ขั้นต่ำ (rad/s)
const uint8_t JOG_AMPL_CRITERIA_NEED = 2;   // ต้องผ่าน >= 2 ข้อ

// ฮิสเทอรีสผลลัพธ์
const uint8_t  VOTE_WIN      = 5;           // โหวตย้อนหลัง 5 ครั้ง
const uint32_t MIN_HOLD_MS   = 1000;        // บังคับค้างสถานะอย่างน้อย 1.0 s
const char* ACT_STAND        = "Stand";
const char* ACT_SQUAT        = "Squat";
const char* ACT_JOG          = "JoggingInPlace";
const char* ACT_MOVING       = "Moving";

// วงแหวนสำหรับโหวต
const char* vote_buf[VOTE_WIN];
uint8_t vote_idx = 0;
uint8_t vote_count = 0;

// สถานะล่าสุด + เวลาอัปเดตล่าสุด
const char* last_activity = ACT_STAND;
uint32_t last_activity_change_ms = 0;

// ================== Utilities ==================
void setup_wifi() {
  delay(10);
  Serial.println();
  Serial.print("Connecting to ");
  Serial.println(ssid);

  WiFi.mode(WIFI_STA);
  WiFi.begin(ssid, password);

  while (WiFi.status() != WL_CONNECTED) {
    delay(500);
    Serial.println("Connecting to WiFi...");
  }
  Serial.println("WiFi connected");
  Serial.print("IP address: ");
  Serial.println(WiFi.localIP());
}

void mqtt_callback(char *topic, byte *payload, unsigned int length) {
  Serial.print("Message arrived in topic: ");
  Serial.println(topic);
  Serial.print("Message: ");
  for (unsigned int i = 0; i < length; i++) Serial.print((char)payload[i]);
  Serial.println();
  Serial.println("-----------------------");
}

void mqtt_reconnect() {
  client.setServer(mqtt_broker, mqtt_port);
  client.setCallback(mqtt_callback);

  while (!client.connected()) {
    String client_id = String(CLIENT_PREF) + String(WiFi.macAddress());
    Serial.printf("The client %s connects to the public mqtt broker\n", client_id.c_str());
    if (client.connect(client_id.c_str())) {
      Serial.println("Public emqx mqtt broker connected");
    } else {
      Serial.print("failed with state ");
      Serial.println(client.state());
      delay(2000);
    }
  }
}

float compute_mean(const float* buf, uint16_t n) {
  double s = 0;
  for (uint16_t i = 0; i < n; i++) s += buf[i];
  return (float)(s / n);
}

float compute_variance(const float* buf, uint16_t n, float mean) {
  double s = 0;
  for (uint16_t i = 0; i < n; i++) {
    double d = buf[i] - mean;
    s += d * d;
  }
  return (float)(s / (n > 1 ? (n - 1) : 1));
}

void min_max(const float* buf, uint16_t n, float* out_min, float* out_max) {
  float mn = buf[0], mx = buf[0];
  for (uint16_t i=1; i<n; i++) {
    if (buf[i] < mn) mn = buf[i];
    if (buf[i] > mx) mx = buf[i];
  }
  *out_min = mn; *out_max = mx;
}

// simple 5-point moving average (edges: copy original)
void smooth5(const float* in, float* out, uint16_t n) {
  if (n < 5) { for (uint16_t i=0;i<n;i++) out[i]=in[i]; return; }
  out[0]=in[0]; out[1]=in[1];
  out[n-2]=in[n-2]; out[n-1]=in[n-1];
  for (uint16_t i=2; i<n-2; i++) {
    out[i] = (in[i-2]+in[i-1]+in[i]+in[i+1]+in[i+2]) / 5.0f;
  }
}

// Peak counter with Schmitt + min gap
uint16_t count_peaks_schmitt(const float* buf, uint16_t n, float meanZ,
                             float up_thresh, float fall_rel, uint16_t min_gap_samples) {
  const float up = meanZ + up_thresh;
  const float down = meanZ + up_thresh * fall_rel;

  uint16_t peaks = 0;
  bool armed = true;
  int32_t last_peak = -10000;

  for (uint16_t i = 0; i < n; i++) {
    float v = buf[i];
    if (armed && v >= up) {
      if ((int32_t)i - last_peak >= (int32_t)min_gap_samples) {
        peaks++;
        last_peak = i;
        armed = false;
      }
    } else if (v < down) {
      armed = true;
    }
  }
  return peaks;
}

const char* classify_once(float freq_hz, float var_mag,
                          float stdZ, float az_pp, float mag_pp, float gyro_std,
                          uint16_t peaks) {
  // ยืนก่อนถ้า variance ต่ำ
  if (var_mag <= VAR_STAND_MAX) return ACT_STAND;

  // ให้ Squat มาก่อน ลดการซ้อนกับ Jogging
  if (freq_hz >= FREQ_SQ_MIN_HZ && freq_hz <= (FREQ_SQ_MAX_HZ + FREQ_GAP_MARGIN)) {
    return ACT_SQUAT;
  }

  // จ๊อกกิ้ง: ต้องความถี่ถึง + จำนวนยอดพอสมควร + แรงพอ (อย่างน้อย 2 ข้อ)
  if (freq_hz >= FREQ_JOG_MIN_HZ) {
    uint8_t pass = 0;
    if (az_pp  >= AZ_PP_JOG_MIN)     pass++;
    if (stdZ   >= STDZ_JOG_MIN)      pass++;
    if (mag_pp >= MAG_RANGE_JOG_MIN) pass++;
    if (gyro_std >= GYRO_STD_JOG_MIN) pass++;
    bool amplitude_ok = (pass >= JOG_AMPL_CRITERIA_NEED);

    // ต้องมีอย่างน้อย 2 ยอดในหน้าต่าง 1s เพื่อกันยอดปลอม
    if (amplitude_ok && peaks >= 2) return ACT_JOG;

    // ความถี่ถึงแต่แรงไม่พอ/ยอดน้อย → ยังไม่เรียก Jogging
    return ACT_MOVING;
  }

  // ถ้าไม่เข้าเกณฑ์ใดชัดเจน
  if (var_mag < 0.6f) return ACT_STAND;
  return ACT_MOVING;
}

// โหวตย้อนหลัง
void vote_push(const char* act) {
  vote_buf[vote_idx] = act;
  vote_idx = (vote_idx + 1) % VOTE_WIN;
  if (vote_count < VOTE_WIN) vote_count++;
}

const char* vote_majority() {
  uint8_t cStand=0, cSquat=0, cJog=0, cMove=0;
  for (uint8_t i = 0; i < vote_count; i++) {
    const char* a = vote_buf[i];
    if      (a == ACT_STAND) cStand++;
    else if (a == ACT_SQUAT) cSquat++;
    else if (a == ACT_JOG)   cJog++;
    else                     cMove++;
  }
  // ให้ Squat ได้เปรียบเมื่อเสมอกับ Jogging
  if (cSquat >= cJog && cSquat >= cStand && cSquat >= cMove) return ACT_SQUAT;
  if (cJog   >  cSquat && cJog >= cStand && cJog >= cMove)   return ACT_JOG;
  if (cStand >= cMove) return ACT_STAND;
  return ACT_MOVING;
}

// ฮิสเทอรีสตามเวลา: บังคับค้าง MIN_HOLD_MS ก่อนเปลี่ยนสถานะ
const char* apply_hold(const char* proposed, uint32_t now_ms) {
  // ถ้าเหมือนเดิม ก็จบ
  if (proposed == last_activity) return last_activity;

  // ยังไม่ครบเวลาค้าง ห้ามเปลี่ยน
  if ((now_ms - last_activity_change_ms) < MIN_HOLD_MS) {
    return last_activity;
  }

  // ========== NEW RULE ==========
  // ห้ามเปลี่ยนจาก Squat -> Jogging โดยตรง
  // ต้องออกจาก Squat ไปสถานะอื่น (เช่น Moving/Stand) อย่างน้อยหนึ่งรอบก่อน
  if (last_activity == ACT_SQUAT && proposed == ACT_JOG) {
    return last_activity; // คงเป็น Squat ต่อไป
  }
  // ==============================

  // อนุมัติการเปลี่ยนสถานะ
  last_activity = proposed;
  last_activity_change_ms = now_ms;
  return last_activity;
}

// ================== Setup / Loop ==================
void setup() {
  Serial.begin(115200);

  setup_wifi();
  mqtt_reconnect();

  // I2C pins on ESP32 (SDA=21, SCL=22)
  Wire.begin(21, 22);
  delay(50);

  if (!mpu.begin()) {
    Serial.println("ไม่พบ MPU6050, ตรวจสอบการต่อสาย!");
    while (1) delay(10);
  }

  // ตั้งค่าเรนจ์และฟิลเตอร์ให้เหมาะกับกิจกรรมคน
  mpu.setAccelerometerRange(MPU6050_RANGE_8_G);
  mpu.setGyroRange(MPU6050_RANGE_500_DEG);
  mpu.setFilterBandwidth(MPU6050_BAND_21_HZ);

  Serial.println("เริ่มอ่านค่า MPU6050...");

  last_sample_ms = millis();
  last_eval_ms   = last_sample_ms;
  buf_idx = 0;

  // init vote buffer
  for (uint8_t i=0; i<VOTE_WIN; i++) vote_buf[i] = ACT_STAND;
  vote_count = 0;
  last_activity = ACT_STAND;
  last_activity_change_ms = millis();
}

void loop() {
  // รักษา MQTT ให้ต่อเนื่อง
  if (!client.connected()) {
    mqtt_reconnect();
  }
  client.loop();

  uint32_t now = millis();

  // Sampling ~100 Hz
  if (now - last_sample_ms >= SAMPLE_PERIOD_MS) {
    last_sample_ms = now;

    sensors_event_t a, g, temp;
    mpu.getEvent(&a, &g, &temp);

    float ax = a.acceleration.x;
    float ay = a.acceleration.y;
    float az = a.acceleration.z;
    float gx = g.gyro.x;
    float gy = g.gyro.y;
    float gz = g.gyro.z;

    float amag = sqrtf(ax*ax + ay*ay + az*az);
    float gmag = sqrtf(gx*gx + gy*gy + gz*gz);

    // เก็บเข้าบัฟเฟอร์วน
    az_buf[buf_idx]   = az;
    amag_buf[buf_idx] = amag;
    gmag_buf[buf_idx] = gmag;
    buf_idx++;
    if (buf_idx >= WINDOW_SAMPLES) buf_idx = 0;
  }

  // Evaluate ทุก HOP_MS
  if ((now - last_eval_ms) >= HOP_MS) {
    last_eval_ms = now;

    // เตรียมหน้าต่าง 1s ล่าสุด (wrap buffer)
    float az_tmp[WINDOW_SAMPLES];
    float am_tmp[WINDOW_SAMPLES];
    float gm_tmp[WINDOW_SAMPLES];
    for (uint16_t i = 0; i < WINDOW_SAMPLES; i++) {
      uint16_t k = (buf_idx + i) % WINDOW_SAMPLES;
      az_tmp[i] = az_buf[k];
      am_tmp[i] = amag_buf[k];
      gm_tmp[i] = gmag_buf[k];
    }

    // smooth Z ก่อนนับยอด
    float az_sm[WINDOW_SAMPLES];
    smooth5(az_tmp, az_sm, WINDOW_SAMPLES);

    float meanZ   = compute_mean(az_sm, WINDOW_SAMPLES);
    float meanMag = compute_mean(am_tmp, WINDOW_SAMPLES);
    float varMag  = compute_variance(am_tmp, WINDOW_SAMPLES, meanMag);
    float varZ    = compute_variance(az_sm, WINDOW_SAMPLES, meanZ);
    float stdZ    = sqrtf(varZ);

    float meanGm  = compute_mean(gm_tmp, WINDOW_SAMPLES);
    float varGm   = compute_variance(gm_tmp, WINDOW_SAMPLES, meanGm);
    float gstd    = sqrtf(varGm);

    // นับ peaks (ใช้ Schmitt + min gap)
    uint16_t peaks = count_peaks_schmitt(az_sm, WINDOW_SAMPLES, meanZ,
                                         PEAK_THRESH_Z, SCHMITT_REL_FALL, MIN_PEAK_GAP_SAMPLES);
    float freq_hz  = (float)peaks / (WINDOW_MS / 1000.0f); // peaks / 1s

    // คำนวณช่วงสวิง (peak-to-peak)
    float az_min, az_max, am_min, am_max;
    min_max(az_sm, WINDOW_SAMPLES, &az_min, &az_max);
    min_max(am_tmp, WINDOW_SAMPLES, &am_min, &am_max);
    float az_pp  = az_max - az_min;
    float mag_pp = am_max - am_min;

    // ตัดสินครั้งเดียว แล้วเอาไปโหวต
    const char* act_once = classify_once(freq_hz, varMag, stdZ, az_pp, mag_pp, gstd, peaks);
    vote_push(act_once);

    // สรุปผลโหวต + ฮิสเทอรีสเวลา
    const char* proposed = vote_majority();
    const char* activity = apply_hold(proposed, now);

    // แสดงผลใน Serial
//    Serial.print("peaks=");
//    Serial.print(peaks);
//    Serial.print(", freq=");
//    Serial.print(freq_hz, 2);
//    Serial.print(" Hz, varMag=");
//    Serial.print(varMag, 3);
//    Serial.print(", stdZ=");
//    Serial.print(stdZ, 3);
//    Serial.print(", az_pp=");
//    Serial.print(az_pp, 2);
//    Serial.print(", mag_pp=");
//    Serial.print(mag_pp, 2);
//    Serial.print(", gstd=");
//    Serial.print(gstd, 2);
//    Serial.print(" -> once=");
//    Serial.print(act_once);
//    Serial.print(" | voted=");
    Serial.println(activity);

    if (activity == "Squat") {
      client.publish(PUB_TOPIC, "W");
      } 
    else if (activity == "JoggingInPlace"){
      client.publish(PUB_TOPIC, "D");
      }
    else if (activity == "Stand") {
      client.publish(PUB_TOPIC, "S");
    }

//    // payload
//    int16_t last_idx = (int16_t)buf_idx - 1; if (last_idx < 0) last_idx += WINDOW_SAMPLES;
//    float az_last = az_buf[last_idx];
//
//    char msg[360];
//    snprintf(msg, sizeof(msg),
//             "{\"peaks\":%u,\"freq_hz\":%.2f,\"var_mag\":%.3f,"
//             "\"stdZ\":%.3f,\"az_pp\":%.2f,\"mag_pp\":%.2f,\"gstd\":%.2f,"
//             "\"meanZ\":%.2f,\"az_last\":%.2f,"
//             "\"activity\":\"%s\"}",
//             peaks, freq_hz, varMag,
//             stdZ, az_pp, mag_pp, gstd,
//             meanZ, az_last, activity);
//
//    client.publish(PUB_TOPIC, msg);
  }
}
