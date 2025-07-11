import frappe
from frappe import _
from frappe.utils import cint

def validate_bundle_logic(doc, method):

    if doc.custom_production_type != "Bundle":
        return  # No validation needed

    if not doc.custom_bundle_configuration or len(doc.custom_bundle_configuration) == 0:
        frappe.throw(_("Bundle Configuration required for the production type Bundle, Pleae check on Live Tracking Tab"))

    total_units = 0
    for row in doc.custom_bundle_configuration:
        if not row.bundle_size or not row.total_number_of_bundles:
            frappe.throw(_("Each row in Bundle Configuration must have Bundle Size and Number of Bundles."))

        if cint(row.bundle_size) <= 0:
            frappe.throw(_("Bundle Size must be greater than zero."))

        if cint(row.total_number_of_bundles) <= 0:
            frappe.throw(_("Number of Bundles must be greater than zero."))

        total_units = total_units + ( row.total_number_of_bundles * row.bundle_size)

    if total_units != doc.qty:
        frappe.throw(_("Bundle Configration total units should match in the Qty to Manufacture"))
