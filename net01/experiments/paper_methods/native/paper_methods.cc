// Isolated synthetic application experiments; never a ROS/Nav2 Action proxy.
#include "ns3/core-module.h"
#include "ns3/network-module.h"
#include "ns3/internet-module.h"
#include "ns3/wifi-module.h"
#include "ns3/mobility-module.h"
#include "ns3/csma-module.h"
#include "ns3/propagation-module.h"
#include "network_config.h"
#include <array>
#include <filesystem>
#include <fstream>
#include <iomanip>
#include <map>
#include <set>
#include <sstream>
#include <vector>
#include <time.h>
using namespace ns3;
static std::ofstream events;
static uint64_t ordinal=0;
static bool tcp=false,position=false,scheduled=false,connected=false,failed=false;
static Ptr<Socket> client,listener,server;
static Ptr<MobilityModel> sta;
static Ipv4Address serverIp;
static std::map<const Socket*,std::vector<uint8_t>> stream;
static std::map<uint32_t,std::vector<uint8_t>> cache;
static std::map<uint32_t,unsigned> processed,replies;
static std::map<std::string,std::set<std::pair<uint32_t,uint32_t>>> tcpSeen;
static unsigned retransmissions=0,lateRejected=0,positionApplied=0,submitted=0;
static int64_t mono() {timespec t;clock_gettime(CLOCK_MONOTONIC,&t);return int64_t(t.tv_sec)*1000000000+t.tv_nsec;}
static int64_t cpu() {timespec t;clock_gettime(CLOCK_THREAD_CPUTIME_ID,&t);return int64_t(t.tv_sec)*1000000000+t.tv_nsec;}
static std::string hex(const std::vector<uint8_t>& b) {std::ostringstream o;o<<std::hex<<std::setfill('0');for(auto v:b)o<<std::setw(2)<<unsigned(v);return o.str();}
static void log(const std::string& kind,const std::string& fields="") {
  events<<"{\"seq\":"<<++ordinal<<",\"kind\":\""<<kind<<"\",\"sim_ns\":"<<Simulator::Now().GetNanoSeconds()
        <<",\"monotonic_ns\":"<<mono()<<",\"thread_cpu_ns\":"<<cpu()<<fields<<"}\n";
}
static void error(const std::string& what) {failed=true;log("error",",\"reason\":\""+what+"\"");}
static std::vector<uint8_t> body(uint32_t id,unsigned size) {
  std::vector<uint8_t>b(size);b[0]='P';b[1]='M';b[2]='0';b[3]='1';
  for(unsigned i=0;i<4;++i)b[4+i]=uint8_t(id>>(24-8*i));
  for(unsigned i=8;i<size;++i)b[i]=uint8_t(id*31+i*17);
  return b;
}
static uint32_t idOf(const std::vector<uint8_t>& b) {uint32_t id=0;for(unsigned i=4;i<8;++i)id=(id<<8)|b[i];return id;}
static std::vector<uint8_t> frame(const std::vector<uint8_t>& b) {
  std::vector<uint8_t> v(4);for(unsigned i=0;i<4;++i)v[i]=uint8_t(b.size()>>(24-8*i));v.insert(v.end(),b.begin(),b.end());return v;
}
static void sendBytes(Ptr<Socket>s,const std::vector<uint8_t>& b,const std::string& kind) {
  auto v=frame(b);auto p=Create<Packet>(v.data(),v.size());int n=s->Send(p);
  log(kind,",\"id\":"+std::to_string(idOf(b))+",\"body_bytes\":"+std::to_string(b.size())+",\"socket_accepted_bytes\":"+std::to_string(n)+",\"body_hex\":\""+hex(b)+"\"");
  if(n!=int(v.size()))error("small complete frame not accepted by socket");
}
static void appReceive(Ptr<Socket>s,const std::vector<uint8_t>& b,bool destination) {
  unsigned n=position?128:105;
  if(b.size()!=n || b.size()<8 || b!=body(idOf(b),n)) {error("received body content mismatch");return;}
  uint32_t id=idOf(b);
  log(destination?"request_whole_rx":"reply_whole_rx",",\"id\":"+std::to_string(id)+",\"body_bytes\":"+std::to_string(b.size())+",\"body_hex\":\""+hex(b)+"\"");
  if(destination) {
    auto it=cache.find(id);
    if(it==cache.end()) {cache[id]=b;++processed[id];log("logical_process",",\"id\":"+std::to_string(id));}
    else if(it->second!=b) {error("ID reused with different actual bytes");return;}
    else log("duplicate_id_cache_reply",",\"id\":"+std::to_string(id));
    sendBytes(s,cache.at(id),"application_reply_tx"); // only bytes obtained from real Recv
  } else ++replies[id];
}
static void receive(Ptr<Socket>s) {
  bool destination=s==server;
  while(auto p=s->Recv()) {
    if(!p->GetSize())break;
    std::vector<uint8_t> v(p->GetSize());p->CopyData(v.data(),v.size());
    if(tcp) {
      auto& q=stream[PeekPointer(s)];q.insert(q.end(),v.begin(),v.end());
      while(q.size()>=4) {
        uint32_t length=0;for(unsigned i=0;i<4;++i)length=(length<<8)|q[i];
        if(length!=105) {error("invalid TCP frame length");q.clear();break;}
        if(q.size()<length+4)break;
        std::vector<uint8_t>b(q.begin()+4,q.begin()+4+length);q.erase(q.begin(),q.begin()+4+length);appReceive(s,b,destination);
      }
    } else {
      uint32_t length=0;if(v.size()>=4)for(unsigned i=0;i<4;++i)length=(length<<8)|v[i];
      if(v.size()!=length+4) {error("invalid UDP frame length");continue;}
      appReceive(s,std::vector<uint8_t>(v.begin()+4,v.end()),destination);
    }
  }
}
static void tcpTrace(std::string direction,std::string kind,Ptr<const Packet> p,const TcpHeader& h,Ptr<const TcpSocketBase>) {
  bool repeat=false;if(kind=="tx" && p->GetSize())repeat=!tcpSeen[direction].insert({h.GetSequenceNumber().GetValue(),p->GetSize()}).second;
  if(repeat)++retransmissions;
  log("tcp_"+kind,",\"direction\":\""+direction+"\",\"tcp_seq\":"+std::to_string(h.GetSequenceNumber().GetValue())+",\"tcp_ack\":"+std::to_string(h.GetAckNumber().GetValue())+",\"flags\":"+std::to_string(h.GetFlags())+",\"payload_bytes\":"+std::to_string(p->GetSize())+",\"repeated_seq_extent\":"+(repeat?"true":"false"));
}
static void attachTcp(Ptr<Socket>s,const std::string& direction) {
  s->TraceConnectWithoutContext("Tx",MakeBoundCallback(&tcpTrace,direction,std::string("tx")));
  s->TraceConnectWithoutContext("Rx",MakeBoundCallback(&tcpTrace,direction,std::string("rx")));
}
static void accept(Ptr<Socket>s,const Address&) {server=s;server->SetIpTos(0);attachTcp(server,"STA1");server->SetRecvCallback(MakeCallback(&receive));log("tcp_accept");}
static bool allow(Ptr<Socket>,const Address&) {return true;}
static void connectOk(Ptr<Socket>) {connected=true;log("tcp_connected");}
static void connectFail(Ptr<Socket>) {error("TCP connect failed");}
static void submit(uint32_t id) {++submitted;sendBytes(client,body(id,position?128:105),"application_request_tx");}
static void simple(std::string kind,unsigned node,Ptr<const Packet>p) {
  log(kind,",\"node\":"+std::to_string(node)+",\"packet_uid\":"+std::to_string(p->GetUid())+",\"packet_bytes\":"+std::to_string(p->GetSize()));
}
static void rxDrop(unsigned node,Ptr<const Packet>p,WifiPhyRxfailureReason r) {simple("phy_rx_drop",node,p);log("phy_rx_reason",",\"node\":"+std::to_string(node)+",\"reason\":"+std::to_string(unsigned(r)));}
static void retry(unsigned node,Mac48Address) {log("mac_retry",",\"node\":"+std::to_string(node));}
static void finalDrop(unsigned node,Mac48Address) {log("mac_final_drop",",\"node\":"+std::to_string(node));}
static void sniff(unsigned node,Ptr<const Packet>p,uint16_t freq,WifiTxVector,MpduInfo,SignalNoiseDbm power,uint16_t) {
  std::ostringstream f;f<<std::setprecision(15)<<",\"node\":"<<node<<",\"packet_uid\":"<<p->GetUid()<<",\"frequency_mhz\":"<<freq<<",\"signal_dbm\":"<<power.signal<<",\"noise_dbm\":"<<power.noise;log("sniffer_rx",f.str());
}
static void setPosition(unsigned id,int64_t source,Vector v) {
  auto old=sta->GetPosition();sta->SetPosition(v);++positionApplied;
  std::ostringstream s;s<<",\"event_id\":"<<id<<",\"source_ns\":"<<source<<",\"old_x\":"<<old.x<<",\"new_x\":"<<v.x;log("position_apply",s.str());
}
static void positionInput(unsigned id,int64_t source,Vector v) {
  std::ostringstream input;input<<std::setprecision(17)<<",\"event_id\":"<<id<<",\"source_ns\":"<<source<<",\"target_x\":"<<v.x<<",\"target_y\":"<<v.y<<",\"target_z\":"<<v.z;
  log("position_input",input.str());
  auto now=Simulator::Now().GetNanoSeconds();
  if(scheduled && source<now) {++lateRejected;log("late_position_rejected",",\"event_id\":"+std::to_string(id));return;}
  if(scheduled)Simulator::Schedule(NanoSeconds(source-now),&setPosition,id,source,v);
  else setPosition(id,source,v);
}
int main(int argc,char**argv) {
  std::string trial,transport,placement,output;
  CommandLine cmd;cmd.AddValue("trial","reliability or position",trial);cmd.AddValue("transport","udp or tcp",transport);cmd.AddValue("placement","immediate or scheduled",placement);cmd.AddValue("output","New exclusive result directory",output);cmd.Parse(argc,argv);
  if((trial!="reliability" && trial!="position") || output.empty())return 2;
  position=trial=="position";tcp=!position && transport=="tcp";scheduled=placement=="scheduled";
  if((!position && transport!="tcp" && transport!="udp") || (position && placement!="immediate" && placement!="scheduled"))return 2;
  if(!std::filesystem::create_directory(output))return 2;
  events.open(output+"/events.jsonl",std::ios::out);events<<std::setprecision(17);
  std::ofstream(output+"/network-v3.json")<<kRawConfig;
  RngSeedManager::SetSeed(kSeed);RngSeedManager::SetRun(kRun);
  Config::SetDefault("ns3::WifiMacQueue::MaxSize",QueueSizeValue(QueueSize("1024p")));
  Config::SetDefault("ns3::WifiMacQueue::MaxDelay",TimeValue(Seconds(0.5)));
  Config::SetDefault("ns3::TcpL4Protocol::SocketType",TypeIdValue(TcpNewReno::GetTypeId()));
  NodeContainer nodes;nodes.Create(5);MobilityHelper mobility;mobility.SetMobilityModel("ns3::ConstantPositionMobilityModel");mobility.Install(nodes);
  for(unsigned i=0;i<5;++i)nodes.Get(i)->GetObject<MobilityModel>()->SetPosition(Vector(kPositions[i][0],kPositions[i][1],kPositions[i][2]));
  sta=nodes.Get(1)->GetObject<MobilityModel>();
  auto loss=CreateObject<LogDistancePropagationLossModel>();loss->SetAttribute("Exponent",DoubleValue(kExponentB));loss->SetReference(1,kReferenceLoss);
  auto gate=CreateObject<RangePropagationLossModel>();gate->SetAttribute("MaxRange",DoubleValue(1e9));loss->SetNext(gate);
  auto channel=CreateObject<YansWifiChannel>();channel->SetPropagationLossModel(loss);channel->SetPropagationDelayModel(CreateObject<ConstantSpeedPropagationDelayModel>());
  YansWifiPhyHelper phy;phy.SetChannel(channel);phy.SetErrorRateModel("ns3::NistErrorRateModel");phy.Set("ChannelSettings",StringValue("{42, 80, BAND_5GHZ, 0}"));
  phy.Set("TxPowerStart",DoubleValue(kTxB));phy.Set("TxPowerEnd",DoubleValue(kTxB));phy.Set("RxNoiseFigure",DoubleValue(7));phy.Set("RxSensitivity",DoubleValue(-101));phy.Set("CcaEdThreshold",DoubleValue(-62));phy.Set("CcaSensitivity",DoubleValue(-82));
  phy.Set("Antennas",UintegerValue(1));phy.Set("MaxSupportedTxSpatialStreams",UintegerValue(1));phy.Set("MaxSupportedRxSpatialStreams",UintegerValue(1));
  WifiHelper wifi;wifi.SetStandard(WIFI_STANDARD_80211ac);wifi.SetRemoteStationManager("ns3::ConstantRateWifiManager","DataMode",StringValue("VhtMcs9"),"ControlMode",StringValue("OfdmRate6Mbps"),"NonUnicastMode",StringValue("OfdmRate6Mbps"),"MaxSsrc",UintegerValue(7),"MaxSlrc",UintegerValue(4),"RtsCtsThreshold",UintegerValue(65535),"FragmentationThreshold",UintegerValue(65535));
  WifiMacHelper mac;Ssid ssid("net01-fixed");mac.SetType("ns3::ApWifiMac","Ssid",SsidValue(ssid),"QosSupported",BooleanValue(true));
  NetDeviceContainer devices=wifi.Install(phy,mac,nodes.Get(0));mac.SetType("ns3::StaWifiMac","Ssid",SsidValue(ssid),"ActiveProbing",BooleanValue(false),"QosSupported",BooleanValue(true));
  for(unsigned i=1;i<=3;++i)devices.Add(wifi.Install(phy,mac,nodes.Get(i)));wifi.AssignStreams(devices,1);
  for(unsigned i=0;i<4;++i) {
    auto d=DynamicCast<WifiNetDevice>(devices.Get(i));d->SetMtu(kMtu);d->GetHtConfiguration()->SetShortGuardIntervalSupported(false);
    d->GetMac()->TraceConnectWithoutContext("MacTx",MakeBoundCallback(&simple,std::string("mac_tx"),i));d->GetMac()->TraceConnectWithoutContext("MacRx",MakeBoundCallback(&simple,std::string("mac_rx"),i));
    d->GetPhy()->TraceConnectWithoutContext("PhyRxDrop",MakeBoundCallback(&rxDrop,i));d->GetPhy()->TraceConnectWithoutContext("MonitorSnifferRx",MakeBoundCallback(&sniff,i));
    d->GetRemoteStationManager()->TraceConnectWithoutContext("MacTxDataFailed",MakeBoundCallback(&retry,i));d->GetRemoteStationManager()->TraceConnectWithoutContext("MacTxFinalDataFailed",MakeBoundCallback(&finalDrop,i));phy.EnablePcap(output+"/wifi",d,true);
  }
  CsmaHelper wire;wire.SetChannelAttribute("DataRate",DataRateValue(DataRate(1000000000)));wire.SetChannelAttribute("Delay",TimeValue(NanoSeconds(1000)));wire.SetDeviceAttribute("Mtu",UintegerValue(1500));wire.SetQueue("ns3::DropTailQueue<Packet>","MaxSize",QueueSizeValue(QueueSize("1024p")));
  NodeContainer wired;wired.Add(nodes.Get(0));wired.Add(nodes.Get(4));auto wires=wire.Install(wired);InternetStackHelper internet;internet.Install(nodes);
  Ipv4AddressHelper ip;ip.SetBase("10.31.0.0","255.255.255.0","0.0.0.1");ip.Assign(NetDeviceContainer(devices.Get(0)));ip.SetBase("10.31.0.0","255.255.255.0","0.0.0.11");NetDeviceContainer stas;for(unsigned i=1;i<=3;++i)stas.Add(devices.Get(i));auto staIps=ip.Assign(stas);
  ip.SetBase("10.32.0.0","255.255.255.0");ip.Assign(wires);Ipv4GlobalRoutingHelper::PopulateRoutingTables();serverIp=staIps.GetAddress(0);
  TypeId factory=tcp?TcpSocketFactory::GetTypeId():UdpSocketFactory::GetTypeId();
  client=Socket::CreateSocket(nodes.Get(4),factory);client->SetIpTos(0);client->Bind(InetSocketAddress(Ipv4Address::GetAny(),19002));client->SetRecvCallback(MakeCallback(&receive));
  if(tcp) {
    listener=Socket::CreateSocket(nodes.Get(1),factory);listener->Bind(InetSocketAddress(Ipv4Address::GetAny(),19001));listener->Listen();listener->SetAcceptCallback(MakeCallback(&allow),MakeCallback(&accept));
    client->SetConnectCallback(MakeCallback(&connectOk),MakeCallback(&connectFail));attachTcp(client,"central");
    UintegerValue segment;TimeValue minRto,connTimeout;client->GetAttribute("SegmentSize",segment);client->GetAttribute("MinRto",minRto);client->GetAttribute("ConnTimeout",connTimeout);
    log("tcp_defaults",",\"segment_bytes\":"+std::to_string(segment.Get())+",\"min_rto_ns\":"+std::to_string(minRto.Get().GetNanoSeconds())+",\"conn_timeout_ns\":"+std::to_string(connTimeout.Get().GetNanoSeconds()));
  } else {
    server=Socket::CreateSocket(nodes.Get(1),factory);server->Bind(InetSocketAddress(Ipv4Address::GetAny(),19001));server->SetIpTos(0);server->SetRecvCallback(MakeCallback(&receive));
    // A connected UDP sender/receiver pair; Connect performs no network handshake.
    server->Connect(InetSocketAddress(Ipv4Address("10.32.0.2"),19002));
  }
  Simulator::Schedule(Seconds(0.8),[] {client->Connect(InetSocketAddress(serverIp,19001));});
  if(tcp)Simulator::Schedule(Seconds(1.4),[] {if(!connected){error("TCP not connected by fixed1.4sim");Simulator::Stop();}});
  if(!position) {
    Simulator::Schedule(Seconds(2),[gate]{gate->SetAttribute("MaxRange",DoubleValue(0));log("channel_blackout_begin");});
    Simulator::Schedule(Seconds(3),[gate]{gate->SetAttribute("MaxRange",DoubleValue(1e9));log("channel_blackout_end");});
    const std::array<double,5> times={1.5,2.1,2.3,4.5,5};const std::array<uint32_t,5> ids={101,102,103,104,101};
    for(unsigned i=0;i<5;++i)Simulator::Schedule(Seconds(times[i]),&submit,ids[i]);
  } else {
    Simulator::Schedule(MilliSeconds(1990),&positionInput,1,2000000000LL,Vector(.727,-.15,.15));Simulator::Schedule(MilliSeconds(2990),&positionInput,2,3000000000LL,Vector(.927,-.15,.15));Simulator::Schedule(MilliSeconds(3500),&positionInput,3,3200000000LL,Vector(.967,-.15,.15));
    const std::array<int64_t,4> edgeMs={1995,2005,2995,3005};
    for(unsigned i=0;i<edgeMs.size();++i)Simulator::Schedule(MilliSeconds(edgeMs[i]),[i]{auto v=sta->GetPosition();log("edge_probe_position",",\"probe_id\":"+std::to_string(2000+i)+",\"x\":"+std::to_string(v.x));submit(2000+i);});
    for(unsigned i=0;i<=92;++i)Simulator::Schedule(MilliSeconds(1200+50*i),[i]{auto v=sta->GetPosition();log("probe_position",",\"probe_id\":"+std::to_string(1000+i)+",\"x\":"+std::to_string(v.x));submit(1000+i);});
  }
  log("trial_start",",\"trial\":\""+trial+"\",\"transport\":\""+(tcp?"tcp":"udp")+"\",\"placement\":\""+placement+"\"");
  const auto start=mono(),startCpu=cpu();Simulator::Stop(Seconds(8));Simulator::Run();auto runWall=mono()-start,runCpu=cpu()-startCpu;
  if(!position) {
    if(tcp) {for(auto id:{101u,102u,103u,104u})if(processed[id]!=1 || replies[id]<(id==101?2u:1u))error("TCP request/reply missing or duplicate logical processing by8sim");}
    for(auto&[id,n]:processed)if(n!=1)error("logical request processed more than once");
  } else if(positionApplied!=(scheduled?2u:3u) || lateRejected!=(scheduled?1u:0u))error("position event admission counts mismatch");
  log("trial_end");Simulator::Destroy();events.close();
  std::ofstream summary(output+"/summary.json");summary<<"{\"scope\":\"synthetic native only, not Nav2\",\"runtime_error\":"<<(failed?"true":"false")<<",\"submitted\":"<<submitted<<",\"run_wall_ns\":"<<runWall<<",\"run_thread_cpu_ns\":"<<runCpu<<",\"tcp_repeated_seq_extents\":"<<retransmissions<<",\"late_positions_rejected\":"<<lateRejected<<",\"positions_applied\":"<<positionApplied<<",\"processed\":{";
  bool first=true;for(auto&[id,n]:processed){if(!first)summary<<",";first=false;summary<<"\""<<id<<"\":"<<n;}summary<<"},\"replies\":{";first=true;for(auto&[id,n]:replies){if(!first)summary<<",";first=false;summary<<"\""<<id<<"\":"<<n;}summary<<"}}\n";
  return failed?1:0;
}
