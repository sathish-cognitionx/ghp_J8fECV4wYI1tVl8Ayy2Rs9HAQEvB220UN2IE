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

        check_and_unlink_if_final_operation(production_item_doc=production_item_doc)
        

        # Check if all items in the Tracking Order are completed
        result = frappe.db.get_all(
            "Production Item",
            filters={
                "tracking_order": production_item_doc.tracking_order,
                "status": "Completed"
            },
            fields=["sum(quantity) as total"]
        )
        completed_qty = result[0].get("total") or 0

        if completed_qty >= tracking_order.quantity and tracking_order.order_status != "Completed":
            tracking_order.order_status = "Completed"
            tracking_order.save()

    except Exception:
        frappe.log_error(
            message=frappe.get_traceback(),
            title="Error in check_and_complete_production_item"
        )
        raise

def check_and_unlink_if_final_operation(production_item_doc):

    # Handle auto unlink of tags
    if production_item_doc.tracking_tag:
        tag = frappe.get_doc("Tracking Tag", production_item_doc.tracking_tag)
        settings = frappe.get_single("TrackerX Live Settings")

        if getattr(settings, "auto_unlink_at_final_operation", False) and tag.tag_type in ["NFC", "RFID"]:
            pitm_records = frappe.get_all(
                "Production Item Tag Map",
                filters={
                    "production_item": production_item_doc.name,
                    "tracking_tag": production_item_doc.tracking_tag,
                    "is_active": 1
                },
                fields=["name"]
            )

            # Deactivate all mapped tags using doc objects
            for record in pitm_records:
                tag_map_doc = frappe.get_doc("Production Item Tag Map", record.name)
                tag_map_doc.is_active = 0
                tag_map_doc.deactivated_source = "Final Operation"
                tag_map_doc.save()

            # Update production item tracking status directly on the doc
            production_item_doc.tracking_status = "Unlinked"
            production_item_doc.unlinked_source = "Final Process"
            production_item_doc.save()
