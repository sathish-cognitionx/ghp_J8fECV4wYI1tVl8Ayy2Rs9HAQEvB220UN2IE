import frappe
from frappe.utils import flt

@frappe.whitelist()
def get_workstation_by_device_id(device_identifier=None):
    device_id = frappe.db.get_value("Digital Device",{"identifier": device_identifier}, "name")

    workstations = frappe.get_all(
        "Digital Device Workstation Map",
        filters={"digital_device": device_id, "link_status": "Linked"},
        fields=["workstation"]
    )

    return workstations




