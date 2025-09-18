import frappe
import json
import hashlib
from frappe import _

@frappe.whitelist()
def get_defects_by_operations(operation_names, page=1, page_size=5, sort_by="defect", sort_order="asc", search=None):
    try:
        # Normalize input (list, JSON string, or CSV string)
        if isinstance(operation_names, str):
            try:
                operation_names = json.loads(operation_names)
            except json.JSONDecodeError:
                operation_names = [op.strip() for op in operation_names.split(",") if op.strip()]

        if not operation_names:
            return {"error": "No operation names provided."}

        # Create cache key (based on params)
        cache_key_data = {
            "operation_names": sorted(operation_names),
            "page": int(page),
            "page_size": int(page_size),
            "sort_by": sort_by,
            "sort_order": sort_order,
            "search": search or ""
        }
        raw_key = json.dumps(cache_key_data, sort_keys=True)
        cache_key = "defects_by_operation_map_" + hashlib.md5(raw_key.encode()).hexdigest()

        cache = frappe.cache()
        cached_result = cache.get_value(cache_key)

        # If cached → return with source=cache
        if cached_result:
            if isinstance(cached_result, str):   # redis often stores as string
                cached_result = json.loads(cached_result)
            cached_result["source"] = "cache"
            return cached_result

        # DB fetch
        operation_defects = {}
        all_defects_combined = {}  # dict to keep unique defects (by code or id)

        for op_name in operation_names:
            try:
                operation_doc = frappe.get_doc("Operation", op_name)
                defects = []

                for row in operation_doc.custom_defect_list:
                    defect = {
                        "defect": row.defect,
                        "defect_description": row.defect_description,
                        "defect_type": row.defect_type,
                        "defect_code": row.defect_code
                    }
                    defects.append(defect)

                    # Unique key: defect_code (if exists) else defect id
                    key = row.defect_code or row.defect
                    all_defects_combined[key] = defect

                # Apply search
                if search:
                    s = search.lower()
                    defects = [
                        d for d in defects
                        if s in (d["defect"] or "").lower()
                        or s in (d["defect_description"] or "").lower()
                        or s in (d["defect_type"] or "").lower()
                        or s in (d["defect_code"] or "").lower()
                    ]

                # Sort
                if defects and sort_by in defects[0]:
                    defects.sort(
                        key=lambda x: (x[sort_by] or ""),
                        reverse=(sort_order.lower() == "desc")
                    )

                operation_defects[op_name] = defects

            except Exception as op_error:
                frappe.log_error(
                    f"Error in operation '{op_name}': {str(op_error)}",
                    "get_defects_by_operations"
                )

        # Pagination
        total_operations = len(operation_names)
        page = int(page)
        page_size = int(page_size)
        start = (page - 1) * page_size
        end = start + page_size
        paginated_operations = operation_names[start:end]

        paginated_defects = {
            op: operation_defects.get(op, []) for op in paginated_operations
        }

        # Final response
        result = {
            "operations": paginated_operations,
            "operation_defects": paginated_defects,
            "all_defects": list(all_defects_combined.values()),  # ✅ always included
            "total_operations": total_operations,
            "page": page,
            "page_size": page_size,
            "source": "db"
        }

        # Save to cache
        cache.set_value(cache_key, json.dumps(result), expires_in_sec=3600)

        return result

    except Exception as e:
        frappe.log_error(frappe.get_traceback(), "get_defects_by_operations_main_error")
        return {"error": str(e)}