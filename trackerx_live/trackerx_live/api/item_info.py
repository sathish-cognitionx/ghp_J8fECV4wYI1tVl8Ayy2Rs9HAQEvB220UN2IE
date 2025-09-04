import frappe
from frappe import _

@frappe.whitelist()
def get_item_information(tag_number):
    if not tag_number:
        frappe.throw(_("Tag Number is required"))

    # Step 1: Check if Tracking Tag exists
    tracking_tag = frappe.get_value("Tracking Tag", {"tag_number": tag_number}, "name")
    if not tracking_tag:
        frappe.throw(_("Invalid Tag Number"))

    # Step 2: Check mapping in Production Item Tag Map
    mapping = frappe.get_doc("Production Item Tag Map", {
        "tracking_tag": tracking_tag,
        "is_active": 1
    })

    if not mapping:
        frappe.throw(_("No active production item linked with this tag"))

    production_item_name = mapping.production_item

    # Step 3: Get Production Item details
    item = frappe.get_doc("Production Item", production_item_name)

    # Step 4: Return response
    return {
        "production_item_number": item.production_item_number,
        "tracking_order": item.tracking_order,
        "bundle_configuration": item.bundle_configuration,
        "component": item.component,
        "size": item.size,
        "quantity": item.quantity,
        "status": item.status,
        "current_operation": item.current_operation,
        "next_operation": item.next_operation,
        "current_workstation":item.current_workstation,
        "next_workstation":item.next_workstation
    }