import frappe
from frappe import _

@frappe.whitelist()
def get_tracking_orders_pending_activation():
    """
    Fetch all Tracking Orders with activation_status in (Ready, In Progress)
    along with their components, reference order details, and item info.
    """
    try:
        tracking_orders_list = []

        # Fetch Tracking Orders
        tracking_orders = frappe.get_all(
            "Tracking Order",
            filters={"activation_status": ["in", ["Ready", "In Progress"]]},
            fields=[
                "name",
                "reference_order_type",
                "reference_order_number",
                "item",
                "quantity"
            ]
        )

        for order in tracking_orders:
            # Fetch components for each order
            components = frappe.get_all(
                "Tracking Component",
                filters={"parent": order.name},
                fields=["name", "component_name"]
            )

            # Fetch Item details
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

            tracking_orders_list.append({
                "tracking_order": order.name,
                "reference_order_type": order.reference_order_type,
                "reference_order_number": order.reference_order_number,
                "item": order.item,
                "quantity":order.quantity,
                "style": item_doc.get("custom_style_master") if item_doc else None,
                "colour_name": item_doc.get("custom_colour_name") if item_doc else None,
                "material_composition": item_doc.get("custom_material_composition") if item_doc else None,
                "brand": item_doc.get("brand") if item_doc else None,
                "gender": item_doc.get("custom_gender") if item_doc else None,
                "season": item_doc.get("custom_season") if item_doc else None,
                "supplier": item_doc.get("custom_preferred_supplier") if item_doc else None,
                "components": components
            })

        return {
                "status": "success",
                "data": tracking_orders_list
        }

    except Exception as e:
        frappe.log_error(frappe.get_traceback(), "get_tracking_orders_pending_activation() error")
        frappe.local.response.http_status_code = 500
        return {"status": "error", "message": str(e)}


@frappe.whitelist()
def get_operation_map_test_api(tracking_order_number, component=None, current_operation=None):


    from trackerx_live.trackerx_live.utils.operation_map_util import OperationMapManager
    operation_map_manager = OperationMapManager()
    operation_map = operation_map_manager.get_operation_map(tracking_order_number)
    next_opeation = operation_map.get_next_operation(current_operation=current_operation, component=component)
    return next_opeation.operation
    response = []

    for node in oper_map.get_component_operations(component):
        previous_operations = []
        next_operations = []
        for prev_node in node.previous_operations:
            previous_operations.append({'op': prev_node.operation})
        for next_node in node.next_operations:
            next_operations.append({'op': next_node.operation})
        response.append({
            'opeation': node.operation,
            'component': node.component,
            'operation_type': str(node.operation_type.value),
            'sequence_no': node.sequence_no,
            'configs': node.configs,
            'next_operations': next_operations,
            'previous_operations': previous_operations,

        })

    

    return response

