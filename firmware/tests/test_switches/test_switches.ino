// 12-SWITCH TEST - checks that every key is wired correctly.
// Wiring: K1..K12 -> pins D22..D33, the other leg of every switch -> GND.
// Open the Serial Monitor (115200) and press the keys one by one.
// The "L" LED on the Arduino board is lit while any key is held down.
//
// RGB LED: every key lights it in a different color (the color stays until the next key).
// LED wiring: R -> 220 ohm -> pin 9, G -> 220 ohm -> pin 10, B -> 220 ohm -> pin 11,
//             longest leg -> GND (or 5V for a common-anode LED).

const bool COMMON_ANODE = false;   // true if the longest leg of the LED is on 5V
const int PIN_R = 9;
const int PIN_G = 10;
const int PIN_B = 11;

// color for every key: {R, G, B}
const uint8_t KEY_COLORS[12][3] = {
  {255,   0,   0},   // K1  red
  {255,  80,   0},   // K2  orange
  {255, 200,   0},   // K3  yellow
  {120, 255,   0},   // K4  lime
  {  0, 255,   0},   // K5  green
  {  0, 255, 120},   // K6  mint
  {  0, 255, 255},   // K7  cyan
  {  0, 120, 255},   // K8  sky blue
  {  0,   0, 255},   // K9  blue
  {140,   0, 255},   // K10 purple
  {255,   0, 255},   // K11 magenta
  {255, 255, 255},   // K12 white
};
const char *COLOR_NAMES[12] = {
  "red", "orange", "yellow", "lime", "green", "mint",
  "cyan", "sky blue", "blue", "purple", "magenta", "white"
};

void setRGB(int r, int g, int b) {
  if (COMMON_ANODE) { r = 255 - r; g = 255 - g; b = 255 - b; }
  analogWrite(PIN_R, r);
  analogWrite(PIN_G, g);
  analogWrite(PIN_B, b);
}

const int FIRST_PIN = 22;
const int NUM_KEYS = 12;
const unsigned long DEBOUNCE_MS = 20;

bool lastState[NUM_KEYS];
unsigned long lastChange[NUM_KEYS];
bool tested[NUM_KEYS];
int pressCount[NUM_KEYS];

void printMissing() {
  int done = 0;
  for (int i = 0; i < NUM_KEYS; i++) if (tested[i]) done++;
  Serial.print("Tested: ");
  Serial.print(done);
  Serial.print("/12");
  if (done < NUM_KEYS) {
    Serial.print("   missing:");
    for (int i = 0; i < NUM_KEYS; i++) {
      if (!tested[i]) { Serial.print(" K"); Serial.print(i + 1); }
    }
    Serial.println();
  } else {
    Serial.println("   ALL KEYS WORK!");
  }
}

void setup() {
  Serial.begin(115200);
  pinMode(LED_BUILTIN, OUTPUT);
  pinMode(PIN_R, OUTPUT); pinMode(PIN_G, OUTPUT); pinMode(PIN_B, OUTPUT);
  setRGB(0, 0, 0);
  for (int i = 0; i < NUM_KEYS; i++) {
    pinMode(FIRST_PIN + i, INPUT_PULLUP);
    lastChange[i] = 0;
    tested[i] = false;
    pressCount[i] = 0;
  }
  delay(100);
  Serial.println();
  Serial.println("=== 12-SWITCH TEST ===");
  Serial.println("Press the keys one by one (K1 = pin 22 ... K12 = pin 33).");

  // a key that reads "pressed" right after start-up = signal wire touching ground (short)
  bool problem = false;
  for (int i = 0; i < NUM_KEYS; i++) {
    lastState[i] = digitalRead(FIRST_PIN + i);
    if (lastState[i] == LOW) {
      Serial.print("WARNING: K"); Serial.print(i + 1);
      Serial.print(" (pin "); Serial.print(FIRST_PIN + i);
      Serial.println(") reads 'pressed' without being touched - check that the wire does not touch ground.");
      problem = true;
    }
  }
  if (!problem) Serial.println("Start OK - no key is shorted.");
  printMissing();
}

void loop() {
  unsigned long now = millis();
  bool anyDown = false;

  for (int i = 0; i < NUM_KEYS; i++) {
    bool state = digitalRead(FIRST_PIN + i);
    if (state != lastState[i] && now - lastChange[i] > DEBOUNCE_MS) {
      lastChange[i] = now;
      lastState[i] = state;
      if (state == LOW) {
        pressCount[i]++;
        Serial.print("K"); Serial.print(i + 1);
        Serial.print(" (pin "); Serial.print(FIRST_PIN + i);
        Serial.print(") PRESSED   [count: "); Serial.print(pressCount[i]); Serial.print("]   LED: ");
        Serial.println(COLOR_NAMES[i]);
        setRGB(KEY_COLORS[i][0], KEY_COLORS[i][1], KEY_COLORS[i][2]);

        // several keys down from a single press = wires touching each other
        int down = 0;
        for (int j = 0; j < NUM_KEYS; j++) if (digitalRead(FIRST_PIN + j) == LOW) down++;
        if (down > 1) {
          Serial.print("   WARNING: pressed at once:");
          for (int j = 0; j < NUM_KEYS; j++)
            if (digitalRead(FIRST_PIN + j) == LOW) { Serial.print(" K"); Serial.print(j + 1); }
          Serial.println("  (if you press only one - the wires of these keys are touching)");
        }

        if (!tested[i]) { tested[i] = true; printMissing(); }
      } else {
        Serial.print("K"); Serial.print(i + 1); Serial.println(" released");
      }
    }
    if (lastState[i] == LOW) anyDown = true;
  }
  digitalWrite(LED_BUILTIN, anyDown);
}
