import frappe
from trackerx_live.trackerx_live.utils.operation_map_util import OperationMapManager

def check_and_complete_production_item(production_item_doc, current_operation):
    try:
        tracking_order = frappe.get_doc("Tracking Order", production_item_doc.tracking_order)

        op_map = OperationMapManager().get_operation_map(tracking_order.name)

        if not op_map.is_final_operation(current_operation, production_item_doc.component):
            return

        if production_item_doc.status != "Completed":
            production_item_doc.status = "Completed"
            production_item_doc.save()

        completed_qty = frappe.db.get_all(
            "Production Item",
            filters={
                "tracking_order": production_item_doc.tracking_order,
                "status": "Completed"
            },
            fields=["sum(quantity) as total"]
        )[0].total or 0

        if completed_qty >= tracking_order.quantity:
            if tracking_order.order_status != "Completed":
                frappe.db.set_value(
                    "Tracking Order",
                    tracking_order.name,
                    "order_status",
                    "Completed"
                )
    except Exception:
        frappe.log_error(
            message=frappe.get_traceback(),
            title="Error in check_and_complete_production_item"
        )
        raise
