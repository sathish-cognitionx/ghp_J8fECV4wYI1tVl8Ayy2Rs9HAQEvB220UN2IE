import frappe
from frappe import _

@frappe.whitelist()
def auto_unlink_tags(tag_numbers):
  
    if not tag_numbers:
        return {"status": "error", "message": "No tracking numbers provided"}

    updated_tags = []
    skipped_tags = []
    not_found_tags = []

    for tracking_tag_number in tag_numbers:
        # Get Tag ID from Tracking Tag doctype
        tag = frappe.get_all(
            "Tracking Tag",
            filters={"tag_number": tracking_tag_number},
            fields=["name"]
        )

        if not tag:
            not_found_tags.append(tracking_tag_number)
            continue

        tag_id = tag[0].name

        # Check Production Item Tag Map for active mapping
        tag_map = frappe.get_all(
            "Production Item Tag Map",
            filters={"tracking_tag": tag_id, "is_active": 1},
            fields=["name"]
        )

        if tag_map:
            tag_doc = frappe.get_doc("Production Item Tag Map", tag_map[0].name)
            tag_doc.is_active = 0
            tag_doc.save()
            frappe.db.commit()
            updated_tags.append(tracking_tag_number)
        else:
            skipped_tags.append(tracking_tag_number)

    return {
        "status": "success",
        "updated_tags": updated_tags,
        "skipped_tags": skipped_tags,
        "not_found_tags": not_found_tags
    }
