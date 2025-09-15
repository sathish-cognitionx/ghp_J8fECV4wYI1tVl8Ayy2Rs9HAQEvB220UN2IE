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

        # Fetch logs (only Counted)
        logs = frappe.db.sql(
            """
            SELECT operation, production_item, COUNT(*) as total_count
            FROM `tabItem Scan Log`
            WHERE workstation = %s
              AND status = 'Counted'
              AND scan_time BETWEEN %s AND %s
            GROUP BY operation, production_item
            """,
            (ws_name, from_time, to_time),
            as_dict=True
        )

        # Overall totals
        total_count = sum([row["total_count"] for row in logs]) if logs else 0

        # Collect all components (map to Tracking Component.component_name)
        all_components = set()
        for row in logs:
            comp_id = frappe.db.get_value("Production Item", row["production_item"], "component")
            if comp_id:
                comp_name = frappe.db.get_value("Tracking Component", comp_id, "component_name")
                if comp_name:
                    all_components.add(comp_name)

        # Global component totals
        component_map = {c: 0 for c in all_components}
        for row in logs:
            comp_id = frappe.db.get_value("Production Item", row["production_item"], "component")
            comp_name = frappe.db.get_value("Tracking Component", comp_id, "component_name") if comp_id else None
            if comp_name:
                component_map[comp_name] += row["total_count"]

        components = [{"component_name": c, "total_count": str(cnt)} for c, cnt in component_map.items()]

        # Operation breakdown
        operation_map = {}
        for row in logs:
            op = row["operation"]
            comp_id = frappe.db.get_value("Production Item", row["production_item"], "component")
            comp_name = frappe.db.get_value("Tracking Component", comp_id, "component_name") if comp_id else None

            if op not in operation_map:
                operation_map[op] = {"total_count": 0, "components": {c: 0 for c in all_components}}

            operation_map[op]["total_count"] += row["total_count"]
            if comp_name:
                operation_map[op]["components"][comp_name] += row["total_count"]

        operations_data = []
        for op, vals in operation_map.items():
            comp_list = [{"component_name": c, "total_count": str(cnt)} for c, cnt in vals["components"].items()]
            operations_data.append({
                "operation_name": op,
                "total_count": vals["total_count"],
                "components": comp_list
            })

        return {
            "total_count": total_count,
            "components": components,
            "operations": operations_data,
            
        }

    except Exception as e:
        frappe.log_error(frappe.get_traceback(), "get_counted_info API Error")
        return {"error": f"An error occurred while fetching counts: {str(e)}"}
