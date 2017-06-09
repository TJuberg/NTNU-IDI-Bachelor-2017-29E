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
module: junos_facts
version_added: "2.1"
author: "Nathaniel Case (@qalthos)"
short_description: Collect facts from remote devices running Junos
description:
  - Collects fact information from a remote device running the Junos
    operating system.  By default, the module will collect basic fact
    information from the device to be included with the hostvars.
    Additional fact information can be collected based on the
    configured set of arguments.
extends_documentation_fragment: junos
options:
  gather_subset:
    description:
      - When supplied, this argument will restrict the facts collected
        to a given subset.  Possible values for this argument include
        all, hardware, config, interfaces, interfaces_ext, optics, temperatures, bgp_summary,
        bgp_peers, snapshots, route_summary, routes, isis_overview, route_engine and
        l2vpn.  Can specify a list of values to include a larger subset.
        Values can also be used with an initial C(M(!)) to specify that a
        specific subset should not be collected.
    required: false
    default: "!config,!bgp_peers,!routes"
    version_added: "2.3"
"""

EXAMPLES = """
- name: collect default set of facts
  junos_facts:

- name: collect default set of facts and configuration
  junos_facts:
    gather_subset: config
"""

RETURN = """
ansible_facts:
  description: Returns the facts collect from the device
  returned: always
  type: dict
"""

import re
from xml.etree.ElementTree import Element, SubElement, tostring

from ansible.module_utils.basic import AnsibleModule
from ansible.module_utils.six import iteritems
from ansible.module_utils.junos import junos_argument_spec, check_args
from ansible.module_utils.junos import command, get_configuration
from ansible.module_utils.netconf import send_request

USE_PERSISTENT_CONNECTION = True


class FactsBase(object):
    def __init__(self, module):
        self.module = module
        self.facts = dict()

    def populate(self):
        raise NotImplementedError

    # noinspection PyShadowingNames
    def cli(self, command):
        reply = command(self.module, command)
        output = reply.find('.//output')
        if not output:
            self.module.fail_json(msg='failed to retrieve facts for command %s' % command)
        return str(output.text).strip()

    def rpc(self, rpc):
        return send_request(self.module, Element(rpc))

    def get_text(self, ele, tag):
        try:
            return str(ele.find(tag).text).strip()
        except AttributeError:
            pass

    def clean_text(self, text):
        return str(text).strip()

    def is_enabled(self, ele, tag):
        if self.get_text(ele, tag) == 'None':
            return str('Enabled')
        else:
            return str('Disabled')

    def match_model(self, match):
        reply = self.rpc('get-software-information')
        data = reply.find('.//software-information')
        model = self.get_text(data, 'product-model')
        res = re.match(r'(' + match + ')[0-9]*[a-z]*', model)
        if res:
            return True
        else:
            return False

    def match_model_number(self, match):
        reply = self.rpc('get-software-information')
        data = reply.find('.//software-information')
        model = self.get_text(data, 'product-model')
        res = re.match(r'[a-z]+(' + match + ')[a-z]*', model)
        if res:
            return True
        else:
            return False

    def iterate_xml_subset(self, subset, ignore_tag='name'):
        obj = {}
        for item in subset:
            if not item.getchildren() and item.tag != ignore_tag:
                obj[item.tag] = self.get_text(item)
        return obj

    def iterate_xml_subset_recursive(self, subset, tag, ignore_tag='name', recurse=False):
        obj = {}
        for item in subset.iter(tag):
            name = self.get_text(item, 'name')

            if name is None or name == 'null':
                name = item.tag

            if not recurse:
                obj[name] = {}

            i = 0
            for entry in item:
                if entry.tag == ignore_tag:
                    continue

                if recurse:
                    if entry.getchildren():
                        r_name = entry.tag
                        if r_name not in obj:
                            obj[r_name] = {}

                        try:
                            r_name_counter
                        except NameError:
                            r_name_counter = 0

                        # sjekk om det finnes mer enn 1 barn

                        obj[r_name ][r_name_counter] = self.iterate_xml_subset_recursive(entry, entry.tag, r_name, True)
                        r_name_counter += 1
                    else:
                        obj[entry.tag] = self.clean_text(entry.text)
                else:
                    if entry.getchildren():
                        r_name = entry.tag
                        if r_name not in obj[name]:
                            obj[name][r_name] = {}

                        obj[name][r_name][i] = self.iterate_xml_subset_recursive(entry, entry.tag, r_name, True)
                        i += 1
                    else:
                        obj[name][entry.tag] = self.clean_text(entry.text)
        return obj


class Default(FactsBase):
    def populate(self):
        reply = self.rpc('get-software-information')
        data = reply.find('.//software-information')

        self.facts.update({
            'hostname': self.get_text(data, 'host-name'),
            'version': self.get_text(data, 'junos-version'),
            'model': self.get_text(data, 'product-model')
        })

        reply = self.rpc('get-chassis-inventory')
        data = reply.find('.//chassis-inventory/chassis')

        self.facts['serialnum'] = self.get_text(data, 'serial-number')


class Config(FactsBase):
    def populate(self):
        config_format = self.module.params['config_format']
        reply = get_configuration(self.module, format=config_format)
        config = ''

        if config_format == 'xml':
            config = tostring(reply.find('configuration')).strip()

        elif config_format == 'text':
            config = self.get_text(reply, 'configuration-text')

        elif config_format == 'json':
            config = str(reply.text).strip()

        elif config_format == 'set':
            config = self.get_text(reply, 'configuration-set')

        self.facts['config'] = config


class Hardware(FactsBase):
    def populate(self):
        reply = self.rpc('get-system-memory-information')
        data = reply.find('.//system-memory-information/system-memory-summary-information')

        self.facts.update({
            'memfree_mb': int(self.get_text(data, 'system-memory-free')),
            'memtotal_mb': int(self.get_text(data, 'system-memory-total'))
        })

        reply = self.rpc('get-system-storage')
        data = reply.find('.//system-storage-information')

        filesystems = list()
        for obj in data:
            filesystems.append(self.get_text(obj, 'filesystem-name'))
        self.facts['filesystems'] = filesystems


class Interfaces(FactsBase):
    def populate(self):
        ele = Element('get-interface-information')
        SubElement(ele, 'detail')
        reply = send_request(self.module, ele)

        interfaces = {}

        for item in reply[0]:
            name = self.get_text(item, 'name')
            obj = {
                'oper-status': self.get_text(item, 'oper-status'),
                'admin-status': self.get_text(item, 'admin-status'),
                'speed': self.get_text(item, 'speed'),
                'macaddress': self.get_text(item, 'hardware-physical-address'),
                'mtu': self.get_text(item, 'mtu'),
                'type': self.get_text(item, 'if-type'),
                'description': self.get_text(item, 'description'),
            }

            interfaces[name] = obj

        self.facts['interfaces'] = interfaces


class InterfacesExt(FactsBase):
    def populate(self):
        ele = Element('get-interface-information')
        SubElement(ele, 'detail')
        reply = send_request(self.module, ele)
        data = reply.find('interface-information')

        interfaces = {}

        for item in data.iter('physical-interface'):
            name = self.get_text(item, 'name')
            interfaces[name] = self.iterate_xml_subset(item, 'name')
            for entry in item.iter('traffic-statistics'):
                interfaces[name][entry.tag] = self.iterate_xml_subset(entry)
                if entry.getchildren():
                    for ipv6 in entry:
                        interfaces[name][entry.tag][ipv6.tag] = self.iterate_xml_subset(ipv6)
            for entry in item.iter('if-device-flags'):
                interfaces[name][entry.tag] = self.iterate_xml_subset(entry)
            for entry in item.iter('ifd-specific-config-flags'):
                interfaces[name][entry.tag] = self.iterate_xml_subset(entry)
            for entry in item.iter('if-config-flags'):
                interfaces[name][entry.tag] = self.iterate_xml_subset(entry)
            for logical in item.iter('logical-interface'):
                l_name = self.get_text(logical, 'name')
                interfaces[name][l_name] = self.iterate_xml_subset(logical, 'name')
                for entry in logical.iter('traffic-statistics'):
                    interfaces[name][l_name][entry.tag] = self.iterate_xml_subset(entry)
                for entry in logical.iter('local-traffic-statistics'):
                    interfaces[name][l_name][entry.tag] = self.iterate_xml_subset(entry)
                for entry in logical.iter('transit-traffic-statistics'):
                    interfaces[name][l_name][entry.tag] = self.iterate_xml_subset(entry)
                for entry in logical.iter('filter-information'):
                    interfaces[name][l_name][entry.tag] = self.iterate_xml_subset(entry)
                for entry in logical.iter('address-family'):
                    interfaces[name][l_name][entry.tag] = self.iterate_xml_subset(entry)
                    for flag in entry.iter('address-family-flags'):
                        interfaces[name][l_name][entry.tag][flag.tag] = self.iterate_xml_subset(flag)
        self.facts['interfaces_ext'] = interfaces
        #self.facts['interfaces_ext'] = self.iterate_xml_subset_recursive(data, 'physical-interface')


class Optics(FactsBase):
    def populate(self):
        if self.match_model('mx|m|t|ex|qfx'):
            reply = self.rpc('get-interface-optics-diagnostics-information')
            data = reply.find('interface-information')
            optics = {}

            for item in data.iter('physical-interface'):
                name = self.get_text(item, 'name')
                optics[name] = {}
                for subitem in item.find('optics-diagnostics'):
                    optics[name][subitem.tag] = subitem.text.strip()
        else:
            optics = 'Not supported'
        self.facts['optics'] = optics


class BgpSummary(FactsBase):
    def populate(self):
        if self.match_model('mx|m|t|ex|qfx'):
            reply = self.rpc('get-bgp-summary-information')
            data = reply.find('.//bgp-information')

            if data is not None:
                bgp = {
                    'rib': {},
                    'peer': {},
                    'group-count': self.get_text(data, 'group-count'),
                    'peer-count': self.get_text(data, 'peer-count'),
                    'down-peer-count': self.get_text(data, 'down-peer-count')
                }

                for item in data.iter('bgp-rib'):
                    name = self.get_text(item, 'name')
                    obj = {
                        'total-prefix-count':
                            self.get_text(item, 'total-prefix-count'),
                        'received-prefix-count':
                            self.get_text(item, 'received-prefix-count'),
                        'accepted-prefix-count':
                            self.get_text(item, 'accepted-prefix-count'),
                        'active-prefix-count':
                            self.get_text(item, 'active-prefix-count'),
                        'suppressed-prefix-count':
                            self.get_text(item, 'suppressed-prefix-count'),
                        'history-prefix-count':
                            self.get_text(item, 'history-prefix-count'),
                        'damped-prefix-count':
                            self.get_text(item, 'damped-prefix-count'),
                        'total-external-prefix-count':
                            self.get_text(item, 'total-external-prefix-count'),
                        'active-external-prefix-count':
                            self.get_text(item, 'active-external-prefix-count'),
                        'suppressed-external-prefix-count':
                            self.get_text(item, 'suppressed-external-prefix-count'),
                        'total-internal-prefix-count':
                            self.get_text(item, 'total-internal-prefix-count'),
                        'active-internal-prefix-count':
                            self.get_text(item, 'active-internal-prefix-count'),
                        'accepted-internal-prefix-count':
                            self.get_text(item, 'accepted-internal-prefix-count'),
                        'suppressed-internal-prefix-count':
                            self.get_text(item, 'suppressed-internal-prefix-count'),
                        'pending-prefix-count':
                            self.get_text(item, 'pending-prefix-count'),
                        'bgp-rib-state':
                            self.get_text(item, 'bgp-rib-state'),
                    }
                    bgp['rib'][name] = obj

                for item in data.iter('bgp-peer'):
                    name = self.get_text(item, 'peer-address')
                    obj = {
                        'peer-as':
                            self.get_text(item, 'peer-as'),
                        'input-messages':
                            self.get_text(item, 'input-messages'),
                        'output-messages':
                            self.get_text(item, 'output-messages'),
                        'route-queue-count':
                            self.get_text(item, 'route-queue-count'),
                        'flap-count':
                            self.get_text(item, 'flap-count'),
                        'elapsed-time':
                            self.get_text(item, 'elapsed-time'),
                        'peer-state':
                            self.get_text(item, 'peer-state'),
                    }
                    bgp['peer'][name] = obj
                    for rib in item.iter('bgp-rib'):
                        rib_name = self.get_text(rib, 'name')
                        obj = {
                            'received-prefix-count':
                                self.get_text(rib, 'received-prefix-count'),
                            'accepted-prefix-count':
                                self.get_text(rib, 'accepted-prefix-count'),
                            'active-prefix-count':
                                self.get_text(rib, 'active-prefix-count'),
                            'suppressed-prefix-count':
                                self.get_text(rib, 'suppressed-prefix-count'),
                        }
                        bgp['peer'][name][rib_name] = obj
            else:
                bgp = self.get_text(reply, 'output')
        else:
            bgp = 'Not supported'

        self.facts['bgp_summary'] = bgp


class BgpPeers(FactsBase):
    def populate(self):
        if self.match_model('mx|m|t|ex|qfx'):
            reply = self.rpc('get-bgp-neighbor-information')
            data = reply.find('.//bgp-information')

            if data is not None:
                bgp = {}

                for item in data.iter('bgp-peer'):
                    name = self.get_text(item, 'peer-address')
                    obj = {
                        'peer-as':
                            self.get_text(item, 'peer-as'),
                        'local-address':
                            self.get_text(item, 'local-address'),
                        'local-as':
                            self.get_text(item, 'local-as'),
                        'peer-type':
                            self.get_text(item, 'peer-type'),
                        'peer-state':
                            self.get_text(item, 'peer-state'),
                        'peer-flags':
                            self.get_text(item, 'peer-flags'),
                        'last-state':
                            self.get_text(item, 'last-state'),
                        'last-error':
                            self.get_text(item, 'last-error'),
                        'flap-count':
                            self.get_text(item, 'flap-count'),
                        'peer-id':
                            self.get_text(item, 'peer-id'),
                        'local-id':
                            self.get_text(item, 'local-id'),
                        'local-interface-name':
                            self.get_text(item, 'local-interface-name'),
                        'peer-restart-nlri-configured':
                            self.get_text(item, 'peer-restart-nlri-configured'),
                        'nlri-type-peer':
                            self.get_text(item, 'nlri-type-peer'),
                        'nlri-type-session':
                            self.get_text(item, 'nlri-type-session'),
                    }
                    bgp[name] = obj

                    subitem = item.find('.//bgp-option-information')
                    bgp[name]['options'] = {
                        'export-policy':
                            self.get_text(subitem, 'export-policy'),
                        'import-policy':
                            self.get_text(subitem, 'import-policy'),
                        'bgp-options2':
                            self.get_text(subitem, 'bgp-options2'),
                        'address-families':
                            self.get_text(subitem, 'address-families'),
                    }

                    for rib in item.iter('bgp-rib'):
                        ribname = self.get_text(rib, 'name')
                        bgp[name][ribname] = {
                            'send-state':
                                self.get_text(rib, 'send-state'),
                            'active-prefix-count':
                                self.get_text(rib, 'active-prefix-count'),
                            'received-prefix-count':
                                self.get_text(rib, 'received-prefix-count'),
                            'accepted-prefix-count':
                                self.get_text(rib, 'accepted-prefix-count'),
                            'suppressed-prefix-count':
                                self.get_text(rib, 'suppressed-prefix-count'),
                        }
            else:
                bgp = self.get_text(reply, 'output')
        else:
            bgp = 'Not supported'
        self.facts['bgp_neighbors'] = bgp


class Temperatures(FactsBase):
    def populate(self):
        if self.match_model('mx|m|t|ex|qfx'):
            ele = Element('get-environment-information')
            reply = send_request(self.module, ele)

            temperature = {}
            fans = {}
            for item in reply[0]:
                name = self.get_text(item, 'name')
                classification = self.get_text(item, 'class')
                if classification is None or classification == 'Temp':
                    obj = {
                        'status': self.get_text(item, 'status'),
                        'temperature': self.get_text(item, 'temperature'),
                    }
                    temperature[name] = obj

                elif classification == 'Fans':
                    obj = {
                        'status': self.get_text(item, 'status'),
                        'comment': self.get_text(item, 'comment'),
                    }
                    fans[name] = obj
        else:
            temperature = 'Not supported'
            fans = temperature

        self.facts['temperature'] = temperature
        self.facts['fans'] = fans


class Snapshots(FactsBase):
    def populate(self):
        if self.match_model('mx|m|t|ex|qfx'):
            if self.match_model('mx') and \
                            self.match_model_number('104') is False:
                snapshots = {'packages': {}}

                reply = self.rpc('get-snapshot-information')
                data = reply.find('.//snapshot-information')
                if data is not None:
                    snapshots['medium'] = self.get_text(data, 'snapshot-medium')

                    for item in data.iter('package'):
                        name = self.get_text(item, 'package-name')
                        snapshots[name] = self.get_text(item, 'package-version')
            else:
                snapshots = 'Not supported'
        else:
            snapshots = 'Not supported'
        self.facts['snapshots'] = snapshots


class RouteSummary(FactsBase):
    def populate(self):
        if self.match_model('mx|m|t|ex|qfx'):
            summary = {}
            reply = self.rpc('get-route-summary-information')
            data = reply.find('.//route-summary-information')

            name = self.get_text(data, 'as-number')
            summary[name] = {}
            summary[name]['router-id'] = self.get_text(data, 'router-id')
            for item in data.iter('route-table'):
                table_name = self.get_text(item, 'table-name')
                obj = {
                    'destination-count':
                        self.get_text(item, 'destination-count'),
                    'total-route-count':
                        self.get_text(item, 'total-route-count'),
                    'active-route-count':
                        self.get_text(item, 'active-route-count'),
                    'holddown-route-count':
                        self.get_text(item, 'holddown-route-count'),
                    'hidden-route-count':
                        self.get_text(item, 'hidden-route-count'),
                }
                summary[name][table_name] = obj

                for subitem in item.iter('protocols'):
                    protocol_name = self.get_text(subitem, 'protocol-name')
                    obj = {
                        'protocol-route-count':
                            self.get_text(subitem, 'protocol-route-count'),
                        'active-route-count':
                            self.get_text(subitem, 'active-route-count'),
                    }
                    summary[name][table_name][protocol_name] = obj
        else:
            summary = 'Not supported'
        self.facts['route_summary'] = summary


class Routes(FactsBase):
    def populate(self):
        if self.match_model('mx|m|t|ex|qfx'):
            routes = {}
            reply = self.rpc('get-route-information')
            data = reply.find('.//route-information')

            for item in data.iter('route-table'):
                name = self.get_text(item, 'table-name')
                obj = {
                    'destination-count':
                        self.get_text(item, 'destination-count'),
                    'total-route-count':
                        self.get_text(item, 'total-route-count'),
                    'active-route-count':
                        self.get_text(item, 'active-route-count'),
                    'holddown-route-count':
                        self.get_text(item, 'holddown-route-count'),
                    'hidden-route-count':
                        self.get_text(item, 'hidden-route-count'),
                }
                routes[name] = obj
                routes[name]['routing-table'] = {}

                for rt in item.iter('rt'):
                    destination = self.get_text(rt, 'rt-destination')
                    i = 0
                    for entry in rt.iter('rt-entry'):
                        routes[name][destination] = {}
                        obj = {
                            'active-tag':
                                self.get_text(entry, 'active-tag'),
                            'current-active':
                                self.get_text(entry, 'current-active'),
                            'last-active':
                                self.get_text(entry, 'last-active'),
                            'protocol-name':
                                self.get_text(entry, 'protocol-name'),
                            'preference':
                                self.get_text(entry, 'preference'),
                            'age':
                                self.get_text(entry, 'age'),
                            'local-preference':
                                self.get_text(entry, 'local-preference'),
                            'learned-from':
                                self.get_text(entry, 'learned-from'),
                            'as-path':
                                self.get_text(entry, 'as-path'),
                        }
                        routes[name][destination][i] = obj

                        j = 0
                        for nh in entry.iter('nh'):
                            obj = {
                                'selected-next-hop':
                                    self.get_text(nh, 'selected-next-hop'),
                                'to':
                                    self.get_text(nh, 'to'),
                                'via':
                                    self.get_text(nh, 'via'),
                            }
                            routes[name][destination][i][j] = obj
                            j += 1

                        i += 1
        else:
            routes = 'Not supported'
        self.facts['routes'] = routes


class ISISOverview(FactsBase):
    def populate(self):
        if self.match_model('mx|m|t|ex|qfx'):
            reply = self.rpc('get-isis-overview-information')
            data = reply.find('.//isis-overview-information')

            isis = {}
            for item in data.iter('isis-overview'):
                name = self.get_text(item, 'instance-name')
                obj = {
                    'router-id':
                        self.get_text(item, 'isis-router-id'),
                    'router-hostname':
                        self.get_text(item, 'isis-router-hostname'),
                    'router-sysid':
                        self.get_text(item, 'isis-router-sysid'),
                    'router-areaid':
                        self.get_text(item, 'isis-router-areaid'),
                    'adjacency-holddown':
                        self.get_text(item, 'isis-adjacency-holddown'),
                    'max-areas':
                        self.get_text(item, 'isis-max-areas'),
                    'lsp-lifetime':
                        self.get_text(item, 'isis-lsp-lifetime'),
                    'attached-bit-evaluation':
                        self.get_text(item, 'isis-attached-bit-evaluation'),
                }
                isis[name] = obj

                spf = item.find('.//isis-spf-information')
                isis['spf-delay'] = self.get_text(spf, 'isis-spf-delay')
                isis['spf-holddown'] = self.get_text(spf, 'isis-spf-holddown')
                isis['spf-rapid-runs'] = self.get_text(spf, 'isis-spf-rapid-runs')

                routing = item.find('.//isis-routing')
                isis['routing-ipv4'] = self.is_enabled(routing, 'isis-routing-ipv4')
                isis['routing-ipv6'] = self.is_enabled(routing, 'isis-routing-ipv6')

                te = item.find('.//isis-traffic-engineering')
                isis['traffic-engineering'] = self.get_text(te, 'isis-te-status')

                restart = item.find('.//isis-restart')
                isis['restart'] = self.get_text(restart, 'isis-restart-enabled')
                isis['helper-mode'] = self.get_text(restart, 'isis-restart-helper-mode-enabled')

                spring = item.find('.//isis-spring')
                isis['spring'] = self.get_text(spring, 'isis-spring-enabled')

                for level in item.iter('isis-level-information'):
                    name = self.get_text(level, 'isis-level')
                    obj = {
                        'preference':
                            self.get_text(level, 'isis-preference'),
                        'external-preference':
                            self.get_text(level, 'isis-external-preference'),
                        'prefix-export-count':
                            self.get_text(level, 'isis-prefix-export-count'),
                        'narrow-metrics':
                            self.is_enabled(level, 'isis-narrow-metrics'),
                        'wide-metrics':
                            self.is_enabled(level, 'isis-wide-metrics'),
                    }
                    isis['level' + name] = obj
        else:
            isis = 'Not supported'
        self.facts['isis_overview'] = isis


class RouteEngine(FactsBase):
    def populate(self):
        if self.match_model('mx|m|t|ex|qfx'):
            reply = self.rpc('get-route-engine-information')
            data = reply.find('.//route-engine-information')

            route_engine = {}
            for item in data.iter('route-engine'):
                slot = self.get_text(item, 'slot')
                route_engine[slot] = {}
                for subitem in item:
                    route_engine[slot][subitem.tag] = subitem.text.strip()
        else:
            route_engine = 'Not supported'
        self.facts['route-engine'] = route_engine


class L2vpn(FactsBase):
    def populate(self):
        if self.match_model('mx|m|t|ex|qfx'):
            reply = self.rpc('get-l2ckt-connection-information')
            data = reply.find('.//l2circuit-connection-information')

            l2vpn = {}
            for item in data.iter('l2circuit-neighbor'):
                name = self.get_text(item, 'neighbor-address')
                for conn in item.iter('connection'):
                    obj = {
                        'id':
                            self.get_text(conn, 'connection-id'),
                        'type':
                            self.get_text(conn, 'connection-type'),
                        'status':
                            self.get_text(conn, 'connection-status'),
                        'last-change':
                            self.get_text(conn, 'last-change'),
                        'up-transitions':
                            self.get_text(conn, 'up-transitions'),
                        'remote-pe':
                            self.get_text(conn, 'remote-pe'),
                        'control-word':
                            self.get_text(conn, 'control-word'),
                        'inbound-label':
                            self.get_text(conn, 'inbound-label'),
                        'outbound-label':
                            self.get_text(conn, 'outbound-label'),
                        'pw-status-tlv':
                            self.get_text(conn, 'pw-status-tlv'),
                        'vc-flow-label-transmit':
                            self.get_text(conn, 'vc-flow-label-transmit'),
                        'vc-flow-label-receive':
                            self.get_text(conn, 'vc-flow-label-receive'),
                    }
                    l2vpn[name] = obj
                    iface = conn.find('../local-interface')
                    l2vpn[name]['interface-name'] = self.get_text(iface, 'interface-name')
                    l2vpn[name]['interface-status'] = self.get_text(iface, 'interface-status')
                    l2vpn[name]['interface-encapsulation'] = self.get_text(iface, 'interface-encapsulation')
        else:
            l2vpn = 'Not supported'
        self.facts['l2vpn'] = l2vpn


FACT_SUBSETS = dict(
    default=Default,
    hardware=Hardware,
    config=Config,
    interfaces=Interfaces,
    interfaces_ext=InterfacesExt,
    optics=Optics,
    temperatures=Temperatures,
    bgp_summary=BgpSummary,
    bgp_peers=BgpPeers,
    snapshots=Snapshots,
    route_summary=RouteSummary,
    routes=Routes,
    isis_overview=ISISOverview,
    route_engine=RouteEngine,
    l2vpn=L2vpn,
)

VALID_SUBSETS = frozenset(FACT_SUBSETS.keys())


def main():
    """ Main entry point for AnsibleModule
    """
    argument_spec = dict(
        gather_subset=dict(default=['!config', '!routes', '!bgppeers'], type='list'),
        config_format=dict(default='text', choices=['xml', 'text', 'set', 'json']),
    )

    argument_spec.update(junos_argument_spec)

    module = AnsibleModule(argument_spec=argument_spec,
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
            module.fail_json(msg='Subset must be one of [%s], got %s' %
                                 (', '.join(VALID_SUBSETS), subset))

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
        instances.append(FACT_SUBSETS[key](module))

    for inst in instances:
        inst.populate()
        facts.update(inst.facts)

    ansible_facts = dict()
    for key, value in iteritems(facts):
        key = 'ansible_net_%s' % key
        ansible_facts[key] = value

    module.exit_json(ansible_facts=ansible_facts, warnings=warnings)


if __name__ == '__main__':
    main()
