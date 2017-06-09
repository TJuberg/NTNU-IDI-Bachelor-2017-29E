#!/usr/bin/python
#
# This file is part of Ansible
#
# Ansible is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
#
# Ansible is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with Ansible.  If not, see <http://www.gnu.org/licenses/>.
#
ANSIBLE_METADATA = {'metadata_version': '1.0',
                    'status': ['preview'],
                    'supported_by': 'core'}


DOCUMENTATION = """
---
module: iosxr_facts
version_added: "2.2"
author: "Ricardo Carrillo Cruz (@rcarrillocruz)"
short_description: Collect facts from remote devices running IOS-XR
description:
  - Collects a base set of device facts from a remote device that
    is running iosxr.  This module prepends all of the
    base network fact keys with C(ansible_net_<fact>).  The facts
    module will always collect a base set of facts from the device
    and can enable or disable collection of additional facts.
extends_documentation_fragment: iosxr
options:
  gather_subset:
    description:
      - When supplied, this argument will restrict the facts collected
        to a given subset.  Possible values for this argument include
        all, hardware, config, and interfaces.  Can specify a list of
        values to include a larger subset.  Values can also be used
        with an initial C(M(!)) to specify that a specific subset should
        not be collected.
    required: false
    default: '!config, !routes'
"""

EXAMPLES = """
# Collect all facts from the device
- iosxr_facts:
    gather_subset: all

# Collect only the config and default facts
- iosxr_facts:
    gather_subset:
      - config

# Do not collect hardware facts
- iosxr_facts:
    gather_subset:
      - "!hardware"
"""

RETURN = """
ansible_net_gather_subset:
  description: The list of fact subsets collected from the device
  returned: always
  type: list

# default
ansible_net_version:
  description: The operating system version running on the remote device
  returned: always
  type: str
ansible_net_hostname:
  description: The configured hostname of the device
  returned: always
  type: string
ansible_net_image:
  description: The image file the device is running
  returned: always
  type: string
ansible_net_serial:
  description: The serialnumber of the remote device.
  returned: always
  type: list


# hardware
ansible_net_filesystems:
  description: All file system names available on the device
  returned: when hardware is configured
  type: list
ansible_net_memfree_mb:
  description: The available free memory on the remote device in Mb
  returned: when hardware is configured
  type: int
ansible_net_memtotal_mb:
  description: The total memory on the remote device in Mb
  returned: when hardware is configured
  type: int
ansible_net_temp:
  description: The diferent temperatures of the remote device in degrees Celsius
  returned: when hardware is configured
  type: dict
ansible_net_cpu_percentage:
  description: 
    - The total CPU usage on the remote device the last minute,
      last 5 minutes and last 15 minutes
  returned: when hardware is configured
  type: dict

# bgp
ansible_net_bgp_info:
  description: General info about BGP settings
  returned: when bgp is configured
  type: list
ansible_net_bgp_process:
  description: The process information from BGP
  returned: when bgp is configured
  type: list
ansible_net_bgp_table:
  description: The entire bgp routing table
  returned: when bgp is configured
  type: dict

# isis
ansible_net_isis_adjacency:
  description: The adjacencies from IS-IS
  returned: when isis is configured
  type: dict

# optics
ansible_net_optics:
  description: The signals on the TenGigE interfaces
  returned: when optics is configured
  type: list

# routesummary
ansible_net_routing_summary:
  description: The summary of the routes on the remote device
  returned: when routesummary is configured
  type: dict

# routes
ansible_net_routing_table_ipv4:
  description: The entire ipv4 routing table from the remote device
  returned: when routes is configured
  type: dict
ansible_net_routing_table_ipv6:
  description: The entire ipv6 routing table from the remote device
  returned: when routes is configured
  type: dict

# config
ansible_net_config:
  description: The current active config from the device
  returned: when config is configured
  type: str

# interfaces
ansible_net_all_ipv4_addresses:
  description: All IPv4 addresses configured on the device
  returned: when interfaces is configured
  type: list
ansible_net_all_ipv6_addresses:
  description: All IPv6 addresses configured on the device
  returned: when interfaces is configured
  type: list
ansible_net_interfaces:
  description: A hash of all interfaces running on the system
  returned: when interfaces is configured
  type: dict
ansible_net_neighbors:
  description: The list of LLDP neighbors from the remote device
  returned: when interfaces is configured
  type: dict
"""
import re

from ansible.module_utils.iosxr import run_commands
from ansible.module_utils.basic import AnsibleModule
from ansible.module_utils.six import iteritems
from ansible.module_utils.six.moves import zip
from ansible.module_utils.iosxr import iosxr_argument_spec, check_args


class FactsBase(object):

    def __init__(self):
        self.facts = dict()
        self.commands()

    def commands(self):
        raise NotImplementedError


class Default(FactsBase):

    def commands(self):
        return(['show version brief', 'admin show dsc'])

    def populate(self, results):
        self.facts['version'] = self.parse_version(results['show version brief'])
        self.facts['image'] = self.parse_image(results['show version brief'])
        self.facts['hostname'] = self.parse_hostname(results['show version brief'])
        self.facts['serial'] = list()
        self.populate_serial(results['admin show dsc'])

    def parse_version(self, data):
        match = re.search(r'Version (\S+)$', data, re.M)
        if match:
            return match.group(1)

    def parse_hostname(self, data):
        match = re.search(r'^(.+) uptime', data, re.M)
        if match:
            return match.group(1)

    def parse_image(self, data):
        match = re.search(r'image file is "(.+)"', data)
        if match:
            return match.group(1)

    def populate_serial(self, data):
        for line in data.split('\n'):
            if line != '---------------------------------------------------------':
                self.facts['serial'].append(line)

class Hardware(FactsBase):

    def commands(self):
        return(['dir /all', 'show memory summary',
                'show environment temperatures',
                'show processes cpu'])

    def populate(self, results):
        self.facts['filesystems'] = self.parse_filesystems(
            results['dir /all'])

        match = re.search(r'Physical Memory: (\d+)M total \((\d+)',
            results['show memory summary'])
        if match:
            self.facts['memtotal_mb'] = match.group(1)
            self.facts['memfree_mb'] = match.group(2)

        self.facts['temp'] = list()
        self.populate_temp(results['show environment temperatures'])
        self.facts['CPU %'] = self.parse_cpu(results['show processes cpu'])

    def parse_filesystems(self, data):
        return re.findall(r'^Directory of (\S+)', data, re.M)

    def parse_cpu(self, data):
        result = re.match(r'CPU utilization for one minute: (\d+)%; five minutes: (\d+)%; fifteen minutes: (\d+)%', data)
        if result:
            return {'One minute': result.group(1)+'%', 'Five minutes': result.group(2)+'%', 'Fifteen minutes': result.group(3)+'%'}

    def populate_temp(self, data):
        unit, inlet, hotspot = "","",""
        for line in data.split('\n'):
            unittmp = re.search(r'(.+)\*', line)
            if unittmp:
                unit = unittmp.group(0)
            intmp = re.search(r'(.+)Inlet0(.+)', line)
            if intmp:
                inlet = intmp.group(2).strip('\t')
            hottmp = re.search(r'(.+)Hotspot0(.+)', line)
            if hottmp:
                hotspot = hottmp.group(2).strip('\t')
            if unit and inlet and hotspot:
                self.facts['temp'].append({unit: {'Inlet0': inlet, 'Hotspot0': hotspot}})
                unit, inlet, hotspot = "","",""	

class Multicast(FactsBase):
    def commands(self):
        return(['show mfib connections', 'show mfib counter',
            'show mrib route outgoing-interface'])

    def populate(self, results):
        self.facts['mfib_connections'] = list()
        self.facts['mfib_counter'] = list()
        self.facts['mrib_route_outgoing_if'] = list()
        self.populate_mfib_con(results['show mfib connections'])
        self.populate_mfib_counter(results['show mfib counter'])	
        self.populate_mrib_route_out(results['show mrib route outgoing-interface'])

    def populate_mfib_con(self, mfib_con):
        for connection in mfib_con.split('\n'):
            self.facts['mfib_connections'].append(connection)

    def populate_mfib_counter(self, mfib_counter):
        for counter in mfib_counter.split('\n'):
            self.facts['mfib_counter'].append(counter)
    
    def populate_mrib_route_out(self, mrib_route_out):
        for route in mrib_route_out.split('\n'):
            if route.startswith('('):
                self.facts['mrib_route_outgoing_if'].append(route)

class Bgp(FactsBase):
    def commands(self):
        return(['show bgp summary'])

    def populate(self, results):
        self.facts['bgp_info'], self.facts['bgp_process'], self.facts['bgp_table'] = self.parseBgpsum(results['show bgp summary'])

    def parseBgpsum(self, data):
        match = re.search('MET((?s).*)e\.((?s).*)', data)
        bgpinfo = list()
        bgptable = dict()
        bgpproccess = list()
        for line in match.group(1).split('\n'):
           bgpinfo.append(line)
        for line in match.group(2).split('\n'):
            if line.startswith('Process') or line.startswith('Speaker'):
                bgpproccess.append(line)
            elif line != "":
                var = line.split()
                neighbor = var[0]
                spk = var[1]
                AS = var[2]
                msgrcvd = var[3]
                msgsent = var[4]
                tblver = var[5]
                inq = var[6]
                outq = var[7]
                updown = var[8]
                stpfxrcd = var[9]
                bgptable.update({neighbor: {'Spk': spk, 'AS': AS, 'MsgRcvd': msgrcvd, 
                                'MsgSent': msgsent, 'TblVer': tblver, 'InQ': inq,
                                'OutQ': outq, 'Up/Down': updown, 'St/PfxRcd': stpfxrcd}})
        return bgpinfo, bgpproccess, bgptable

class Isis(FactsBase):
    def commands(self):
        return(['show isis adjacency'])

    def populate(self, results):
        self.facts['ISIS_adjacency'] = self.parseIsisadj(results['show isis adjacency'])

    def parseIsisadj(self, data):
        match = re.search('((?s).*)IS-IS (\d+) Level-1 adjacencies:((?s).*)IS-IS (\d+) Level-2 adjacencies:((?s).+)', data)
        level1 = dict()
        level1.update({'Level-1 adjacencies': dict()})
        for line in match.group(3).split('\n'):
            if not (line.startswith('Total') or line == "" or line.startswith('System') or line.strip().startswith('BFD')):
                var = line.split()
                sysid = var[0]
                interface = var[1]
                snpa = var[2]
                state = var[3]
                hold = var[4]
                changed = var[5]
                nsf = var[6]
                ipv4 = var[7]
                ipv6 = var[8]
                level1['Level-1 adjacencies'].update({sysid: {'Interface': interface,
                                'SNPA': snpa, 'State': state, 'Hold': hold,
                                'Changed': changed, 'NSF': nsf, 
                                'IPv4': ipv4,'IPv6': ipv6}})
        level2 = dict()
        level2.update({'Level-2 adjacencies': dict()})
        for line in match.group(5).split('\n'):
            if not (line.startswith('Total') or line == "" or line.startswith('System') or line.strip().startswith('BFD')):
                var = line.split()
                sysid = var[0]
                interface = var[1]
                snpa = var[2]
                state = var[3]
                hold = var[4]
                changed = var[5]
                nsf = var[6]
                ipv4 = var[7]
                ipv6 = var[8]
                level2['Level-2 adjacencies'].update({sysid: {'Interface': interface,
                                'SNPA': snpa, 'State': state, 'Hold': hold,
                                'Changed': changed, 'NSF': nsf, 
                                'IPv4': ipv4,'IPv6': ipv6}})
        if match:
            return level1, level2

class Config(FactsBase):

    def commands(self):
        return(['show running-config'])

    def populate(self, results):
        self.facts['config'] = results['show running-config']


class Optics(FactsBase):

    def commands(self):
        return(['show controller TenGigE * phy'])

    def populate(self, results):
        self.facts['optics'] = list()
        self.populate_optics(results['show controller TenGigE * phy'])

    def populate_optics(self, data):
        xfpmem, txmem, rxmem = '','',''
        for line in data.split('\n'):
            noxfp = re.search(r'XFP #(.+)$', line)
            xfp = re.search(r'XFP (.+) port:(.+)$', line)
            if xfp:
                xfpmem = xfp.group(0)
            tx = re.search(r'Tx Power:  (.+)$', line)
            if tx:
                txmem = tx.group(0)
            rx = re.search(r'Rx Power:  (.+)$', line)
            if rx:
                rxmem = rx.group(0)
            if (xfpmem and txmem and rxmem):
                self.facts['optics'].append({xfpmem: {'TX': txmem, 'RX': rxmem}})
                xfpmem,txmem,rxmem = '','',''
            elif noxfp:
                self.facts['optics'].append(noxfp.group(0))

class L2vpn(FactsBase):
    def commands(self):
        return(['show l2vpn xconnect'])

    def populate(self, results):
        self.facts['l2vpn'] = self.parse_l2vpn(results['show l2vpn xconnect'])

    def parse_l2vpn(self, data):
        parsed = dict()
        lines = data.split('\n')
        combined = ""
        for line in lines[6:]:
            if line.startswith('--'):
                continue
            elif len(line.split()) <= 6:
                combined += line
            if len(combined.split()) == 8:
                line = combined
                combined = ""
            if len(line.split()) == 8:       
                var = line.split()
                group = var[0]
                name = var[1]
                state = var[2]
                interface = var[3]
                address = var[5]
                parsed.update({name: {'State': state, 'Interface': interface,
                                     'Address': address}})
        return parsed

class Route_Summary(FactsBase):
    def commands(self):
        return(['show route summary'])

    def populate(self, results):
        self.facts['routing_summary'] = self.parse_route_sum(results['show route summary'])

    def parse_route_sum(self, data):
        match = re.search('((?s).*)MET((?s).*)', data)
        routesum = dict()
        for line in match.group(2).split('\n'):
            if not (line.startswith('Route Source') or line == ''):
                var = line.split()
                source = var[0]
                routes = var[1]
                backup = var[2]
                deleted = var[3]
                memory = var[4]
                routesum.update({source: {'Routes': routes, 'Backup': backup,
                                'Deleted': deleted, 'Memory': memory}})
        return routesum

class Routes(FactsBase):
    def commands(self):
        return(['show route', 'show route ipv6'])

    def populate(self, results):
        self.facts['routing_table_IPv4'] = self.parse_route_tablev4(results['show route'])
        self.facts['routing_table_IPv6'] = self.parse_route_tablev6(results['show route ipv6'])

    def parse_route_tablev4(self, data):
        match = re.search('((?s).*)Gateway ((?s).*)', data)
        routetable = dict()
        routetable.update({'BGP': dict()})
        routetable.update({'ISIS': dict()})
        prot = ""
        source = ""
        for line in match.group(2).split('\n'):
            if not (line.startswith('of last') or line == ""): 
                var = line.split()
                if var[0].startswith('B'):
                    prot = 'BGP'
                    source = var[1]
                    protocol, prefered = var[2].strip('[]').split('/')
                    via = var[4]
                    uptime = var[5]
                    routetable['BGP'].update({source: {via: {'Uptime': uptime, 
                                             'Protocol': protocol, 
                                             'Prefered': prefered}}})
                elif var[0].startswith('i'):
                    prot = 'ISIS'
                    source = var[2]
                    protocol, prefered = var[3].strip('[]').split('/')
                    level = var[1]
                    via = var[5]
                    uptime = var[6]
                    interface = var[7]
                    routetable['ISIS'].update({source: {via: {'level': level, 
                                              'Uptime': uptime, 'interface':interface,
                                              'Protocol': protocol, 
                                              'Prefered': prefered}}})
                else:
                    via = var[2]
                    uptime = var[3]              
                    if prot == 'BGP':
                        routetable[prot][source].update({via: {'Uptime': uptime}})
                    elif prot == 'ISIS':
                        interface = var[4]
                        routetable[prot][source].update({via: {'Uptime': uptime,
                                                        'interface': interface}})
        return routetable
                    

    def parse_route_tablev6(self, data):
        match = re.search('((?s).*)Gateway ((?s).*)', data)
        routetable = dict()
        routetable.update({'BGP': dict()})
        routetable.update({'ISIS': dict()})
        routetable.update({'Direct': dict()})
        routetable.update({'Static': dict()})
        prot = ""
        source = ""
        level = ""
        for line in match.group(2).split('\n'):
            if not (line.startswith('of last') or line == ""): 
                var = line.split()
                if var[0].startswith('B'):
                    prot = 'BGP'
                    source = var[1]
                    routetable['BGP'].update({source: dict()})
                elif var[0].startswith('i'):
                    prot = 'ISIS'
                    source = var[2]
                    level = var[1]
                    routetable['ISIS'].update({source: dict()})
                elif var[0].startswith('C') or var[0].startswith('L'):
                    prot = 'Direct'
                    source = var[1]
                    routetable['Direct'].update({source: dict()})
                elif var[0].startswith('S'):
                    prot = 'Static'
                    source = var[1]
                    routetable['Static'].update({source: dict()})
                else:
                    if (prot == 'BGP' or prot == 'ISIS'):
                        via = var[2]
                        uptime = var[3]
                    elif (prot == 'Direct'):
                        uptime = var[0]
                        interface = var[1]
                        routetable[prot][source].update({'Uptime': uptime,
                                                        'Interface': interface})
                    if (prot == 'BGP' or prot == 'Static'):
                        routetable[prot][source].update({via: {'Uptime': uptime}})
                    elif prot == 'ISIS':
                        interface = var[4]
                        routetable[prot][source].update({via: {'Uptime': uptime,
                                                        'interface': interface}})
        return routetable

class Interfaces(FactsBase):

    def commands(self):
        return(['show interfaces', 'show ipv6 interface',
            'show lldp', 'show lldp neighbors detail'])

    def populate(self, results):
        self.facts['all_ipv4_addresses'] = list()
        self.facts['all_ipv6_addresses'] = list()
        interfaces = self.parse_interfaces(results['show interfaces'])
        self.facts['interfaces'] = self.populate_interfaces(interfaces)

        data = results['show ipv6 interface']
        if len(data) > 0:
            data = self.parse_interfaces(data)
            self.populate_ipv6_interfaces(data)
        if 'LLDP is not enabled' not in results['show lldp']:
            neighbors = results['show lldp neighbors detail']
            self.facts['neighbors'] = self.parse_neighbors(neighbors)
	

    def populate_interfaces(self, interfaces):
        facts = dict()
        for key, value in iteritems(interfaces):
            intf = dict()
            intf['description'] = self.parse_description(value)
            intf['macaddress'] = self.parse_macaddress(value)

            ipv4 = self.parse_ipv4(value)
            intf['ipv4'] = self.parse_ipv4(value)
            if ipv4:
                self.add_ip_address(ipv4['address'], 'ipv4')

            intf['mtu'] = self.parse_mtu(value)
            intf['bandwidth'] = self.parse_bandwidth(value)
            intf['duplex'] = self.parse_duplex(value)
            intf['lineprotocol'] = self.parse_lineprotocol(value)
            intf['operstatus'] = self.parse_operstatus(value)
            intf['type'] = self.parse_type(value)
            facts[key] = intf
        return facts

    def populate_ipv6_interfaces(self, data):
        for key, value in iteritems(data):
            if key in ['No', 'RPF'] or key.startswith('IP'):
                continue
            self.facts['interfaces'][key]['ipv6'] = list()
            addresses = re.findall(r'\s+(.+), subnet', value, re.M)
            subnets = re.findall(r', subnet is (.+)$', value, re.M)
            for addr, subnet in zip(addresses, subnets):
                ipv6 = dict(address=addr.strip(), subnet=subnet.strip())
                self.add_ip_address(addr.strip(), 'ipv6')
                self.facts['interfaces'][key]['ipv6'].append(ipv6)

    def add_ip_address(self, address, family):
        if family == 'ipv4':
            self.facts['all_ipv4_addresses'].append(address)
        else:
            self.facts['all_ipv6_addresses'].append(address)

    def parse_neighbors(self, neighbors):
        facts = dict()
        nbors = neighbors.split('------------------------------------------------')
        for entry in nbors[1:]:
            if entry == '':
                continue
            intf = self.parse_lldp_intf(entry)
            if intf not in facts:
                facts[intf] = list()
            fact = dict()
            fact['host'] = self.parse_lldp_host(entry)
            fact['port'] = self.parse_lldp_port(entry)
            facts[intf].append(fact)
        return facts
  

    def parse_interfaces(self, data):
        parsed = dict()
        key = ''
        for line in data.split('\n'):
            if len(line) == 0:
                continue
            elif line[0] == ' ':
                parsed[key] += '\n%s' % line
            else:
                match = re.match(r'^(\S+)', line)
                if match:
                    key = match.group(1)
                    parsed[key] = line
        return parsed

    def parse_description(self, data):
        match = re.search(r'Description: (.+)$', data, re.M)
        if match:
            return match.group(1)

    def parse_macaddress(self, data):
        match = re.search(r'address is (\S+)', data)
        if match:
            return match.group(1)

    def parse_ipv4(self, data):
        match = re.search(r'Internet address is (\S+)/(\d+)', data)
        if match:
            addr = match.group(1)
            masklen = int(match.group(2))
            return dict(address=addr, masklen=masklen)

    def parse_mtu(self, data):
        match = re.search(r'MTU (\d+)', data)
        if match:
            return int(match.group(1))

    def parse_bandwidth(self, data):
        match = re.search(r'BW (\d+)', data)
        if match:
            return int(match.group(1))

    def parse_duplex(self, data):
        match = re.search(r'(\w+) Duplex', data, re.M)
        if match:
            return match.group(1)

    def parse_type(self, data):
        match = re.search(r'Hardware is (.+),', data, re.M)
        if match:
            return match.group(1)

    def parse_lineprotocol(self, data):
        match = re.search(r'line protocol is (.+)\s+?$', data, re.M)
        if match:
            return match.group(1)

    def parse_operstatus(self, data):
        match = re.search(r'^(?:.+) is (.+),', data, re.M)
        if match:
            return match.group(1)

    def parse_lldp_intf(self, data):
        match = re.search(r'^Local Interface: (.+)$', data, re.M)
        if match:
            return match.group(1)

    def parse_lldp_host(self, data):
        match = re.search(r'System Name: (.+)$', data, re.M)
        if match:
            return match.group(1)

    def parse_lldp_port(self, data):
        match = re.search(r'Port id: (.+)$', data, re.M)
        if match:
            return match.group(1)


FACT_SUBSETS = dict(
    default=Default,
    hardware=Hardware,
    interfaces=Interfaces,
    config=Config,
    multicast=Multicast,
    bgp=Bgp,
    isis=Isis,
#    optics=Optics,
    routes=Routes,
    route_summary=Route_Summary,
    l2vpn=L2vpn,
)

VALID_SUBSETS = frozenset(FACT_SUBSETS.keys())


def main():
    spec = dict(
        gather_subset=dict(default=['!config', '!routes'], type='list')
    )

    spec.update(iosxr_argument_spec)

    module = AnsibleModule(argument_spec=spec,
                           supports_check_mode=True)

    warnings = list()
    check_args(module, warnings)

    gather_subset = module.params['gather_subset']

    runable_subsets = set()
    exclude_subsets = set()

    for subset in gather_subset:
        if subset == 'all':
            runable_subsets.update(VALID_SUBSETS)
            continue

        if subset.startswith('!'):
            subset = subset[1:]
            if subset == 'all':
                exclude_subsets.update(VALID_SUBSETS)
                continue
            exclude = True
        else:
            exclude = False

        if subset not in VALID_SUBSETS:
            module.fail_json(msg='Bad subset')

        if exclude:
            exclude_subsets.add(subset)
        else:
            runable_subsets.add(subset)

    if not runable_subsets:
        runable_subsets.update(VALID_SUBSETS)

    runable_subsets.difference_update(exclude_subsets)
    runable_subsets.add('default')

    facts = dict()
    facts['gather_subset'] = list(runable_subsets)

    instances = list()
    for key in runable_subsets:
        instances.append(FACT_SUBSETS[key]())

    try:
        for inst in instances:
            commands = inst.commands()
            responses = run_commands(module, commands)
            results = dict(zip(commands, responses))
            inst.populate(results)
            facts.update(inst.facts)
    except Exception:
        module.exit_json(out=module.from_json(results))

    ansible_facts = dict()
    for key, value in iteritems(facts):
        key = 'ansible_net_%s' % key
        ansible_facts[key] = value

    module.exit_json(ansible_facts=ansible_facts, warnings=warnings)


if __name__ == '__main__':
    main()
