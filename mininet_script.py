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
    s3 = net.addSwitch('s3')

    info("Criando hosts...\n")
    hosts = []
    for i in range(1, 10):
        host = net.addHost(f'h{i}', ip=f'10.0.0.{i}', mac=f'00:00:00:00:00:{i:02x}')
        hosts.append(host)


    info("Desativando IPv6 nos hosts...\n") #nao sei se eh opcional de primeiro momento desativei
    for host in hosts:
        host.cmd('sysctl -w net.ipv6.conf.all.disable_ipv6=1')
        host.cmd('sysctl -w net.ipv6.conf.default.disable_ipv6=1')
        host.cmd('sysctl -w net.ipv6.conf.lo.disable_ipv6=1')


    info("Criando links...\n")
    # Conectando switches entre si
    net.addLink(s1, s2, bw=20, delay='2ms')
    net.addLink(s1, s3, bw=20, delay='2ms')
    # net.addLink(s2, s3, bw=20, delay='2ms')

    # Conectando hosts aos switches
    for i in range(3):  # h1, h2, h3 -> s1
        net.addLink(hosts[i], s1, bw=10, delay='2ms')
    for i in range(3, 6):  # h4, h5, h6 -> s2
        net.addLink(hosts[i], s2, bw=10, delay='2ms')
    for i in range(6, 9):  # h7, h8, h9 -> s3
        net.addLink(hosts[i], s3, bw=10, delay='2ms')
    


    info("Iniciando a rede...\n")
    net.start()

    info("Iniciando o CLI...\n")
    CLI(net)

    info("Parando a rede...\n")
    net.stop()

if __name__ == '__main__':
    setLogLevel('info')
    setup_mininet()