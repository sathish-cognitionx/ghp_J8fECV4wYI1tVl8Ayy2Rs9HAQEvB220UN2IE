import frappe
from datetime import timedelta
from trackerx_live.trackerx_live.utils.cell_operator_ws_util import get_cell_operator_by_ws


@frappe.whitelist()
def get_counted_info(ws_name, period="today"):
    try:
        if not ws_name:
            return {"error": "Workstation name is required."}

        ws_info = get_cell_operator_by_ws(ws_name)
        if not ws_info:
            return {"error": f"No mapping found for workstation: {ws_name}"}

        now = frappe.utils.now_datetime()

        if period == "last_hour":
            from_time = now - timedelta(hours=1)
            to_time = now
        elif period == "current_hour":
            from_time = now.replace(minute=0, second=0, microsecond=0)
            to_time = now
        elif period == "today":
            from_time = now.replace(hour=0, minute=0, second=0, microsecond=0)
            to_time = now
        else:
            return {"error": f"Invalid period '{period}'. Use today, current_hour, or last_hour."}

        # Fetch logs (status = Counted), join with Production Item
        logs = frappe.db.sql(
            """
            SELECT 
                sl.operation,
                sl.production_item,
                COUNT(sl.name) as bundle_count,
                SUM(pi.quantity) as total_count
            FROM `tabItem Scan Log` sl
            INNER JOIN `tabProduction Item` pi 
                ON pi.name = sl.production_item
            WHERE sl.workstation = %s
              AND sl.status = 'Counted'
              AND sl.scan_time BETWEEN %s AND %s
            GROUP BY sl.operation, sl.production_item
            """,
            (ws_name, from_time, to_time),
            as_dict=True
        )

        total_count = int(sum([row["total_count"] for row in logs]) if logs else 0)
        bundle_count = int(sum([row["bundle_count"] for row in logs]) if logs else 0)

        tracking_order = None
        component_map = {}

        for row in logs:
            comp_id, size, tracking_order = frappe.db.get_value(
                "Production Item", row["production_item"], ["component", "size", "tracking_order"]
            )
            comp_name = frappe.db.get_value("Tracking Component", comp_id, "component_name") if comp_id else None
            if not comp_name:
                continue

            if comp_name not in component_map:
                component_map[comp_name] = {"total_count": 0, "sizes": {}}

            component_map[comp_name]["total_count"] += int(row["total_count"])
            if size not in component_map[comp_name]["sizes"]:
                component_map[comp_name]["sizes"][size] = 0
            component_map[comp_name]["sizes"][size] += int(row["total_count"])

        # If no logs, try to fetch tracking_order directly from workstation mapping
        if not tracking_order:
            tracking_order = frappe.db.get_value(
                "Production Item",
                {"current_workstation": ws_name},
                "tracking_order"
            )

        # Always fetch product info
        item_code = style = colour_name = material_composition = None
        if tracking_order:
            item_code, style, colour_name, material_composition = frappe.db.get_value(
                "Item",
                frappe.db.get_value("Tracking Order", tracking_order, "item"),
                ["item_code", "custom_style_master", "custom_colour_name", "custom_material_composition"]
            )

        # Always build components structure from Tracking Order
        components = []
        if tracking_order:
            tracking_components = frappe.db.sql(
                """
                SELECT tc.name, tc.component_name
                FROM `tabTracking Component` tc
                WHERE tc.parent = %s
                """,
                (tracking_order,),
                as_dict=True
            )

            for tc in tracking_components:
                comp_id = tc["name"]
                comp_name = tc["component_name"]

                sizes_in_config = frappe.db.sql(
                    """
                    SELECT DISTINCT tbc.size
                    FROM `tabTracking Order Bundle Configuration` tbc
                    INNER JOIN `tabTracking Order` todr
                        ON tbc.parent = todr.name
                    WHERE tbc.component = %s
                    AND todr.name = %s
                    """,
                    (comp_id, tracking_order),
                    as_dict=True
                )

                size_data = []
                for s in sizes_in_config:
                    size_val = s["size"]
                    count_val = 0
                    if comp_name in component_map:
                        count_val = component_map[comp_name]["sizes"].get(size_val, 0)
                    size_data.append({
                        "size": size_val,
                        "total_count": int(count_val)
                    })

                comp_total = 0
                if comp_name in component_map:
                    comp_total = component_map[comp_name]["total_count"]

                components.append({
                    "component_name": comp_name,
                    "total_count": int(comp_total),
                    "size_data": size_data
                })

        # Operation breakdown (only if logs exist)
        operation_map = {}
        for row in logs:
            op = row["operation"]
            comp_id, size, total_count_row = frappe.db.get_value(
                "Production Item", row["production_item"], ["component", "size", "quantity"]
            )
            comp_name = frappe.db.get_value("Tracking Component", comp_id, "component_name") if comp_id else None

            if op not in operation_map:
                operation_map[op] = {
                    "op_total_count": 0,
                    "bundle_count": 0,
                    "components": {}
                }

            operation_map[op]["op_total_count"] += int(row["total_count"])
            operation_map[op]["bundle_count"] += int(row["bundle_count"])

            if comp_name:
                if comp_name not in operation_map[op]["components"]:
                    operation_map[op]["components"][comp_name] = {
                        "comp_total_count": 0,
                        "sizes": {}
                    }
                operation_map[op]["components"][comp_name]["comp_total_count"] += int(row["total_count"])
                if size not in operation_map[op]["components"][comp_name]["sizes"]:
                    operation_map[op]["components"][comp_name]["sizes"][size] = 0
                operation_map[op]["components"][comp_name]["sizes"][size] += int(row["total_count"])

        operations_data = []
        for op, vals in operation_map.items():
            comp_list = []
            for c, cdata in vals["components"].items():
                size_data_list = [{"size": s, "total_count": int(count)} for s, count in cdata["sizes"].items()]
                comp_list.append({
                    "component_name": c,
                    "total_count": int(cdata["comp_total_count"]),
                    "size_data": size_data_list
                })

            production_type = frappe.db.get_value("Tracking Order", tracking_order, "production_type") if tracking_order else None
            operations_data.append({
                "operation_name": op,
                "production_type": production_type or "",
                "bundle_count": int(vals["bundle_count"]),
                "total_count": int(vals["op_total_count"]),
                "product_code": item_code,
                "style": style,
                "colour_name": colour_name,
                "material_composition": material_composition,
                "components": comp_list
            })

        return {
            "total_count": total_count,
            "bundle_count": bundle_count,
            "components": components,
            "operations": operations_data
        }

    except Exception as e:
        frappe.log_error(frappe.get_traceback(), "get_counted_info API Error")
        return {"error": f"An error occurred while fetching counts: {str(e)}"}
