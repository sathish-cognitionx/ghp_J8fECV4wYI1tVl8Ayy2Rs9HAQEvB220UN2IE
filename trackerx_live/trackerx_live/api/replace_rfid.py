import frappe


@frappe.whitelist()
def check_tag_number_status(tag_number=None):
    if not tag_number:
        return {"status": "error", "message": "tag_number is required"}

    # Fetch Tracking Tag record
    tracking_tag = frappe.db.get_value(
        "Tracking Tag",
        {"tag_number": tag_number},
        ["name", "status"],
        as_dict=True
    )

    # If no tag found
    if not tracking_tag:
        return {"status": "not_found", "message": "Tag number not found in system"}

    # If inactive
    if tracking_tag.status.lower() == "inactive":
        return {
            "status": "inactive",
            "message": "This tag is inactive"
        }

    # If active, then get Production Item linked with this Tracking Tag
    production_item = frappe.db.get_value(
        "Production Item",
        {"tracking_tag": tracking_tag.name},
        ["name", "production_item_number", "tracking_order", "tracking_tag"],
        as_dict=True
    )

    if not production_item:
        return {
            "status": "no_production_item",
            "message": "No Production Item found for this tag",
            "tracking_tag": tracking_tag.name
        }

    # Return full data
    return {
        "status": "success",
        "tracking_tag": tracking_tag.name,
        "production_item": production_item
    }




@frappe.whitelist()
def replace_rfid_tag(old_tag_number=None, new_tag_number=None):
    if not old_tag_number or not new_tag_number:
        return {"status": "error", "message": "old_tag_number and new_tag_number both are required"}

    # Fetch old tag
    old_tracking_tag = frappe.db.get_value(
        "Tracking Tag",
        {"tag_number": old_tag_number},
        ["name", "status"],
        as_dict=True
    )

    if not old_tracking_tag:
        return {"status": "not_found", "message": "Old Tag number not found in system"}

    if old_tracking_tag.status.lower() == "inactive":
        return {"status": "inactive", "message": "Old tag is inactive"}

    #  STEP 1: Fetch new tag and check status first
    new_tracking_tag = frappe.db.get_value(
        "Tracking Tag",
        {"tag_number": new_tag_number},
        ["name", "status"],
        as_dict=True
    )

    if new_tracking_tag:
        # Check status of new tag
        if new_tracking_tag.status.lower() == "inactive":
            return {"status": "inactive", "message": "New tag is inactive, cannot replace"}

        # Check if new tag assigned to any production item
        assigned_item = frappe.db.get_value(
            "Production Item",
            {"tracking_tag": new_tracking_tag.name},
            "name"
        )
        if assigned_item:
            return {
                "status": "assigned",
                "message": "New Tag is already linked to a Production Item",
                "production_item": assigned_item
            }

        # If new tag exists but not assigned → continue replacement (no return here)
        new_tag_name = new_tracking_tag.name

    else:
        # STEP 2: If new tag not found - create it
        doc = frappe.new_doc("Tracking Tag")
        doc.tag_number = new_tag_number
        doc.tag_type = "RFID"
        doc.status = "Active"
        doc.activation_source = "Faulty Tag Replacement"
        doc.insert(ignore_permissions=True)
        frappe.db.commit()
        new_tag_name = doc.name

    # STEP 3: Fetch Production Item linked to old tag
    production_item = frappe.db.get_value(
        "Production Item",
        {"tracking_tag": old_tracking_tag.name},
        ["name", "production_item_number", "tracking_order", "tracking_tag"],
        as_dict=True
    )

    if production_item:
        frappe.db.set_value("Production Item", production_item.name, "tracking_tag", new_tag_name)
        frappe.db.commit()
        production_item["tracking_tag"] = new_tag_name
    else:
        return {
            "status": "no_production_item",
            "message": "Old Tag is not linked to any Production Item"
        }

    # STEP 4: Deactivate old tag
    frappe.db.set_value("Tracking Tag", old_tracking_tag.name, "status", "Inactive")
    frappe.db.commit()

    return {
        "status": "success",
        "message": "RFID Tag replaced successfully",
        "old_tracking_tag": old_tracking_tag.name,
        "new_tracking_tag": new_tag_name,
        "production_item": production_item
    }
