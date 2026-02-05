#ifndef CONFIG_H
#define CONFIG_H

// ============================================================================
// FloodSafe IoT Sensor Configuration
// ============================================================================
// IMPORTANT: Update these values before uploading to your ESP32!

// ------------ WiFi Configuration -------------------------------------------
// Replace with your home WiFi credentials
#define WIFI_SSID       "YOUR_WIFI_SSID"
#define WIFI_PASSWORD   "YOUR_WIFI_PASSWORD"

// ------------ API Configuration --------------------------------------------
// For local development (run: docker-compose up)
// Change to your computer's local IP if ESP32 can't resolve localhost
#define API_ENDPOINT    "http://192.168.1.100:8001/ingest"

// Sensor identification (will be replaced with UUID from backend registration)
// For now, use a placeholder - actual UUID assigned after sensor registration
#define SENSOR_ID       "00000000-0000-0000-0000-000000000001"

// API Key (generated from backend after sensor registration)
// Leave empty for MVP - auth will be added in Week 2
#define API_KEY         ""

// ------------ Hardware Configuration ---------------------------------------
// Grove Water Level Sensor I2C addresses
#define WATER_SENSOR_ADDR_LOW   0x77    // Lower 8 segments
#define WATER_SENSOR_ADDR_HIGH  0x78    // Upper 12 segments
#define SEGMENT_THRESHOLD       100     // Wet/dry threshold (0-255)

// VL53L0X Distance Sensor (default I2C address)
// Note: Default is 0x29, no need to change unless using multiple sensors

// Grove OLED Display (128x64, SSD1306)
// Note: Default I2C address is 0x3C

// ------------ Geometry Configuration ---------------------------------------
// Adjust these based on your bucket/container setup
#define SENSOR_HEIGHT_MM    175.0f    // Distance to bottom when empty (mm)
#define BUCKET_HEIGHT_MM    180.0f    // Usable water height (mm)

// ------------ Alert Thresholds ---------------------------------------------
// Adjust based on your testing observations
#define WARN_PERCENT_STRIPS     5.0f    // >= X% strips wet = WARNING (1/20 = 5%)
#define FLOOD_PERCENT_STRIPS    50.0f   // >= X% strips wet = FLOOD (10/20 = 50%)
#define WARN_PERCENT_DISTANCE   10.0f   // >= X% full by distance = WARNING
#define FLOOD_PERCENT_DISTANCE  50.0f   // >= X% full by distance = FLOOD

// ------------ Timing Configuration -----------------------------------------
#define READING_INTERVAL_MS     5000    // Take readings every 5 seconds
#define UPLOAD_INTERVAL_MS      30000   // Upload to cloud every 30 seconds
#define DISPLAY_UPDATE_MS       1000    // Update OLED every 1 second
#define WIFI_RETRY_DELAY_MS     5000    // Retry WiFi connection every 5 seconds
#define WIFI_CONNECT_TIMEOUT_MS 15000   // WiFi connection timeout

// ------------ Buffer Configuration -----------------------------------------
#define BUFFER_SIZE             100     // Store up to 100 readings when offline
                                        // At 30s intervals = ~50 minutes of data

// ------------ Debug Configuration ------------------------------------------
#define DEBUG_SERIAL            true    // Print debug info to Serial
#define SERIAL_BAUD_RATE        115200

#endif // CONFIG_H
