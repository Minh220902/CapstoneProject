#include "certs.h"
#include <WiFi.h>
#include <WiFiClientSecure.h>
#include <PubSubClient.h>
#include <WiFiUdp.h>
#include <Adafruit_SSD1306.h>
#include "esp32-hal.h"
#include <Arduino_BuiltIn.h>

#define LED_INDICATOR 33
#define OLED_RESET    -1
#define SCREEN_WIDTH 128
#define SCREEN_HEIGHT 32

// WiFi credentials for your local network
const char* ssid = "Dash";
const char* password = "Chloe98765";

const int udpPort = 8889;

WiFiUDP udp;
WiFiClientSecure net;
PubSubClient client(net);

Adafruit_SSD1306 display(SCREEN_WIDTH, SCREEN_HEIGHT, &Wire, OLED_RESET);

char packetBuffer[255];

// Add these definitions
#define AWS_IOT_PUBLISH_TOPIC   "warehouse/products"
#define AWS_IOT_SUBSCRIBE_TOPIC "warehouse/commands"
#define THINGNAME "EEK_CPS_2"

void setupWiFi() {
  WiFi.mode(WIFI_STA);
  WiFi.begin(ssid, password);
  
  while (WiFi.status() != WL_CONNECTED) {
    delay(500);
    Serial.print(".");
  }

  Serial.println("");
  Serial.println("WiFi connected");
  Serial.println("IP address: ");
  Serial.println(WiFi.localIP());
}

void connectAWS() {
  net.setCACert(AWS_CERT_CA);
  net.setCertificate(AWS_CERT_CRT);
  net.setPrivateKey(AWS_CERT_PRIVATE);

  client.setServer(AWS_IOT_ENDPOINT, 8883);

  Serial.println("Connecting to AWS IoT");
  while (!client.connect(THINGNAME)) {
    Serial.print(".");
    delay(1000);
  }

  if (!client.connected()) {
    Serial.println("AWS IoT Timeout!");
    return;
  }

  Serial.println("AWS IoT Connected!");
}

void setup() {
  Serial.begin(115200);
  
  pinMode(LED_INDICATOR, OUTPUT);
  digitalWrite(LED_INDICATOR, LOW);

  if(!display.begin(SSD1306_SWITCHCAPVCC, 0x3C)) {
    Serial.println(F("SSD1306 allocation failed"));
    for(;;);
  }
  display.clearDisplay();
  display.setTextSize(1);
  display.setTextColor(SSD1306_WHITE);
  display.setCursor(0,0);
  display.println("Initializing...");
  display.display();

  setupWiFi();
  connectAWS();
  
  udp.begin(udpPort);
  Serial.printf("UDP server listening on port %d\n", udpPort);

  display.clearDisplay();
  display.setCursor(0,0);
  display.println("Ready for data");
  display.println(WiFi.localIP());
  display.display();
}

void loop() {
  if (WiFi.status() != WL_CONNECTED) {
    Serial.println("WiFi connection lost. Reconnecting...");
    setupWiFi();
  }

  if (!client.connected()) {
    Serial.println("Reconnecting to AWS IoT");
    connectAWS();
  }
  client.loop();

  int packetSize = udp.parsePacket();
  if (packetSize) {
    int len = udp.read(packetBuffer, 255);
    if (len > 0) {
      packetBuffer[len] = 0; // Null-terminate the received data
    }

    Serial.println("Received UDP packet");
    Serial.println(packetBuffer);
    
    digitalWrite(LED_INDICATOR, HIGH);
    
    display.clearDisplay();
    display.setCursor(0,0);
    display.println("QR Data received");
    display.println(packetBuffer);
    display.display();

    if (client.publish(AWS_IOT_PUBLISH_TOPIC, packetBuffer)) {
      Serial.println("Published to AWS IoT");
    } else {
      Serial.println("Failed to publish to AWS IoT");
    }

    delay(500);
    digitalWrite(LED_INDICATOR, LOW);
  }

  delay(10); // Short delay to prevent watchdog timer issues
}
