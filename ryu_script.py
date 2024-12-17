from ryu.base import app_manager
from ryu.controller import ofp_event
from ryu.controller.handler import MAIN_DISPATCHER, CONFIG_DISPATCHER
from ryu.controller.handler import set_ev_cls
from ryu.ofproto import ofproto_v1_0

class MACMonitor(app_manager.RyuApp):
    OFP_VERSIONS = [ofproto_v1_0.OFP_VERSION]

    def __init__(self, *args, **kwargs):
        super(MACMonitor, self).__init__(*args, **kwargs)
        self.mac_table = {}  #Dicionário para rastrear pacotes e endereços MAC

    @set_ev_cls(ofp_event.EventOFPSwitchFeatures, CONFIG_DISPATCHER)
    def switch_features_handler(self, ev):
        dp = ev.msg.datapath
        #self.logger.info(f"Switch {dp.id} adicionado no controlador.\n")

    @set_ev_cls(ofp_event.EventOFPPacketIn, MAIN_DISPATCHER)
    def packet_in_handler(self, ev):
        msg = ev.msg
        dp = msg.datapath
        pkt = msg.data

        src_mac = pkt[6:12].hex()
        dst_mac = pkt[0:6].hex()

        # Filtrando trafego 
        ethertype = int.from_bytes(pkt[12:14], byteorder='big')
        if ethertype == 0x0806:  # ARP
            self.logger.info("Pacote ARP capturado.")
            
            # Verificando se é ICMP
        elif ethertype == 0x0800:
            self.logger.info("Pacote ICMP capturado.")

        else:
            self.logger.info(f"Pacote desconhecido com ethertype: {hex(ethertype)}")
            
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
            datapath=dp, buffer_id=msg.buffer_id, in_port=msg.in_port,
            actions=actions, data=msg.data)
        dp.send_msg(out)
