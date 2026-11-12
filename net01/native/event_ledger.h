#pragma once
// NET01 diagnostic ledger only. No simulator objects or payload bytes cross threads.
#include <algorithm>
#include <charconv>
#include <condition_variable>
#include <cstdint>
#include <deque>
#include <exception>
#include <fstream>
#include <iomanip>
#include <mutex>
#include <sstream>
#include <stdexcept>
#include <string>
#include <thread>
#include <time.h>
#include <vector>

namespace LedgerText {
template<class Integer> inline void integer(std::string& output,Integer value) {
  char buffer[32];const auto result=std::to_chars(buffer,buffer+sizeof(buffer),value);
  if(result.ec!=std::errc{})throw std::runtime_error("Ledger integer formatting failed");
  output.append(buffer,result.ptr);
}
inline void general12(std::string& output,double value) {
  char buffer[64];const auto result=std::to_chars(buffer,buffer+sizeof(buffer),value,std::chars_format::general,12);
  if(result.ec!=std::errc{})throw std::runtime_error("Ledger floating formatting failed");
  output.append(buffer,result.ptr);
}
}

struct LedgerRecord {
  enum Layout {Raw,Packet,Sniff,Drop,Node} layout=Raw;
  uint64_t sequence=0,packetUid=0;
  int64_t ns3=0,monotonic=0;
  uint32_t node=0,packetBytes=0,frequency=0,reason=0;
  double signal=0,noise=0;
  std::string kind,fields;
};

class EventLedger {
  static constexpr uint64_t capacity=16384;
  static constexpr uint64_t sessionCapacity=32000000,sessionByteLimit=8ULL*1024*1024*1024;
  std::ofstream stream;
  std::thread writer;
  std::mutex mutex;
  std::condition_variable changed;
  std::deque<LedgerRecord> pending;
  std::vector<LedgerRecord> session;
  bool sessionRam=false;
  uint64_t sessionOwnedBytes=0;
  bool asynchronous=false,stopping=false;
  std::exception_ptr writeError;
  uint64_t attempted=0,captured=0,written=0,flushed=0,flushTarget=0,peak=0,maxOwnedBytes=0;
  int64_t writerCpu=0;
  static int64_t cpu() {timespec t;clock_gettime(CLOCK_THREAD_CPUTIME_ID,&t);return int64_t(t.tv_sec)*1000000000+t.tv_nsec;}
  void write(const LedgerRecord& r) {
    stream<<"{\"kind\":\""<<r.kind<<"\",\"ns3_ns\":"<<r.ns3<<",\"monotonic_ns\":"<<r.monotonic;
    if(r.layout==LedgerRecord::Raw)stream<<r.fields;
    else {
      stream<<",\"node\":"<<r.node;
      if(r.layout!=LedgerRecord::Node)stream<<",\"packet_uid\":"<<r.packetUid<<",\"packet_bytes\":"<<r.packetBytes;
      if(r.layout==LedgerRecord::Drop)stream<<",\"reason\":"<<r.reason;
      if(r.layout==LedgerRecord::Sniff) {
        std::ostringstream fields;fields<<std::setprecision(12)<<",\"frequency_mhz\":"<<r.frequency
          <<",\"signal_dbm\":"<<r.signal<<",\"noise_dbm\":"<<r.noise<<",\"snr_db\":"<<r.signal-r.noise;
        stream<<fields.str();
      }
    }
    stream<<"}\n";
  }
  void work() {
    const auto start=cpu();
    try {
      for(;;) {
        LedgerRecord row;uint64_t mark=0;
        {
          std::unique_lock<std::mutex> lock(mutex);
          changed.wait(lock,[&]{return stopping || !pending.empty() || flushTarget>flushed;});
          if(written>=flushTarget && flushTarget>flushed)mark=written;
          else if(!pending.empty()) {row=std::move(pending.front());pending.pop_front();}
          else if(stopping)break;
        }
        if(mark) {
          stream.flush();std::lock_guard<std::mutex> lock(mutex);flushed=mark;changed.notify_all();
        } else {
          if(row.sequence!=written+1)throw std::runtime_error("Ledger sequence mismatch");
          write(row);std::lock_guard<std::mutex> lock(mutex);++written;
        }
      }
      stream.flush();std::lock_guard<std::mutex> lock(mutex);flushed=written;
    } catch(...) {std::lock_guard<std::mutex> lock(mutex);writeError=std::current_exception();}
    writerCpu=cpu()-start;changed.notify_all();
  }
public:
  void open(const std::string& path,bool enabled,bool retainSession=false) {
    if(enabled && retainSession)throw std::runtime_error("Session RAM and async ledger are mutually exclusive");
    sessionRam=retainSession;
    asynchronous=enabled;stream.exceptions(std::ios::badbit|std::ios::failbit);stream.open(path);
    if(sessionRam) {
      session.reserve(sessionCapacity);
      // Include the whole ledger object and64KiB conservative fixed allowance
      // for stream/deque bookkeeping, besides the reserved record storage.
      sessionOwnedBytes=sizeof(*this)+65536+session.capacity()*sizeof(LedgerRecord);
      if(sessionOwnedBytes>sessionByteLimit)throw std::runtime_error("Session ledger reserved capacity exceeds8GiB");
    }
    if(asynchronous)writer=std::thread([this]{work();});
  }
  void raw(const std::string& kind,int64_t ns3,int64_t monotonic,const std::string& fields) {
    if(!asynchronous && !sessionRam) {
      ++attempted;++captured;
      std::string line;line.reserve(kind.size()+fields.size()+96);
      line+="{\"kind\":\"";line+=kind;line+="\",\"ns3_ns\":";LedgerText::integer(line,ns3);
      line+=",\"monotonic_ns\":";LedgerText::integer(line,monotonic);line+=fields;line+="}\n";
      stream.write(line.data(),line.size());
      ++written;return;
    }
    LedgerRecord row;row.kind=kind;row.ns3=ns3;row.monotonic=monotonic;row.fields=fields;capture(std::move(row));
  }
  void capture(LedgerRecord row) {
    if(sessionRam) {
      ++attempted;
      // Count reserved record storage, both string capacities (including SSO
      // conservatively), and64 bytes/string allocation/alignment allowance.
      // This bounded owned-capacity accounting is deliberately not an RSS claim.
      const uint64_t owned=row.kind.capacity()+1+row.fields.capacity()+1+128;
      if(session.size()>=sessionCapacity || owned>sessionByteLimit-sessionOwnedBytes)
        throw std::runtime_error("Session ledger32M/8GiB capacity exceeded; captured prefix retained");
      row.sequence=++captured;sessionOwnedBytes+=owned;
      maxOwnedBytes=std::max<uint64_t>(maxOwnedBytes,sizeof(row)+owned);
      session.push_back(std::move(row));peak=std::max(peak,captured-written);return;
    }
    std::lock_guard<std::mutex> lock(mutex);++attempted;
    if(writeError)std::rethrow_exception(writeError);
    // captured-written includes the writer's inflight row, not just deque size.
    if(captured-written>=capacity)throw std::runtime_error("Ledger pending capacity16384 exceeded");
    row.sequence=++captured;
    maxOwnedBytes=std::max<uint64_t>(maxOwnedBytes,sizeof(row)+row.kind.capacity()+row.fields.capacity());
    pending.push_back(std::move(row));peak=std::max(peak,captured-written);changed.notify_one();
  }
  uint64_t barrier() {
    if(!asynchronous)return captured; // Serial and RAM modes do not wait for a writer.
    std::unique_lock<std::mutex> lock(mutex);const auto target=captured;flushTarget=target;changed.notify_one();
    changed.wait(lock,[&]{return flushed>=target || writeError;});
    if(writeError)std::rethrow_exception(writeError);
    return target;
  }
  void finish() {
    if(sessionRam) {
      while(written<captured) {
        const auto& row=session[written];
        if(row.sequence!=written+1)throw std::runtime_error("Session ledger sequence mismatch");
        write(row);++written;
      }
    }
    if(writer.joinable()) {
      {std::lock_guard<std::mutex> lock(mutex);stopping=true;changed.notify_one();}
      writer.join();
    }
    if(writeError)std::rethrow_exception(writeError);
    stream.flush();
    if(attempted!=captured || captured!=written)throw std::runtime_error("Ledger captured/written mismatch");
  }
  void status(const std::string& path,int64_t finalNs3,int64_t modelCpu,const std::string& error) {
    std::ofstream out(path);out.exceptions(std::ios::badbit|std::ios::failbit);
    out<<"{\"async\":"<<(asynchronous?"true":"false")<<",\"captured\":"<<captured<<",\"written\":"<<written
      <<",\"attempted\":"<<attempted<<",\"pending_capacity_records\":"<<(sessionRam?sessionCapacity:capacity)<<",\"peak_pending_including_inflight\":"<<peak
      <<",\"max_record_owned_bytes\":"<<maxOwnedBytes<<",\"writer_cpu_ns\":"<<writerCpu
      <<",\"model_cpu_ns\":"<<modelCpu<<",\"final_ns3_ns\":"<<finalNs3<<",\"failed\":"<<(error.empty()?"false":"true");
    if(sessionRam)out<<",\"mode\":\"session-ram-v1\",\"record_size_bytes\":"<<sizeof(LedgerRecord)
      <<",\"reserved_capacity_records\":"<<session.capacity()<<",\"owned_capacity_bytes\":"<<sessionOwnedBytes
      <<",\"owned_capacity_limit_bytes\":"<<sessionByteLimit<<",\"capacity_accounting\":\"reserved vector+ledger object+64KiB bookkeeping+string capacities+64B per string allowance; not RSS\"";
    out<<"}\n";
    out.close();
  }
};
