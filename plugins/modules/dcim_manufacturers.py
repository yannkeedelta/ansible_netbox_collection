#!/usr/bin/python
# -*- coding: utf-8 -*-


from ansible.module_utils.basic import AnsibleModule
import pynetbox
import os
from ansible_collections.yannkeedelta.netbox.plugins.module_utils.dcim_manufacturers import DcimManufacturers


def main():
    module_args = dict(
        netbox_url=dict(type='str', required=False, default=os.getenv('NETBOX_API_URL')),
        netbox_token=dict(type='str', required=False, default=os.getenv('NETBOX_API_TOKEN'), no_log=True),
        manufacturers=dict(
            type='list',
            required=True,
            elements='dict',
            options=dict(
                name=dict(type='str', required=True),
                slug=dict(type='str', required=False),
                description=dict(type='str', required=False),
                tags=dict(type='list', elements='str', required=False),
                id=dict(type='int', required=False),
            ),
        ),
        state=dict(type='str', required=False, default='merged', choices=['merged', 'overridden', 'deleted', 'gathered']),
    )

    module = AnsibleModule(
        argument_spec=module_args,
        supports_check_mode=True
    )




    state = module.params['state']
    manufacturers = module.params['manufacturers']

    netbox_url = module.params['netbox_url'] or os.getenv('NETBOX_API_URL')
    netbox_token = module.params['netbox_token'] or os.getenv('NETBOX_API_TOKEN')
    nb_api = pynetbox.api(netbox_url, token=netbox_token)

    if not netbox_url or not netbox_token:
        module.fail_json(msg="NetBox URL and token must be provided either via parameters or environment variables")


    results = []
    changed = False

    for manufacturer in manufacturers:
        dcim_manufacturer = DcimManufacturers(api=nb_api, data=manufacturer, check_mode=module.check_mode)

        if state == "gathered":
            result = dcim_manufacturer.gather_element()
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