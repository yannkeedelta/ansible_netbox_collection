#!/usr/bin/python
# -*- coding: utf-8 -*-

DOCUMENTATION = r'''
---
module: dcim_manufacturers
short_description: Manage NetBox manufacturers
version_added: "1.0"
description:
  - Create, update, or delete manufacturers in NetBox via the REST API.
  - Allows lookup by various fields and supports idempotent operations.
options:
  manufacturers:
    description:
      - List of manufacturer definitions.
    required: true
    type: list
    elements: dict
    suboptions:
      name:
        description: Manufacturer name.
        required: true
        type: str
      slug:
        description: Optional slug. If not provided, will be auto-generated from name.
        required: false
        type: str
      description:
        description: Optional description of the manufacturer.
        required: false
        type: str
      tags:
        description: List of tags to assign to the manufacturer.
        required: false
        type: list
        elements: str
      lookup:
        description:
          - Optional lookup fields to identify the existing manufacturer.
          - If not specified, the module will attempt to match using name and slug.
        required: false
        type: dict
        suboptions:
          name:
            description: Name to use for lookup.
            type: str
          slug:
            description: Slug to use for lookup.
            type: str
          description:
            description: Description to use for lookup.
            type: str
          tags:
            description:
              - List of tags used for lookup. All tags must match.
              - Useful to disambiguate when multiple manufacturers share the same name or description.
            type: list
            elements: str
  state:
    description:
      - Desired state of the object.
    default: present
    choices: [ absent, present, override ]
    type: str
author:
  - "YannkeeDelta (@yannkeedelta)"
'''

EXAMPLES = r'''
- name: Create a manufacturer
  yannkeedelta.netbox.dcim_manufacturers:
    manufacturers:
      - name: Cisco
        description: Vendor Cisco Systems
        tags: [networking, trusted]

- name: Ensure manufacturer is absent
  yannkeedelta.netbox.dcim_manufacturers:
    manufacturers:
      - name: ObsoleteVendor
        state: absent

- name: Override an existing manufacturer
  yannkeedelta.netbox.dcim_manufacturers:
    manufacturers:
      - name: Juniper
        description: Updated description
        tags: [networking]
        state: override

- name: Lookup with additional fields
  yannkeedelta.netbox.dcim_manufacturers:
    manufacturers:
      - name: HP
        lookup:
          description: Hewlett-Packard Inc.
          tags: [hardware]
'''

RETURN = r'''
manufacturer:
  description: Details of the affected manufacturer.
  type: dict
  returned: when changed or found
changed:
  description: Whether any change was made.
  type: bool
  returned: always
msg:
  description: Description of the action taken.
  type: str
  returned: always
updates:
  description: Fields that were changed.
  type: dict
  returned: when changes were made during update
'''

from ansible.module_utils.basic import AnsibleModule
import pynetbox
import os
from ansible_collections.yannkeedelta.netbox.plugins.module_utils.dcim_manufacturers import DcimManufacturers


def main():
    argument_spec = dict(
        netbox_url=dict(type='str', required=False),
        netbox_token=dict(type='str', required=False, no_log=True),
        manufacturers=dict(type='list', elements='dict', required=True),
        state=dict(type='str', choices=['merged', 'override', 'absent'], default='merged'),
    )

    module = AnsibleModule(argument_spec=argument_spec, supports_check_mode=True)

    netbox_url = module.params['netbox_url'] or os.getenv('NETBOX_API_URL')
    netbox_token = module.params['netbox_token'] or os.getenv('NETBOX_API_TOKEN')
    state = module.params['state']
    manufacturers = module.params['manufacturers']

    if not netbox_url or not netbox_token:
        module.fail_json(msg="NetBox URL and token must be provided either via parameters or environment variables")

    nb = pynetbox.api(netbox_url, token=netbox_token)

    results = []
    changed = False

    for manufacturer in manufacturers:
        handler = DcimManufacturers(api=nb, data=manufacturer, state=state, check_mode=module.check_mode)

        if state == "merged":
            result = handler.ensure_present()
        elif state == "override":
            result = handler.override()
        elif state == "absent":
            result = handler.ensure_absent()
        else:
            result = None
            module.fail_json(msg="Invalid state: {}".format(state))


        if result.get("failed", False):
            module.fail_json(**result)

        results.append(result)
        if result.get("changed", False):
            changed = True

    module.exit_json(changed=changed, results=results)

if __name__ == "__main__":
    main()