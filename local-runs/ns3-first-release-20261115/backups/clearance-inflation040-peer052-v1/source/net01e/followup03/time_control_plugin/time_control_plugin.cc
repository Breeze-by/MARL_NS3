// A physics-completion RPC only. No clock, pose, velocity or parameter writes.
#include <gazebo/common/Plugin.hh>
#include <gazebo/physics/PhysicsEngine.hh>
#include <gazebo/physics/World.hh>
#include <gazebo_ros/node.hpp>
#include <std_srvs/srv/trigger.hpp>

#include <cstdint>
#include <sstream>
#include <memory>
#include <time.h>

namespace net01
{
int64_t Nanoseconds(const gazebo::common::Time &time)
{
  return int64_t(time.sec) * 1000000000LL + time.nsec;
}

// Linux CLOCK_MONOTONIC is shared with Python time.monotonic_ns() on this
// same-host user-namespace-only execution. Diagnostic marks are not ROS time.
int64_t MonotonicNanoseconds()
{
  timespec time;
  clock_gettime(CLOCK_MONOTONIC, &time);
  return int64_t(time.tv_sec) * 1000000000LL + time.tv_nsec;
}

class TimeControlPlugin : public gazebo::WorldPlugin
{
public:
  void Load(gazebo::physics::WorldPtr world, sdf::ElementPtr sdf) override
  {
    node_ = gazebo_ros::Node::Get(sdf);
    group_ = node_->create_callback_group(rclcpp::CallbackGroupType::MutuallyExclusive);
    // Callback group is mutually exclusive. Own this tiny counter by value in
    // the service closure, preserving the original world/lifetime semantics.
    auto observed_callbacks = std::make_shared<uint64_t>(0);
    service_ = node_->create_service<std_srvs::srv::Trigger>(
      "/net01/physics_step",
      [world, observed_callbacks](std_srvs::srv::Trigger::Request::SharedPtr,
        std_srvs::srv::Trigger::Response::SharedPtr response)
      {
        const bool observe = *observed_callbacks < 8;
        const auto callback_index = observe ? ++*observed_callbacks : 0;
        const auto callback_enter = observe ? MonotonicNanoseconds() : 0;
        const auto before_ns = Nanoseconds(world->SimTime());
        const auto before_iterations = world->Iterations();
        const bool allowed = world->IsPaused() &&
          world->Physics()->GetMaxStepSize() == 0.001;
        // gazebo_ros::Node services run on its background ROS executor, not
        // the world-update thread. Step blocks until post-update stepInc==0,
        // or until the world stops; never call this from an update callback.
        const auto step_begin = observe ? MonotonicNanoseconds() : 0;
        if (allowed) {
          world->Step(10);
        }
        const auto step_end = observe ? MonotonicNanoseconds() : 0;
        const auto after_ns = Nanoseconds(world->SimTime());
        const auto after_iterations = world->Iterations();
        const auto completed_steps = uint32_t(after_iterations - before_iterations);
        response->success = allowed && world->IsPaused() && completed_steps == 10 &&
          after_ns - before_ns == 10000000LL;
        std::ostringstream message;
        message << "{\"before_ns\":" << before_ns
                << ",\"after_ns\":" << after_ns
                << ",\"before_iterations\":" << before_iterations
                << ",\"after_iterations\":" << after_iterations
                << ",\"completed_steps\":" << completed_steps;
        if (observe) {
          message << ",\"diagnostic_timing_v1\":{\"callback_index\":" << callback_index
                  << ",\"callback_enter_mono_ns\":" << callback_enter
                  << ",\"step_begin_mono_ns\":" << step_begin
                  << ",\"step_end_mono_ns\":" << step_end
                  << ",\"step_called\":" << (allowed ? "true" : "false")
                  << ",\"response_ready_mono_ns\":" << MonotonicNanoseconds() << "}";
        }
        message << "}";
        response->message = message.str();
      }, rmw_qos_profile_services_default, group_);
  }

private:
  rclcpp::CallbackGroup::SharedPtr group_;
  gazebo_ros::Node::SharedPtr node_;
  rclcpp::Service<std_srvs::srv::Trigger>::SharedPtr service_;
};

GZ_REGISTER_WORLD_PLUGIN(TimeControlPlugin)
}  // namespace net01
