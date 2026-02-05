# FloodSafe IoT Sensor Firmware

Production-ready firmware for ESP32-based flood detection sensors.

## Hardware Requirements

| Component | Model | I2C Address |
|-----------|-------|-------------|
| Microcontroller | Seeed XIAO ESP32S3 (or compatible) | - |
| Water Level Sensor | Grove Water Level Sensor (10cm) | 0x77, 0x78 |
| Distance Sensor | VL53L0X Time-of-Flight | 0x29 |
| Display | Grove OLED 128x64 (SSD1306) | 0x3C |

### Wiring Diagram

```
ESP32S3 XIAO
    │
    ├── I2C (SDA/SCL) ─────┬─── Grove Water Sensor
    │                      │      ├── 0x77 (lower 8 segments)
    │                      │      └── 0x78 (upper 12 segments)
    │                      │
    │                      ├─── VL53L0X Distance (0x29)
    │                      │
    │                      └─── Grove OLED (0x3C)
    │
    └── WiFi ─────────────────── Home Router
```

## Software Requirements

### Arduino IDE Setup

1. **Install ESP32 Board Support**
   - Open Arduino IDE → File → Preferences
   - Add to "Additional Board Manager URLs":
     ```
     https://raw.githubusercontent.com/espressif/arduino-esp32/gh-pages/package_esp32_index.json
     ```
   - Tools → Board → Board Manager → Search "ESP32" → Install "esp32 by Espressif Systems"

2. **Install Required Libraries** (Tools → Manage Libraries)
   - `Adafruit_VL53L0X` - VL53L0X distance sensor
   - `U8g2` - Universal graphics library for OLED
   - `ArduinoJson` - JSON serialization

3. **Select Board**
   - Tools → Board → ESP32 Arduino → "XIAO_ESP32S3" (or your ESP32 variant)
   - Tools → Port → Select the COM port for your device

## Quick Start

1. **Clone the firmware directory**
   ```
   cd apps/esp32-firmware/FloodSafe_IoT
   ```

2. **Configure `config.h`**
   ```cpp
   // Update with your WiFi credentials
   #define WIFI_SSID       "YourWiFiName"
   #define WIFI_PASSWORD   "YourWiFiPassword"

   // Update with your computer's local IP (run 'ipconfig' on Windows)
   #define API_ENDPOINT    "http://192.168.1.100:8001/ingest"
   ```

3. **Upload to ESP32**
   - Connect ESP32 via USB
   - Click Upload button (→) in Arduino IDE
   - Wait for "Done uploading"

4. **Monitor Output**
   - Tools → Serial Monitor
   - Set baud rate to `115200`
   - You should see:
     ```
     ========================================
       FloodSafe IoT Sensor v1.0
       Dual Sensor Flood Detection
     ========================================

     Initializing OLED display... OK
     Initializing VL53L0X... OK
     Connecting to WiFi: YourWiFiName
     ....
     Connected! IP: 192.168.1.50
     Sensor ready!
     ```

## Features

### Dual Sensor Fusion

The firmware combines two independent water detection methods:

1. **Grove Water Level Sensor** - Capacitive strips (0-20 segments)
   - Detects water contact along 10cm vertical range
   - Binary output per segment (wet/dry)

2. **VL53L0X Distance Sensor** - Time-of-Flight measurement
   - Measures distance to water surface in mm
   - Calculates water height based on known sensor position

### Alert Logic

| Condition | Strips | Distance | Status |
|-----------|--------|----------|--------|
| Dry | 0/20 | <10% | SAFE |
| Low water | 1+/20 | ≥10% | WARNING |
| High water | 10+/20 | ≥50% | FLOOD |

Either sensor triggering the threshold activates the alert.

### Offline Buffering

When WiFi is unavailable:
- Readings stored in circular buffer (100 readings max)
- At 30-second intervals = ~50 minutes of offline data
- Automatic upload when connectivity restored
- FIFO: oldest readings uploaded first

### OLED Display

Real-time status display showing:
- Water level (strips and distance %)
- Alert status (SAFE/WARNING/FLOOD)
- WiFi connectivity status
- Pending upload count

## Configuration Reference

Edit `config.h` to customize:

| Setting | Default | Description |
|---------|---------|-------------|
| `READING_INTERVAL_MS` | 5000 | Take reading every 5 seconds |
| `UPLOAD_INTERVAL_MS` | 30000 | Upload every 30 seconds |
| `BUFFER_SIZE` | 100 | Max offline readings |
| `SENSOR_HEIGHT_MM` | 175.0 | Distance to bottom when empty |
| `BUCKET_HEIGHT_MM` | 180.0 | Usable water height |
| `WARN_PERCENT_DISTANCE` | 10.0 | Warning threshold |
| `FLOOD_PERCENT_DISTANCE` | 50.0 | Flood threshold |

## Calibration

### Geometry Calibration

1. With bucket **empty**, record distance reading from VL53L0X
2. Update `SENSOR_HEIGHT_MM` in `config.h`
3. Measure total usable bucket height → update `BUCKET_HEIGHT_MM`

### Threshold Calibration

1. Fill bucket to "warning" level, observe readings
2. Adjust `WARN_PERCENT_DISTANCE` and `WARN_PERCENT_STRIPS`
3. Fill to "flood" level, adjust `FLOOD_PERCENT_*` values

## Backend Setup

Before the sensor can upload data, ensure:

1. **Backend is running**
   ```bash
   cd FloodSafe
   docker-compose up
   ```

2. **Find your local IP** (Windows)
   ```bash
   ipconfig
   # Look for "IPv4 Address" under your WiFi adapter
   # e.g., 192.168.1.100
   ```

3. **Update config.h**
   ```cpp
   #define API_ENDPOINT "http://192.168.1.100:8001/ingest"
   ```

4. **Register sensor** (future - Week 2)
   ```bash
   # API key authentication will be added in Week 2
   # For now, use the placeholder sensor_id
   ```

## Troubleshooting

### "VL53L0X not detected"
- Check I2C wiring (SDA, SCL, VCC, GND)
- Ensure 3.3V power (NOT 5V for XIAO)
- Run I2C scanner sketch to verify address

### "WiFi connection timeout"
- Verify SSID and password in config.h
- Ensure 2.4GHz network (ESP32 doesn't support 5GHz)
- Move closer to router

### OLED displays nothing
- Check I2C address (default 0x3C, some are 0x3D)
- Verify wiring
- Try U8G2_R2 rotation in code

### Readings not appearing in backend
- Verify API_ENDPOINT IP is correct
- Ensure docker-compose is running
- Check Serial monitor for HTTP error codes

## Files

```
apps/esp32-firmware/
├── FloodSafe_IoT/
│   ├── FloodSafe_IoT.ino   # Main firmware (all features)
│   └── config.h             # User configuration
└── README.md               # This file
```

## Future Enhancements

- [ ] NTP time sync for accurate timestamps
- [ ] API key authentication (Week 2)
- [ ] OTA firmware updates
- [ ] Deep sleep for battery power
- [ ] Multiple sensor modes (pond, drain, river)
