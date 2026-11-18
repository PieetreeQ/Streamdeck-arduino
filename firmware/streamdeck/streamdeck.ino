// DIY Stream Deck - Arduino Mega 2560 firmware
//
// Keys:    K1..K12 on pins D22..D33, the other leg of every switch goes to GND
//          (internal pull-ups, no diodes or resistors needed).
// RGB LED: plain 5 mm 4-pin RGB LED. R, G, B legs each through their own
//          220 ohm resistor to PWM pins 9, 10, 11.
//          Longest (common) leg -> GND (common cathode) or 5V (common anode).
//
// Serial protocol (115200 baud):
//   Arduino -> PC:  "KEY:n"        key n was pressed (1..12)
//   PC -> Arduino:  "C:r,g,b"      LED color of the active profile (0..255)
//                   "P:name"       profile name (ignored here, used by display variants)
//                   "A:label"      last action label (ignored here)
// Any line from the PC counts as a heartbeat. With no message for PC_TIMEOUT_MS
// the LED slowly pulses white ("host program not running").
//
// No extra libraries required.

const bool COMMON_ANODE = false;   // set to true if the longest leg goes to 5V

const int PIN_R = 9;
const int PIN_G = 10;
const int PIN_B = 11;
const uint8_t BRIGHTNESS = 120;    // 0-255; plain RGB LEDs are very bright

const int FIRST_PIN = 22;
const int NUM_KEYS = 12;
const unsigned long DEBOUNCE_MS = 20;
const unsigned long FLASH_MS = 120;
const unsigned long PC_TIMEOUT_MS = 12000;

bool lastState[NUM_KEYS];
unsigned long lastChange[NUM_KEYS];

uint8_t cr = 0, cg = 0, cb = 0;
unsigned long lastPcMsg = 0, flashAt = 0;
bool pcConnected = false, flashing = false;

char lineBuf[40];
uint8_t lineLen = 0;

void setRGB(uint8_t r, uint8_t g, uint8_t b) {
  r = (uint16_t)r * BRIGHTNESS / 255;
  g = (uint16_t)g * BRIGHTNESS / 255;
  b = (uint16_t)b * BRIGHTNESS / 255;
  if (COMMON_ANODE) { r = 255 - r; g = 255 - g; b = 255 - b; }
  analogWrite(PIN_R, r);
  analogWrite(PIN_G, g);
  analogWrite(PIN_B, b);
}

void handleLine(const char *line) {
  lastPcMsg = millis();
  pcConnected = true;
  if (strncmp(line, "C:", 2) == 0) {
    int r, g, b;
    if (sscanf(line + 2, "%d,%d,%d", &r, &g, &b) == 3) {
      cr = constrain(r, 0, 255); cg = constrain(g, 0, 255); cb = constrain(b, 0, 255);
    }
  }
}

void readSerial() {
  while (Serial.available()) {
    char c = Serial.read();
    if (c == '\n') {
      lineBuf[lineLen] = 0;
      handleLine(lineBuf);
      lineLen = 0;
    } else if (c != '\r' && lineLen < sizeof(lineBuf) - 1) {
      lineBuf[lineLen++] = c;
    }
  }
}

void updateLed(unsigned long now) {
  if (flashing && now - flashAt < FLASH_MS) {
    setRGB(255, 255, 255);                       // short white flash after a key press
  } else if (!pcConnected) {
    float t = (sin(now / 700.0) + 1.0) / 2.0;    // slow white pulse: host program not running
    uint8_t v = 10 + t * 120;
    setRGB(v, v, v);
  } else {
    flashing = false;
    setRGB(cr, cg, cb);                          // active profile color
  }
}

void setup() {
  Serial.begin(115200);
  for (int i = 0; i < NUM_KEYS; i++) {
    pinMode(FIRST_PIN + i, INPUT_PULLUP);
    lastState[i] = HIGH;
    lastChange[i] = 0;
  }
  pinMode(PIN_R, OUTPUT); pinMode(PIN_G, OUTPUT); pinMode(PIN_B, OUTPUT);
  // quick color check on power-up: red, green, blue
  setRGB(255, 0, 0); delay(300);
  setRGB(0, 255, 0); delay(300);
  setRGB(0, 0, 255); delay(300);
  setRGB(0, 0, 0);
}

void loop() {
  unsigned long now = millis();

  for (int i = 0; i < NUM_KEYS; i++) {
    bool state = digitalRead(FIRST_PIN + i);
    if (state != lastState[i] && now - lastChange[i] > DEBOUNCE_MS) {
      lastChange[i] = now;
      lastState[i] = state;
      if (state == LOW) {
        Serial.print("KEY:");
        Serial.println(i + 1);
        flashing = true;
        flashAt = now;
      }
    }
  }

  readSerial();
  if (pcConnected && now - lastPcMsg > PC_TIMEOUT_MS) pcConnected = false;

  static unsigned long lastLed = 0;
  if (now - lastLed >= 20) {
    lastLed = now;
    updateLed(now);
  }
}
