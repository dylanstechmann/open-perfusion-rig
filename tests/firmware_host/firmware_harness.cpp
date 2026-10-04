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

  if (scenario == "wait-for-completion") {
    startWith("DIA 14.5\nPITCH 8\nMICRO 16\nFLOW 60\nRUN 0.01\n");
    assert(running);
    assert(Serial.output().find("OK DONE") == std::string::npos);
    // Model the transport rule: do not send the next FLOW/RUN until DONE.
    fakeMillis = 9;
    fakeMicros = 9000;
    loop();
    assert(running);
    assert(Serial.output().find("OK DONE") == std::string::npos);
    fakeMillis = 10;
    fakeMicros = 10000;
    loop();
    assert(!running);
    assert(Serial.output().find("OK DONE") != std::string::npos);
    Serial.feedNext("FLOW 30\nRUN 0.01\n");
    loop();
    assert(running);
    assert(flowUlPerMin == 30.0f);
    fakeMillis = 20;
    fakeMicros = 20000;
    loop();
    assert(!running);
    const size_t first_done = Serial.findOutput("OK DONE");
    assert(first_done != std::string::npos);
    assert(Serial.findOutput("OK DONE", first_done + 1) != std::string::npos);
    return 0;
  }

  if (scenario == "run-clock-rollover") {
    fakeMillis = UINT32_MAX - 4;
    fakeMicros = UINT32_MAX - 5000;
    startWith("FLOW 60\nRUN 0.01\n");
    assert(running);
    fakeMillis += 9;  // Wraps; nine elapsed milliseconds must not complete RUN.
    loop();
    assert(running);
    assert(Serial.output().find("OK DONE") == std::string::npos);
    fakeMillis += 1;
    loop();
    assert(!running);
    assert(pinValues[EN_PIN] == HIGH);
    assert(Serial.output().find("OK DONE") != std::string::npos);
    return 0;
  }

  if (scenario == "step-clock-rollover") {
    fakeMicros = UINT32_MAX - 50;
    startWith("FLOW 120\nRUN 2\n");
    assert(stepCount == 0);
    fakeMicros += stepIntervalUs - 1;
    loop();
    assert(stepCount == 0);
    fakeMicros += 1;
    loop();
    assert(stepCount == 1);
    assert(pinValues[STEP_PIN] == LOW);
    // The four-microsecond pulse does not count as another whole interval.
    loop();
    assert(stepCount == 1);
    return 0;
  }

  if (scenario == "fresh-run-pulse-baseline") {
    fakeMicros = 2000000;  // Simulate a long idle period before RUN.
    startWith("FLOW 120\nRUN 2\n");
    assert(stepCount == 0);
    fakeMicros += stepIntervalUs - 1;
    loop();
    assert(stepCount == 0);
    fakeMicros += 1;
    loop();
    assert(stepCount == 1);
    return 0;
  }

  if (scenario == "reject-submillisecond-run") {
    startWith("RUN 0.0001\n");
    assert(!running);
    assert(Serial.output().find("ERR run") != std::string::npos);
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
