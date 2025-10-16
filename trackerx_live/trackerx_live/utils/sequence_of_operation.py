
import frappe

class SequenceOfOpeationUtil:
    
    @staticmethod
    def can_this_item_scan_in_this_operation(production_item, workstation, operation, physical_cell):
        old_logs = frappe.get_list("Item Scan Log",
            filters = {
                "production_item": production_item,
                "operation": operation,
                "log_status": "Completed"
            },
            fields=["name", "status", "creation"]
        )

        if not old_logs:
            return {
                "is_allowed": True
            }
        
        for log in old_logs:
            if log.status in ('Pass', 'SP Pass', 'Counted'):
                # frappe.throw(
                #     f"Item is already scanned in this operation"
                # )
                return {
                    "is_allowed": False,
                    "reason": "ALREADY_PASSED",
                    "old_logs": old_logs
                }
            
        return {
                "is_allowed": True
        }
        

        