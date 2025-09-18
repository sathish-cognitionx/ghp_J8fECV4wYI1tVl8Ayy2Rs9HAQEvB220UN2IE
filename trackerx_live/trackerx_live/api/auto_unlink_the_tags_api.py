import frappe
from frappe import _

@frappe.whitelist()
def auto_unlink_tags(tag_numbers, ws_name=None):
    if not tag_numbers:
        return {"status": "error", "message": "No tracking numbers provided"}

    if not ws_name:
        return {"status": "error", "message": "Workstation name is required"}

    updated_tags, skipped_tags, not_found_tags = [], [], []

    for tracking_tag_number in tag_numbers:
        tag = frappe.get_all(
            "Tracking Tag",
            filters={"tag_number": tracking_tag_number},
            fields=["name"]
        )

        if not tag:
            not_found_tags.append(tracking_tag_number)
            continue

        tag_id = tag[0].name
        tag_map = frappe.get_all(
            "Production Item Tag Map",
            filters={"tracking_tag": tag_id, "is_active": 1},
            fields=["name", "production_item"]
        )

        if not tag_map:
            skipped_tags.append(tracking_tag_number)
            continue

        tag_doc = frappe.get_doc("Production Item Tag Map", tag_map[0].name)
        tag_doc.is_active = 0
        tag_doc.deactivated_source = "EOL UnLink"
        tag_doc.save()

        production_item_name = tag_map[0].get("production_item")
        if production_item_name:
            pi_doc = frappe.get_doc("Production Item", production_item_name)
            pi_doc.tracking_status = "Unlinked"
            pi_doc.unlinked_source = "EOL"
            pi_doc.save()


        updated_tags.append(tracking_tag_number)

    frappe.db.commit()

    return {
        "status": "success",
        "updated_tags": updated_tags,
        "skipped_tags": skipped_tags,
        "not_found_tags": not_found_tags
    }
