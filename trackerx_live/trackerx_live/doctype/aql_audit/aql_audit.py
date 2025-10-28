# Copyright (c) 2025, CognitionX and contributors
# For license information, please see license.txt

import frappe
from frappe.model.document import Document
from frappe.utils import nowdate


class AQLAudit(Document):
	pass


@frappe.whitelist()
def get_work_orders(search=None):
    filters = {}
    if search:
        filters["name"] = ["like", f"%{search}%"]

    # Get all work orders
    work_orders = frappe.get_all(
        "Work Order",
        filters=filters,
        fields=["name", "production_item", "qty", "status"],
        limit_page_length=50,
        order_by="creation desc"
    )

    result = []

    for wo in work_orders:
        # 🔹 Check if any AQL Audit exists for this Work Order
        aql = frappe.db.get_value(
            "AQL Audit",
            {"work_order": wo.name},
            ["name", "audit_result", "style", "color", "order_qty", "audit_date", "inspected_by"],
            as_dict=True
        )

        # 🔸 Skip work orders with "Pass" result in AQL Audit
        if aql and (aql.audit_result or "").lower() == "pass":
            continue

        # 🔹 Fetch item details for color & style if not in AQL
        style = color = ""
        if wo.production_item:
            item = frappe.get_doc("Item", wo.production_item)
            style = getattr(item, "custom_style_name", "") or item.item_name
            color = getattr(item, "custom_colour_name", "") or "-"

        # 🔸 If AQL Audit exists, override fields with its data
        if aql:
            style = aql.style or style
            color = aql.color or color
            order_qty = aql.order_qty or wo.qty
            audit_result = aql.audit_result or "Pending"
            audit_date = aql.audit_date or ""
            inspected_by = aql.inspected_by or frappe.session.user
        else:
            order_qty = wo.qty
            audit_result = "Pending"
            audit_date = ""
            inspected_by = frappe.session.user

        # 🔹 Add the final row data
        result.append({
            "work_order": wo.name,
            "style": style,
            "color": color,
            "order_qty": order_qty,
            "received_qty": 0,
            "vendor": "",
            "audit_date": audit_date,
            "audit_result": audit_result,
            "inspected_by": inspected_by,
            "aql_audit": aql.name if aql else None
        })

    return result




# @frappe.whitelist()
# def update_aql_audit(work_order, audit_result, inspected_by):
#     if not work_order:
#         return {"status": "error", "message": "Work Order is required"}

#     audit_date = nowdate()

#     # Lock if already Passed
#     current_status = frappe.db.get_value("Work Order", work_order, "audit_result")
#     if current_status == "Pass":
#         return {"status": "error", "message": "Audit already passed. Changes not allowed."}

#     frappe.db.set_value("Work Order", work_order, {
#         "audit_result": audit_result,
#         "inspected_by": inspected_by,
#         "audit_date": audit_date
#     })

#     return {"status": "success", "message": "Audit updated successfully"}

    

@frappe.whitelist()
def create_aql_audit(work_order,audit_date=None, color=None, audit_result=None, style=None, order_qty=None, inspected_by=None):
    # default inspected_by to current user if not provided
    if not inspected_by:
        inspected_by = frappe.session.user

    existing = frappe.db.exists("AQL Audit", {"work_order": work_order})
    
    if existing:
        doc = frappe.get_doc("AQL Audit", existing)
        doc.update({
            "audit_result": audit_result,
            "inspected_by": inspected_by,
            "color": color,
            "style": style,
            "order_qty": order_qty,
            "audit_date" : nowdate()
        })
        doc.save(ignore_permissions=True)
        frappe.db.commit()
        return {"status": "success", "message": f"AQL Audit updated for {work_order}"}

    # create new AQL Audit
    doc = frappe.get_doc({
        "doctype": "AQL Audit",
        "work_order": work_order,
        "audit_result": audit_result,
        "color": color,
        "style": style,
        "order_qty": order_qty,
        "inspected_by": inspected_by,
        "audit_date" : nowdate()
    })
    doc.insert(ignore_permissions=True)
    frappe.db.commit()

    return {"status": "success", "message": f"AQL Audit created for {work_order}"}
