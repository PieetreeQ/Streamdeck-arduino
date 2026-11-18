// RGB LED TEST - checks that the LED is wired correctly.
// Wiring: R -> 220 ohm -> pin 9, G -> 220 ohm -> pin 10, B -> 220 ohm -> pin 11,
//         longest leg -> GND (or 5V for a common-anode LED).
// Open the Serial Monitor (115200) - it tells you which color SHOULD be lit right now.

const bool COMMON_ANODE = false;   // set to true if the longest leg is on 5V

const int PIN_R = 9;
const int PIN_G = 10;
const int PIN_B = 11;

void setColor(int r, int g, int b) {
  if (COMMON_ANODE) { r = 255 - r; g = 255 - g; b = 255 - b; }
  analogWrite(PIN_R, r);
  analogWrite(PIN_G, g);
  analogWrite(PIN_B, b);
}

void show(const char *name, int r, int g, int b) {
  Serial.print("Should be lit now: ");
  Serial.println(name);
  setColor(r, g, b);
  delay(1500);
}

void setup() {
  Serial.begin(115200);
  pinMode(PIN_R, OUTPUT);
  pinMode(PIN_G, OUTPUT);
  pinMode(PIN_B, OUTPUT);
  Serial.println("RGB LED test - start");
}

void loop() {
  show("RED", 255, 0, 0);
  show("GREEN", 0, 255, 0);
  show("BLUE", 0, 0, 255);
  show("YELLOW (red + green)", 255, 255, 0);
  show("PURPLE (red + blue)", 255, 0, 255);
  show("WHITE (all three)", 255, 255, 255);
  show("OFF", 0, 0, 0);

  // smooth rainbow through all colors
  Serial.println("Now: smooth rainbow");
  for (int i = 0; i < 768; i += 2) {
    int r, g, b;
    if (i < 256)      { r = 255 - i;  g = i;         b = 0; }
    else if (i < 512) { r = 0;        g = 511 - i;   b = i - 256; }
    else              { r = i - 512;  g = 0;         b = 767 - i; }
    setColor(r, g, b);
    delay(8);
  }
}
