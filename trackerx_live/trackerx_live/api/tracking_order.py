import frappe
from frappe import _

@frappe.whitelist()
def get_tracking_orders_pending_activation():
    """
    Fetch all Tracking Orders with activation_status in (Ready, In Progress)
    along with their components and reference order details.
    """
    try:
        result = []

        # Fetch Tracking Orders
        tracking_orders = frappe.get_all(
            "Tracking Order",
            filters={"activation_status": ["in", ["Ready", "In Progress"]]},
            fields=[
                "name",
                "reference_order_type",
                "reference_order_number"
            ]
        )

        for order in tracking_orders:
            # Fetch components for each order
            components = frappe.get_all(
                "Tracking Component",
                filters={"parent": order.name},
                fields=["name", "component_name"]
            )

            result.append({
                "tracking_order": order.name,
                "reference_order_type": order.reference_order_type,
                "reference_order_number": order.reference_order_number,
                "components": components
            })

        return {
            "status": "success",
            "tracking_orders": result
        }

    except Exception as e:
        frappe.log_error(frappe.get_traceback(), "Get Tracking Orders With Components Error")
        return {"status": "error", "message": str(e)}
