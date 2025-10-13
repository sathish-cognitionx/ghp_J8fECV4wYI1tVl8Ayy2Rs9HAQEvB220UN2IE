import frappe


class TrackerXLiveSettings:

    @staticmethod
    def is_allow_partial_bundle_progressive_enabled():
        return frappe.db.get_single_value("TrackerX Live Settings", "progressive_defective_unit_tagging") and frappe.db.get_single_value("TrackerX Live Settings", "progressive_allow_partial_bundle_flow") 

    @staticmethod
    def is_allow_partial_bundle_component_enabled():
        return frappe.db.get_single_value("TrackerX Live Settings", "component_defective_unit_tagging") and frappe.db.get_single_value("TrackerX Live Settings", "component_allow_partial_bundle_flow") 

    @staticmethod
    def is_dut_on(type):
        return frappe.db.get_single_value("TrackerX Live Settings", "component_defective_unit_tagging") if type == "Component" else frappe.db.get_single_value("TrackerX Live Settings", "progressive_defective_unit_tagging") 