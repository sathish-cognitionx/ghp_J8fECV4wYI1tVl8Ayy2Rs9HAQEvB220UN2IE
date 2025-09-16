import frappe

def is_last_operation(production_item, current_operation):
    """
    Temporary hardcoded logic for last operation check.
    Toggle True/False for testing.
    Later we will replace with actual operation map check.
    """
    return False  


def check_and_complete_production_item(production_item_doc, current_operation):

    try:
       
        tracking_order = frappe.get_doc("Tracking Order", production_item_doc.tracking_order)

        if not is_last_operation(production_item_doc, current_operation):
            return

        if production_item_doc.status != "Completed":
            production_item_doc.status = "Completed"
            production_item_doc.save()

        completed_items = frappe.db.count(
            "Production Item",
            filters={
                "tracking_order": production_item_doc.tracking_order,
                "status": "Completed"
            }
        )

        total_bundles = 0
        if tracking_order.component_bundle_configurations:
            for row in tracking_order.component_bundle_configurations:
                total_bundles += row.number_of_bundles or 0

        if completed_items < total_bundles:
            return

        if tracking_order.order_status != "Completed":
            frappe.db.set_value(
                "Tracking Order",
                tracking_order.name,
                "order_status",
                "Completed"
            )
            

    except Exception as e:
        frappe.log_error(
            message=frappe.get_traceback(),
            title="Error in check_and_complete_production_item"
        )
        raise
