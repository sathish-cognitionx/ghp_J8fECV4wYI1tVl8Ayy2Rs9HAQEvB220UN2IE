import frappe
from frappe import _

@frappe.whitelist()
def get_tracking_orders_pending_activation():
    """
    Fetch all Tracking Orders with activation_status in (Ready, In Progress)
    along with their components, reference order details, and item info.
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
                "reference_order_number",
                "item"
            ]
        )

        for order in tracking_orders:
            # Fetch components for each order
            components = frappe.get_all(
                "Tracking Component",
                filters={"parent": order.name},
                fields=["name", "component_name"]
            )

            # Fetch Item details with your custom fields
            item_doc = frappe.db.get_value(
                "Item",
                order.item,
                [
                    "custom_style_master",
                    "custom_colour_name",
                    "custom_material_composition",
                    "brand",
                    "custom_gender",
                    "custom_season",
                    "custom_preferred_supplier"
                ],
                as_dict=True
            ) if order.item else {}

            item_details = {
                "style": item_doc.get("custom_style_master") if item_doc else None,
                "colour_name": item_doc.get("custom_colour_name") if item_doc else None,
                "material_composition": item_doc.get("custom_material_composition") if item_doc else None,
                "brand": item_doc.get("brand") if item_doc else None,
                "gender": item_doc.get("custom_gender") if item_doc else None,
                "season": item_doc.get("custom_season") if item_doc else None,
                "supplier": item_doc.get("custom_preferred_supplier") if item_doc else None,
            }

            result.append({
                "tracking_order": order.name,
                "reference_order_type": order.reference_order_type,
                "reference_order_number": order.reference_order_number,
                "item": order.item,
                "item_details": item_details,
                "components": components
            })

        return {
            "message": {
                "status": "success",
                "tracking_orders": result
            }
        }

    except Exception as e:
        frappe.log_error(frappe.get_traceback(), "Get Tracking Orders With Components Error")
        return {
            "message": {
                "status": "error",
                "error": str(e)
            }
        }
