// Independent read-only DDS clock observer. No use_sim_time, timers or publishers.
#include <rclcpp/rclcpp.hpp>
#include <rosgraph_msgs/msg/clock.hpp>
#include <algorithm>
#include <array>
#include <cerrno>
#include <cstdio>
#include <fcntl.h>
#include <iostream>
#include <stdexcept>
#include <string>
#include <system_error>
#include <time.h>
#include <unistd.h>
#include <vector>

uint64_t clock_ns(clockid_t clock) {
  timespec t{};
  if (clock_gettime(clock, &t)) throw std::system_error(errno, std::generic_category());
  return uint64_t(t.tv_sec) * 1000000000ULL + t.tv_nsec;
}

struct Row {
  uint64_t sim, mono, realtime, mono_after;
  int64_t source, received;
  std::array<uint8_t, RMW_GID_STORAGE_SIZE> gid;
};

int main(int argc, char **argv) {
  if (argc != 2) throw std::runtime_error("usage: net01-clock-witness NEW_OUTPUT.csv");
  const std::string path(argv[1]);
  std::vector<Row> rows;
  rclcpp::init(argc, argv);
  auto node = std::make_shared<rclcpp::Node>("net01_clock_witness",
    rclcpp::NodeOptions().enable_rosout(false).start_parameter_services(false)
      .start_parameter_event_publisher(false));
  auto subscription = node->create_subscription<rosgraph_msgs::msg::Clock>(
    "/clock", rclcpp::SensorDataQoS(),
    [&rows](const rosgraph_msgs::msg::Clock &message, const rclcpp::MessageInfo &info) {
      const auto mono = clock_ns(CLOCK_MONOTONIC);
      const auto realtime = clock_ns(CLOCK_REALTIME);
      const auto mono_after = clock_ns(CLOCK_MONOTONIC);
      const auto &rmw = info.get_rmw_message_info();
      Row row{uint64_t(message.clock.sec) * 1000000000ULL + message.clock.nanosec,
        mono, realtime, mono_after, rmw.source_timestamp, rmw.received_timestamp, {}};
      std::copy(std::begin(rmw.publisher_gid.data), std::end(rmw.publisher_gid.data), row.gid.begin());
      rows.push_back(row);
    });
  std::cout << "CLOCK_WITNESS_READY" << std::endl;
  // Existing outer experiment bound/owned SIGINT ends this process. RAM only
  // while spinning; this observer never supplies policy, clock or safety input.
  rclcpp::spin(node);
  subscription.reset(); node.reset();
  rclcpp::shutdown();
  int fd = open(path.c_str(), O_WRONLY | O_CREAT | O_EXCL, 0644);
  if (fd < 0) throw std::system_error(errno, std::generic_category());
  FILE *stream = fdopen(fd, "w");
  if (!stream) { close(fd); throw std::system_error(errno, std::generic_category()); }
  fputs("clock_ns,dds_source_timestamp_ns,dds_received_timestamp_ns,callback_monotonic_ns,callback_realtime_ns,callback_monotonic_after_ns,publisher_gid\n", stream);
  for (const auto &row : rows) {
    fprintf(stream, "%llu,%lld,%lld,%llu,%llu,%llu,", (unsigned long long)row.sim,
      (long long)row.source, (long long)row.received,
      (unsigned long long)row.mono, (unsigned long long)row.realtime,
      (unsigned long long)row.mono_after);
    for (auto byte : row.gid) fprintf(stream, "%02x", byte);
    fputc('\n', stream);
  }
  const bool failed = ferror(stream);
  const int closed = fclose(stream);
  if (failed || closed) throw std::runtime_error("clock witness CSV persistence failed");
  return 0;
}
