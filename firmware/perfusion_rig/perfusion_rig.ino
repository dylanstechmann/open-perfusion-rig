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

#include <stdint.h>
#include <math.h>
#include <stdlib.h>

const int STEP_PIN = 2;
const int DIR_PIN = 3;
const int EN_PIN = 4;
const float FULL_STEPS = 200.0f;
const float MAX_FLOW = 2000.0f;
const float MIN_NONZERO_FLOW = 0.01f;
const float MIN_STEP_INTERVAL_US = 4.0f; // STEP pulse is held HIGH for four microseconds.
const float MAX_STEP_INTERVAL_US = 4294967040.0f; // Float-safe margin below 32-bit micros overflow.
const float MIN_RUN_SECONDS = 0.001f; // The run clock resolves whole milliseconds.
const float MAX_RUN_SECONDS = 86400.0f;

float diameterMm = 14.5f;
float pitchMm = 8.0f;
int microsteps = 16;
float flowUlPerMin = 0.0f;
uint32_t stepIntervalUs = 0;
uint32_t lastStepUs = 0;
uint32_t runStartedMs = 0;
uint32_t runDurationMs = 0;
bool running = false;
long stepCount = 0;

float ulPerRevolution() {
  float radius = diameterMm * 0.5f;
  return 3.14159265f * radius * radius * pitchMm;
}

bool applyFlow(float flow) {
  if (flow == 0.0f) {
    flowUlPerMin = 0.0f;
    stepIntervalUs = 0;
    digitalWrite(EN_PIN, HIGH);
    return true;
  }
  float volumePerRev = ulPerRevolution();
  float ulPerS = fabs(flow) / 60.0f;
  float stepsPerS = (ulPerS / volumePerRev) * FULL_STEPS * microsteps;
  double intervalUs = 1000000.0 / (double)stepsPerS;
  if (!isfinite(volumePerRev) || volumePerRev <= 0.0f ||
      !isfinite(stepsPerS) || stepsPerS <= 0.0f ||
      !isfinite(intervalUs) || intervalUs < MIN_STEP_INTERVAL_US ||
      intervalUs > MAX_STEP_INTERVAL_US) {
    flowUlPerMin = 0.0f;
    stepIntervalUs = 0;
    digitalWrite(EN_PIN, HIGH);
    return false;
  }
  flowUlPerMin = flow;
  digitalWrite(DIR_PIN, flow > 0 ? HIGH : LOW);
  stepIntervalUs = (uint32_t)intervalUs;
  digitalWrite(EN_PIN, LOW);
  return true;
}

bool parseFiniteValue(String token, float *value) {
  token.trim();
  if (token.length() == 0) return false;
  const char *text = token.c_str();
  char *end = NULL;
  double parsed = strtod(text, &end);
  if (end == text || *end != '\0' || !isfinite(parsed) ||
      parsed > 3.402823466e+38 || parsed < -3.402823466e+38) return false;
  *value = (float)parsed;
  return isfinite(*value);
}

bool hasInternalWhitespace(String token) {
  const char *text = token.c_str();
  for (size_t i = 0; i < token.length(); i++) {
    if (text[i] == ' ' || text[i] == '\t' || text[i] == '\r' || text[i] == '\n') return true;
  }
  return false;
}

void handleLine(String line) {
  line.trim();
  if (line.length() == 0) return;
  int space = line.indexOf(' ');
  String op = (space < 0 ? line : line.substring(0, space));
  op.toUpperCase();
  String argument = (space < 0) ? String("") : line.substring(space + 1);
  bool takesValue = (op == "DIA" || op == "PITCH" || op == "MICRO" || op == "FLOW" || op == "RUN");
  bool takesNoArguments = (op == "STOP" || op == "STATUS");
  if (!takesValue && !takesNoArguments) { Serial.println("ERR command"); return; }
  if (takesNoArguments && argument.length() != 0) { Serial.println("ERR arity"); return; }
  float value = 0.0f;
  if (takesValue && (space < 0 || !parseFiniteValue(argument, &value))) {
    Serial.println(hasInternalWhitespace(argument) ? "ERR arity" : "ERR number");
    return;
  }
  if (op == "DIA") {
    if (value < 1.0f || value > 40.0f) { Serial.println("ERR diameter"); return; }
    diameterMm = value;
  } else if (op == "PITCH") {
    if (value <= 0.0f) { Serial.println("ERR pitch"); return; }
    pitchMm = value;
  } else if (op == "MICRO") {
    if (!(value == 1.0f || value == 2.0f || value == 4.0f || value == 8.0f || value == 16.0f)) { Serial.println("ERR micro"); return; }
    microsteps = (int)value;
  } else if (op == "FLOW") {
    if (fabs(value) > MAX_FLOW) { Serial.println("ERR flow cap"); return; }
    if (value != 0.0f && fabs(value) < MIN_NONZERO_FLOW) {
      running = false;
      applyFlow(0);
      Serial.println("ERR flow below motor deadband");
      return;
    }
    if (!applyFlow(value)) {
      running = false;
      Serial.println("ERR step interval");
      return;
    }
  } else if (op == "RUN") {
    if (value < MIN_RUN_SECONDS || value > MAX_RUN_SECONDS) { Serial.println("ERR run"); return; }
    running = true;
    // Explicit 32-bit elapsed arithmetic matches the MCU on host builds too.
    runStartedMs = (uint32_t)millis();
    runDurationMs = (uint32_t)(value * 1000.0f);
    // Idle time is not part of the next run's first pulse interval.
    lastStepUs = (uint32_t)micros();
  } else if (op == "STOP") {
    running = false;
    applyFlow(0);
    Serial.println("OK STOP");
  } else if (op == "STATUS") {
    Serial.print("flow_ul_per_min ");
    Serial.println(flowUlPerMin);
    Serial.print("steps ");
    Serial.println(stepCount);
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
  if (running && (uint32_t)((uint32_t)millis() - runStartedMs) >= runDurationMs) {
    running = false;
    applyFlow(0);
    Serial.println("OK DONE");
  }
  if (running && stepIntervalUs > 0) {
    uint32_t now = (uint32_t)micros();
    if ((uint32_t)(now - lastStepUs) >= stepIntervalUs) {
      lastStepUs = now;
      digitalWrite(STEP_PIN, HIGH);
      delayMicroseconds(4);
      digitalWrite(STEP_PIN, LOW);
      stepCount++;
    }
  }
}
