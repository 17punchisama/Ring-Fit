#include <WiFi.h>
#include <PubSubClient.h> //include library
#include <Wire.h>
#include <Adafruit_MPU6050.h>
#include <Adafruit_Sensor.h>
#include <Adafruit_Sensor.h>

Adafruit_MPU6050 mpu;

//=================================================================================================
WiFiClient   espClient;                     //คำสั่งจาก library
PubSubClient client(espClient);             //สร้างออปเจ็ค สำหรับเชื่อมต่อ mqtt
//=================================================================================================
const char* ssid = "VLY";                   //wifi name
const char* password = "14122550";           //wifi password
//=================================================================================================
const char* mqtt_broker = "broker.emqx.io";       //IP mqtt server
//const char* mqtt_username = "mqtt username";      //mqtt username
//const char* mqtt_password = "mqtt password";      //mqtt password
const int   mqtt_port = 1883;         //port mqtt server
//=================================================================================================

void setup_wifi() {   //ฟังก์ชั่นเชื่อมต่อwifi
  delay(10);
  Serial.println();
  Serial.print("Connecting to ");
  Serial.println(ssid);
  WiFi.mode(WIFI_STA);                      //เลือกโหมดรับ wifi
  WiFi.begin(ssid, password);               //เชื่อมต่อ wifi
  while (WiFi.status() != WL_CONNECTED)     //รอจนกว่าจะเชื่อมต่อwifiสำเร็จ
  {
    delay(500);
    Serial.println("Connecting to WiFi...");
  }
  Serial.println("WiFi connected");
  Serial.println("IP address: ");
  Serial.println(WiFi.localIP());
}

void callback(char *topic, byte *payload, unsigned int length) {  //ฟังก์ชั่นsubscribe
  Serial.print("Message arrived in topic: ");
  Serial.println(topic);
  Serial.print("Message:");
  for (int i = 0; i < length; i++)          //รับค่าโดยการปริ้นอักษรที่ละตัวออกมา เป็น char
    Serial.print((char) payload[i]);
  Serial.println();
  Serial.println("-----------------------");
}

void reconnect() {  //ฟังก์ชั่นเชื่อมต่อmqtt
  client.setServer(mqtt_broker, mqtt_port);   //เชื่อมต่อmqtt
  client.setCallback(callback);               //เลือกฟังก์ชั่นsubscribe
  while (!client.connected())                 //รอจนกว่าจะเชื่อมต่อmqttสำเร็จ
  {
    String client_id = "esp32-client-";
    client_id += String(WiFi.macAddress());
    Serial.printf("The client %s connects to the public mqtt broker\n", client_id.c_str());
    if (client.connect(client_id.c_str())) {
      Serial.println("Public emqx mqtt broker connected");
    }
    else {
      Serial.print("failed with state ");
      Serial.print(client.state());
      delay(2000);
    }
  }
}

void setup()
{
  Serial.begin(115200);
  setup_wifi(); //เชื่อมต่อwifi
  reconnect();  //เชื่อมต่อmqtt
  //client.subscribe("topic");  //กำหนด topic ที่จะ subscribe
  // client.publish("topic", "xxxxxxx"); //กำหนด topic ที่จะ publish และ valu

  while (!Serial)
    delay(10); // รอ serial

  // เริ่มการทำงานของ MPU6050
  if (!mpu.begin()) {
    Serial.println("ไม่พบ MPU6050, ตรวจสอบการต่อสาย!");
    while (1) {
      delay(10);
    }
  }

  // ตั้งค่าเซนเซอร์
  mpu.setAccelerometerRange(MPU6050_RANGE_8_G);
  mpu.setGyroRange(MPU6050_RANGE_500_DEG);
  mpu.setFilterBandwidth(MPU6050_BAND_21_HZ);

  Serial.println("เริ่มอ่านค่า MPU6050...");
}

void loop()
{
  client.loop();//วนลูปรอsubscribe valu จาก mqtt
  sensors_event_t a, g, temp;
  mpu.getEvent(&a, &g, &temp);
  
  // อ่านค่าจาก Accelerometer
  // Serial.print("Accel X: "); Serial.print(a.acceleration.x);
  // Serial.print(" m/s^2, Y: "); Serial.print(a.acceleration.y);
  // Serial.print(" m/s^2, Z: "); Serial.print(a.acceleration.z);
  // Serial.println(" m/s^2");

  char msg[100];
  snprintf(msg, sizeof(msg), "{\"x\":%.2f,\"y\":%.2f,\"z\":%.2f}", 
           a.acceleration.x, a.acceleration.y, a.acceleration
           .z);

  client.publish("gyro/test", msg);   // publish ไปที่ topic mpu6050/accel

  delay(100);
}
