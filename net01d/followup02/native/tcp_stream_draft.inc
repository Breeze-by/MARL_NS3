// Explicit TCP transport versions, selected by the native adapter.
// Three full-duplex connections retain original Fragment bytes/offsets.
struct TcpFrame {
  Fragment header;
  std::vector<uint8_t> bytes;
  uint32_t accepted=0;
  uint64_t streamBegin=0;
};
struct TcpEndpoint {
  uint8_t local=0,remote=0;
  Ptr<Socket> socket;
  bool connected=false,draining=false;
  std::deque<TcpFrame> outgoing;
  std::vector<uint8_t> incoming;
  uint64_t queuedBytes=0,peakQueuedBytes=0,nextStreamByte=0;
};
static constexpr uint64_t TCP_QUEUE_BUDGET=8ULL*1024*1024;
static std::array<TcpEndpoint,4> tcpCentral,tcpRobot;
static std::array<Ptr<Socket>,4> tcpListeners;
static std::map<const Socket*,TcpEndpoint*> tcpEndpoints;
static std::vector<std::string> tcpConfigurations,tcpListenerConfigurations;
static bool tcpEnding=false;
static bool tcpConfigurationAttempted=false;
static TcpEndpoint& tcpEndpoint(Ptr<Socket> socket) {
  return *tcpEndpoints.at(PeekPointer(socket));
}
static std::string tcpDirection(const TcpEndpoint& endpoint) {
  return ",\"local\":"+std::to_string(endpoint.local)+",\"remote\":"+std::to_string(endpoint.remote);
}
static void tcpTrace(uint8_t local,uint8_t remote,std::string kind,
    Ptr<const Packet> packet,const TcpHeader& header,Ptr<const TcpSocketBase>) {
  std::string values;values.reserve(192);
  values+=",\"local\":";LedgerText::integer(values,local);
  values+=",\"remote\":";LedgerText::integer(values,remote);
  values+=",\"tcp_seq\":";LedgerText::integer(values,header.GetSequenceNumber().GetValue());
  values+=",\"tcp_ack\":";LedgerText::integer(values,header.GetAckNumber().GetValue());
  values+=",\"flags\":";LedgerText::integer(values,header.GetFlags());
  values+=",\"payload_bytes\":";LedgerText::integer(values,packet->GetSize());
  values+=",\"packet_uid\":";LedgerText::integer(values,packet->GetUid());
  event(kind,values);
}
static void tcpPump(Ptr<Socket> socket) {
  auto& endpoint=tcpEndpoint(socket);
  if(!endpoint.connected || endpoint.draining)return;
  endpoint.draining=true;
  while(!endpoint.outgoing.empty()) {
    auto& frame=endpoint.outgoing.front();
    const auto available=socket->GetTxAvailable();
    if(!available)break;
    const auto count=std::min<uint32_t>(available,frame.bytes.size()-frame.accepted);
    auto packet=Create<Packet>(frame.bytes.data()+frame.accepted,count);
    const auto accepted=socket->Send(packet);
    if(accepted<0) {
      if(socket->GetErrno()==Socket::ERROR_AGAIN)break;
      throw std::runtime_error("TCP Send failed errno="+std::to_string(socket->GetErrno()));
    }
    if(!accepted || uint32_t(accepted)>count)throw std::runtime_error("Invalid TCP Send extent");
    event("tcp_write",fields(frame.header)+
      ",\"frame_offset\":"+std::to_string(frame.accepted)+
      ",\"stream_offset\":"+std::to_string(frame.streamBegin+frame.accepted)+
      ",\"offered_bytes\":"+std::to_string(count)+
      ",\"accepted_bytes\":"+std::to_string(accepted));
    frame.accepted+=accepted;
    endpoint.queuedBytes-=accepted;
    if(frame.accepted==frame.bytes.size())endpoint.outgoing.pop_front();
  }
  endpoint.draining=false;
}
static void tcpWritable(Ptr<Socket> socket,uint32_t) {tcpPump(socket);}
static void tcpReceive(Ptr<Socket> socket) {
  CpuScope measure(ReceiveCpu);
  auto& endpoint=tcpEndpoint(socket);
  while(auto packet=socket->Recv()) {
    if(!packet->GetSize()) {
      if(!tcpEnding)throw std::runtime_error("Unexpected TCP EOF");
      break;
    }
    const auto oldSize=endpoint.incoming.size();
    endpoint.incoming.resize(oldSize+packet->GetSize());
    // Only actual ns3 Socket::Recv bytes enter this destination buffer.
    packet->CopyData(endpoint.incoming.data()+oldSize,packet->GetSize());
    event("tcp_stream_read",tcpDirection(endpoint)+",\"bytes\":"+std::to_string(packet->GetSize()));
    size_t consumed=0;
    while(endpoint.incoming.size()-consumed>=WIRE_HEADER) {
      auto probe=Create<Packet>(endpoint.incoming.data()+consumed,WIRE_HEADER);
      Fragment header;probe->PeekHeader(header);
      if(!header.length || header.length>CHUNK || header.from!=endpoint.remote || header.to!=endpoint.local)
        throw std::runtime_error("Invalid TCP Fragment identity/length");
      const auto length=WIRE_HEADER+header.length;
      if(endpoint.incoming.size()-consumed<length)break;
      auto actual=Create<Packet>(endpoint.incoming.data()+consumed,length);
      // Common original reassembly gets only a real received stream frame.
      receiveFragment(socket,actual,"tcp_frame_rx");
      consumed+=length;
    }
    endpoint.incoming.erase(endpoint.incoming.begin(),endpoint.incoming.begin()+consumed);
  }
}
static void tcpClosed(Ptr<Socket> socket) {
  auto& endpoint=tcpEndpoint(socket);endpoint.connected=false;
  event("tcp_closed",tcpDirection(endpoint));
  if(!tcpEnding)throw std::runtime_error("Unexpected TCP close; no reconnect/fallback");
}
static void tcpFailed(Ptr<Socket> socket) {
  auto& endpoint=tcpEndpoint(socket);endpoint.connected=false;
  event("tcp_error",tcpDirection(endpoint)+",\"socket_errno\":"+std::to_string(socket->GetErrno()));
  throw std::runtime_error("TCP connection failure; no fallback");
}
static std::string tcpAttributes(Ptr<Socket> socket,uint8_t local,uint8_t remote) {
  UintegerValue segment,snd,rcv,cwnd;TimeValue minRto,connection,delayedAck;
  BooleanValue noDelay,timestamp,sack,scaling;
  socket->GetAttribute("SegmentSize",segment);socket->GetAttribute("SndBufSize",snd);
  socket->GetAttribute("RcvBufSize",rcv);socket->GetAttribute("MinRto",minRto);
  socket->GetAttribute("ConnTimeout",connection);socket->GetAttribute("DelAckTimeout",delayedAck);
  socket->GetAttribute("TcpNoDelay",noDelay);
  socket->GetAttribute("InitialCwnd",cwnd);socket->GetAttribute("Timestamp",timestamp);
  socket->GetAttribute("Sack",sack);socket->GetAttribute("WindowScaling",scaling);
  TypeIdValue congestion;socket->GetNode()->GetObject<TcpL4Protocol>()->GetAttribute("SocketType",congestion);
  return "{\"local\":"+std::to_string(local)+",\"remote\":"+std::to_string(remote)+
    ",\"SegmentSize\":"+std::to_string(segment.Get())+",\"SndBufSize\":"+std::to_string(snd.Get())+
    ",\"RcvBufSize\":"+std::to_string(rcv.Get())+",\"MinRto_ns\":"+std::to_string(minRto.Get().GetNanoSeconds())+
    ",\"ConnTimeout_ns\":"+std::to_string(connection.Get().GetNanoSeconds())+
    ",\"DelAckTimeout_ns\":"+std::to_string(delayedAck.Get().GetNanoSeconds())+
    ",\"TcpNoDelay\":"+(noDelay.Get()?"true":"false")+
    ",\"Timestamp\":"+(timestamp.Get()?"true":"false")+",\"Sack\":"+(sack.Get()?"true":"false")+
    ",\"WindowScaling\":"+(scaling.Get()?"true":"false")+
    ",\"InitialCwnd_segments\":"+std::to_string(cwnd.Get())+
    ",\"InitialCwnd_bytes\":"+std::to_string(cwnd.Get()*segment.Get())+
    ",\"SocketType\":\""+congestion.Get().GetName()+"\"}";
}
static void tcpAttach(TcpEndpoint& endpoint) {
  auto socket=endpoint.socket;tcpEndpoints.emplace(PeekPointer(socket),&endpoint);
  socket->SetIpTos(0);
  socket->SetRecvCallback(MakeCallback(&tcpReceive));
  socket->SetSendCallback(MakeCallback(&tcpWritable));
  socket->SetCloseCallbacks(MakeCallback(&tcpClosed),MakeCallback(&tcpFailed));
  socket->TraceConnectWithoutContext("Tx",MakeBoundCallback(&tcpTrace,endpoint.local,endpoint.remote,std::string("tcp_tx")));
  socket->TraceConnectWithoutContext("Rx",MakeBoundCallback(&tcpTrace,endpoint.local,endpoint.remote,std::string("tcp_rx")));
  const auto config=tcpAttributes(socket,endpoint.local,endpoint.remote);
  tcpConfigurations.push_back(config);event("tcp_effective_attributes",",\"attributes\":"+config);
}
static void tcpConnected(Ptr<Socket> socket) {
  auto& endpoint=tcpEndpoint(socket);endpoint.connected=true;
  event("tcp_connected",tcpDirection(endpoint));tcpPump(socket);
}
static bool tcpAllow(Ptr<Socket>,const Address&) {return true;}
static void tcpAccepted(uint8_t robot,Ptr<Socket> socket,const Address&) {
  auto& endpoint=tcpRobot[robot];
  if(endpoint.socket)throw std::runtime_error("Duplicate TCP robot connection");
  endpoint.socket=socket;endpoint.connected=true;tcpAttach(endpoint);
  event("tcp_accepted",tcpDirection(endpoint));tcpPump(socket);
}
static void setupTcp(const NodeContainer& nodes,const std::array<Ipv4Address,4>& addresses) {
  if(nativeTransport=="tcp-mtu-v2")Config::SetDefault("ns3::TcpSocket::SegmentSize",UintegerValue(1448));
  for(uint8_t robot=1;robot<=3;++robot) {
    tcpRobot[robot].local=robot;tcpRobot[robot].remote=0;
    auto listener=Socket::CreateSocket(nodes.Get(robot),TcpSocketFactory::GetTypeId());
    const auto config=tcpAttributes(listener,robot,0);tcpListenerConfigurations.push_back(config);
    event("tcp_listener_effective_attributes",",\"attributes\":"+config);
    if(listener->Bind(InetSocketAddress(Ipv4Address::GetAny(),19001))<0 || listener->Listen()<0)
      throw std::runtime_error("TCP listener setup failed");
    listener->SetAcceptCallback(MakeCallback(&tcpAllow),MakeBoundCallback(&tcpAccepted,robot));
    tcpListeners[robot]=listener;
    auto& endpoint=tcpCentral[robot];endpoint.local=0;endpoint.remote=robot;
    endpoint.socket=Socket::CreateSocket(nodes.Get(4),TcpSocketFactory::GetTypeId());
    if(endpoint.socket->Bind()<0)throw std::runtime_error("TCP client bind failed");
    tcpAttach(endpoint);
    endpoint.socket->SetConnectCallback(MakeCallback(&tcpConnected),MakeCallback(&tcpFailed));
    if(endpoint.socket->Connect(InetSocketAddress(addresses[robot],19001))<0)
      throw std::runtime_error("TCP connect submission failed");
  }
}
static void tcpTransmit(Fragment header,std::vector<uint8_t> body) {
  CpuScope measure(TransmitCpu);
  if((header.from==0)==(header.to==0))throw std::runtime_error("TCP supports central/robot directions only");
  auto& endpoint=header.from==0?tcpCentral[header.to]:tcpRobot[header.from];
  const uint64_t framedBytes=body.size()+((body.size()+CHUNK-1)/CHUNK)*WIRE_HEADER;
  if(framedBytes>TCP_QUEUE_BUDGET-endpoint.queuedBytes) {
    event("tcp_queue_budget_exceeded",fields(header)+tcpDirection(endpoint)+
      ",\"queued_unsent_bytes\":"+std::to_string(endpoint.queuedBytes)+
      ",\"incoming_framed_bytes\":"+std::to_string(framedBytes)+
      ",\"budget_bytes\":"+std::to_string(TCP_QUEUE_BUDGET));
    throw std::runtime_error("TCP endpoint unsent-byte budget exceeded");
  }
  // One whole native message is admitted atomically, before any frame is queued.
  endpoint.queuedBytes+=framedBytes;
  endpoint.peakQueuedBytes=std::max(endpoint.peakQueuedBytes,endpoint.queuedBytes);
  for(uint32_t offset=0;offset<body.size();offset+=CHUNK) {
    header.offset=offset;header.length=std::min<uint32_t>(CHUNK,body.size()-offset);
    auto packet=Create<Packet>(body.data()+offset,header.length);packet->AddHeader(header);
    TcpFrame frame;frame.header=header;frame.bytes.resize(packet->GetSize());
    frame.streamBegin=endpoint.nextStreamByte;endpoint.nextStreamByte+=frame.bytes.size();
    packet->CopyData(frame.bytes.data(),frame.bytes.size());endpoint.outgoing.push_back(std::move(frame));
  }
  if(endpoint.socket)tcpPump(endpoint.socket);
}
static std::string tcpSummary() {
  uint64_t queued=0,queuedBytes=0,partial=0,buffered=0;
  std::ostringstream states;states<<"[";bool firstEndpoint=true;
  for(uint8_t robot=1;robot<=3;++robot)for(auto endpoint:{&tcpCentral[robot],&tcpRobot[robot]}) {
    queued+=endpoint->outgoing.size();partial+=endpoint->incoming.size();
    for(const auto& frame:endpoint->outgoing)queuedBytes+=frame.bytes.size()-frame.accepted;
    if(endpoint->socket) {
      UintegerValue size;endpoint->socket->GetAttribute("SndBufSize",size);
      buffered+=size.Get()-endpoint->socket->GetTxAvailable();
    }
    if(!firstEndpoint)states<<",";firstEndpoint=false;
    states<<"{\"local\":"<<unsigned(endpoint->local)<<",\"remote\":"<<unsigned(endpoint->remote)
      <<",\"connected\":"<<(endpoint->connected?"true":"false")
      <<",\"queue_budget_bytes\":"<<TCP_QUEUE_BUDGET
      <<",\"queued_unsent_bytes\":"<<endpoint->queuedBytes
      <<",\"peak_queued_unsent_bytes\":"<<endpoint->peakQueuedBytes
      <<",\"partial_stream_bytes\":"<<endpoint->incoming.size()<<",\"unsent_frames\":[";
    bool firstFrame=true;
    for(const auto& frame:endpoint->outgoing) {
      if(!firstFrame)states<<",";firstFrame=false;
      states<<"{\"message_id\":"<<frame.header.id<<",\"flow\":"<<frame.header.flow
        <<",\"fragment_offset\":"<<frame.header.offset<<",\"frame_bytes\":"<<frame.bytes.size()
        <<",\"accepted_prefix_bytes\":"<<frame.accepted<<",\"stream_begin\":"<<frame.streamBegin<<"}";
    }
    states<<"]}";
  }
  states<<"]";
  return "{\"queued_frames\":"+std::to_string(queued)+",\"queued_unsent_bytes\":"+std::to_string(queuedBytes)+
    ",\"partial_stream_bytes\":"+std::to_string(partial)+",\"socket_buffered_bytes\":"+std::to_string(buffered)+
    ",\"end_is_right_censored\":true,\"endpoints\":"+states.str()+"}";
}
static void saveTcpConfiguration(const std::string& directory) {
  if(tcpConfigurationAttempted)return;
  tcpConfigurationAttempted=true;
  std::ofstream file(directory+"/transport-config.json");
  if(!file)throw std::runtime_error("Cannot create TCP configuration/end-state evidence");
  file<<"{\"transport\":\""<<nativeTransport<<"\",\"connections\":3,\"TCP_attributes_changed\":"
    <<(nativeTransport=="tcp-mtu-v2"?"true":"false")<<",\"configured_overrides\":"
    <<(nativeTransport=="tcp-mtu-v2"?"{\"SegmentSize\":1448}":"{}")<<",\"listener_attributes\":[";
  for(size_t i=0;i<tcpListenerConfigurations.size();++i){if(i)file<<",";file<<tcpListenerConfigurations[i];}
  file<<"],\"attributes\":[";
  for(size_t i=0;i<tcpConfigurations.size();++i){if(i)file<<",";file<<tcpConfigurations[i];}
  file<<"],\"end_state\":"<<tcpSummary()<<"}\n";
  file.close();
  if(!file)throw std::runtime_error("Cannot persist TCP configuration/end-state evidence");
}
