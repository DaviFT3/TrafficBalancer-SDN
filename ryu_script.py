import time
import csv
from itertools import cycle
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
        self.LATENCY_THRESHOLD = 0.01  # Limite de latência em segundos para redirecionamento

    @set_ev_cls(ofp_event.EventOFPSwitchFeatures, CONFIG_DISPATCHER)
    def switch_features_handler(self, ev):
        dp = ev.msg.datapath
        self.logger.info(f"Switch {dp.id} adicionado no controlador.")

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

            self.log_latency(flow_key, latency, "before")

            elapsed_time = current_time - self.flow_table[flow_key]['first_seen']
            throughput = (self.flow_table[flow_key]['bytes'] * 8) / (elapsed_time * 10**6) if elapsed_time > 0 else 0

            self.logger.info(f"Fluxo {flow_key} - "
                            f"Pacotes: {self.flow_table[flow_key]['count']}, "
                            f"Bytes: {self.flow_table[flow_key]['bytes']}, "
                            f"Latência: {latency:.6f} s, "
                            f"Throughput: {throughput:.2f} Mbps")

            if latency > self.LATENCY_THRESHOLD:
                self.logger.info(f"Fluxo {flow_key} excedeu a latência limite ({self.LATENCY_THRESHOLD}s). Aplicando balanceamento.")
                self.apply_load_balancing(dp, msg, flow_key)
                self.log_latency(flow_key, latency, "after")

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

        # Ação padrão para inundar o pacote
        actions = [ofp_parser.OFPActionOutput(ofp.OFPP_FLOOD)]

        out = ofp_parser.OFPPacketOut(
            datapath=dp, buffer_id=msg.buffer_id, in_port=msg.in_port,
            actions=actions, data=msg.data)
        dp.send_msg(out)
    
    def apply_load_balancing(self, dp, msg, flow_key):
        """Aplica balanceamento de carga para o fluxo"""
        ofp = dp.ofproto
        ofp_parser = dp.ofproto_parser

        src, dst = flow_key
        self.logger.info(f"Redirecionando fluxo {src} -> {dst} para balanceamento.")

        actions = [ofp_parser.OFPActionOutput(2)]  #porta alternativa para balanceamento
        match = ofp_parser.OFPMatch(dl_type=0x0800, nw_src=src, nw_dst=dst)

        mod = ofp_parser.OFPFlowMod(
            datapath=dp, match=match, cookie=0,
            command=ofp.OFPFC_ADD, idle_timeout=10, hard_timeout=30,
            priority=1, actions=actions)
        dp.send_msg(mod)

    def log_latency(self, flow_key, latency, stage):
        """Log de latência em um arquivo CSV"""
        with open('latency_metrics.csv', 'a', newline='') as csvfile:
            writer = csv.writer(csvfile)
            writer.writerow([time.time(), flow_key[0], flow_key[1], latency, stage])    

    '''
    def apply_load_balancing(self, dp, msg, flow_key):
        """Aplica balanceamento de carga para o fluxo"""
        ofp = dp.ofproto
        ofp_parser = dp.ofproto_parser

        src, dst = flow_key
        self.logger.info(f"Redirecionando fluxo {src} -> {dst} para balanceamento.")

        # Seleciona uma porta disponível dinamicamente
        next_port = next(self.available_ports)
        self.logger.info(f"Redirecionando fluxo para a porta {next_port}.")

        actions = [ofp_parser.OFPActionOutput(next_port)]
        match = ofp_parser.OFPMatch(dl_type=0x0800, nw_src=src, nw_dst=dst)

        mod = ofp_parser.OFPFlowMod(
            datapath=dp, match=match, cookie=0,
            command=ofp.OFPFC_ADD, idle_timeout=10, hard_timeout=30,
            priority=1, actions=actions)
        dp.send_msg(mod)
    '''    