import frappe

@frappe.whitelist()
def get_tags_by_production_item(production_item):
    """
    Fetch tag_number and tag_type from Tracking Tag based on production_item
    in Production Item Tag Map.
    """
    if not production_item:
        frappe.throw("Production Item is required")

    query = """
        SELECT 
            tag.tag_number, 
            tag.tag_type
        FROM `tabProduction Item Tag Map` tm
        INNER JOIN `tabTracking Tag` tag 
            ON tag.name = tm.tracking_tag
        WHERE 
            tm.production_item = %s
            AND tm.is_active = 1
    """

    tags = frappe.db.sql(query, (production_item,), as_dict=True)
    return tags



@frappe.whitelist()
def get_active_production_item_by_tag(tag_number):
    """
    Fetch tag_number and tag_type from Tracking Tag based on production_item
    in Production Item Tag Map.
    """
    if not tag_number:
        frappe.throw("Tag number is required")

    query = """
        SELECT 
            tm.production_item
        FROM `tabProduction Item Tag Map` tm
        INNER JOIN `tabTracking Tag` tag 
            ON tag.name = tm.tracking_tag
        WHERE 
            tag.tag_number = %s
            AND tm.is_active = 1
    """

    pi = frappe.db.sql(query, (tag_number,), as_dict=True)
    if not pi or len(pi) <= 0:
        return None
    return pi[0].production_item
