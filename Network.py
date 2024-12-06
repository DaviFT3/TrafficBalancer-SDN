import threading
import time
import signal
from ryu.base import app_manager
from ryu.controller import ofp_event
from ryu.controller.handler import MAIN_DISPATCHER
from ryu.controller.handler import set_ev_cls
from ryu.ofproto import ofproto_v1_0
from mininet.net import Mininet
from mininet.node import Controller, RemoteController, CPULimitedHost
from mininet.link import TCLink
from mininet.log import setLogLevel, info
from mininet.cli import CLI

# Variável global para encerrar o Ryu com segurança
ryu_running = True

# Classe do controlador Ryu
class L2Switch(app_manager.RyuApp):
    OFP_VERSIONS = [ofproto_v1_0.OFP_VERSION]

    def __init__(self, *args, **kwargs):
        super(L2Switch, self).__init__(*args, **kwargs)

    @set_ev_cls(ofp_event.EventOFPPacketIn, MAIN_DISPATCHER)
    def packet_in_handler(self, ev):
        msg = ev.msg
        dp = msg.datapath
        ofp = dp.ofproto
        ofp_parser = dp.ofproto_parser

        actions = [ofp_parser.OFPActionOutput(ofp.OFPP_FLOOD)]

        data = None
        if msg.buffer_id == ofp.OFP_NO_BUFFER:
            data = msg.data

        out = ofp_parser.OFPPacketOut(
            datapath=dp, buffer_id=msg.buffer_id, in_port=msg.in_port,
            actions=actions, data=data)
        dp.send_msg(out)

# Função para inicializar o Ryu em uma thread separada
def start_ryu_controller():
    global ryu_running
    while ryu_running:
        app_manager.AppManager.run_apps(['__main__'])

# Função para configurar e rodar o Mininet
def setup_mininet():
    net = Mininet(controller=RemoteController, host=CPULimitedHost, link=TCLink)
    
    info("Criando controlador remoto...\n")
    ryu_controller = net.addController('ryu', controller=RemoteController, ip='127.0.0.1', port=6633)
    
    info("Criando switches...\n")
    s1 = net.addSwitch('s1')
    s2 = net.addSwitch('s2')
    s3 = net.addSwitch('s3')

    info("Criando hosts...\n")
    h1 = net.addHost('h1', ip='10.0.0.1')
    h2 = net.addHost('h2', ip='10.0.0.2')
    
    info("Criando links...\n")
    net.addLink(h1, s1, bw=10, delay='5ms')
    net.addLink(h2, s2, bw=10, delay='5ms')
    net.addLink(s1, s3, bw=20, delay='2ms')
    net.addLink(s2, s3, bw=20, delay='2ms')

    info("Iniciando a rede... \n")
    net.start()
    
    info("Testando conectividade...\n")
    net.pingAll()
    
    info("Iniciando o CLI...\n")
    CLI(net)
    
    info("Parando a rede...\n")
    net.stop()

# Handler para sinais de interrupção (CTRL+C)
def signal_handler(sig, frame):
    global ryu_running
    ryu_running = False
    info("Encerrando controlador Ryu...\n")
    time.sleep(2)  # Tempo para encerrar o controlador Ryu
    exit(0)

if __name__ == '__main__':
    setLogLevel('info')

    # Configurar o handler para sinais de interrupção
    signal.signal(signal.SIGINT, signal_handler)

    # Inicializar o Ryu em uma thread separada
    info("Iniciando controlador Ryu...\n")
    ryu_thread = threading.Thread(target=start_ryu_controller, daemon=True)
    ryu_thread.start()
    
    # Aguardar alguns segundos para o controlador iniciar
    time.sleep(5)
    
    # Configurar e iniciar o Mininet
    setup_mininet()
