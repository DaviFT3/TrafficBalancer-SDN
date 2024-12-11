from mininet.net import Mininet
from mininet.node import RemoteController, CPULimitedHost
from mininet.link import TCLink
from mininet.log import setLogLevel, info
from mininet.cli import CLI

def setup_mininet():
    net = Mininet(controller=RemoteController, host=CPULimitedHost, link=TCLink)

    info("Criando controlador remoto...\n")
    ryu_controller = net.addController('ryu', controller=RemoteController, ip='127.0.0.1', port=6633)

    info("Criando switches...\n")
    s1 = net.addSwitch('s1')
    s2 = net.addSwitch('s2')

    info("Criando hosts...\n")
    h1 = net.addHost('h1', ip='10.0.0.1')
    h2 = net.addHost('h2', ip='10.0.0.2')

    info("Criando links...\n")
    net.addLink(h1, s1, bw=10, delay='5ms')
    net.addLink(h2, s2, bw=10, delay='5ms')
    net.addLink(s1, s2, bw=20, delay='2ms')

    info("Iniciando a rede...\n")
    net.start()

    info("Testando conectividade...\n")
    net.pingAll()

    info("Iniciando o CLI...\n")
    CLI(net)

    info("Parando a rede...\n")
    net.stop()

if __name__ == '__main__':
    setLogLevel('info')
    setup_mininet()
