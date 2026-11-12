// NET-01 isolated all-byte transport. No ROS, robot controls, policy or host NICs.
#include "ns3/core-module.h"
#include "ns3/network-module.h"
#include "ns3/internet-module.h"
#include "ns3/wifi-module.h"
#include "ns3/csma-module.h"
#include "ns3/mobility-module.h"
#include "ns3/propagation-module.h"
#include "network_config.h"
#include "event_ledger.h"
#include <array>
#include <algorithm>
#include <deque>
#include <stdexcept>
#include <cmath>
#include <chrono>
#include <ctime>
#include <fstream>
#include <iomanip>
#include <iostream>
#include <map>
#include <set>
#include <sstream>
#include <vector>
#include <unistd.h>

using namespace ns3;
static constexpr uint32_t WIRE_HEADER=36, CHUNK=1200-WIRE_HEADER;
static EventLedger ledger;
static bool asyncLedger=false,simulatorDestroyAttempted=false;
static std::string ledgerMode="serial";
static std::string outputDirectory;
static int64_t finalNs3=0,modelCpuStart=0;
static std::map<std::string,uint64_t> counts;
static bool controlTrace=false;
static std::string nativeTransport="udp";
static bool cpuProfile=false;
static int64_t activeHorizon=0;
static uint64_t outputMessages=0,outputBytes=0;
static int64_t outputWall=0,outputCpu=0;
static int64_t mono() {
  return std::chrono::duration_cast<std::chrono::nanoseconds>(
      std::chrono::steady_clock::now().time_since_epoch()).count();
}
static int64_t threadCpu() {
  timespec value;clock_gettime(CLOCK_THREAD_CPUTIME_ID,&value);
  return int64_t(value.tv_sec)*1000000000+value.tv_nsec;
}
enum CpuCategory {FieldsCpu,EventCpu,SniffCpu,TraceCpu,DropCpu,ReceiveCpu,TransmitCpu,CpuCategories};
static const char* cpuNames[]={"fields","event","sniff","packet_trace","rx_drop","receive","transmit"};
struct CpuTotal {uint64_t calls=0;int64_t inclusive=0,exclusive=0;};
static std::array<CpuTotal,CpuCategories> cpuTotals;
struct CpuScope {
  CpuCategory category;CpuScope* parent=nullptr;int64_t begin=0,children=0;
  static CpuScope* current;
  explicit CpuScope(CpuCategory value):category(value) {
    if(cpuProfile) {parent=current;begin=threadCpu();current=this;}
  }
  ~CpuScope() {
    if(!cpuProfile)return;
    const auto elapsed=threadCpu()-begin;auto& total=cpuTotals[category];
    ++total.calls;total.inclusive+=elapsed;total.exclusive+=elapsed-children;
    if(parent)parent->children+=elapsed;
    current=parent;
  }
};
CpuScope* CpuScope::current=nullptr;
static void controlBoundary(const std::string& kind,const std::string& fields="") {
  if(!controlTrace)return;
  const auto line="NET01_CONTROL {\"kind\":\""+kind+"\",\"monotonic_ns\":"+std::to_string(mono())+
    ",\"thread_cpu_ns\":"+std::to_string(threadCpu())+",\"ns3_ns\":"+std::to_string(Simulator::Now().GetNanoSeconds())+
    ",\"horizon_ns\":"+std::to_string(activeHorizon)+fields+"}\n";
  NS_ABORT_MSG_IF(::write(STDERR_FILENO,line.data(),line.size())!=static_cast<ssize_t>(line.size()),"Diagnostic boundary write failed");
}
static void cpuBoundary(const std::string& kind) {
  if(!cpuProfile)return;
  std::string fields=",\"cumulative_cpu\":{";
  for(unsigned i=0;i<CpuCategories;++i) {
    if(i)fields+=",";
    const auto& total=cpuTotals[i];
    fields+="\""+std::string(cpuNames[i])+"\":{\"calls\":"+std::to_string(total.calls)+
      ",\"inclusive_ns\":"+std::to_string(total.inclusive)+",\"exclusive_ns\":"+std::to_string(total.exclusive)+"}";
  }
  fields+="},\"active_scope\":\""+std::string(CpuScope::current?cpuNames[CpuScope::current->category]:"none")+"\"";
  controlBoundary(kind,fields);
}
static void event(const std::string& kind,const std::string& fields="") {
  CpuScope measure(EventCpu);
  ++counts[kind];
  ledger.raw(kind,Simulator::Now().GetNanoSeconds(),mono(),fields);
}
static LedgerRecord primitiveRecord(const std::string& kind,LedgerRecord::Layout layout) {
  ++counts[kind];LedgerRecord row;row.kind=kind;row.layout=layout;
  row.ns3=Simulator::Now().GetNanoSeconds();row.monotonic=mono();return row;
}
class Fragment : public Header {
public:
  uint64_t id=0,source=0;
  uint8_t from=0,to=0;
  uint16_t flow=0;
  uint32_t offset=0,total=0,length=0;
  static TypeId GetTypeId() {static TypeId t=TypeId("net01::Fragment").SetParent<Header>().AddConstructor<Fragment>();return t;}
  TypeId GetInstanceTypeId() const override {return GetTypeId();}
  uint32_t GetSerializedSize() const override {return WIRE_HEADER;}
  void Serialize(Buffer::Iterator i) const override {
    i.WriteHtonU32(0x4e455431);i.WriteHtonU64(id);i.WriteU8(from);i.WriteU8(to);i.WriteHtonU16(flow);
    i.WriteHtonU32(offset);i.WriteHtonU32(total);i.WriteHtonU32(length);i.WriteHtonU64(source);
  }
  uint32_t Deserialize(Buffer::Iterator i) override {
    NS_ABORT_MSG_IF(i.ReadNtohU32()!=0x4e455431,"Invalid NET01 frame magic");
    id=i.ReadNtohU64();from=i.ReadU8();to=i.ReadU8();flow=i.ReadNtohU16();
    offset=i.ReadNtohU32();total=i.ReadNtohU32();length=i.ReadNtohU32();source=i.ReadNtohU64();return WIRE_HEADER;
  }
  void Print(std::ostream& o) const override {o<<id<<":"<<offset<<"/"<<total;}
};
static std::string fields(const Fragment& h) {
  CpuScope measure(FieldsCpu);
  return ",\"message_id\":"+std::to_string(h.id)+",\"from\":"+std::to_string(h.from)+
    ",\"to\":"+std::to_string(h.to)+",\"flow\":"+std::to_string(h.flow)+
    ",\"offset\":"+std::to_string(h.offset)+",\"total\":"+std::to_string(h.total)+
    ",\"body_bytes\":"+std::to_string(h.length)+",\"source_stamp_ns\":"+std::to_string(h.source);
}
struct Message {
  Fragment h;
  std::vector<uint8_t> data;
  std::vector<bool> pieces;
  uint32_t received=0;
};
static std::map<uint64_t,Message> pending;
static std::set<uint64_t> completed,expired;
static uint64_t discardId=0;
static uint32_t discardOffset=0;
static void expire(uint64_t id) {
  auto it=pending.find(id);
  if(it!=pending.end()) {event("incomplete_expired",fields(it->second.h)+",\"received_bytes\":"+std::to_string(it->second.received));pending.erase(it);expired.insert(id);}
}
static void receiveFragment(Ptr<Socket> socket,Ptr<Packet> packet,const std::string& kind) {
  NS_ABORT_MSG_IF(packet->GetSize()<WIRE_HEADER,"Truncated NET01 UDP frame");
  Fragment h;packet->RemoveHeader(h);
  event(kind,fields(h)+(kind=="udp_rx"?",\"packet_uid\":"+std::to_string(packet->GetUid()):""));
  NS_ABORT_MSG_IF(h.to!=socket->GetNode()->GetId() && !(h.to==0 && socket->GetNode()->GetId()==4),"Wrong receiver");
  NS_ABORT_MSG_IF(h.length!=packet->GetSize() || !h.total || h.offset%CHUNK || h.offset+h.length>h.total || h.length!=std::min(CHUNK,h.total-h.offset),"Invalid fragment extent");
  if(h.id==discardId && h.offset==discardOffset) {event("test_receiver_discard_fragment",fields(h));return;}
  if(completed.count(h.id)||expired.count(h.id)) {event("late_or_duplicate_fragment",fields(h));return;}
  auto [it,newMessage]=pending.try_emplace(h.id);
  auto& m=it->second;
  if(newMessage) {m.h=h;m.data.resize(h.total);m.pieces.resize((h.total+CHUNK-1)/CHUNK);Simulator::Schedule(Seconds(kReassemblyDeadline),&expire,h.id);}
  NS_ABORT_MSG_IF(m.h.total!=h.total || m.h.from!=h.from || m.h.to!=h.to || m.h.flow!=h.flow || m.h.source!=h.source,"Identity changed within message");
  auto index=h.offset/CHUNK;
  if(m.pieces[index]) {event("duplicate_fragment",fields(h));return;}
  // The only message data write uses bytes copied from a real ns3 socket receive.
  packet->CopyData(m.data.data()+h.offset,h.length);m.pieces[index]=true;m.received+=h.length;
  if(m.received==h.total) {
    event("message_deliver",fields(h));
    const bool detailed=controlTrace && m.data.size()>=16384;
    const auto outputFields=",\"message_id\":"+std::to_string(h.id)+",\"bytes\":"+std::to_string(m.data.size());
    if(detailed)controlBoundary("rx_output_begin",outputFields);
    if(detailed)cpuBoundary("cpu_large_output_checkpoint");
    const auto outputBeginMono=controlTrace?mono():0,outputBeginCpu=controlTrace?threadCpu():0;
    std::cout<<"RX "<<unsigned(h.from)<<" "<<unsigned(h.to)<<" "<<h.flow<<" "<<h.id<<" "<<h.source<<" "<<Simulator::Now().GetNanoSeconds()<<" "<<m.data.size()<<"\n";
    std::cout.write(reinterpret_cast<const char*>(m.data.data()),m.data.size());std::cout<<"\n";std::cout.flush();
    if(controlTrace) {++outputMessages;outputBytes+=m.data.size();outputWall+=mono()-outputBeginMono;outputCpu+=threadCpu()-outputBeginCpu;}
    if(detailed)controlBoundary("rx_output_end",outputFields);
    completed.insert(h.id);pending.erase(it);
  }
}
static void receive(Ptr<Socket> socket) {
  CpuScope measure(ReceiveCpu);
  Address address;
  while(auto packet=socket->RecvFrom(address))receiveFragment(socket,packet,"udp_rx");
}
static void simpleTrace(std::string kind,uint32_t node,Ptr<const Packet> packet) {
  CpuScope measure(TraceCpu);
  if(asyncLedger || ledgerMode=="session-ram-v1") {
    auto row=primitiveRecord(kind,LedgerRecord::Packet);row.node=node;row.packetUid=packet->GetUid();row.packetBytes=packet->GetSize();
    ledger.capture(std::move(row));return;
  }
  std::string values;values.reserve(112);
  values+=",\"node\":";LedgerText::integer(values,node);
  values+=",\"packet_uid\":";LedgerText::integer(values,packet->GetUid());
  values+=",\"packet_bytes\":";LedgerText::integer(values,packet->GetSize());
  event(kind,values);
}
static void rxDrop(uint32_t node,Ptr<const Packet> packet,WifiPhyRxfailureReason reason) {
  CpuScope measure(DropCpu);
  if(asyncLedger || ledgerMode=="session-ram-v1") {
    auto row=primitiveRecord("phy_rx_drop",LedgerRecord::Drop);row.node=node;row.packetUid=packet->GetUid();row.packetBytes=packet->GetSize();row.reason=static_cast<unsigned>(reason);
    ledger.capture(std::move(row));return;
  }
  event("phy_rx_drop",",\"node\":"+std::to_string(node)+",\"packet_uid\":"+
      std::to_string(packet->GetUid())+",\"packet_bytes\":"+std::to_string(packet->GetSize())+
      ",\"reason\":"+std::to_string(static_cast<unsigned>(reason)));
}
static void sniff(uint32_t node,Ptr<const Packet> packet,uint16_t freq,WifiTxVector tx,MpduInfo mpdu,SignalNoiseDbm power,uint16_t sta) {
  CpuScope measure(SniffCpu);
  if(asyncLedger || ledgerMode=="session-ram-v1") {
    auto row=primitiveRecord("wifi_sniffer_rx",LedgerRecord::Sniff);row.node=node;row.packetUid=packet->GetUid();row.packetBytes=packet->GetSize();row.frequency=freq;row.signal=power.signal;row.noise=power.noise;
    ledger.capture(std::move(row));return;
  }
  std::string values;values.reserve(240);
  values+=",\"node\":";LedgerText::integer(values,node);
  values+=",\"packet_uid\":";LedgerText::integer(values,packet->GetUid());
  values+=",\"packet_bytes\":";LedgerText::integer(values,packet->GetSize());
  values+=",\"frequency_mhz\":";LedgerText::integer(values,freq);
  values+=",\"signal_dbm\":";LedgerText::general12(values,power.signal);
  values+=",\"noise_dbm\":";LedgerText::general12(values,power.noise);
  values+=",\"snr_db\":";LedgerText::general12(values,power.signal-power.noise);
  event("wifi_sniffer_rx",values);
}
static void nodeEvent(const std::string& kind,uint32_t node) {
  if(asyncLedger || ledgerMode=="session-ram-v1") {auto row=primitiveRecord(kind,LedgerRecord::Node);row.node=node;ledger.capture(std::move(row));}
  else event(kind,",\"node\":"+std::to_string(node));
}
static void retry(uint32_t node,Mac48Address address) {CpuScope measure(TraceCpu);nodeEvent("mac_data_retry",node);}
static void finalDrop(uint32_t node,Mac48Address address) {CpuScope measure(TraceCpu);nodeEvent("mac_final_data_drop",node);}
static void transmit(Ptr<Socket> socket,Ipv4Address destination,Fragment identity,std::vector<uint8_t> body) {
  CpuScope measure(TransmitCpu);
  for(uint32_t offset=0;offset<body.size();offset+=CHUNK) {
    auto h=identity;h.offset=offset;h.length=std::min(CHUNK,static_cast<uint32_t>(body.size())-offset);
    auto packet=Create<Packet>(body.data()+offset,h.length);packet->AddHeader(h);
    event("udp_tx",fields(h)+",\"packet_uid\":"+std::to_string(packet->GetUid()));
    int sent=socket->SendTo(packet,0,InetSocketAddress(destination,19001));
    if(sent<0)event("udp_send_error",fields(h)+",\"socket_errno\":"+std::to_string(socket->GetErrno()));
  }
}

#include "../../net01d/followup02/native/tcp_stream_draft.inc"

static int modelMain(int argc,char** argv) {
  std::string directory,profile="B";
  struct StepTrace {int64_t horizon,beginMono,beginCpu,beginNs3,endMono,endCpu,endNs3;};
  std::vector<StepTrace> controlSteps;
  CommandLine cmd;cmd.AddValue("output", "New output directory",directory);cmd.AddValue("profile","Locked B or C",profile);cmd.AddValue("controlTrace","Diagnostic STEP boundary timestamps only",controlTrace);
  cmd.AddValue("transport","Explicit udp, tcp-v1 or tcp-mtu-v2; no fallback",nativeTransport);
  cmd.AddValue("cpuProfile","Diagnostic own-callback cumulative CPU only; use with controlTrace",cpuProfile);
  cmd.AddValue("asyncLedger","Move diagnostic formatting to one bounded writer",asyncLedger);
  cmd.AddValue("ledgerMode","Explicit serial or session-ram-v1 diagnostic storage",ledgerMode);cmd.Parse(argc,argv);
  // asyncLedger remains opt-in; the reference keeps serial formatting/buffering.
  NS_ABORT_MSG_IF(directory.empty() || (profile!="B" && profile!="C") || (nativeTransport!="udp" && nativeTransport!="tcp-v1" && nativeTransport!="tcp-mtu-v2"),"Explicit output and locked profile needed");
  outputDirectory=directory;
  if(ledgerMode!="serial" && ledgerMode!="session-ram-v1")throw std::runtime_error("Unknown ledger mode");
  ledger.open(directory+"/packet-ledger.jsonl",asyncLedger,ledgerMode=="session-ram-v1");
  std::ofstream(directory+"/configured-lock.json")<<kRawConfig;
  RngSeedManager::SetSeed(kSeed);RngSeedManager::SetRun(kRun);
  Config::SetDefault("ns3::WifiMacQueue::MaxSize",QueueSizeValue(QueueSize(std::to_string(kQueuePackets)+"p")));
  Config::SetDefault("ns3::WifiMacQueue::MaxDelay",TimeValue(Seconds(kQueueDelay)));
  Config::SetDefault("ns3::Ipv4L3Protocol::DefaultTtl",UintegerValue(64));
  NodeContainer nodes;nodes.Create(5); // AP0, STA1..3, wired central4; business id0 maps to central4.
  MobilityHelper mobility;mobility.SetMobilityModel("ns3::ConstantPositionMobilityModel");mobility.Install(nodes);
  for(uint32_t i=0;i<5;++i)nodes.Get(i)->GetObject<MobilityModel>()->SetPosition(Vector(kPositions[i][0],kPositions[i][1],kPositions[i][2]));
  auto loss=CreateObject<LogDistancePropagationLossModel>();loss->SetAttribute("Exponent",DoubleValue(profile=="B"?kExponentB:kExponentC));loss->SetReference(1.0,kReferenceLoss);
  // Normal mode is exactly transparent. Only the independent no-motion fault
  // command blocks the real channel; do not force an already-OFF STA PHY off.
  auto faultGate=CreateObject<RangePropagationLossModel>();
  faultGate->SetAttribute("MaxRange",DoubleValue(1e9));loss->SetNext(faultGate);
  auto channel=CreateObject<YansWifiChannel>();channel->SetPropagationLossModel(loss);channel->SetPropagationDelayModel(CreateObject<ConstantSpeedPropagationDelayModel>());
  YansWifiPhyHelper phy;phy.SetChannel(channel);phy.SetErrorRateModel("ns3::NistErrorRateModel");
  phy.Set("ChannelSettings",StringValue("{42, 80, BAND_5GHZ, 0}"));
  double power=profile=="B"?kTxB:kTxC;
  phy.Set("TxPowerStart",DoubleValue(power));phy.Set("TxPowerEnd",DoubleValue(power));phy.Set("RxNoiseFigure",DoubleValue(7));
  phy.Set("RxSensitivity",DoubleValue(-101));phy.Set("CcaEdThreshold",DoubleValue(-62));phy.Set("CcaSensitivity",DoubleValue(-82));
  phy.Set("Antennas",UintegerValue(1));phy.Set("MaxSupportedTxSpatialStreams",UintegerValue(1));phy.Set("MaxSupportedRxSpatialStreams",UintegerValue(1));
  WifiHelper wifi;wifi.SetStandard(WIFI_STANDARD_80211ac);
  wifi.SetRemoteStationManager("ns3::ConstantRateWifiManager","DataMode",StringValue(profile=="B"?"VhtMcs9":"VhtMcs3"),"ControlMode",StringValue("OfdmRate6Mbps"),"NonUnicastMode",StringValue("OfdmRate6Mbps"),"MaxSsrc",UintegerValue(7),"MaxSlrc",UintegerValue(4),"RtsCtsThreshold",UintegerValue(65535),"FragmentationThreshold",UintegerValue(65535));
  WifiMacHelper mac;Ssid ssid("net01-fixed");
  mac.SetType("ns3::ApWifiMac","Ssid",SsidValue(ssid),"QosSupported",BooleanValue(true));
  NetDeviceContainer allWifi=wifi.Install(phy,mac,nodes.Get(0));
  mac.SetType("ns3::StaWifiMac","Ssid",SsidValue(ssid),"ActiveProbing",BooleanValue(false),"QosSupported",BooleanValue(true));
  for(uint32_t i=1;i<=3;++i)allWifi.Add(wifi.Install(phy,mac,nodes.Get(i)));
  for(uint32_t i=0;i<4;++i) {
    auto dev=DynamicCast<WifiNetDevice>(allWifi.Get(i));dev->SetMtu(kMtu);
    dev->GetHtConfiguration()->SetShortGuardIntervalSupported(false);
    auto m=dev->GetMac();auto ph=dev->GetPhy();
    NS_ABORT_MSG_IF(!m->TraceConnectWithoutContext("MacTx",MakeBoundCallback(&simpleTrace,std::string("mac_tx"),i)),"MacTx trace unavailable");
    m->TraceConnectWithoutContext("MacRx",MakeBoundCallback(&simpleTrace,std::string("mac_rx"),i));
    ph->TraceConnectWithoutContext("PhyTxEnd",MakeBoundCallback(&simpleTrace,std::string("phy_tx_end"),i));
    ph->TraceConnectWithoutContext("PhyRxEnd",MakeBoundCallback(&simpleTrace,std::string("phy_rx_end"),i));
    ph->TraceConnectWithoutContext("PhyTxDrop",MakeBoundCallback(&simpleTrace,std::string("phy_tx_drop"),i));
    ph->TraceConnectWithoutContext("PhyRxDrop",MakeBoundCallback(&rxDrop,i));
    ph->TraceConnectWithoutContext("MonitorSnifferRx",MakeBoundCallback(&sniff,i));
    dev->GetRemoteStationManager()->TraceConnectWithoutContext("MacTxDataFailed",MakeBoundCallback(&retry,i));
    dev->GetRemoteStationManager()->TraceConnectWithoutContext("MacTxFinalDataFailed",MakeBoundCallback(&finalDrop,i));
    phy.EnablePcap(directory+"/wifi",dev,true);
  }
  CsmaHelper wire;wire.SetChannelAttribute("DataRate",DataRateValue(DataRate(1000000000)));wire.SetChannelAttribute("Delay",TimeValue(NanoSeconds(1000)));wire.SetDeviceAttribute("Mtu",UintegerValue(kMtu));
  wire.SetQueue("ns3::DropTailQueue<Packet>","MaxSize",QueueSizeValue(QueueSize(std::to_string(kQueuePackets)+"p")));
  NodeContainer wired;wired.Add(nodes.Get(0));wired.Add(nodes.Get(4));auto wiredDevices=wire.Install(wired);
  InternetStackHelper internet;internet.Install(nodes);
  Ipv4AddressHelper ip;ip.SetBase("10.31.0.0","255.255.255.0","0.0.0.1");auto apIp=ip.Assign(NetDeviceContainer(allWifi.Get(0)));
  ip.SetBase("10.31.0.0","255.255.255.0","0.0.0.11");NetDeviceContainer staDevices;for(int i=1;i<=3;++i)staDevices.Add(allWifi.Get(i));auto staIps=ip.Assign(staDevices);
  ip.SetBase("10.32.0.0","255.255.255.0");auto wiredIps=ip.Assign(wiredDevices);Ipv4GlobalRoutingHelper::PopulateRoutingTables();
  std::array<Ipv4Address,4> addresses={wiredIps.GetAddress(1),staIps.GetAddress(0),staIps.GetAddress(1),staIps.GetAddress(2)};
  std::array<Ptr<Socket>,4> sockets;
  if(nativeTransport=="udp") {
  for(int i=0;i<4;++i) {sockets[i]=Socket::CreateSocket(nodes.Get(i==0?4:i),UdpSocketFactory::GetTypeId());NS_ABORT_MSG_IF(sockets[i]->Bind(InetSocketAddress(Ipv4Address::GetAny(),19001))<0,"UDP bind failed");sockets[i]->SetIpTos(0);sockets[i]->SetRecvCallback(MakeCallback(&receive));}
  } else setupTcp(nodes,addresses);
  event("model_ready",",\"profile\":\""+profile+"\",\"host_network_changed\":false,\"ROS_Node\":0");
  std::cout<<"READY\n"<<std::flush;
  int64_t knownHorizon=0;
  std::string line;
  while(std::getline(std::cin,line)) {
    std::istringstream in(line);std::string op;in>>op;
    if(op=="SEND" || op=="SENDAT") {
      unsigned from,to,flow;uint64_t id,source;uint32_t size;
      in>>from>>to>>flow>>id>>source>>size;
      int64_t admission=Simulator::Now().GetNanoSeconds();
      if(op=="SENDAT")in>>admission;
      NS_ABORT_MSG_IF(!in || from>3 || to>3 || from==to || !size,"Invalid SEND command");
      NS_ABORT_MSG_IF(admission<Simulator::Now().GetNanoSeconds() || (op=="SENDAT" && admission>knownHorizon),"Injection outside current/actually observed horizon");
      std::vector<uint8_t> body(size);std::cin.read(reinterpret_cast<char*>(body.data()),size);
      NS_ABORT_MSG_IF(std::cin.gcount()!=size || std::cin.get()!='\n',"Truncated IPC body");
      event("ipc_ingress",",\"from\":"+std::to_string(from)+",\"to\":"+std::to_string(to)+",\"flow\":"+std::to_string(flow)+",\"message_id\":"+std::to_string(id)+",\"body_bytes\":"+std::to_string(size)+",\"source_stamp_ns\":"+std::to_string(source)+",\"admission_ns\":"+std::to_string(admission));
      Fragment h;h.id=id;h.from=from;h.to=to;h.flow=flow;h.total=size;h.source=source;
      if(nativeTransport!="udp") {
        if(admission==Simulator::Now().GetNanoSeconds())tcpTransmit(h,std::move(body));
        else Simulator::Schedule(NanoSeconds(admission-Simulator::Now().GetNanoSeconds()),&tcpTransmit,h,std::move(body));
      } else {
      if(admission==Simulator::Now().GetNanoSeconds())transmit(sockets[from],addresses[to],h,std::move(body));
      else Simulator::Schedule(NanoSeconds(admission-Simulator::Now().GetNanoSeconds()),&transmit,sockets[from],addresses[to],h,std::move(body));
      }
      // body is discarded here: receive reconstruction has no access to source bytes.
    } else if(op=="KNOWN") {
      int64_t latest;in>>latest;
      NS_ABORT_MSG_IF(!in || latest<knownHorizon || latest<Simulator::Now().GetNanoSeconds(),"Observed clock moved backwards");
      knownHorizon=latest;event("actual_clock_horizon_known",",\"latest_ns\":"+std::to_string(latest));
    } else if(op=="POSITION") {
      uint32_t robot;double x,y,z;in>>robot>>x>>y>>z;
      NS_ABORT_MSG_IF(!in || robot<1 || robot>3 || !std::isfinite(x) || !std::isfinite(y) || !std::isfinite(z),"Invalid network-only mobility input");
      nodes.Get(robot)->GetObject<MobilityModel>()->SetPosition(Vector(x,y,z));
      std::ostringstream s;s<<std::setprecision(15)<<",\"robot\":"<<robot<<",\"xyz\":["<<x<<","<<y<<","<<z<<"],\"source\":\"GT_NETWORK_CONTROL_ONLY\"";
      event("network_mobility_control",s.str());
    } else if(op=="STEP") {
      int64_t horizon;in>>horizon;
      NS_ABORT_MSG_IF(!in || horizon<Simulator::Now().GetNanoSeconds() || horizon-Simulator::Now().GetNanoSeconds()>100000000,"Invalid/nonmonotonic/>.1s horizon");
      StepTrace trace{};
      if(controlTrace)trace={horizon,mono(),threadCpu(),Simulator::Now().GetNanoSeconds(),0,0,0};
      activeHorizon=horizon;
      outputMessages=outputBytes=0;outputWall=outputCpu=0;
      cpuBoundary("cpu_step_begin");
      controlBoundary("step_begin");
      Simulator::Stop(NanoSeconds(horizon-Simulator::Now().GetNanoSeconds()));Simulator::Run();
      controlBoundary("step_end",",\"output_messages\":"+std::to_string(outputMessages)+",\"output_bytes\":"+std::to_string(outputBytes)+
        ",\"output_wall_ns\":"+std::to_string(outputWall)+",\"output_cpu_ns\":"+std::to_string(outputCpu));
      if(controlTrace) {
        trace.endCpu=threadCpu();trace.endMono=mono();trace.endNs3=Simulator::Now().GetNanoSeconds();controlSteps.push_back(trace);
      }
      cpuBoundary("cpu_step_end");
      event("horizon_return",",\"requested_horizon_ns\":"+std::to_string(horizon));
      controlBoundary("ledger_barrier_begin");
      ledger.barrier();
      controlBoundary("ledger_barrier_end");
      std::cout<<"STEP "<<Simulator::Now().GetNanoSeconds()<<"\n"<<std::flush;
    } else if(op=="RADIO") {
      int enabled;in>>enabled;
      faultGate->SetAttribute("MaxRange",DoubleValue(enabled?1e9:0.));
      event(enabled?"channel_restored":"channel_blackout",",\"fault_definition\":\"transparent-range-gate-v1\"");
    } else if(op=="DISCARD") {
      if(nativeTransport!="udp")throw std::runtime_error("DISCARD is a UDP-only diagnostic; no TCP fallback");
      in>>discardId>>discardOffset;
      event("test_fault_configured",",\"message_id\":"+std::to_string(discardId)+",\"offset\":"+std::to_string(discardOffset));
    } else if(op=="END") {break;}
    else NS_ABORT_MSG("Unknown IPC command: "<<op);
  }
  event("transport_end");
  if(nativeTransport!="udp"){saveTcpConfiguration(directory);tcpEnding=true;}
  if(controlTrace) {
    std::ofstream timing(directory+"/control-step-trace.jsonl");
    for(const auto& t:controlSteps)timing<<"{\"horizon_ns\":"<<t.horizon<<",\"begin_monotonic_ns\":"<<t.beginMono
      <<",\"begin_thread_cpu_ns\":"<<t.beginCpu<<",\"begin_ns3_ns\":"<<t.beginNs3<<",\"end_monotonic_ns\":"<<t.endMono
      <<",\"end_thread_cpu_ns\":"<<t.endCpu<<",\"end_ns3_ns\":"<<t.endNs3<<"}\n";
  }
  finalNs3=Simulator::Now().GetNanoSeconds();
  simulatorDestroyAttempted=true;Simulator::Destroy();
  ledger.finish();
  ledger.status(directory+"/ledger-status.json",finalNs3,threadCpu()-modelCpuStart,"");
  std::ofstream summary(directory+"/native-summary.json");summary<<"{\"counts\":{";bool first=true;for(auto& [name,n]:counts){if(!first)summary<<",";first=false;summary<<"\""<<name<<"\":"<<n;}summary<<"},\"pending_incomplete\":"<<pending.size()<<",\"completed_messages\":"<<completed.size()<<",\"ns3_ns\":"<<finalNs3<<"}\n";
  return 0;
}

int main(int argc,char** argv) {
  modelCpuStart=threadCpu();
  try {return modelMain(argc,argv);}
  catch(const std::exception& error) {
    const std::string firstError=error.what();
    std::cerr<<"NET01 ledger/model failure: "<<firstError<<"\n";
    if(nativeTransport!="udp") {
      tcpEnding=true;
      try {saveTcpConfiguration(outputDirectory);}
      catch(const std::exception& save) {std::cerr<<"TCP evidence save: "<<save.what()<<"\n";}
    }
    if(!simulatorDestroyAttempted) {
      finalNs3=Simulator::Now().GetNanoSeconds();
      try {simulatorDestroyAttempted=true;Simulator::Destroy();}
      catch(const std::exception& cleanup) {std::cerr<<"Simulator cleanup: "<<cleanup.what()<<"\n";}
    }
    try {ledger.finish();}catch(const std::exception& cleanup) {std::cerr<<"Ledger cleanup: "<<cleanup.what()<<"\n";}
    try {ledger.status(outputDirectory+"/ledger-status.json",finalNs3,threadCpu()-modelCpuStart,firstError);}
    catch(const std::exception& save) {std::cerr<<"Ledger status save failed: "<<save.what()<<"\n";}
    return 1;
  }
}
