# Copyright (c) 2025, CognitionX and contributors
# For license information, please see license.txt

import frappe
from frappe.model.document import Document

class TrackingOrderBundleConfiguration(Document):
    def before_insert(self):
        """
        This method is called before a new Bundle Configuration row is inserted into the database.
        It ensures that the 'production_type' is copied from the parent 'Tracking Order'.
        """
        self._set_production_type_from_parent()
        frappe.log_error("TrackingOrderBundleConfiguration before_insert triggered", f"Parent: {self.parent}, Parent Type: {self.parenttype}, Production Type: {self.production_type}")

    def before_save(self):
        """
        This method is called before a Bundle Configuration row is saved (both new and existing).
        It acts as a fallback to ensure 'production_type' is always in sync with the parent.
        """
        self._set_production_type_from_parent()
        frappe.log_error("TrackingOrderBundleConfiguration before_save triggered", f"Parent: {self.parent}, Parent Type: {self.parenttype}, Production Type: {self.production_type}")

    def _set_production_type_from_parent(self):
        """
        Helper method to fetch and set the production_type from the parent Tracking Order.
        """
        # Ensure this is a child of Tracking Order and parent name is available
        if self.parenttype == "Tracking Order" and self.parent:
            try:
                # Get the parent document
                parent_doc = frappe.get_doc("Tracking Order", self.parent)
                # Set the production_type from the parent
                self.production_type = parent_doc.production_type
                frappe.log_error("Production Type Copied (Server-Side)", f"From Parent: {parent_doc.production_type} to Child: {self.production_type}")
            except Exception as e:
                frappe.log_error("Error in _set_production_type_from_parent", f"Error: {e}, Parent: {self.parent}")
        else:
            frappe.log_error("No Parent Tracking Order Found", f"Parent: {self.parent}, Parent Type: {self.parenttype}")

