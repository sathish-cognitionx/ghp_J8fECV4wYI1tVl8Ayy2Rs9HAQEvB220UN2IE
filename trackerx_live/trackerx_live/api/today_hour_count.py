import frappe
from frappe import _
from trackerx_live.trackerx_live.api.counted_info import get_counted_info


@frappe.whitelist()
def get_today_and_hour_count(ws_name):
    try:
        if not ws_name:
            return {"status": "error", "message": _("Workstation name is required.")}

        today_info = get_counted_info(ws_name, "today") or {}
        current_hour_info = get_counted_info(ws_name, "current_hour") or {}

        return {
            "status": "success",
            "today_count": today_info.get("total_count", 0),
            "current_hour_count": current_hour_info.get("total_count", 0),
        }
    except Exception as e:
        frappe.log_error(frappe.get_traceback(), "get_today_and_hour_count Error")
        return {"status": "error", "message": str(e)}
