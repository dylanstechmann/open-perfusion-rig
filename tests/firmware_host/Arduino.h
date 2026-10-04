#pragma once

#include <cstdint>
#include <sstream>
#include <string>

constexpr int HIGH = 1;
constexpr int LOW = 0;
constexpr int OUTPUT = 1;

class String {
 public:
  String() = default;
  String(const char *value) : value_(value ? value : "") {}
  String(const std::string &value) : value_(value) {}

  size_t length() const { return value_.length(); }
  int indexOf(char value) const {
    size_t found = value_.find(value);
    return found == std::string::npos ? -1 : static_cast<int>(found);
  }
  String substring(size_t start) const { return String(value_.substr(start)); }
  String substring(size_t start, size_t end) const { return String(value_.substr(start, end - start)); }
  const char *c_str() const { return value_.c_str(); }
  bool operator==(const char *other) const { return value_ == (other ? other : ""); }
  void trim() {
    size_t first = value_.find_first_not_of(" \t\r\n");
    if (first == std::string::npos) {
      value_.clear();
      return;
    }
    size_t last = value_.find_last_not_of(" \t\r\n");
    value_ = value_.substr(first, last - first + 1);
  }
  void toUpperCase() {
    for (char &value : value_) {
      if (value >= 'a' && value <= 'z') value = static_cast<char>(value - 'a' + 'A');
    }
  }
  String &operator+=(char value) {
    value_.push_back(value);
    return *this;
  }

 private:
  std::string value_;
};

class FakeSerial {
 public:
  void begin(unsigned long) {}
  int available() const { return static_cast<int>(input_.size() - read_pos_); }
  char read() { return input_[read_pos_++]; }
  void feed(const std::string &input) { input_ += input; }
  void feedNext(const std::string &input) { input_ = input; read_pos_ = 0; }
  void reset() { input_.clear(); read_pos_ = 0; output_.clear(); }
  void clearOutput() { output_.clear(); }
  const std::string &output() const { return output_; }
  size_t findOutput(const std::string &needle, size_t pos = 0) const { return output_.find(needle, pos); }

  template <typename T>
  void print(const T &value) {
    std::ostringstream stream;
    stream << value;
    output_ += stream.str();
  }
  template <typename T>
  void println(const T &value) {
    print(value);
    output_ += "\n";
  }

 private:
  std::string input_;
  size_t read_pos_ = 0;
  std::string output_;
};

extern FakeSerial Serial;
extern uint32_t fakeMillis;
extern uint32_t fakeMicros;

inline unsigned long millis() { return fakeMillis; }
inline unsigned long micros() { return fakeMicros; }
inline void delayMicroseconds(unsigned int duration) { fakeMicros += duration; }
inline void pinMode(int, int) {}
void digitalWrite(int pin, int value);
