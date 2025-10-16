import frappe


@frappe.whitelist()
def check_tag_number_status(tag_number=None):
    if not tag_number:
        return {"status": "error", "message": "tag_number is required"}

    # STEP 1: Fetch Tracking Tag record
    tracking_tag = frappe.db.get_value(
        "Tracking Tag",
        {"tag_number": tag_number},
        ["name", "status"],
        as_dict=True
    )

    if not tracking_tag:
        return {"status": "not_found", "message": "Tag number not found in system"}

    if tracking_tag.status.lower() == "inactive":
        return {"status": "inactive", "message": "This tag is inactive"}

    # STEP 2: Check if Production Item Tag Map exists for this tag
    tag_map = frappe.db.get_value(
        "Production Item Tag Map",
        {"tracking_tag": tracking_tag.name},
        ["name", "is_active", "production_item"],
        as_dict=True
    )

    if not tag_map:
        return {
            "status": "not_found",
            "message": "No Production Item Tag Map found for this tag",
            "tracking_tag": tracking_tag.name
        }

    if not tag_map.is_active:
        return {
            "status": "inactive",
            "message": "Production Item Tag Map is inactive",
            "tracking_tag": tracking_tag.name
        }

    # STEP 3: Get Production Item linked in the Tag Map
    production_item = frappe.db.get_value(
        "Production Item",
        {"name": tag_map.production_item},
        ["name", "production_item_number", "tracking_order","bundle_configuration","component","device_id", "tracking_tag","size","quantity","status","current_operation","next_operation","current_workstation"],
        as_dict=True
    )

    if not production_item:
        return {
            "status": "no_production_item",
            "message": "No Production Item found for this tag",
            "tracking_tag": tracking_tag.name
        }

    # STEP 4: Return full JSON
    return {
        "status": "success",
        "tracking_tag": tracking_tag.name,
        "production_item": {
            "id":production_item.name,
            "production_item_number": production_item.production_item_number,
            "tracking_order": production_item.tracking_order,
            "bundle_configuration":production_item.bundle_configuration,
            "tracking_tag": production_item.tracking_tag,
            "component":production_item.component,
            "device_id":production_item.device_id,
            "quantity":production_item.quantity,
            "status":production_item.status,
            "current_operation":production_item.current_operation,
            "next_operation":production_item.next_operation,
            "current_workstation":production_item.current_workstation

        }
    }




@frappe.whitelist()
def replace_rfid_tag(old_tag_number=None, new_tag_number=None):
    if not old_tag_number or not new_tag_number:
        return {"status": "error", "message": "old_tag_number and new_tag_number both are required"}

    # ------------------ STEP 1: Validate OLD Tag ------------------
    old_tag = frappe.db.get_value(
        "Tracking Tag",
        {"tag_number": old_tag_number},
        ["name", "status"],
        as_dict=True
    )
    if not old_tag:
        return {"status": "not_found", "message": "Old Tag not found in system"}

    if old_tag.status.lower() == "inactive":
        return {"status": "inactive", "message": "Old Tag is already inactive"}

    # ------------------ STEP 2: Validate OLD Tag Map ------------------
    old_tag_map = frappe.db.get_value(
        "Production Item Tag Map",
        {"tracking_tag": old_tag.name, "is_active": 1},
        ["name", "production_item"],
        as_dict=True
    )
    if not old_tag_map:
        return {"status": "no_mapping", "message": "Old Tag has no active mapping in Production Item Tag Map"}

    # ------------------ STEP 3: Fetch Production Item ------------------
    production_item = frappe.db.get_value(
        "Production Item",
        {"name": old_tag_map.production_item},
        [
            "name", "production_item_number", "tracking_order", "bundle_configuration",
            "component", "device_id", "tracking_tag", "size", "quantity", "status",
            "current_operation", "next_operation", "current_workstation"
        ],
        as_dict=True
    )
    if not production_item:
        return {"status": "no_production_item", "message": "No Production Item found for this Tag"}

    # ------------------ STEP 4: Validate/Create NEW Tag ------------------
    new_tag = frappe.db.get_value(
        "Tracking Tag",
        {"tag_number": new_tag_number},
        ["name", "status"],
        as_dict=True
    )



    if new_tag:
        if new_tag.status.lower() == "inactive":
            return {"status": "inactive", "message": "New Tag exists but is inactive"}
        else:
            # ------------------ STEP 5: Check New Tag Mapping ------------------
            production_item_map = frappe.db.get_value(
                "Production Item Tag Map",
                {"tracking_tag": new_tag["name"],"is_active":1},
                ["name", "is_active", "production_item"],
                as_dict=True
            )
            if production_item_map:
                return {
                    "status": "active",
                    "prodution_item_tag_map":production_item_map.name,
                    "message": "New Tag is linked to Production Item Tag Map we can not replace"
                }
        
    if not new_tag:
        # Create New Tag
        new_tag_doc = frappe.new_doc("Tracking Tag")
        new_tag_doc.tag_number = new_tag_number
        new_tag_doc.tag_type = "RFID"
        new_tag_doc.status = "Active"
        new_tag_doc.activation_source = "Faulty Tag Replacement"
        new_tag_doc.insert(ignore_permissions=True)
        frappe.db.commit()
        new_tag = {"name": new_tag_doc.name, "status": "Active"}


   
   
    # ------------------ STEP 6: Deactivate OLD Mapping ------------------
    frappe.db.set_value("Production Item Tag Map", old_tag_map.name, {
        "is_active": 0,
        "deactivated_source": "Faulty Tag Replacement",
        "linked_on": frappe.utils.now(),
        "activated_source":None
    })
    frappe.db.commit()



    # ------------------ STEP 7: Create NEW Tag Mapping ------------------
    new_map = frappe.new_doc("Production Item Tag Map")
    new_map.production_item = production_item.name
    new_map.tracking_tag = new_tag["name"]
    new_map.activated_source = "Faulty Tag Replacement"
    new_map.is_active = 1
    new_map.linked_on = frappe.utils.now()
    new_map.insert(ignore_permissions=True)
    frappe.db.commit()

    # ------------------ STEP 8: Update Production Item ------------------
    frappe.db.set_value("Production Item", production_item.name, "tracking_tag", new_tag["name"])
    frappe.db.commit()

    # ------------------ STEP 9: Deactivate OLD Tag ------------------
    frappe.db.set_value("Tracking Tag", old_tag["name"], {
        "status": "Inactive",
        "activation_source": "Faulty Tag Replacement",
        "activation_time": frappe.utils.now()
    })
    frappe.db.commit()


    return {
        "old_tag": old_tag.name,
        "new_tag": new_tag["name"],
        "prodution_item_tag_map":new_map.name,
        "production_item": production_item.name ,
        "message": "RFID Tag replaced successfully",
    }
