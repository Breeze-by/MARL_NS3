// A physics-completion RPC only. No clock, pose, velocity or parameter writes.
#include <gazebo/common/Plugin.hh>
#include <gazebo/physics/PhysicsEngine.hh>
#include <gazebo/physics/World.hh>
#include <gazebo_ros/node.hpp>
#include <std_srvs/srv/trigger.hpp>

#include <cstdint>
#include <sstream>

namespace net01
{
int64_t Nanoseconds(const gazebo::common::Time &time)
{
  return int64_t(time.sec) * 1000000000LL + time.nsec;
}

class TimeControlPlugin : public gazebo::WorldPlugin
{
public:
  void Load(gazebo::physics::WorldPtr world, sdf::ElementPtr sdf) override
  {
    node_ = gazebo_ros::Node::Get(sdf);
    group_ = node_->create_callback_group(rclcpp::CallbackGroupType::MutuallyExclusive);
    service_ = node_->create_service<std_srvs::srv::Trigger>(
      "/net01/physics_step",
      [world](std_srvs::srv::Trigger::Request::SharedPtr,
        std_srvs::srv::Trigger::Response::SharedPtr response)
      {
        const auto before_ns = Nanoseconds(world->SimTime());
        const auto before_iterations = world->Iterations();
        const bool allowed = world->IsPaused() &&
          world->Physics()->GetMaxStepSize() == 0.001;
        // gazebo_ros::Node services run on its background ROS executor, not
        // the world-update thread. Step blocks until post-update stepInc==0,
        // or until the world stops; never call this from an update callback.
        if (allowed) {
          world->Step(10);
        }
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
                << ",\"completed_steps\":" << completed_steps << "}";
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
