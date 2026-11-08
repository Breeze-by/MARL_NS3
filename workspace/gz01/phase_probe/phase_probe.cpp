// Observation only. No ROS publisher, force, joint command, or state setter.
#include <gazebo/gazebo.hh>
#include <gazebo/physics/physics.hh>
#include <gazebo/physics/ode/ODEJoint.hh>
#include <gazebo/physics/ode/ODESurfaceParams.hh>
#include <chrono>
#include <fstream>
#include <iomanip>
#include <string>
#include <set>

namespace gazebo
{
class Gz01PhaseProbe : public WorldPlugin
{
public:
  void Load(physics::WorldPtr world, sdf::ElementPtr sdf) override
  {
    world_ = world;
    output_.open(sdf->Get<std::string>("output"));
    if (!output_) throw std::runtime_error("Cannot open phase-probe output");
    const auto filename = sdf->Get<std::string>("output");
    loads_.open(filename.substr(0, filename.find_last_of('/')+1)+"wheel-load.csv");
    if (!loads_) throw std::runtime_error("Cannot open wheel-load output");
    loads_ << std::setprecision(17)
      << "sim,iteration,robot,joint,wheel,feedback_body1,feedback_body2,"
      << "axis_x,axis_y,axis_z,anchor_x,anchor_y,anchor_z,lower,upper,position,velocity,"
      << "fmax,motor_velocity,wheel_mu,wheel_mu2,wheel_slip1,wheel_slip2,"
      << "mass,cog_x,cog_y,cog_z,omega_x,omega_y,omega_z,"
      << "I00,I01,I02,I10,I11,I12,I20,I21,I22,"
      << "joint_force_x,joint_force_y,joint_force_z,joint_torque_x,joint_torque_y,joint_torque_z,"
      << "contact_points,contact_force_x,contact_force_y,contact_force_z,"
      << "contact_torque_x,contact_torque_y,contact_torque_z,"
      << "contact_force_link_x,contact_force_link_y,contact_force_link_z,"
      << "contact_torque_link_x,contact_torque_link_y,contact_torque_link_z\n";
    // Preserve feedback data only; this does not add/remove contact constraints.
    world_->Physics()->GetContactManager()->SetNeverDropContacts(true);
    output_ << std::setprecision(17)
      << "pair,phase,begin_sim,world_sim,iteration,step_s,callback_steady_ns,robot,canonical,"
      << "model_x,model_y,model_z,model_qx,model_qy,model_qz,model_qw,"
      << "model_vx,model_vy,model_vz,model_wx,model_wy,model_wz,"
      << "link_x,link_y,link_z,link_qx,link_qy,link_qz,link_qw,"
      << "link_vx,link_vy,link_vz,link_wx,link_wy,link_wz,"
      << "wheel_left_radps,wheel_right_radps,"
      << "body_x,body_y,body_z,body_qx,body_qy,body_qz,body_qw,"
      << "body_vx,body_vy,body_vz,body_wx,body_wy,body_wz,"
      << "body_cog_vx,body_cog_vy,body_cog_vz,"
      << "canonical_mass,canonical_gravity,canonical_collisions,"
      << "body_mass,body_gravity,body_collisions,"
      << "base_joint_parent,base_joint_child,base_joint_fixed,"
      << "ode_solver,ode_iters,ode_sor,left_fmax,right_fmax,left_motor_radps,right_motor_radps\n";
    begin_ = event::Events::ConnectWorldUpdateBegin(
      [this](const common::UpdateInfo &info) {
        ++pair_;
        // Adjacent sampled steps expose End(k) -> Begin(k+1), not only
        // the two phases inside an isolated step.
        capture_ = pair_ % 10 < 2;
        if (capture_) { beginSim_ = info.simTime.Double(); Capture("begin"); }
      });
    end_ = event::Events::ConnectWorldUpdateEnd(
      [this]() { if (capture_) Capture("end"); });
  }

  ~Gz01PhaseProbe() override
  {
    gzmsg << "GZ01 phase probe: rows=" << rows_
      << " callback_total_ns=" << callbackNs_
      << " callback_max_ns=" << maxCallbackNs_ << "\n";
  }

private:
  void Pose(const ignition::math::Pose3d &p)
  {
    output_ << ',' << p.Pos().X() << ',' << p.Pos().Y() << ',' << p.Pos().Z()
      << ',' << p.Rot().X() << ',' << p.Rot().Y() << ',' << p.Rot().Z() << ',' << p.Rot().W();
  }

  void Vector(const ignition::math::Vector3d &v)
  { output_ << ',' << v.X() << ',' << v.Y() << ',' << v.Z(); }

  void LoadVector(const ignition::math::Vector3d &v)
  { loads_ << ',' << v.X() << ',' << v.Y() << ',' << v.Z(); }

  void WheelLoad(const physics::ModelPtr &model, const physics::JointPtr &joint)
  {
    const auto wheel = joint->GetChild();
    const auto ode = boost::dynamic_pointer_cast<physics::ODEJoint>(joint);
    const auto first = ode->GetJointLink(0), second = ode->GetJointLink(1);
    const auto feedback = ode->GetFeedback();
    const auto surface=boost::dynamic_pointer_cast<physics::ODESurfaceParams>(
        wheel->GetCollisions()[0]->GetSurface());
    // Raw ODE feedback is WORLD frame at each body's CoG. Do not use the
    // converted GetForceTorque frame, or label net constraint torque as motor.
    const auto f = first == wheel ? feedback->f1 : feedback->f2;
    const auto t = first == wheel ? feedback->t1 : feedback->t2;
    ignition::math::Vector3d contactForce, contactTorque;
    int points = 0;
    auto manager = world_->Physics()->GetContactManager();
    for (unsigned int n = 0; n < manager->GetContactCount(); ++n)
    {
      const auto contact = manager->GetContact(n);
      const bool one = contact->collision1->GetLink() == wheel;
      const bool two = contact->collision2->GetLink() == wheel;
      if (!one && !two) continue;
      for (int i = 0; i < contact->count; ++i)
      {
        const auto &w = contact->wrench[i];
        contactForce += one ? w.body1Force : w.body2Force;
        contactTorque += one ? w.body1Torque : w.body2Torque;
        ++points;
      }
    }
    loads_ << world_->SimTime().Double() << ',' << world_->Iterations()
      << ',' << model->GetName() << ',' << joint->GetName() << ',' << wheel->GetName()
      << ',' << first->GetName() << ',' << second->GetName();
    LoadVector(joint->GlobalAxis(0)); LoadVector(joint->Anchor(0));
    loads_ << ',' << joint->LowerLimit(0) << ',' << joint->UpperLimit(0)
      << ',' << joint->Position(0) << ',' << joint->GetVelocity(0)
      << ',' << joint->GetParam("fmax",0) << ',' << joint->GetParam("vel",0)
      << ',' << surface->FrictionPyramid()->MuPrimary()
      << ',' << surface->FrictionPyramid()->MuSecondary()
      << ',' << surface->slip1 << ',' << surface->slip2
      << ',' << wheel->GetInertial()->Mass();
    LoadVector(wheel->WorldCoGPose().Pos()); LoadVector(wheel->WorldAngularVel());
    const auto inertia = wheel->WorldInertiaMatrix();
    for (int r = 0; r < 3; ++r)
      for (int c = 0; c < 3; ++c) loads_ << ',' << inertia(r,c);
    LoadVector({f[0],f[1],f[2]}); LoadVector({t[0],t[1],t[2]});
    // ODEPhysics::UpdatePhysics rotates raw contact feedback to LINK frame,
    // despite Contact.hh's WORLD comment. Preserve raw values and explicitly
    // rotate at this sampled wheel pose for the WORLD comparison columns.
    loads_ << ',' << points;
    LoadVector(wheel->WorldPose().Rot().RotateVector(contactForce));
    LoadVector(wheel->WorldPose().Rot().RotateVector(contactTorque));
    LoadVector(contactForce); LoadVector(contactTorque);
    loads_ << '\n';
  }

  void Capture(const char *phase)
  {
    const auto start = std::chrono::steady_clock::now();
    const auto steadyNs = std::chrono::duration_cast<std::chrono::nanoseconds>(
      start.time_since_epoch()).count();
    for (const auto &name : {"tb1", "tb2", "tb3"})
    {
      auto model = world_->ModelByName(name);
      if (!model) continue; // Models are physically spawned after world load.
      auto link = model->GetLink("canonical");
      auto body = model->GetLink("base_link");
      auto baseJoint = model->GetJoint("base_joint");
      auto left = model->GetJoint("wheel_left_joint");
      auto right = model->GetJoint("wheel_right_joint");
      if (feedbackEnabled_.insert(name).second)
      {
        left->SetProvideFeedback(true);
        right->SetProvideFeedback(true);
      }
      if (std::string(phase) == "end")
      {
        WheelLoad(model, left);
        WheelLoad(model, right);
      }
      output_ << pair_ << ',' << phase << ',' << beginSim_ << ',' << world_->SimTime().Double()
        << ',' << world_->Iterations() << ',' << world_->Physics()->GetMaxStepSize()
        << ',' << steadyNs << ',' << name << ',' << link->GetName();
      Pose(model->WorldPose()); Vector(model->WorldLinearVel()); Vector(model->WorldAngularVel());
      Pose(link->WorldPose()); Vector(link->WorldLinearVel()); Vector(link->WorldAngularVel());
      output_ << ',' << left->GetVelocity(0) << ',' << right->GetVelocity(0);
      Pose(body->WorldPose()); Vector(body->WorldLinearVel()); Vector(body->WorldAngularVel());
      Vector(body->WorldCoGLinearVel());
      output_ << ',' << link->GetInertial()->Mass() << ',' << link->GetGravityMode()
        << ',' << link->GetCollisions().size()
        << ',' << body->GetInertial()->Mass() << ',' << body->GetGravityMode()
        << ',' << body->GetCollisions().size()
        << ',' << baseJoint->GetParent()->GetName() << ',' << baseJoint->GetChild()->GetName()
        << ',' << baseJoint->HasType(physics::Base::FIXED_JOINT)
        << ',' << boost::any_cast<std::string>(world_->Physics()->GetParam("solver_type"))
        << ',' << boost::any_cast<int>(world_->Physics()->GetParam("iters"))
        << ',' << boost::any_cast<double>(world_->Physics()->GetParam("sor"))
        << ',' << left->GetParam("fmax",0) << ',' << right->GetParam("fmax",0)
        << ',' << left->GetParam("vel",0) << ',' << right->GetParam("vel",0) << '\n';
      ++rows_;
    }
    const auto ns = std::chrono::duration_cast<std::chrono::nanoseconds>(
      std::chrono::steady_clock::now()-start).count();
    callbackNs_ += ns;
    maxCallbackNs_ = std::max(maxCallbackNs_, ns);
  }

  physics::WorldPtr world_;
  event::ConnectionPtr begin_, end_;
  std::ofstream output_, loads_;
  std::set<std::string> feedbackEnabled_;
  uint64_t pair_ = 0, rows_ = 0;
  int64_t callbackNs_ = 0, maxCallbackNs_ = 0;
  double beginSim_ = 0;
  bool capture_ = false;
};
GZ_REGISTER_WORLD_PLUGIN(Gz01PhaseProbe)
}
