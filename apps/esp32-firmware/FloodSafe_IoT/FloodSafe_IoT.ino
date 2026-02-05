/**
 * FloodSafe IoT Sensor Firmware
 * ==============================
 *
 * Hardware:
 *   - Seeed XIAO ESP32S3 (or compatible ESP32 board)
 *   - Grove Water Level Sensor (10cm, I2C)
 *   - VL53L0X Time-of-Flight Distance Sensor
 *   - Grove OLED Display 128x64 (SSD1306, I2C)
 *
 * Features:
 *   - Dual sensor fusion (water strips + distance)
 *   - WiFi connectivity with auto-reconnect
 *   - OLED status display
 *   - Circular buffer for offline data storage
 *   - HTTP POST to FloodSafe backend
 *   - Rule-based WARNING/FLOOD detection
 *
 * Libraries Required (install via Arduino Library Manager):
 *   - Adafruit_VL53L0X
 *   - U8g2 (for OLED)
 *   - ArduinoJson
 *   - Wire (built-in)
 *   - WiFi (built-in for ESP32)
 *   - HTTPClient (built-in for ESP32)
 *
 * Author: FloodSafe Team
 * License: MIT
 */

#include <Wire.h>
#include <WiFi.h>
#include <HTTPClient.h>
#include <Adafruit_VL53L0X.h>
#include <U8g2lib.h>
#include <ArduinoJson.h>
#include "config.h"

// ============================================================================
// GLOBAL OBJECTS
// ============================================================================

// VL53L0X distance sensor
Adafruit_VL53L0X lox;

// OLED display (SSD1306 128x64, hardware I2C)
// Use U8G2_R0 for normal orientation, U8G2_R2 for 180-degree rotation
U8G2_SSD1306_128X64_NONAME_F_HW_I2C u8g2(U8G2_R0, /* reset=*/ U8X8_PIN_NONE);

// ============================================================================
// DATA STRUCTURES
// ============================================================================

// Single sensor reading
struct SensorReading {
  unsigned long timestamp;        // millis() when reading was taken
  int active_segments;            // 0-20 wet strips
  float distance_mm;              // VL53L0X raw distance
  float water_height_mm;          // Calculated water height
  float water_percent_strips;     // % from strip sensor
  float water_percent_distance;   // % from distance sensor
  bool is_warning;
  bool is_flood;
  bool uploaded;                  // Has this been sent to cloud?
};

// Circular buffer for offline storage
struct CircularBuffer {
  SensorReading readings[BUFFER_SIZE];
  int head;       // Next write position
  int count;      // Number of readings stored
};

// ============================================================================
// GLOBAL STATE
// ============================================================================

CircularBuffer buffer = { .head = 0, .count = 0 };

// Water sensor raw data
uint8_t low_data[8];
uint8_t high_data[12];

// Timing
unsigned long lastReadingTime = 0;
unsigned long lastUploadTime = 0;
unsigned long lastDisplayTime = 0;

// Current status for display
int currentSegments = 0;
float currentDistancePercent = 0.0f;
const char* currentStatus = "INIT";
bool wifiConnected = false;
int pendingUploads = 0;

// ============================================================================
// WIFI FUNCTIONS
// ============================================================================

/**
 * Connect to WiFi with timeout.
 * Returns true if connected, false if timeout.
 */
bool connectWiFi() {
  if (WiFi.status() == WL_CONNECTED) {
    return true;
  }

  #if DEBUG_SERIAL
    Serial.print("Connecting to WiFi: ");
    Serial.println(WIFI_SSID);
  #endif

  WiFi.begin(WIFI_SSID, WIFI_PASSWORD);

  unsigned long startTime = millis();
  while (WiFi.status() != WL_CONNECTED) {
    if (millis() - startTime > WIFI_CONNECT_TIMEOUT_MS) {
      #if DEBUG_SERIAL
        Serial.println("WiFi connection timeout!");
      #endif
      return false;
    }
    delay(500);
    #if DEBUG_SERIAL
      Serial.print(".");
    #endif
  }

  #if DEBUG_SERIAL
    Serial.println();
    Serial.print("Connected! IP: ");
    Serial.println(WiFi.localIP());
  #endif

  return true;
}

/**
 * Check WiFi status and reconnect if needed.
 */
void ensureWiFiConnected() {
  wifiConnected = (WiFi.status() == WL_CONNECTED);
  if (!wifiConnected) {
    connectWiFi();
    wifiConnected = (WiFi.status() == WL_CONNECTED);
  }
}

// ============================================================================
// SENSOR FUNCTIONS (from original sketch_dec7a.ino)
// ============================================================================

/**
 * Read lower 8 segments from Grove water sensor.
 */
void getLowSegments() {
  Wire.requestFrom((uint8_t)WATER_SENSOR_ADDR_LOW, (uint8_t)8);
  for (int i = 0; i < 8; i++) {
    if (Wire.available()) {
      low_data[i] = Wire.read();
    }
  }
}

/**
 * Read upper 12 segments from Grove water sensor.
 */
void getHighSegments() {
  Wire.requestFrom((uint8_t)WATER_SENSOR_ADDR_HIGH, (uint8_t)12);
  for (int i = 0; i < 12; i++) {
    if (Wire.available()) {
      high_data[i] = Wire.read();
    }
  }
}

/**
 * Count wet segments (0-20).
 */
int readActiveSegments() {
  getLowSegments();
  getHighSegments();

  int active = 0;

  for (int i = 0; i < 8; i++) {
    if (low_data[i] > SEGMENT_THRESHOLD) active++;
  }
  for (int i = 0; i < 12; i++) {
    if (high_data[i] > SEGMENT_THRESHOLD) active++;
  }

  return active;
}

/**
 * Read distance in mm from VL53L0X.
 * Returns -1 if out of range.
 */
int readDistanceMM() {
  VL53L0X_RangingMeasurementData_t measure;
  lox.rangingTest(&measure, false);

  if (measure.RangeStatus != 4) {  // 4 = Out of range
    return (int)measure.RangeMilliMeter;
  }
  return -1;
}

// ============================================================================
// BUFFER FUNCTIONS
// ============================================================================

/**
 * Add a reading to the circular buffer.
 */
void bufferAddReading(SensorReading reading) {
  buffer.readings[buffer.head] = reading;
  buffer.head = (buffer.head + 1) % BUFFER_SIZE;
  if (buffer.count < BUFFER_SIZE) {
    buffer.count++;
  }
}

/**
 * Get count of readings not yet uploaded.
 */
int countPendingUploads() {
  int pending = 0;
  for (int i = 0; i < buffer.count; i++) {
    int idx = (buffer.head - buffer.count + i + BUFFER_SIZE) % BUFFER_SIZE;
    if (!buffer.readings[idx].uploaded) {
      pending++;
    }
  }
  return pending;
}

/**
 * Get the oldest non-uploaded reading index, or -1 if none.
 */
int getOldestPendingIndex() {
  for (int i = 0; i < buffer.count; i++) {
    int idx = (buffer.head - buffer.count + i + BUFFER_SIZE) % BUFFER_SIZE;
    if (!buffer.readings[idx].uploaded) {
      return idx;
    }
  }
  return -1;
}

// ============================================================================
// HTTP UPLOAD FUNCTIONS
// ============================================================================

/**
 * Upload a single reading to the FloodSafe backend.
 * Returns true if successful.
 */
bool uploadReading(SensorReading* reading) {
  if (WiFi.status() != WL_CONNECTED) {
    return false;
  }

  HTTPClient http;
  http.begin(API_ENDPOINT);
  http.addHeader("Content-Type", "application/json");

  // Add API key header if configured
  #if defined(API_KEY) && strlen(API_KEY) > 0
    http.addHeader("X-API-Key", API_KEY);
  #endif

  // Build JSON payload
  // Using the water_level field as the primary metric (distance-based %)
  // Extended fields will be added in Week 2 migration
  StaticJsonDocument<256> doc;
  doc["sensor_id"] = SENSOR_ID;
  doc["water_level"] = reading->water_percent_distance;

  // ISO 8601 timestamp (using millis offset from device boot)
  // In production, you'd use NTP for real timestamps
  // For now, omit timestamp to let backend use server time
  // doc["timestamp"] = "2025-01-01T00:00:00Z";

  String jsonPayload;
  serializeJson(doc, jsonPayload);

  #if DEBUG_SERIAL
    Serial.print("Uploading: ");
    Serial.println(jsonPayload);
  #endif

  int httpCode = http.POST(jsonPayload);

  bool success = (httpCode == 200 || httpCode == 201);

  #if DEBUG_SERIAL
    if (success) {
      Serial.println("Upload SUCCESS");
    } else {
      Serial.print("Upload FAILED, code: ");
      Serial.println(httpCode);
    }
  #endif

  http.end();
  return success;
}

/**
 * Upload all pending readings from buffer.
 */
void uploadPendingReadings() {
  if (WiFi.status() != WL_CONNECTED) {
    return;
  }

  int idx;
  int uploaded = 0;
  int maxUploads = 5;  // Limit uploads per cycle to avoid blocking

  while ((idx = getOldestPendingIndex()) >= 0 && uploaded < maxUploads) {
    if (uploadReading(&buffer.readings[idx])) {
      buffer.readings[idx].uploaded = true;
      uploaded++;
    } else {
      break;  // Stop on first failure
    }
  }

  pendingUploads = countPendingUploads();
}

// ============================================================================
// DISPLAY FUNCTIONS
// ============================================================================

/**
 * Update the OLED display with current status.
 */
void updateDisplay() {
  u8g2.clearBuffer();

  // Line 1: Title
  u8g2.setFont(u8g2_font_6x10_tf);
  u8g2.drawStr(0, 10, "FloodSafe IoT v1.0");
  u8g2.drawHLine(0, 12, 128);

  // Line 2: Water level (strips)
  char line2[32];
  snprintf(line2, sizeof(line2), "Strips: %d/20 (%.0f%%)",
           currentSegments, (currentSegments / 20.0f) * 100.0f);
  u8g2.drawStr(0, 24, line2);

  // Line 3: Water level (distance)
  char line3[32];
  snprintf(line3, sizeof(line3), "Distance: %.1f%%", currentDistancePercent);
  u8g2.drawStr(0, 36, line3);

  // Line 4: Status (larger font, highlighted if alert)
  u8g2.setFont(u8g2_font_7x14B_tf);

  // Draw status with appropriate emphasis
  char statusLine[16];
  snprintf(statusLine, sizeof(statusLine), "%s", currentStatus);

  // Draw inverted box for FLOOD status
  if (strcmp(currentStatus, "FLOOD") == 0) {
    u8g2.drawBox(0, 40, 128, 14);
    u8g2.setDrawColor(0);  // Black text on white
  }
  u8g2.drawStr(4, 52, statusLine);
  u8g2.setDrawColor(1);  // Reset to white

  // Line 5: Connectivity status (smaller font)
  u8g2.setFont(u8g2_font_5x7_tf);
  char connLine[32];
  if (wifiConnected) {
    snprintf(connLine, sizeof(connLine), "WiFi: OK | Pending: %d", pendingUploads);
  } else {
    snprintf(connLine, sizeof(connLine), "WiFi: OFFLINE | Buf: %d", buffer.count);
  }
  u8g2.drawStr(0, 62, connLine);

  u8g2.sendBuffer();
}

// ============================================================================
// CORE READING LOGIC
// ============================================================================

/**
 * Take a sensor reading and determine status.
 */
SensorReading takeSensorReading() {
  SensorReading reading;
  reading.timestamp = millis();
  reading.uploaded = false;

  // Read strip sensor
  reading.active_segments = readActiveSegments();
  reading.water_percent_strips = (reading.active_segments / 20.0f) * 100.0f;

  // Read distance sensor
  int dist_mm = readDistanceMM();
  reading.distance_mm = (float)dist_mm;

  if (dist_mm > 0) {
    reading.water_height_mm = SENSOR_HEIGHT_MM - (float)dist_mm;
    if (reading.water_height_mm < 0) reading.water_height_mm = 0;
    if (reading.water_height_mm > BUCKET_HEIGHT_MM) reading.water_height_mm = BUCKET_HEIGHT_MM;
    reading.water_percent_distance = (reading.water_height_mm / BUCKET_HEIGHT_MM) * 100.0f;
  } else {
    reading.water_height_mm = 0;
    reading.water_percent_distance = 0;
  }

  // Determine warning/flood status (dual sensor fusion)
  reading.is_warning = false;
  reading.is_flood = false;

  // Strip sensor logic
  if (reading.water_percent_strips >= WARN_PERCENT_STRIPS) {
    reading.is_warning = true;
  }
  if (reading.water_percent_strips >= FLOOD_PERCENT_STRIPS) {
    reading.is_flood = true;
  }

  // Distance sensor logic
  if (reading.water_percent_distance >= WARN_PERCENT_DISTANCE) {
    reading.is_warning = true;
  }
  if (reading.water_percent_distance >= FLOOD_PERCENT_DISTANCE) {
    reading.is_flood = true;
  }

  return reading;
}

// ============================================================================
// SETUP
// ============================================================================

void setup() {
  // Initialize Serial
  #if DEBUG_SERIAL
    Serial.begin(SERIAL_BAUD_RATE);
    delay(500);
    Serial.println();
    Serial.println("========================================");
    Serial.println("  FloodSafe IoT Sensor v1.0");
    Serial.println("  Dual Sensor Flood Detection");
    Serial.println("========================================");
    Serial.println();
  #endif

  // Initialize I2C
  Wire.begin();
  delay(100);

  // Initialize OLED display
  #if DEBUG_SERIAL
    Serial.print("Initializing OLED display... ");
  #endif
  if (u8g2.begin()) {
    #if DEBUG_SERIAL
      Serial.println("OK");
    #endif
    u8g2.clearBuffer();
    u8g2.setFont(u8g2_font_6x10_tf);
    u8g2.drawStr(20, 30, "FloodSafe IoT");
    u8g2.drawStr(30, 45, "Starting...");
    u8g2.sendBuffer();
  } else {
    #if DEBUG_SERIAL
      Serial.println("FAILED (continuing without display)");
    #endif
  }
  delay(500);

  // Initialize VL53L0X distance sensor
  #if DEBUG_SERIAL
    Serial.print("Initializing VL53L0X... ");
  #endif
  if (!lox.begin()) {
    #if DEBUG_SERIAL
      Serial.println("FAILED!");
      Serial.println("ERROR: VL53L0X not detected. Check I2C wiring!");
    #endif
    // Display error on OLED
    u8g2.clearBuffer();
    u8g2.setFont(u8g2_font_6x10_tf);
    u8g2.drawStr(10, 30, "ERROR: VL53L0X");
    u8g2.drawStr(10, 45, "not detected!");
    u8g2.sendBuffer();
    while (1) { delay(1000); }  // Halt
  }
  #if DEBUG_SERIAL
    Serial.println("OK");
  #endif

  // Connect to WiFi
  #if DEBUG_SERIAL
    Serial.println("Connecting to WiFi...");
  #endif
  if (connectWiFi()) {
    wifiConnected = true;
  } else {
    #if DEBUG_SERIAL
      Serial.println("WiFi failed - running in offline mode");
    #endif
    wifiConnected = false;
  }

  // Ready
  #if DEBUG_SERIAL
    Serial.println();
    Serial.println("Sensor ready!");
    Serial.print("Reading interval: ");
    Serial.print(READING_INTERVAL_MS / 1000);
    Serial.println(" seconds");
    Serial.print("Upload interval: ");
    Serial.print(UPLOAD_INTERVAL_MS / 1000);
    Serial.println(" seconds");
    Serial.println();
  #endif

  currentStatus = "SAFE";
  updateDisplay();
}

// ============================================================================
// MAIN LOOP
// ============================================================================

void loop() {
  unsigned long now = millis();

  // ----- Take sensor reading at interval -----
  if (now - lastReadingTime >= READING_INTERVAL_MS) {
    lastReadingTime = now;

    SensorReading reading = takeSensorReading();

    // Update global state for display
    currentSegments = reading.active_segments;
    currentDistancePercent = reading.water_percent_distance;

    if (reading.is_flood) {
      currentStatus = "FLOOD";
    } else if (reading.is_warning) {
      currentStatus = "WARNING";
    } else {
      currentStatus = "SAFE";
    }

    // Add to buffer
    bufferAddReading(reading);
    pendingUploads = countPendingUploads();

    // Serial debug output
    #if DEBUG_SERIAL
      Serial.print("Strips: ");
      Serial.print(reading.active_segments);
      Serial.print("/20 (");
      Serial.print(reading.water_percent_strips, 1);
      Serial.print("%)  |  Distance: ");
      Serial.print(reading.water_percent_distance, 1);
      Serial.print("%  |  Status: ");
      Serial.print(currentStatus);
      Serial.print("  |  Buffer: ");
      Serial.print(buffer.count);
      Serial.print("  |  Pending: ");
      Serial.println(pendingUploads);
    #endif
  }

  // ----- Upload to cloud at interval -----
  if (now - lastUploadTime >= UPLOAD_INTERVAL_MS) {
    lastUploadTime = now;

    ensureWiFiConnected();

    if (wifiConnected) {
      uploadPendingReadings();
    }
  }

  // ----- Update display at interval -----
  if (now - lastDisplayTime >= DISPLAY_UPDATE_MS) {
    lastDisplayTime = now;
    updateDisplay();
  }

  // Small delay to prevent watchdog issues
  delay(10);
}
