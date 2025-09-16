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

        # Overall totals (float)
        total_count = float(sum([row["total_count"] for row in logs]) if logs else 0)
        bundle_count = float(sum([row["bundle_count"] for row in logs]) if logs else 0)

        # Collect component → { size, total_count }
        component_map = {}
        for row in logs:
            comp_id, size, tracking_order = frappe.db.get_value(
                "Production Item", row["production_item"], ["component", "size", "tracking_order"]
            )
            comp_name = frappe.db.get_value("Tracking Component", comp_id, "component_name") if comp_id else None
            if not comp_name:
                continue

            if comp_name not in component_map:
                component_map[comp_name] = {"total_count": 0.0, "sizes": {}}

            component_map[comp_name]["total_count"] += float(row["total_count"])
            if size not in component_map[comp_name]["sizes"]:
                component_map[comp_name]["sizes"][size] = 0.0
            component_map[comp_name]["sizes"][size] += float(row["total_count"])

        # Prepare components with size_data
        components = []
        for comp_name, data in component_map.items():
            # Get the component ID (docname of Tracking Component)
            comp_id = frappe.db.get_value("Tracking Component", {"component_name": comp_name}, "name")

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
                count_val = data["sizes"].get(size_val, 0.0)  # default 0 if not scanned
                size_data.append({
                    "size": size_val,
                    "total_count": float(count_val)
                })

            components.append({
                "component_name": comp_name,
                "total_count": float(data["total_count"]),
                "size_data": size_data
            })


        # Operation breakdown
        operation_map = {}
        for row in logs:
            op = row["operation"]
            comp_id, size = frappe.db.get_value(
                "Production Item", row["production_item"], ["component", "size"]
            )
            comp_name = frappe.db.get_value("Tracking Component", comp_id, "component_name") if comp_id else None

            if op not in operation_map:
                operation_map[op] = {
                    "total_count": 0.0,
                    "bundle_count": 0.0,
                    "components": {}
                }

            operation_map[op]["total_count"] += float(row["total_count"])
            operation_map[op]["bundle_count"] += float(row["bundle_count"])

            if comp_name:
                if comp_name not in operation_map[op]["components"]:
                    operation_map[op]["components"][comp_name] = {"total_count": 0.0, "sizes": {}}
                operation_map[op]["components"][comp_name]["total_count"] += float(row["total_count"])
                if size not in operation_map[op]["components"][comp_name]["sizes"]:
                    operation_map[op]["components"][comp_name]["sizes"][size] = 0.0
                operation_map[op]["components"][comp_name]["sizes"][size] += float(row["total_count"])

        # Get product info from Tracking Order → Item
        item_code, style, colour_name, material_composition = frappe.db.get_value(
            "Item",
            frappe.db.get_value("Tracking Order", tracking_order, "item"),
            ["item_code", "custom_style_master", "custom_colour_name", "custom_material_composition"]
        )


        # Build operations response
        operations_data = []
        for op, vals in operation_map.items():
            comp_list = []
            for c, cdata in vals["components"].items():
                comp_list.append({
                    "component_name": c,
                    "total_count": float(cdata["total_count"])
                })
            operations_data.append({
                "operation_name": op,
                "bundle_count": float(vals["bundle_count"]),
                "total_count": float(vals["total_count"]),
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