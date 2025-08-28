import frappe

@frappe.whitelist(allow_guest=True)
def get_production_items():
    items = frappe.get_all('Production Item', fields=[
        'name',
        'production_item_number',
        'tracking_order',
        'bundle_configuration',
        'component',
        'status',
        'current_operation',
        'current_workstation',
    ])

    return {"production_items": items}

