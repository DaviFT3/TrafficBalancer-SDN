import time
from ryu.base import app_manager
from ryu.controller import ofp_event
from ryu.controller.handler import MAIN_DISPATCHER, CONFIG_DISPATCHER
from ryu.controller.handler import set_ev_cls
from ryu.ofproto import ofproto_v1_0

from ryu.lib.packet import packet, ethernet, ipv4

class balancingLoad(app_manager.RyuApp):
    OFP_VERSIONS = [ofproto_v1_0.OFP_VERSION]

    def __init__(self, *args, **kwargs):
        super(balancingLoad, self).__init__(*args, **kwargs)
        self.mac_table = {}  
        self.flow_table = {}  
        self.flow_latency = {}  
        self.flow_throughput = {}  


    @set_ev_cls(ofp_event.EventOFPSwitchFeatures, CONFIG_DISPATCHER)
    def switch_features_handler(self, ev):
        dp = ev.msg.datapath
        #self.logger.info(f"Switch {dp.id} adicionado no controlador.\n")

    @set_ev_cls(ofp_event.EventOFPPacketIn, MAIN_DISPATCHER)
    def packet_in_handler(self, ev):
        msg = ev.msg
        dp = msg.datapath
        pkt = msg.data

        pktIP = packet.Packet(msg.data)
        ip = pktIP.get_protocol(ipv4.ipv4)

        if ip:  
            flow_key = (ip.src, ip.dst)

            
            if flow_key not in self.flow_table:
                self.flow_table[flow_key] = {
                    'count': 0,
                    'bytes': 0,
                    'first_seen': time.time(),
                    'last_seen': time.time(),
                }

            self.flow_table[flow_key]['count'] += 1
            self.flow_table[flow_key]['bytes'] += len(pkt)

            current_time = time.time()
            last_seen = self.flow_table[flow_key]['last_seen']
            latency = current_time - last_seen
            self.flow_table[flow_key]['last_seen'] = current_time

            elapsed_time = current_time - self.flow_table[flow_key]['first_seen']
            throughput = (self.flow_table[flow_key]['bytes'] * 8) / (elapsed_time * 10**6) if elapsed_time > 0 else 0

            self.logger.info(f"Fluxo {flow_key} - "
                            f"Pacotes: {self.flow_table[flow_key]['count']}, "
                            f"Bytes: {self.flow_table[flow_key]['bytes']}, "
                            f"Latência: {latency:.6f} s, "
                            f"Throughput: {throughput:.2f} Mbps")


            if self.flow_table[flow_key]['count'] > 100:  
                self.logger.info(f"Fluxo {flow_key} excedeu o limite de pacotes. "
                                f"Considerando redirecionamento para balanceamento.")

        src_mac = pkt[6:12].hex()
        dst_mac = pkt[0:6].hex()
        ethertype = int.from_bytes(pkt[12:14], byteorder='big')

        if ethertype == 0x0800:  # IPv4
            self.logger.info("Pacote IPv4 capturado.")
        else:
            self.logger.info(f"Pacote desconhecido com ethertype: {hex(ethertype)}")
        
        self.logger.info(f"Pacote recebido: SRC={src_mac}, DST={dst_mac}")

        if src_mac not in self.mac_table:
            self.mac_table[src_mac] = 0
        self.mac_table[src_mac] += 1

        self.logger.info(f"Endereço MAC {src_mac} enviou {self.mac_table[src_mac]} pacotes.")


        ofp = dp.ofproto
        ofp_parser = dp.ofproto_parser

  
        actions = [ofp_parser.OFPActionOutput(ofp.OFPP_FLOOD)]

        out = ofp_parser.OFPPacketOut(
            datapath=dp, buffer_id=msg.buffer_id, in_port=msg.in_port,
            actions=actions, data=msg.data)
        dp.send_msg(out)
