# Copyright (c) 2025, CognitionX and contributors
# For license information, please see license.txt

import frappe
from frappe.model.document import Document

class FactoryProdId(Document):
    def validate(self):
        # Skip validation if mandatory fields are missing
        if not all([self.style, self.colour, self.brand]):
            return

        # Check for existing combination (excluding current document)
        existing = frappe.get_all("Factory Prod Id",
            filters={
                "style": self.style,
                "colour": self.colour,
                "brand": self.brand,
                "name": ("!=", self.name or "")
            },
            limit=1
        )

        if existing:
            frappe.throw(
                "A record with this style/colour/brand combination already exists. "
                "Duplicate combinations are not allowed."
            )

        # Generate factory_prod_id if empty
        if not self.factory_prod_id:
            self.factory_prod_id = self.generate_factory_prod_id()

        # Set document name to match factory_prod_id
        self.name = self.factory_prod_id

    def generate_factory_prod_id(self):
        """Generate a unique ID based on style, colour, brand"""
        style_part = (frappe.scrub(self.style[:3]) if self.style else "sty").lower()
        colour_part = (frappe.scrub(self.colour[:2]) if self.colour else "cl").lower()
        brand_part = (frappe.scrub(self.brand[:3]) if self.brand else "brd").lower()
        base_id = f"{style_part}-{colour_part}-{brand_part}"

        # Ensure uniqueness
        counter = 1
        new_id = base_id
        while frappe.db.exists("Factory Prod Id", {"factory_prod_id": new_id}):
            new_id = f"{base_id}-{counter}"
            counter += 1

        return new_id

    def before_save(self):
        # Final check to ensure name is set
        if not self.name and self.factory_prod_id:
            self.name = self.factory_prod_id

    def autoname(self):
        # Skip default naming as we handle it in validate
        pass

    @frappe.whitelist()
    def check_existing_combination(style, colour, brand):
        """Client-side method to check for existing combinations"""
        exists = frappe.db.exists("Factory Prod Id", {
            "style": style,
            "colour": colour,
            "brand": brand
        })
        return bool(exists)
