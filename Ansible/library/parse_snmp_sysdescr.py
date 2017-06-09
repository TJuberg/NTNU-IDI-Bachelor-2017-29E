#!/usr/bin/python

# The module is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
#
# The module is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with Ansible.  If not, see <http://www.gnu.org/licenses/>.


from ansible.module_utils.basic import *
import re


def decode_os(sysdescr):
    results = {}
    tokens = {}
    desc = sysdescr.split(',')
    os_vendor = 'Unknown'
    os_type = 'Unknown'
    os_model = 'Unknown'
    os_version = 'Unknown'
    os_buildtime = 'Unknown'

    i = 0
    for string in desc:
        tokens[i] = string.split()
        i += 1

    # This holds true for Cisco and Juniper at least
    os_vendor = tokens[0][0]

    # Cisco
    if tokens[0][0].lower() == 'cisco':
        # Detect Cisco OS type
        if tokens[0][2].lower() == 'software':
            os_type = tokens[0][1].lower()
        else:
            os_type = tokens[0][1].lower() + '_' + tokens[0][2].lower()

        # Find version string
        i = 0
        for string in desc:
            if re.search('version', string, re.IGNORECASE):
                os_version = tokens[i][1]
                break
            i += 1

    # Juniper
    elif tokens[0][0].lower() == 'juniper':
        os_type = tokens[2][1].lower()
        os_model = tokens[1][1]
        os_version = tokens[2][2]
        os_buildtime = tokens[3][2] + ' ' + tokens[3][3]

    results['ansible_os_vendor'] = os_vendor
    results['ansible_os_model'] = os_model
    results['ansible_os_type'] = os_type
    results['ansible_os_version'] = os_version
    results['ansible_os_buildtime'] = os_buildtime

    return results


def main():
    module = AnsibleModule(
            argument_spec=dict(
                sysdescr=dict(required=True)
            )
    )

    m_args = module.params
    results = decode_os(m_args['sysdescr'])

    module.exit_json(ansible_facts=results)


if __name__ == '__main__':
    main()
