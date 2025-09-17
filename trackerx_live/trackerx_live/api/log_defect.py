import frappe
import json
from frappe.utils import now_datetime

@frappe.whitelist()
def log_defective_units(scan_id=None, defective_units=None, device_id=None):
    """
     Defect Logging Flow with Defect Type:
      - Accepts scan_id, defect_type (default: QC Rework), device_id (optional), and defective_units
      - Handles both Component and Unit flows,
      -Defect Logging Flow:
      - If DUT OFF/component flow : Parent Item Scan Log = Fail + Completed, attach defects to parent
      - If DUT ON/Unit flow : Parent Item Scan Log = Fail + Completed (no defects on parent)
                    For each defective unit:
                      - Create Production Item (copy parent fields)
                      - Assign Production Item Number with -001, -002 ...
                      - Status = In Production
                      - tracking_status & source = "Defect Unit Tagging"
                      - Create Bundle Configuration (once for all units)
                      - Create Production Item Tag Map
                     - Create Item Scan Log (Fail + Completed) with defects
                    Defect Logging Flow with Defect Type:
                        - Accepts scan_id, device_id (optional), and defective_units
                        - defect_type is taken from each defective unit (default: QC Rework)
                        - Handles both Component and Unit flows
    """

    try:
        if not (scan_id and defective_units is not None):
            return {"error": "Missing required parameters: scan_id, defective_units"}

        if isinstance(defective_units, str):
            defective_units = json.loads(defective_units)

        # Fetch parent scan log + production item
        parent_scan = frappe.get_doc("Item Scan Log", scan_id)
        parent_prod_name = parent_scan.get("production_item")
        if not parent_prod_name:
            return {"error": "Parent scan does not have linked Production Item"}

        parent_prod = frappe.get_doc("Production Item", parent_prod_name)
        prod_type = (parent_prod.get("type") or "").strip().lower()

        # Update parent scan log (status fixed for now)
        # Take defect_type from first unit, if available
        first_defect_type = (defective_units[0].get("defect_type") or "QC Rework").strip()
        parent_scan.status = first_defect_type
        parent_scan.logged_time = now_datetime()
        parent_scan.log_type = "User Scanned"
        parent_scan.remarks = f"{len(defective_units)} defective units received"
        parent_scan.log_status = "Completed"
        parent_scan.set("defect_list", [])

        # ====== Component Flow ======
        if prod_type == "component":
            for unit in defective_units:
                unit_defect_type = (unit.get("defect_type") or "QC Rework").strip()
                for d in unit.get("defects", []):
                    defect_id = d.get("defectid")
                    if not defect_id:
                        continue
                    if frappe.db.exists("Tracking Order Defect Master", defect_id):
                        defect_doc = frappe.get_doc("Tracking Order Defect Master", defect_id)
                        parent_scan.append("defect_list", {
                            "defect": defect_doc.name,
                            "defect_type": unit_defect_type
                        })
            parent_scan.save(ignore_permissions=True)
            return {
                "status": "success",
                "dut_enabled": False,
                "scan_log_id": parent_scan.name,
                "message": "Parent scan updated and defects attached (Component Flow).",
                "total_units": len(defective_units)
            }

        # ====== Unit Flow ======
        elif prod_type == "unit":
            parent_scan.save(ignore_permissions=True)
            created = []

            parent_number = parent_prod.get("production_item_number") or parent_prod.name
            existing = frappe.get_all(
                "Production Item",
                filters={"production_item_number": ["like", f"{parent_number}-%"]},
                fields=["production_item_number"]
            )
            existing_suffix = [
                int(x["production_item_number"].split("-")[-1])
                for x in existing if "-" in x["production_item_number"]
            ]
            seq = max(existing_suffix) + 1 if existing_suffix else 1

            # Create Bundle Configuration ONCE
            bc = frappe.get_doc({
                "doctype": "Tracking Order Bundle Configuration",
                "bc_name": parent_prod.get("bundle_configuration"),
                "size": parent_prod.get("size"),
                "bundle_quantity": 1,
                "number_of_bundles": parent_prod.get("quantity") or 1,
                "production_type": "Single Unit",
                "parent": parent_prod.get("tracking_order"),
                "parenttype": "Tracking Order",
                "parentfield": "bundle_configurations",
                "source": "Defective Unit Tagging"
            })
            bc.insert(ignore_permissions=True)
            bc_name = bc.name

            for unit in defective_units:
                unit_defect_type = (unit.get("defect_type") or "QC Rework").strip()

                tag_value = unit.get("tag") or unit.get("tag_number")
                if not tag_value:
                    return {"error": "Missing tag number for defective unit. User must provide tag."}

                tag_name = frappe.db.get_value("Tracking Tag", {"tag_number": tag_value}, "name")

                if not tag_name:
                    try:
                        tag_doc = frappe.get_doc({
                            "doctype": "Tracking Tag",
                            "tag_number": tag_value,
                            "tag_type": unit.get("tag_type") or "Default",
                            "status": "Active",
                            "activation_time": now_datetime(),
                            "last_used_on": now_datetime(),
                            "remarks": f"Auto-created from defective unit tagging for {parent_number}",
                            "activation_source": "App"
                        })
                        tag_doc.insert(ignore_permissions=True)
                        tag_name = tag_doc.name
                    except frappe.DuplicateEntryError:
                        frappe.db.rollback()
                        tag_name = frappe.db.get_value("Tracking Tag", {"tag_number": tag_value}, "name")

                if not tag_name:
                    return {"error": f"Failed to find or create Tracking Tag for value: {tag_value}"}

                child_prod_number = f"{parent_number}-{seq:03d}"
                while frappe.db.exists("Production Item", {"production_item_number": child_prod_number}):
                    seq += 1
                    child_prod_number = f"{parent_number}-{seq:03d}"

                new_prod_fields = {
                    "doctype": "Production Item",
                    "production_item_number": child_prod_number,
                    "tracking_order": parent_prod.get("tracking_order"),
                    "bundle_configuration": bc_name,
                    "tracking_tag": tag_name,
                    "component": parent_prod.get("component"),
                    "device_id": unit.get("device_id") or device_id or parent_prod.get("device_id"),
                    "size": parent_prod.get("size"),
                    "quantity": 1,
                    "status": "In Production",
                    "current_operation": parent_prod.get("current_operation"),
                    "next_operation": parent_prod.get("next_operation"),
                    "current_workstation": parent_prod.get("current_workstation"),
                    "next_workstation": parent_prod.get("next_workstation"),
                    "source": "Defective Unit Tagging",
                    "tracking_status": "Defective Unit Tagging",
                    "unlinked_source": None
                }
                new_prod = frappe.get_doc(new_prod_fields)
                new_prod.insert(ignore_permissions=True)

                pi_tag_map = frappe.get_doc({
                    "doctype": "Production Item Tag Map",
                    "production_item": new_prod.name,
                    "tracking_tag": tag_name,
                    "linked_on": now_datetime(),
                    "is_active": 1,
                })
                pi_tag_map.insert(ignore_permissions=True)

                child_scan = frappe.get_doc({
                    "doctype": "Item Scan Log",
                    "production_item": new_prod.name,
                    "status": unit_defect_type,
                    "logged_time": now_datetime(),
                    "log_status": "Completed",
                    "log_type": "User Scanned",
                    "remarks": f"Auto-created defective unit ({unit_defect_type})",
                    "scanned_by": frappe.session.user,
                    "scan_time": now_datetime(),
                    "workstation": parent_scan.workstation,
                    "operation": parent_scan.operation,
                    "physical_cell": parent_scan.physical_cell
                })

                for d in unit.get("defects", []):
                    defect_id = d.get("defectid")
                    if not defect_id:
                        continue
                    if frappe.db.exists("Tracking Order Defect Master", defect_id):
                        defect_doc = frappe.get_doc("Tracking Order Defect Master", defect_id)
                        child_scan.append("defect_list", {
                            "defect": defect_doc.name,
                            "defect_type": unit_defect_type
                        })
                    else:
                        child_scan.append("defect_list", {
                            "defect": defect_id,
                            "defect_type": unit_defect_type
                        })
                child_scan.insert(ignore_permissions=True)

                created.append({
                    "production_item": new_prod.name,
                    "production_item_number": new_prod.get("production_item_number"),
                    "tracking_tag": tag_value,
                    "device_id": unit.get("device_id") or device_id or parent_prod.get("device_id"),
                    "item_scan_log": child_scan.name
                })

                seq += 1

            return {
                "status": "success",
                "dut_enabled": True,
                "parent_scan_log": parent_scan.name,
                "total_units": len(defective_units),
                "created_units": created,
                "message": "Unit flow executed successfully"
            }

        else:
            return {"error": f"Invalid Production Item.type: {prod_type}"}

    except Exception as e:
        frappe.log_error(frappe.get_traceback(), "log_defective_units_error")
        return {"error": str(e)}