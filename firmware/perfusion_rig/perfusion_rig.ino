// Plunger pusher for an in-vitro perfusion syringe.
// Fluid stays inside a sterile syringe and purchased tubing.
// Not an infusion pump. Not for animals or people.
// Command grammar is the one simulated by perfusion.pump.simulate.
//
// Wiring (example, A4988 or DRV8825):
//   STEP -> pin 2
//   DIR  -> pin 3
//   EN   -> pin 4 (driver enable, active low on most pololu-style boards)
// Use a commercial enclosed 12 V supply. Do not wire mains.

const int STEP_PIN = 2;
const int DIR_PIN = 3;
const int EN_PIN = 4;
const float FULL_STEPS = 200.0f;
const float MAX_FLOW = 2000.0f;

float diameterMm = 14.5f;
float pitchMm = 8.0f;
int microsteps = 16;
float flowUlPerMin = 0.0f;
unsigned long stepIntervalUs = 0;
unsigned long lastStepUs = 0;
unsigned long runUntilMs = 0;
bool running = false;
long stepCount = 0;

float ulPerRevolution() {
  float radius = diameterMm * 0.5f;
  return 3.14159265f * radius * radius * pitchMm;
}

void applyFlow(float flow) {
  flowUlPerMin = flow;
  if (fabs(flow) < 0.01f) {
    stepIntervalUs = 0;
    digitalWrite(EN_PIN, HIGH);
    return;
  }
  digitalWrite(DIR_PIN, flow > 0 ? HIGH : LOW);
  float ulPerS = fabs(flow) / 60.0f;
  float stepsPerS = (ulPerS / ulPerRevolution()) * FULL_STEPS * microsteps;
  stepIntervalUs = (unsigned long)(1000000.0f / stepsPerS);
  digitalWrite(EN_PIN, LOW);
}

void handleLine(String line) {
  line.trim();
  if (line.length() == 0) return;
  int space = line.indexOf(' ');
  String op = (space < 0 ? line : line.substring(0, space));
  op.toUpperCase();
  float value = (space < 0) ? 0.0f : line.substring(space + 1).toFloat();
  if (op == "DIA") {
    if (value < 1.0f || value > 40.0f) { Serial.println("ERR diameter"); return; }
    diameterMm = value;
  } else if (op == "PITCH") {
    if (value <= 0.0f) { Serial.println("ERR pitch"); return; }
    pitchMm = value;
  } else if (op == "MICRO") {
    int m = (int)value;
    if (!(m == 1 || m == 2 || m == 4 || m == 8 || m == 16)) { Serial.println("ERR micro"); return; }
    microsteps = m;
  } else if (op == "FLOW") {
    if (fabs(value) > MAX_FLOW) { Serial.println("ERR flow cap"); return; }
    applyFlow(value);
  } else if (op == "RUN") {
    if (value <= 0.0f) { Serial.println("ERR run"); return; }
    running = true;
    runUntilMs = millis() + (unsigned long)(value * 1000.0f);
  } else if (op == "STOP") {
    running = false;
    applyFlow(0);
    Serial.println("OK STOP");
  } else if (op == "STATUS") {
    Serial.print("flow_ul_per_min ");
    Serial.println(flowUlPerMin);
    Serial.print("steps ");
    Serial.println(stepCount);
  } else {
    Serial.println("ERR command");
  }
}

void setup() {
  pinMode(STEP_PIN, OUTPUT);
  pinMode(DIR_PIN, OUTPUT);
  pinMode(EN_PIN, OUTPUT);
  digitalWrite(EN_PIN, HIGH);
  Serial.begin(115200);
  Serial.println("perfusion-rig research plunger");
}

void loop() {
  static String buffer;
  while (Serial.available()) {
    char c = (char)Serial.read();
    if (c == '\n' || c == '\r') {
      handleLine(buffer);
      buffer = "";
    } else {
      buffer += c;
    }
  }
  if (running && (long)(millis() - runUntilMs) >= 0) {
    running = false;
    applyFlow(0);
    Serial.println("OK DONE");
  }
  if (running && stepIntervalUs > 0) {
    unsigned long now = micros();
    if ((unsigned long)(now - lastStepUs) >= stepIntervalUs) {
      lastStepUs = now;
      digitalWrite(STEP_PIN, HIGH);
      delayMicroseconds(4);
      digitalWrite(STEP_PIN, LOW);
      stepCount++;
    }
  }
}
