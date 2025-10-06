#include <WiFi.h>
#include <PubSubClient.h>

// ===== WiFi / MQTT =====
const char* ssid        = "VLY";
const char* password    = "14122550";
const char* mqtt_broker = "broker.emqx.io";
const int   mqtt_port   = 1883;

WiFiClient   espClient;
PubSubClient client(espClient);

// ===== UART mapping =====
// UART1 (Serial1) → FORCE
const int UART1_TX_PIN = 4;    // เลือกพินที่ว่างบนบอร์ด (ตัวอย่างใช้ GPIO4)
const int UART1_RX_PIN = 13;   // ตัวอย่างใช้ GPIO13
// UART2 (Serial2) → GYRO
const int UART2_TX_PIN = 17;   // ดีฟอลต์ของบอร์ด
const int UART2_RX_PIN = 16;   // ดีฟอลต์ของบอร์ด
const int UART_BAUD    = 115200;

// ===== MQTT topics =====
const char* gyro_topic  = "gyro/test";   // จะถูกส่งออกทาง UART2
const char* force_topic = "force/test";  // จะถูกส่งออกทาง UART1

// ===== WiFi connect =====
void setup_wifi() {
  Serial.println();
  Serial.print("Connecting to "); Serial.println(ssid);
  WiFi.mode(WIFI_STA);
  WiFi.begin(ssid, password);
  while (WiFi.status() != WL_CONNECTED) {
    delay(500); Serial.print('.');
  }
  Serial.println("\nWiFi connected, IP: " + WiFi.localIP().toString());
}

// ===== MQTT callback: route by topic =====
void mqtt_callback(char* topic, byte* payload, unsigned int length) {
  Serial.print("MQTT IN ["); Serial.print(topic); Serial.print("]: ");

  HardwareSerial* out = nullptr;
  if (strcmp(topic, gyro_topic) == 0) {
    out = &Serial2;                 // gyro → UART2
  } else if (strcmp(topic, force_topic) == 0) {
    out = &Serial1;                 // force → UART1
  }

  for (unsigned int i = 0; i < length; i++) {
    char c = (char)payload[i];
    Serial.print(c);                // debug log
    if (out) out->write(c);         // forward to selected UART
  }
  Serial.println();
  if (out) out->write('\n');        // newline terminator for STM32
}

// ===== MQTT connect (with retries) =====
void mqtt_reconnect() {
  client.setServer(mqtt_broker, mqtt_port);
  client.setCallback(mqtt_callback);
  while (!client.connected()) {
    String client_id = "esp32-client-" + WiFi.macAddress();
    Serial.print("Connecting MQTT as "); Serial.println(client_id);
    if (client.connect(client_id.c_str())) {
      Serial.println("MQTT connected");
      client.subscribe(gyro_topic);
      client.subscribe(force_topic);
    } else {
      Serial.print("failed, rc="); Serial.print(client.state());
      Serial.println(" retry in 2s");
      delay(2000);
    }
  }
}

void setup() {
  // UART0 → USB debug (อย่าใช้พิน GPIO1/3 ต่อกับ STM32)
  Serial.begin(UART_BAUD);

  // UART1 → FORCE (remap ขา หลีกเลี่ยง GPIO9/10 เพราะชนแฟลช)
  Serial1.begin(UART_BAUD, SERIAL_8N1, UART1_RX_PIN, UART1_TX_PIN);

  // UART2 → GYRO
  Serial2.begin(UART_BAUD, SERIAL_8N1, UART2_RX_PIN, UART2_TX_PIN);

  setup_wifi();
  mqtt_reconnect();

  Serial.println("ESP32 bridge ready (MQTT -> UART1/UART2)");
  Serial1.println("ESP32 UART1 ready (force)");
  Serial2.println("ESP32 UART2 ready (gyro)");
}

void loop() {
  if (!client.connected()) mqtt_reconnect();
  client.loop();
}