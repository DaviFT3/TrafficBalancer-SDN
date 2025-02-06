from ryu.base import app_manager
from ryu.controller import ofp_event
from ryu.controller.handler import CONFIG_DISPATCHER, MAIN_DISPATCHER
from ryu.controller.handler import set_ev_cls
from ryu.ofproto import ofproto_v1_3
from ryu.lib.packet import packet, ethernet
from ryu.ofproto import ether
from ryu.lib import hub
from ryu.topology import event
import time

class LatencyBalancer(app_manager.RyuApp):
    """
    Controlador SDN para balanceamento baseado em latência.
    Ele monitora o tráfego da rede e ajusta os fluxos conforme necessário.
    """
    OFP_VERSIONS = [ofproto_v1_3.OFP_VERSION]

    def __init__(self, *args, **kwargs):
        super(LatencyBalancer, self).__init__(*args, **kwargs)
        self.datapaths = {}  # Armazena switches conectados
        self.latency_stats = {}  # Armazena estatísticas de latência
        self.monitor_thread = hub.spawn(self._monitor)
        self.mac_to_port = {}  # Mapeia MACs para portas correspondentes

    @set_ev_cls(ofp_event.EventOFPStateChange, [CONFIG_DISPATCHER, MAIN_DISPATCHER])
    def _state_change_handler(self, ev):
        """Gerencia mudanças no estado dos switches."""
        datapath = ev.datapath
        if ev.state == MAIN_DISPATCHER:
            self.datapaths[datapath.id] = datapath
        elif ev.state == CONFIG_DISPATCHER:
            self.datapaths.pop(datapath.id, None)

    def _monitor(self):
        """Solicita estatísticas periodicamente dos switches."""
        while True:
            for datapath in self.datapaths.values():
                self._request_stats(datapath)
            hub.sleep(2)

    def _request_stats(self, datapath):
        """Solicita estatísticas de porta ao switch."""
        ofproto = datapath.ofproto
        parser = datapath.ofproto_parser
        req = parser.OFPPortStatsRequest(datapath, 0, ofproto.OFPP_ANY)
        datapath.send_msg(req)

    @set_ev_cls(ofp_event.EventOFPPortStatsReply, MAIN_DISPATCHER)
    def _port_stats_reply_handler(self, ev):
        """Processa as estatísticas de porta recebidas."""
        datapath = ev.msg.datapath
        dpid = datapath.id
        self.latency_stats.setdefault(dpid, {})

        for stat in ev.msg.body:
            port_no = stat.port_no
            tx_bytes = stat.tx_bytes
            rx_bytes = stat.rx_bytes
            current_time = time.time()

            if port_no in self.latency_stats[dpid]:
                prev_tx, prev_rx, prev_time = self.latency_stats[dpid][port_no]
                time_diff = current_time - prev_time
                
                if time_diff > 0:
                    throughput = ((tx_bytes - prev_tx) * 8) / (time_diff * 1e6)  # Mbps
                    latency = time_diff  # ms
                    prev_throughput = self.latency_stats[dpid][port_no][0]
                    prev_latency = (current_time - prev_time) * 1000
                    
                    if abs(throughput - prev_throughput) > 5 or abs(latency - prev_latency) > 10:
                        self.logger.info(f"⚡ Switch {dpid}, Porta {port_no} -> Throughput: {throughput:.2f} Mbps, Latência: {latency:.2f} ms")

            self.latency_stats[dpid][port_no] = (tx_bytes, rx_bytes, current_time)

    @set_ev_cls(event.EventSwitchEnter)
    def _switch_enter_handler(self, ev):
        """Gerencia a conexão de novos switches."""
        switch = ev.switch.dp
        self.datapaths[switch.id] = switch
        self.logger.info(f"Switch {switch.id} conectado")
        self.add_default_flows(switch)

    @set_ev_cls(ofp_event.EventOFPPacketIn, MAIN_DISPATCHER)
    def _packet_in_handler(self, ev):
        """Lida com pacotes desconhecidos recebidos pelo controlador."""
        msg = ev.msg
        datapath = msg.datapath
        in_port = msg.match['in_port']
        dpid = datapath.id
        parser = datapath.ofproto_parser
        ofproto = datapath.ofproto

        pkt = packet.Packet(msg.data)
        eth = pkt.get_protocol(ethernet.ethernet)

        if eth:
            src = eth.src
            dst = eth.dst
            self.mac_to_port.setdefault(dpid, {})
            self.mac_to_port[dpid][src] = in_port

            if dst in self.mac_to_port[dpid]:
                out_port = self.mac_to_port[dpid][dst]
                self.install_flow(datapath, in_port, dst, out_port)
                actions = [parser.OFPActionOutput(out_port)]
            else:
                actions = [parser.OFPActionOutput(ofproto.OFPP_FLOOD)]

            out = parser.OFPPacketOut(
                datapath=datapath,
                buffer_id=ofproto.OFP_NO_BUFFER,
                in_port=in_port,
                actions=actions,
                data=msg.data,
            )
            datapath.send_msg(out)

    def add_default_flows(self, datapath):
        """Adiciona regras padrão ao switch para enviar pacotes ao controlador."""
        ofproto = datapath.ofproto
        parser = datapath.ofproto_parser
        match = parser.OFPMatch()
        actions = [parser.OFPActionOutput(ofproto.OFPP_CONTROLLER, ofproto.OFPCML_NO_BUFFER)]
        inst = [parser.OFPInstructionActions(ofproto.OFPIT_APPLY_ACTIONS, actions)]
        mod = parser.OFPFlowMod(datapath=datapath, priority=0, match=match, instructions=inst)
        datapath.send_msg(mod)
        self.logger.info(f"Regras padrão adicionadas ao switch {datapath.id}")

    def install_flow(self, datapath, in_port, dst, out_port):
        """Instala regras de fluxo para pacotes conhecidos."""
        ofproto = datapath.ofproto
        parser = datapath.ofproto_parser
        match = parser.OFPMatch(in_port=in_port, eth_dst=dst)
        actions = [parser.OFPActionOutput(out_port)]
        inst = [parser.OFPInstructionActions(ofproto.OFPIT_APPLY_ACTIONS, actions)]
        mod = parser.OFPFlowMod(datapath=datapath, priority=1, match=match, instructions=inst)
        datapath.send_msg(mod)
        self.logger.info(f"Instalando fluxo: {datapath.id} - {in_port} -> {out_port} para destino {dst}")
