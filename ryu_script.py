from ryu.base import app_manager
from ryu.controller import ofp_event
from ryu.controller.handler import MAIN_DISPATCHER, CONFIG_DISPATCHER
from ryu.controller.handler import set_ev_cls
from ryu.ofproto import ofproto_v1_3

from ryu.lib.packet import packet, ethernet, ipv4

class MACMonitor(app_manager.RyuApp):
    OFP_VERSIONS = [ofproto_v1_3.OFP_VERSION]

    def __init__(self, *args, **kwargs):
        super(MACMonitor, self).__init__(*args, **kwargs)
        self.mac_table = {}  #Dicionário para rastrear pacotes e endereços MAC
        self.flow_table = {}  # Dicionário para rastrear tráfego por fluxo

    @set_ev_cls(ofp_event.EventOFPSwitchFeatures, CONFIG_DISPATCHER)
    def switch_features_handler(self, ev):
        datapath = ev.msg.datapath
        ofproto = datapath.ofproto
        parser = datapath.ofproto_parser

        # install the table-miss flow entry.
        match = parser.OFPMatch()
        actions = [parser.OFPActionOutput(ofproto.OFPP_CONTROLLER,
                                          ofproto.OFPCML_NO_BUFFER)]
        self.add_flow(datapath, 0, match, actions)

    def add_flow(self, datapath, priority, match, actions):
        ofproto = datapath.ofproto
        parser = datapath.ofproto_parser

        # construct flow_mod message and send it.
        inst = [parser.OFPInstructionActions(ofproto.OFPIT_APPLY_ACTIONS,
                                             actions)]
        mod = parser.OFPFlowMod(datapath=datapath, priority=priority,
                                match=match, instructions=inst)
        datapath.send_msg(mod)
        
    @set_ev_cls(ofp_event.EventOFPPacketIn, MAIN_DISPATCHER)
    def packet_in_handler(self, ev):
        msg = ev.msg
        dp = msg.datapath
        pkt = msg.data
        pktIP = packet.Packet(msg.data)
        
        # Se for IPv4, registre o fluxo
        ip = pktIP.get_protocol(ipv4.ipv4)
        if ip:
            flow_key = (ip.src, ip.dst)
            self.logger.info(f"IPv4: SRC={ip.src}, DST={ip.dst}")
            if flow_key not in self.flow_table:
                self.flow_table[flow_key] = 0
            self.flow_table[flow_key] += 1

            self.logger.info(f"Fluxo {flow_key} registrou {self.flow_table[flow_key]} pacotes.")


        src_mac = pkt[6:12].hex()
        dst_mac = pkt[0:6].hex()

        # Filtrando trafego 
        ethertype = int.from_bytes(pkt[12:14], byteorder='big')

        if ethertype == 0x0800:
            self.logger.info("Pacote ICMP capturado.")
            
        self.logger.info(f"Pacote recebido: SRC={src_mac}, DST={dst_mac}")

        # Atualizar a tabela MAC com contagem de pacotes
        if src_mac not in self.mac_table:
            self.mac_table[src_mac] = 0
        self.mac_table[src_mac] += 1

        self.logger.info(f"Endereço MAC {src_mac} enviou {self.mac_table[src_mac]} pacotes.\nConteúdo do pacote (hex): {pkt[:64].hex()}\n\n")

        # Ações de flooding para pacotes desconhecidos
        ofp = dp.ofproto
        ofp_parser = dp.ofproto_parser
        actions = [ofp_parser.OFPActionOutput(ofp.OFPP_FLOOD)]

        out = ofp_parser.OFPPacketOut(
            datapath=dp, buffer_id=msg.buffer_id, in_port=msg.match['in_port'],
            actions=actions, data=msg.data)
        dp.send_msg(out)
