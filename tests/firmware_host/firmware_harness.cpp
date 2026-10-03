#include <cassert>
#include <cstdint>
#include <map>
#include <string>

#include "Arduino.h"

FakeSerial Serial;
uint32_t fakeMillis = 0;
uint32_t fakeMicros = 0;
std::map<int, int> pinValues;

void digitalWrite(int pin, int value) { pinValues[pin] = value; }

#include "../../firmware/perfusion_rig/perfusion_rig.ino"

static void startWith(const std::string &commands) {
  setup();
  Serial.feed(commands);
  loop();
}

int main(int argc, char **argv) {
  assert(argc == 2);
  const std::string scenario = argv[1];

  if (scenario == "reject-invalid") {
    startWith("DIA nan\nFLOW 1 2\nMICRO 1.5\nRUN 86401\n");
    const std::string output = Serial.output();
    assert(output.find("ERR number") != std::string::npos);
    assert(output.find("ERR arity") != std::string::npos);
    assert(output.find("ERR micro") != std::string::npos);
    assert(output.find("ERR run") != std::string::npos);
    assert(diameterMm == 14.5f);
    assert(microsteps == 16);
    assert(!running);
    return 0;
  }

  if (scenario == "reject-pulse-rate") {
    startWith("DIA 1\nPITCH 0.00001\nMICRO 16\nFLOW 2000\n");
    assert(Serial.output().find("ERR step interval") != std::string::npos);
    assert(flowUlPerMin == 0.0f);
    assert(stepIntervalUs == 0);
    assert(pinValues[EN_PIN] == HIGH);
    return 0;
  }

  if (scenario == "reject-deadband") {
    startWith("DIA 14.5\nPITCH 8\nMICRO 16\nFLOW 0.005\n");
    assert(Serial.output().find("ERR flow below motor deadband") != std::string::npos);
    assert(flowUlPerMin == 0.0f);
    assert(pinValues[EN_PIN] == HIGH);
    return 0;
  }

  if (scenario == "complete-run") {
    startWith("DIA 14.5\nPITCH 8\nMICRO 16\nFLOW 60\nRUN 0.01\n");
    assert(running);
    assert(flowUlPerMin == 60.0f);
    fakeMillis = 10;
    fakeMicros = 10000;
    loop();
    assert(!running);
    assert(flowUlPerMin == 0.0f);
    assert(pinValues[EN_PIN] == HIGH);
    assert(Serial.output().find("OK DONE") != std::string::npos);
    return 0;
  }

  if (scenario == "step-pulse") {
    startWith("DIA 14.5\nPITCH 8\nMICRO 16\nFLOW 120\nRUN 2\n");
    fakeMicros = stepIntervalUs;
    loop();
    assert(stepCount == 1);
    assert(pinValues[STEP_PIN] == LOW);
    assert(fakeMicros == stepIntervalUs + 4);
    return 0;
  }

  return 2;
}
