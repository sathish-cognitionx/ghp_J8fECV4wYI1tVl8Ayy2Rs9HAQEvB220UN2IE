import frappe
import json
from frappe.utils import now_datetime

@frappe.whitelist()
def log_defective_units(scan_id=None, operation=None, ws=None, defective_units=None):
    """
    Defect Logging Flow:
    - If DUT OFF: Parent Item Scan Log = Fail + Completed, attach defects to parent
    - If DUT ON : Parent Item Scan Log = Fail + Completed (no defects on parent)
                  For each defective unit:
                    - Create Production Item (copy parent fields)
                    - Assign Production Item Number with -001, -002 ...
                    - Status = In Production
                    - tracking_status & source = "Defect Unit Tagging"
                    - Create Bundle Configuration (once for all units)
                    - Create Production Item Tag Map
                    - Create Item Scan Log (Fail + Completed) with defects
    """

    try:
        # Validate inputs
        if not (scan_id and operation and ws and defective_units is not None):
            return {"error": "Missing required parameters: scan_id, operation, ws, defective_units"}

        if isinstance(defective_units, str):
            defective_units = json.loads(defective_units)

        # Fetch parent scan log + production item
        parent_scan = frappe.get_doc("Item Scan Log", scan_id)
        parent_prod_name = parent_scan.get("production_item")
        if not parent_prod_name:
            return {"error": "Parent scan does not have linked Production Item"}

        parent_prod = frappe.get_doc("Production Item", parent_prod_name)

        # Check DUT flag based on explicit "on" / "off" string
        dut_flag = parent_scan.get("dut")

        # Normalize and check value (uppercase to be safe)
        if isinstance(dut_flag, str):
            dut_flag = dut_flag.upper()

        if dut_flag == "OFF":
            is_dut = False
        elif dut_flag == "ON":
            is_dut = True
        else:
            is_dut = False  # Default to OFF if missing or unexpected value

        # Update parent scan log
        parent_scan.status = "Fail"
        parent_scan.operation = operation
        parent_scan.workstation = ws
        parent_scan.logged_time = now_datetime()
        # parent_scan.log_type = "Defect" if not is_dut else "User Scanned"
        parent_scan.log_type = "User Scanned"
        parent_scan.remarks = f"{len(defective_units)} defective units received"
        parent_scan.log_status = "Completed"
        parent_scan.set("defect_list", [])

        if not is_dut:
            # Attach defects to parent if DUT OFF
            for unit in defective_units:
                for d in unit.get("defects", []):
                    defect_id = d.get("defectid")
                    if not defect_id:
                        continue
                    if frappe.db.exists("Tracking Order Defect Master", defect_id):
                        defect_doc = frappe.get_doc("Tracking Order Defect Master", defect_id)
                        parent_scan.append("defect_list", {
                            "defect": defect_doc.name,
                            "defect_type": defect_doc.get("defect_type")
                        })
            parent_scan.save(ignore_permissions=True)
            return {
                "status": "success",
                "dut_enabled": False,
                "scan_log_id": parent_scan.name,
                "message": "Parent scan updated and defects attached (Draft).",
                "total_units": len(defective_units)
            }

        # If DUT ON, save parent scan without defects
        parent_scan.save(ignore_permissions=True)
        created = []

        # Existing children suffix calculation
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

        # Create Bundle Configuration ONCE for all children (as per requirements)
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
            "source": "Activation"
        })
        bc.insert(ignore_permissions=True)
        bc_name = bc.name

        # Loop for each defective unit
        for unit in defective_units:
            # Ensure tracking tag
            tag_value = unit.get("tag") or unit.get("tag_number")
            if not tag_value:
                return {"error": "Missing tag number for defective unit. User must provide tag."}
            
            tag_name = frappe.db.get_value("Tracking Tag", {"tag_number": tag_value}, "name")
            
            if not tag_name:
                try:
                    tag_doc = frappe.get_doc({
                        "doctype": "Tracking Tag",
                        "tag_number": tag_value,
                        "status": "Active"
                    })
                    tag_doc.insert(ignore_permissions=True)
                    tag_name = tag_doc.name
                except frappe.DuplicateEntryError:
                    # In case of race condition, get the docname that was just created
                    frappe.db.rollback()
                    tag_name = frappe.db.get_value("Tracking Tag", {"tag_number": tag_value}, "name")
            
            if not tag_name:
                return {"error": f"Failed to find or create Tracking Tag for value: {tag_value}"}

            # Child Production Item Number → PARENT-001, PARENT-002...
            child_prod_number = f"{parent_number}-{seq:03d}"
            while frappe.db.exists("Production Item", {"production_item_number": child_prod_number}):
                seq += 1
                child_prod_number = f"{parent_number}-{seq:03d}"

            # Create Production Item
            new_prod_fields = {
                "doctype": "Production Item",
                "production_item_number": child_prod_number,
                "tracking_order": parent_prod.get("tracking_order"),
                "bundle_configuration": bc_name, # Use the single, shared bundle config
                "tracking_tag": tag_name, 
                "component": parent_prod.get("component"),
                "device_id": parent_prod.get("device_id"),
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

            # Production Item Tag Map
            pi_tag_map = frappe.get_doc({
                "doctype": "Production Item Tag Map",
                "production_item": new_prod.name,
                "tracking_tag": tag_name,
                "linked_on": now_datetime(),  # Add this line to set the value
                "is_active": 1,   
            })
            pi_tag_map.insert(ignore_permissions=True)

            # Item Scan Log for child
            child_scan = frappe.get_doc({
                "doctype": "Item Scan Log",
                "production_item": new_prod.name,
                "operation": operation,
                "workstation": ws,
                "status": "Fail",
                "logged_time": now_datetime(),
                "log_status": "Completed",
                "log_type": "User Scanned",
                "remarks": "Auto-created defective unit",
                "scanned_by": frappe.session.user, 
                "scan_time": now_datetime(),  
            })
            
            # Attach defects to child scan
            for d in unit.get("defects", []):
                defect_id = d.get("defectid")
                if not defect_id:
                    continue
                if frappe.db.exists("Tracking Order Defect Master", defect_id):
                    defect_doc = frappe.get_doc("Tracking Order Defect Master", defect_id)
                    child_scan.append("defect_list", {
                        "defect": defect_doc.name,
                        "defect_type": defect_doc.get("defect_type")
                    })
                else:
                    child_scan.append("defect_list", {
                        "defect": defect_id,
                        "defect_type": "UNKNOWN"
                    })
            child_scan.insert(ignore_permissions=True)

            created.append({
                "production_item": new_prod.name,
                "production_item_number": new_prod.get("production_item_number"),
                "tracking_tag": tag_value,
                "item_scan_log": child_scan.name
            })

            seq += 1

        return {
            "status": "success",
            "dut_enabled": True,
            "parent_scan_log": parent_scan.name,
            "total_units": len(defective_units),
            "created_units": created,
            "message": "DUT flow executed successfully"
        }

    except Exception as e:
        frappe.log_error(frappe.get_traceback(), "log_defective_units_error")
        return {"error": str(e)}