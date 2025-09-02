import frappe
import json
from frappe import _

@frappe.whitelist(allow_guest=True)
def get_defects_by_operation(operation_name, page=1, page_size=5, sort_by="defect", sort_order="asc", search=None):
    """
    Get all defects linked with a given operation with pagination, sorting, and searching
    """
    try:
        operation_doc = frappe.get_doc("Operation", operation_name)

        defects = []
        for row in operation_doc.custom_defect_list:
            defects.append({
                "defect": row.defect,
                "defect_description": row.defect_description,
                "defect_type": row.defect_type,
                "defect_code": row.defect_code
            })

        # Searching
        if search:
            search_lower = search.lower()
            defects = [
                d for d in defects 
                if search_lower in d["defect"].lower() 
                or search_lower in (d["defect_description"] or "").lower() 
                or search_lower in (d["defect_type"] or "").lower()
                or search_lower in (d["defect_code"] or "").lower()
            ]

        # Sorting
        if sort_by in defects[0]:
            reverse = True if sort_order.lower() == "desc" else False
            defects.sort(key=lambda x: (x[sort_by] or ""), reverse=reverse)

        # Pagination
        total = len(defects)
        start = (int(page) - 1) * int(page_size)
        end = start + int(page_size)
        defects_paginated = defects[start:end]

        return {
            "operation": operation_name,
            "total_defect": total,
            "page": int(page),
            "page_size": int(page_size),
            "defects": defects_paginated
        }

    except Exception as e:
        frappe.log_error(frappe.get_traceback(), "get_defects_by_operation_error")
        return {"error": str(e)}
