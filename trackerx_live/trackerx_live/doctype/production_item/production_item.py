# Copyright (c) 2025, CognitionX and contributors
# For license information, please see license.txt

import frappe
from frappe.model.document import Document

class ProductionItem(Document):
    pass
    # def before_insert(self):
    #     # Ensure request context exists
    #     if frappe.request:
    #         path = frappe.request.path or ""
            
    #         # If request comes from Desk/UI it usually looks like `/api/method/frappe.desk.form.save.savedocs`
    #         if "frappe.desk.form.save.savedocs" in path:
    #             frappe.throw("You cannot manage this from Web UI, Use our TrackerX Live Native App, Please contact support team. ")