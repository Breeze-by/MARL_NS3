// NET-01 isolated all-byte transport. No ROS, robot controls, policy or host NICs.
#include "ns3/core-module.h"
#include "ns3/network-module.h"
#include "ns3/internet-module.h"
#include "ns3/wifi-module.h"
#include "ns3/csma-module.h"
#include "ns3/mobility-module.h"
#include "ns3/propagation-module.h"
#include "network_config.h"
#include <array>
#include <chrono>
#include <fstream>
#include <iomanip>
#include <iostream>
#include <map>
#include <set>
#include <sstream>
#include <vector>

using namespace ns3;
static constexpr uint32_t WIRE_HEADER=36, CHUNK=1200-WIRE_HEADER;
static std::ofstream ledger;
static std::map<std::string,uint64_t> counts;
static int64_t mono() {
  return std::chrono::duration_cast<std::chrono::nanoseconds>(
      std::chrono::steady_clock::now().time_since_epoch()).count();
}
static void event(const std::string& kind,const std::string& fields="") {
  ++counts[kind];
  ledger<<"{\"kind\":\""<<kind<<"\",\"ns3_ns\":"<<Simulator::Now().GetNanoSeconds()
        <<",\"monotonic_ns\":"<<mono()<<fields<<"}\n";
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
static void receive(Ptr<Socket> socket) {
  Address address;
  while(auto packet=socket->RecvFrom(address)) {
    NS_ABORT_MSG_IF(packet->GetSize()<WIRE_HEADER,"Truncated NET01 UDP frame");
    Fragment h;packet->RemoveHeader(h);
    event("udp_rx",fields(h)+",\"packet_uid\":"+std::to_string(packet->GetUid()));
    NS_ABORT_MSG_IF(h.to!=socket->GetNode()->GetId() && !(h.to==0 && socket->GetNode()->GetId()==4),"Wrong receiver");
    NS_ABORT_MSG_IF(h.length!=packet->GetSize() || !h.total || h.offset%CHUNK || h.offset+h.length>h.total || h.length!=std::min(CHUNK,h.total-h.offset),"Invalid fragment extent");
    if(h.id==discardId && h.offset==discardOffset) {event("test_receiver_discard_fragment",fields(h));continue;}
    if(completed.count(h.id)||expired.count(h.id)) {event("late_or_duplicate_fragment",fields(h));continue;}
    auto [it,newMessage]=pending.try_emplace(h.id);
    auto& m=it->second;
    if(newMessage) {m.h=h;m.data.resize(h.total);m.pieces.resize((h.total+CHUNK-1)/CHUNK);Simulator::Schedule(Seconds(kReassemblyDeadline),&expire,h.id);}
    NS_ABORT_MSG_IF(m.h.total!=h.total || m.h.from!=h.from || m.h.to!=h.to || m.h.source!=h.source,"Identity changed within message");
    auto index=h.offset/CHUNK;
    if(m.pieces[index]) {event("duplicate_fragment",fields(h));continue;}
    // The only message data write uses bytes copied from a real ns3 socket receive.
    packet->CopyData(m.data.data()+h.offset,h.length);m.pieces[index]=true;m.received+=h.length;
    if(m.received==h.total) {
      event("message_deliver",fields(h));
      std::cout<<"RX "<<unsigned(h.from)<<" "<<unsigned(h.to)<<" "<<h.id<<" "<<Simulator::Now().GetNanoSeconds()<<" "<<m.data.size()<<"\n";
      std::cout.write(reinterpret_cast<const char*>(m.data.data()),m.data.size());std::cout<<"\n";std::cout.flush();
      completed.insert(h.id);pending.erase(it);
    }
  }
}
static void simpleTrace(std::string kind,uint32_t node,Ptr<const Packet> packet) {
  event(kind,",\"node\":"+std::to_string(node)+",\"packet_uid\":"+std::to_string(packet->GetUid())+",\"packet_bytes\":"+std::to_string(packet->GetSize()));
}
static void rxDrop(uint32_t node,Ptr<const Packet> packet,WifiPhyRxfailureReason reason) {
  event("phy_rx_drop",",\"node\":"+std::to_string(node)+",\"packet_uid\":"+
      std::to_string(packet->GetUid())+",\"packet_bytes\":"+std::to_string(packet->GetSize())+
      ",\"reason\":"+std::to_string(static_cast<unsigned>(reason)));
}
static void sniff(uint32_t node,Ptr<const Packet> packet,uint16_t freq,WifiTxVector tx,MpduInfo mpdu,SignalNoiseDbm power,uint16_t sta) {
  std::ostringstream s;s<<std::setprecision(12)<<",\"node\":"<<node<<",\"packet_uid\":"<<packet->GetUid()
    <<",\"packet_bytes\":"<<packet->GetSize()<<",\"frequency_mhz\":"<<freq<<",\"signal_dbm\":"<<power.signal
    <<",\"noise_dbm\":"<<power.noise<<",\"snr_db\":"<<power.signal-power.noise;
  event("wifi_sniffer_rx",s.str());
}
static void retry(uint32_t node,Mac48Address address) {event("mac_data_retry",",\"node\":"+std::to_string(node));}
static void finalDrop(uint32_t node,Mac48Address address) {event("mac_final_data_drop",",\"node\":"+std::to_string(node));}

int main(int argc,char** argv) {
  std::string directory,profile="B";
  CommandLine cmd;cmd.AddValue("output", "New output directory",directory);cmd.AddValue("profile","Locked B or C",profile);cmd.Parse(argc,argv);
  NS_ABORT_MSG_IF(directory.empty() || (profile!="B" && profile!="C"),"Explicit output and locked profile needed");
  ledger.open(directory+"/packet-ledger.jsonl");
  NS_ABORT_MSG_IF(!ledger,"Cannot open packet ledger");
  std::ofstream(directory+"/configured-lock.json")<<kRawConfig;
  RngSeedManager::SetSeed(kSeed);RngSeedManager::SetRun(kRun);
  Config::SetDefault("ns3::WifiMacQueue::MaxSize",QueueSizeValue(QueueSize(std::to_string(kQueuePackets)+"p")));
  Config::SetDefault("ns3::WifiMacQueue::MaxDelay",TimeValue(Seconds(kQueueDelay)));
  Config::SetDefault("ns3::Ipv4L3Protocol::DefaultTtl",UintegerValue(64));
  NodeContainer nodes;nodes.Create(5); // AP0, STA1..3, wired central4; business id0 maps to central4.
  MobilityHelper mobility;mobility.SetMobilityModel("ns3::ConstantPositionMobilityModel");mobility.Install(nodes);
  for(uint32_t i=0;i<5;++i)nodes.Get(i)->GetObject<MobilityModel>()->SetPosition(Vector(kPositions[i][0],kPositions[i][1],kPositions[i][2]));
  auto loss=CreateObject<LogDistancePropagationLossModel>();loss->SetAttribute("Exponent",DoubleValue(profile=="B"?kExponentB:kExponentC));loss->SetReference(1.0,kReferenceLoss);
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
  for(int i=0;i<4;++i) {sockets[i]=Socket::CreateSocket(nodes.Get(i==0?4:i),UdpSocketFactory::GetTypeId());NS_ABORT_MSG_IF(sockets[i]->Bind(InetSocketAddress(Ipv4Address::GetAny(),19001))<0,"UDP bind failed");sockets[i]->SetIpTos(0);sockets[i]->SetRecvCallback(MakeCallback(&receive));}
  event("model_ready",",\"profile\":\""+profile+"\",\"host_network_changed\":false,\"ROS_Node\":0");
  std::cout<<"READY\n"<<std::flush;
  std::string line;
  while(std::getline(std::cin,line)) {
    std::istringstream in(line);std::string op;in>>op;
    if(op=="SEND") {
      unsigned from,to,flow;uint64_t id,source;uint32_t size;
      in>>from>>to>>flow>>id>>source>>size;
      NS_ABORT_MSG_IF(!in || from>3 || to>3 || from==to || !size,"Invalid SEND command");
      std::vector<uint8_t> body(size);std::cin.read(reinterpret_cast<char*>(body.data()),size);
      NS_ABORT_MSG_IF(std::cin.gcount()!=size || std::cin.get()!='\n',"Truncated IPC body");
      event("ipc_ingress",",\"from\":"+std::to_string(from)+",\"to\":"+std::to_string(to)+",\"message_id\":"+std::to_string(id)+",\"body_bytes\":"+std::to_string(size)+",\"source_stamp_ns\":"+std::to_string(source));
      for(uint32_t offset=0;offset<size;offset+=CHUNK) {
        Fragment h;h.id=id;h.from=from;h.to=to;h.flow=flow;h.offset=offset;h.total=size;h.length=std::min(CHUNK,size-offset);h.source=source;
        auto packet=Create<Packet>(body.data()+offset,h.length);packet->AddHeader(h);
        event("udp_tx",fields(h)+",\"packet_uid\":"+std::to_string(packet->GetUid()));
        int sent=sockets[from]->SendTo(packet,0,InetSocketAddress(addresses[to],19001));
        if(sent<0)event("udp_send_error",fields(h)+",\"socket_errno\":"+std::to_string(sockets[from]->GetErrno()));
      }
      // body is discarded here: receive reconstruction has no access to source bytes.
    } else if(op=="STEP") {
      int64_t horizon;in>>horizon;
      NS_ABORT_MSG_IF(!in || horizon<Simulator::Now().GetNanoSeconds() || horizon-Simulator::Now().GetNanoSeconds()>100000000,"Invalid/nonmonotonic/>.1s horizon");
      Simulator::Stop(NanoSeconds(horizon-Simulator::Now().GetNanoSeconds()));Simulator::Run();
      event("horizon_return",",\"requested_horizon_ns\":"+std::to_string(horizon));
      std::cout<<"STEP "<<Simulator::Now().GetNanoSeconds()<<"\n"<<std::flush;
    } else if(op=="RADIO") {
      int enabled;in>>enabled;
      for(uint32_t i=0;i<4;++i) {auto ph=DynamicCast<WifiNetDevice>(allWifi.Get(i))->GetPhy();if(enabled)ph->ResumeFromOff();else ph->SetOffMode();}
      event(enabled?"radio_on":"radio_off");
    } else if(op=="DISCARD") {
      in>>discardId>>discardOffset;
      event("test_fault_configured",",\"message_id\":"+std::to_string(discardId)+",\"offset\":"+std::to_string(discardOffset));
    } else if(op=="END") {break;}
    else NS_ABORT_MSG("Unknown IPC command: "<<op);
  }
  event("transport_end");
  std::ofstream summary(directory+"/native-summary.json");summary<<"{\"counts\":{";bool first=true;for(auto& [name,n]:counts){if(!first)summary<<",";first=false;summary<<"\""<<name<<"\":"<<n;}summary<<"},\"pending_incomplete\":"<<pending.size()<<",\"completed_messages\":"<<completed.size()<<",\"ns3_ns\":"<<Simulator::Now().GetNanoSeconds()<<"}\n";
  Simulator::Destroy();return 0;
}
