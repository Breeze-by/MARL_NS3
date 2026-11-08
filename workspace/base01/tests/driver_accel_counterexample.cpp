// Offline component counterexample. The step body below is copied verbatim
// from the preserved gazebo_ros_diff_drive.cpp; this does not load Gazebo.
// Original component: Copyright 2012 Open Source Robotics Foundation,
// Apache License 2.0, as retained in evidence/initial/gazebo_ros_diff_drive.cpp.
#include <algorithm>
#include <cmath>
#include <iostream>
#include <memory>
#include <string>
#include <vector>
struct Joint {
  double motor = 0;
  void SetParam(const std::string &, int, double value) { motor = value; }
};
struct Drive {
  enum { LEFT=0, RIGHT=1 };
  unsigned int num_wheel_pairs_ = 1;
  double max_wheel_accel_ = 1.0;
  std::vector<double> wheel_diameter_{0.066};
  std::vector<double> wheel_speed_instr_{0.0,0.0};
  std::vector<double> desired_wheel_speed_{0.0,0.0};
  std::vector<std::shared_ptr<Joint>> joints_{std::make_shared<Joint>(),std::make_shared<Joint>()};
  void step(const std::vector<double> & current_speed, double seconds_since_last_update) {
  // If max_accel == 0, or target speed is reached
  for (unsigned int i = 0; i < num_wheel_pairs_; ++i) {
    if (max_wheel_accel_ == 0 ||
      ((fabs(desired_wheel_speed_[2 * i + LEFT] - current_speed[2 * i + LEFT]) < 0.01) &&
      (fabs(desired_wheel_speed_[2 * i + RIGHT] - current_speed[2 * i + RIGHT]) < 0.01)))
    {
      joints_[2 * i + LEFT]->SetParam(
        "vel", 0, desired_wheel_speed_[2 * i + LEFT] / (wheel_diameter_[i] / 2.0));
      joints_[2 * i + RIGHT]->SetParam(
        "vel", 0, desired_wheel_speed_[2 * i + RIGHT] / (wheel_diameter_[i] / 2.0));
    } else {
      if (desired_wheel_speed_[2 * i + LEFT] >= current_speed[2 * i + LEFT]) {
        wheel_speed_instr_[2 * i + LEFT] += fmin(
          desired_wheel_speed_[2 * i + LEFT] -
          current_speed[2 * i + LEFT], max_wheel_accel_ * seconds_since_last_update);
      } else {
        wheel_speed_instr_[2 * i + LEFT] += fmax(
          desired_wheel_speed_[2 * i + LEFT] -
          current_speed[2 * i + LEFT], -max_wheel_accel_ * seconds_since_last_update);
      }

      if (desired_wheel_speed_[2 * i + RIGHT] > current_speed[2 * i + RIGHT]) {
        wheel_speed_instr_[2 * i + RIGHT] += fmin(
          desired_wheel_speed_[2 * i + RIGHT] -
          current_speed[2 * i + RIGHT], max_wheel_accel_ * seconds_since_last_update);
      } else {
        wheel_speed_instr_[2 * i + RIGHT] += fmax(
          desired_wheel_speed_[2 * i + RIGHT] -
          current_speed[2 * i + RIGHT], -max_wheel_accel_ * seconds_since_last_update);
      }

      joints_[2 * i + LEFT]->SetParam(
        "vel", 0, wheel_speed_instr_[2 * i + LEFT] / (wheel_diameter_[i] / 2.0));
      joints_[2 * i + RIGHT]->SetParam(
        "vel", 0, wheel_speed_instr_[2 * i + RIGHT] / (wheel_diameter_[i] / 2.0));
    }
  }

  }
};
int main() {
  Drive driver;
  // Reach the stale-state case from reset with finite target/measurement inputs.
  driver.desired_wheel_speed_ = {0.05,0.05};
  driver.step({0.0,0.0},1.0/30);
  driver.step({0.009,0.009},1.0/30);
  driver.desired_wheel_speed_ = {0.0,0.0};
  driver.step({0.009,0.009},1.0/30);
  double first=driver.joints_[0]->motor*0.033;
  double stale=driver.wheel_speed_instr_[0];
  driver.step({0.011,0.011},1.0/30);
  double second=driver.joints_[0]->motor*0.033;
  double fixed=0.011+std::clamp(0.0-0.011,-1.0/30,1.0/30);
  std::cout << "{\"zero_request_first_output\":" << first
            << ",\"instruction_state_after_zero\":" << stale
            << ",\"zero_request_next_output\":" << second
            << ",\"candidate_synced_output\":" << fixed
            << ",\"scope\":\"component counterexample, not run-03 causal proof\"}\n";
  return !(first==0.0 && stale>0.06 && second>0.05 && std::abs(fixed)<1e-12);
}
