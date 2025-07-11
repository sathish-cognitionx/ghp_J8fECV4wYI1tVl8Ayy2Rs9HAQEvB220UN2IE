import frappe
from frappe import _

@frappe.whitelist()
def get_work_order_details(work_order_name):
    if not work_order_name:
        frappe.throw(_("Missing Work Order name"))

    doc = frappe.get_doc("Work Order", work_order_name)

    # Gather basic info
    result = {
        "name": doc.name,
        "production_item": doc.production_item,
        "qty": doc.qty,
        "status": doc.status,
        "production_type": doc.custom_production_type,
        "bundle_configuration": []
    }

    # Add bundle child table details if production_type == Bundle
    if doc.custom_production_type == "Bundle":
        for row in doc.custom_bundle_configuration:
            result["bundle_configuration"].append({
                "bundle_size": row.bundle_size,
                "total_number_of_bundles": row.total_number_of_bundles
            })

    return result
