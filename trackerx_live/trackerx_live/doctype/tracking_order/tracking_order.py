# Copyright (c) 2025, CognitionX and contributors
# For license information, please see license.txt

import frappe
from frappe.model.document import Document

class TrackingOrder(Document):
    def validate(self):

        self.validate_bundle_configurations()

        self.validate_tracking_components()
    

    def validate_bundle_configurations(self):
        """
        Validates the Tracking Order document before saving.
        Includes checks for Bundle Configuration:
        1. Ensures at least one row if production_type is 'Bundle'.
        2. Ensures the sum of (bundle_quantity * number_of_bundles) matches
           the main Tracking Order quantity.
        """
        if self.production_type == "Bundle":
            # Validation 1: Ensure at least one row in Bundle Configuration
            if not self.bundle_configurations:
                frappe.throw("For 'Bundle' production type, at least one Bundle Configuration row is required.")

            # Validation 2: Sum of (bundle_quantity * number_of_bundles) must match quantity
            total_bundled_quantity = 0
            for bundle_config in self.bundle_configurations:
                # Ensure bundle_quantity and number_of_bundles are not None and are numbers
                # Use frappe.utils.flt for robust type conversion and handling potential None/empty values
                bundle_qty = frappe.utils.flt(bundle_config.bundle_quantity)
                num_bundles = frappe.utils.flt(bundle_config.number_of_bundles)

                if bundle_config.bundle_quantity is None or bundle_qty <= 0:
                    frappe.throw(f"Bundle Quantity must be a positive number in row {bundle_config.idx}.")
                if bundle_config.number_of_bundles is None or num_bundles <= 0:
                    frappe.throw(f"Number of Bundles must be a positive number in row {bundle_config.idx}.")

                total_bundled_quantity += (bundle_qty * num_bundles)

            # Ensure the main quantity is not None and is a number
            main_quantity = frappe.utils.flt(self.quantity)
            if self.quantity is None or main_quantity <= 0:
                frappe.throw("Quantity to manufacture must be a positive number.")

            if total_bundled_quantity != main_quantity:
                frappe.throw(
                    "The sum of (Units per Bundle * Number of Bundles) "
                    f"({total_bundled_quantity}) does not match the Tracking Order Quantity ({self.quantity})."
                )

    def validate_tracking_components(self):
        # --- Validation: Tracking Components ---
        component_names = set()
        parent_components = set()
        main_component = None

        for row in self.tracking_components:
            name = row.component_name.strip() if row.component_name else None
            if not name:
                frappe.throw(f"Component Name is required in row {row.idx} of Tracking Components.")
            
            # Track uniqueness
            if name in component_names:
                frappe.throw(f"Duplicate Component Name '{name}' found in Tracking Components at row {row.idx}.")
            component_names.add(name)

            # Track parent usage
            if row.parent_component:
                if row.parent_component == name:
                    frappe.throw(f"Component '{name}' cannot be its own parent (row {row.idx}).")
                parent_components.add(row.parent_component)

            # Check for multiple main components
            if row.is_main:
                if main_component:
                    frappe.throw(f"Multiple main components found: '{main_component}' and '{name}'. Only one is allowed.")
                main_component = name

        # Leaf validation: main component must not be a parent of any other
        if main_component and main_component in parent_components:
            frappe.throw(f"The main component '{main_component}' cannot be a parent to another component. It must be a leaf node.")

        


    def before_save(self):
		# set the production type to bundle configurations
        self.set_production_type_on_children()
        
        if self.production_type == "Single Unit":
        # Clear existing bundle configurations to ensure only one row for single unit
            if self.bundle_configurations:
                self.bundle_configurations = [] # Clear the table

            # Add a new row to bundle_configurations for the single unit
            new_bundle_row = self.append("bundle_configurations", {})
            new_bundle_row.bc_name = "Single Unit Bundle"
            new_bundle_row.production_type="Single Unit"
            new_bundle_row.size = self.single_unit_size if hasattr(self, 'single_unit_size') and self.single_unit_size else "None"
            new_bundle_row.bundle_quantity = self.quantity # Total quantity of Tracking Order
            new_bundle_row.number_of_bundles = 1

			# The production_type for this child row will be set by
			# self.set_production_type_on_children() which runs above.

            frappe.log_error("Single Unit Bundle Created", f"Tracking Order: {self.name}, Quantity: {self.quantity}")
        
        
        


	
    def set_production_type_on_children(self):
        for row in self.bundle_configurations:
            row.production_type = self.production_type
