import frappe
import json
from frappe.utils import now_datetime

from trackerx_live.trackerx_live.utils.trackerx_live_settings_util import TrackerXLiveSettings

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
            frappe.throw(
                f"Missing required parameters: scan_id, defective_units",
                frappe.ValidationError
            )

        if isinstance(defective_units, str):
            defective_units = json.loads(defective_units)

        # Fetch parent scan log + production item
        parent_scan = frappe.get_doc("Item Scan Log", scan_id)
        parent_prod_name = parent_scan.get("production_item")
        if not parent_prod_name:
            frappe.throw(
                f"Parent scan does not have linked Production Item",
                frappe.ValidationError
            )
            

        parent_prod = frappe.get_doc("Production Item", parent_prod_name)
        prod_type = (parent_prod.get("type") or "").strip()

        # Update parent scan log (status fixed for now)
        # Take defect_type from first unit, if available
        first_defect_type = (defective_units[0].get("defect_type") or "QC Rework").strip()
        parent_scan.status = first_defect_type
        parent_scan.logged_time = now_datetime()
        parent_scan.log_type = "User Scanned"
        parent_scan.remarks = f"{len(defective_units)} defective units received"
        parent_scan.log_status = "Completed"
        parent_scan.set("defect_list", [])

        parent_bc = frappe.get_doc("Tracking Order Bundle Configuration", parent_prod.get("bundle_configuration"))


        
        is_dut_on = parent_bc.production_type == "Bundle" and TrackerXLiveSettings.is_dut_on(parent_prod.type)
        is_partial_bundle_allowed =  parent_bc.production_type == "Bundle" and  TrackerXLiveSettings.is_partial_bundle_enabled(parent_prod.type)
        
        parent_scan.dut = "ON" if is_dut_on else "OFF"
        
        # DUT is OFF
        ''' add all the defective units against the same bundle '''
        if not is_dut_on:
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
            parent_scan.remarks = "DUT is Off, so defective units logged on the same parent bundle"
            parent_scan.save(ignore_permissions=True)
            frappe.db.commit()
            return {
                "status": "success",
                "dut_enabled": False,
                "scan_log_id": parent_scan.name,
                "message": "Parent scan updated and defects attached (Component Flow).",
                "total_units": len(defective_units),
                "debug": f"bc type: {parent_bc.type}, parent prod type: {parent_prod.type}, is dut on: {is_dut_on}, partial bundle: {is_partial_bundle_allowed}"
            }

        # DUT On
        else:
            ''' DUT is ON so add the defective units for each of the units seperatly'''
            parent_scan.remarks = f"DUT was ON, so defective units logged on the diff child units, parital bundle config: {is_partial_bundle_allowed} "
            parent_scan.status = "DUT Parent Defect"
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

            # Check if the bundle configuration is already created from this parent bundle parent_production_item
            frappe.get_doc("Tracking Order Bundle Configuration", parent_prod.get("bundle_configuration"))
            prev_child_bc_id = frappe.db.get_value('Tracking Order Bundle Configuration', {'parent_production_item': parent_prod.name}, 'name')

            if prev_child_bc_id:
                child_bc = frappe.get_doc("Tracking Order Bundle Configuration", prev_child_bc_id)
            else:
                child_bc = frappe.get_doc({
                    "doctype": "Tracking Order Bundle Configuration",
                    "bc_name": parent_prod.get("bundle_configuration"),
                    "size": parent_prod.get("size"),
                    "bundle_quantity": 1,
                    "number_of_bundles": parent_prod.get("quantity") or 1,
                    "production_type": "Single Unit",
                    "parent": parent_prod.get("tracking_order"),
                    "parenttype": "Tracking Order",
                    "parentfield": "bundle_configurations",
                    "source": "Defective Unit Tagging",
                    "work_order": parent_bc.work_order,
                    "sales_order": parent_bc.sales_order,
                    "shade": parent_bc.shade,
                    "parent_production_item": parent_prod.name
                })
                child_bc.insert(ignore_permissions=True)
            
            child_bc_name = child_bc.name

            child_prod_items = []
            for unit in defective_units:
                unit_defect_type = (unit.get("defect_type") or "QC Rework").strip()

                tag_value = unit.get("tag") or unit.get("tag_number")
                if not tag_value:
                    frappe.throw(
                        f"Missing tag number for defective unit. User must provide tag.",
                        frappe.ValidationError
                    )

                tag_name = frappe.db.get_value("Tracking Tag", {"tag_number": tag_value}, "name")

                if not tag_name:
                    try:
                        tag_doc = frappe.get_doc({
                            "doctype": "Tracking Tag",
                            "tag_number": tag_value,
                            "tag_type": unit.get("tag_type") or "Unknown",
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
                    frappe.throw(
                        f"Failed to find or create Tracking Tag for value: {tag_value}",
                        frappe.ValidationError
                    )

                child_prod_number = f"{parent_number}-{seq:03d}"
                while frappe.db.exists("Production Item", {"production_item_number": child_prod_number}):
                    seq += 1
                    child_prod_number = f"{parent_number}-{seq:03d}"

                new_prod_fields = {
                    "doctype": "Production Item",
                    "production_item_number": child_prod_number,
                    "tracking_order": parent_prod.get("tracking_order"),
                    "bundle_configuration": child_bc_name,
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
                    "tracking_status": "Active" if is_partial_bundle_allowed else "Defective Unit Tagging", 
                    "unlinked_source": None,
                    "type": parent_prod.get("type"),
                    "physical_cell": "",
                    "last_scan_log": None
                }
                new_prod = frappe.get_doc(new_prod_fields)
                new_prod.insert(ignore_permissions=True)
                child_prod_items.append(new_prod)

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
                            "defect_type": defect_doc.defect_type,
                            "defect_code": defect_doc.defect_code,
                            "defect_description": defect_doc.defect_description,
                            "severity": defect_doc.severity,
                            "defect_category": defect_doc.defect_category
                        })
                    else:
                        child_scan.append("defect_list", {
                            "defect": defect_id
                        })
                child_scan.insert(ignore_permissions=True)

                new_prod.last_scan_log = child_scan.name
                new_prod.save()

                created.append({
                    "production_item": new_prod.name,
                    "production_item_number": new_prod.get("production_item_number"),
                    "tracking_tag": tag_value,
                    "device_id": unit.get("device_id") or device_id or parent_prod.get("device_id"),
                    "item_scan_log": child_scan.name
                })

                seq += 1

            if is_partial_bundle_allowed:
                ''' Partial bundle is enabled, so reduced the bundles to good units and mark them as passed '''
                reduced_the_bundle_to_good_units_bundle(parent_scan, parent_prod, parent_bc, defective_units, is_dut_on, child_prod_items)

            frappe.db.commit()
            return {
                "status": "success",
                "dut_enabled": True,
                "parent_scan_log": parent_scan.name,
                "total_units": len(defective_units),
                "created_units": created,
                "message": "Unit flow executed successfully"
            }

    except frappe.ValidationError as e:
        frappe.db.rollback()
        frappe.log_error(frappe.get_traceback(), "log_defective_units() error")
        frappe.local.response.http_status_code = 400
        return {"status": "error", "message": str(e)} 
    except Exception as e:
        frappe.db.rollback()
        frappe.log_error(frappe.get_traceback(), "log_defective_units() error")
        frappe.local.response.http_status_code = 500
        return {"status": "error", "message": str(e)} 

def reduced_the_bundle_to_good_units_bundle(parent_scan, parent_prod, parent_bc, defective_units, is_dut_on, unit_child_prod_items):
    # If partial bundle is enabled then reduce the parent into Good units and defective units as seperate scannable units
    reduced_qty = parent_bc.bundle_quantity - len(defective_units)

    mappings = frappe.get_all(
        "Production Item Tag Map",
        filters={"production_item": parent_prod.name, "is_active": True},
        fields=["name", "tracking_tag"]
    )

    if reduced_qty > 0:
        
        #create new parent reduced bc
        new_parent_bc = frappe.copy_doc(parent_bc)
        new_parent_bc.bundle_quantity = reduced_qty
        new_parent_bc.number_of_bundles = 1
        new_parent_bc.production_type = "Bundle"
        new_parent_bc.parent_bundle_configuration = parent_bc.name
        new_parent_bc.source = "Partial Bundle"
        new_parent_bc.activation_status = "Completed"
        new_parent_bc.insert(ignore_permissions=True)

        
        # create parent prod item for good units
        good_unit_parent_prod_item = frappe.copy_doc(parent_prod)
        good_unit_parent_prod_item.bundle_configuration = new_parent_bc
        good_unit_parent_prod_item.quantity = reduced_qty
        good_unit_parent_prod_item.source = "Partial Bundle"
        good_unit_parent_prod_item.tracking_status = ""
        good_unit_parent_prod_item.insert(ignore_permissions=True)

        
        #link the tag to this new item
        for mapping in mappings:
            new_bundle_map = frappe.new_doc("Production Item Tag Map")
            new_bundle_map.production_item = good_unit_parent_prod_item.name
            new_bundle_map.tracking_tag = mapping.get("tracking_tag")
            new_bundle_map.linked_on = frappe.utils.now_datetime()
            new_bundle_map.is_active=True 
            new_bundle_map.activated_source = "Partial Bundle"
            new_bundle_map.deactivated_source = None
            new_bundle_map.insert(ignore_permissions=True)
    
        #TODO
        #add the item scan log in the current operaiotn as pass for this reduced prod item
        item_scan_log = frappe.new_doc("Item Scan Log")
        item_scan_log.production_item = good_unit_parent_prod_item.name
        item_scan_log.workstation = parent_scan.workstation
        item_scan_log.operation = parent_scan.operation
        item_scan_log.physical_cell = parent_scan.physical_cell
        item_scan_log.scanned_by = parent_scan.scanned_by
        item_scan_log.scan_time = parent_scan.scan_time
        item_scan_log.logged_time = frappe.utils.now_datetime()
        item_scan_log.status = "Pass"
        item_scan_log.log_status = "Completed"
        item_scan_log.log_type = "User Scanned"
        item_scan_log.remarks = None
        item_scan_log.defect_list = []
        item_scan_log.production_item_type = parent_scan.production_item_type
        item_scan_log.dut = "ON" if is_dut_on else "OFF"
        item_scan_log.device_id = parent_scan.device_id
        item_scan_log.insert(ignore_permissions=True)

        # add information into swith log
        all_child_items = unit_child_prod_items.copy()
        all_child_items.append(new_parent_bc)

        parent_production_items = [parent_prod]
        child_production_items = all_child_items
        switch_log = frappe.new_doc("Switch Log")
        switch_log.switch_type = "Partial Bundle"
        switch_log.from_production_items = parent_production_items
        switch_log.to_production_items = child_production_items
        switch_log.switched_on= frappe.utils.now_datetime()
        switch_log.switched_by = None
        switch_log.remarks = "Partial bundle reduce"
        switch_log.insert(ignore_permissions=True)



    #update status of the old parent prod
    parent_prod.status = "Switched"
    parent_prod.tracking_status = "Unlinked"
    parent_prod.save()

    #unlink the tag from the old mapping
    for mapping in mappings:
        parent_prod_mapping = frappe.get_doc("Production Item Tag Map", mapping.name)
        parent_prod_mapping.is_active=False
        parent_prod_mapping.deactivated_source = "Partial Bundle Unlink"
        parent_prod_mapping.save()


  

@frappe.whitelist()
def unit_scan(production_item_id=None, scan_id=None, unit_tag=None, existing_defective_units=[]):
    try:
        if not scan_id or not unit_tag:
            frappe.throw(
                f"Oops something went wrong from our end, Please contact system admin, required info empty"
            )
        #TODO
        #Check if the unit tag already used for any, if used then it must be used as DUT tag from this bundle itself, otherwise throw error
        tag = frappe.db.get_value(
            "Tracking Tag",
            {"tag_number": unit_tag},
            ["name"],
            as_dict=True
        )

        if not tag:
            return "Success"

        tag_map = frappe.db.get_value(
            "Production Item Tag Map",
            {"tracking_tag": tag.name, "is_active": True},
            ["name", "is_active", "production_item"],
            as_dict=True
        )

        if not tag_map:
            return "Success"
        
        






        #TODO
        #If its the new tag then it must not create more unit tags than the bundle quantity, use existing defective units (local) and existing db together to verify

        #TODO
        #if all the above validations pass, then just return as valid possible item, we must return item number of this tag, if new possible item number for now 

        return "Success"

    except frappe.ValidationError as e:
        frappe.log_error(frappe.get_traceback(), "unit_scan() error")
        frappe.local.response.http_status_code = 400
        return {"status": "error", "message": str(e)} 
    except Exception as e:
        frappe.log_error(frappe.get_traceback(), "unit_scan() error")
        frappe.local.response.http_status_code = 500
        return {"status": "error", "message": str(e)} 
    

def is_partial_bundle_allowed():
    return True