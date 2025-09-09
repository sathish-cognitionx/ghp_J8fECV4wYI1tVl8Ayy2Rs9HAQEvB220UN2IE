import frappe
from frappe.utils import flt
from frappe.exceptions import ValidationError

@frappe.whitelist()
def get_workstation_by_device_id(device_identifier=None):
    try:
        device_id = frappe.db.get_value("Digital Device",{"identifier": device_identifier}, "name")

        workstations = frappe.get_all(
            "Digital Device Workstation Map",
            filters={"digital_device": device_id, "link_status": "Linked"},
            fields=["workstation"]
        )

        
        for workstation in workstations:
            ws_info = get_workstation_info(workstation.workstation)  # Fixed: accessing workstation.workstation
            if ws_info.get('status') == 'success':  # Fixed: using .get() method
                workstation['ws_info'] = ws_info["data"]  # Fixed: using dictionary access

        return {
            "status": "success",
            "data": workstations
        }
    except frappe.ValidationError as e:
        frappe.log_error(frappe.get_traceback(), "get_workstation_by_device_id() error")
        frappe.local.response.http_status_code = 400
    except Exception as e:
        frappe.log_error(frappe.get_traceback(), "get_workstation_by_device_id() error")
        return {"status": "error", "message": str(e)}


@frappe.whitelist()
def get_workstations():
    try:
        workstations = frappe.get_all("Workstation", fields=["name"])

        return {
            "status": "success",
            "data": workstations
        }
        # Removed: unreachable return statement
    except frappe.ValidationError as e:
        frappe.log_error(frappe.get_traceback(), "get_workstations() error")
        frappe.local.response.http_status_code = 400
        return {"status": "error", "message": str(e)}
    except Exception as e:
        frappe.log_error(frappe.get_traceback(), "get_workstations() error")
        return {"status": "error", "message": str(e)}


@frappe.whitelist()
def get_workstation_info(ws_name=None):
    try:
        cell_operation_ws_list = frappe.get_all( "Physical Cell Operation",
            filters={
                "workstation": ws_name,  
            },
            fields=["name", "operation", "parent"]
        )

        workstation_info_list = []

        for cell_operation_ws in cell_operation_ws_list:
            cell = frappe.get_doc("Physical Cell", cell_operation_ws.parent)
            operation = frappe.get_doc("Operation", cell_operation_ws.operation)
            workstation_info_list.append({
                 "workstation": ws_name,
                 "cell_number": cell.cell_number,
                 "cell_name": cell.cell_name,
                 "cell_id": cell.name,
                 "operation_group": cell.supported_operation_group,
                 "operation_name": operation.name,
                 "operation_type": operation.custom_operation_type
            })

        return {
             "status": "success",
             "data": workstation_info_list
        }
    except frappe.ValidationError as e:
        frappe.log_error(frappe.get_traceback(), "get_workstation_info() error")
        frappe.local.response.http_status_code = 400
        return {"status": "error", "message": str(e)}
    except Exception as e:
            frappe.log_error(frappe.get_traceback(), "get_workstation_info() error")
            return {"status": "error", "message": str(e)}
    

@frappe.whitelist()
def device_choosen_workstation(device_identifier, ws_name, device_identifer_type='IMEI', device_type='Tablet'):
    try:
        # Fixed: Proper way to check if document exists
        digital_device = None
        try:
            digital_device = frappe.get_doc("Digital Device", {"identifier": device_identifier})
        except frappe.DoesNotExistError:
            pass

        cell_operations = frappe.get_all("Physical Cell Operation", 
            filters={"workstation": ws_name},
            fields=["name"])
        
        if not cell_operations:
            frappe.throw(
                f"Workstation {ws_name} is not added to any cell",
                ValidationError
            )
        
        if not digital_device:
            #insert digital device
            digital_device = frappe.new_doc("Digital Device")
            digital_device.asset_tag_number = device_identifier
            digital_device.device_type = device_type
            digital_device.serial_number = None
            digital_device.model_number = None
            digital_device.manufacturer = None
            digital_device.identifier = device_identifier
            digital_device.identifier_type = device_identifer_type
            digital_device.imei = device_identifier if device_identifer_type == 'IMEI' else None
            digital_device.mac = device_identifier if device_identifer_type == 'Mac' else None
            digital_device.ipv4 = device_identifier if device_identifer_type == 'IPv4' else None
            digital_device.id = device_identifier if device_identifer_type == 'ID' else None
            digital_device.insert()

        # Fixed: Properly updating existing records
        digital_device_ws_maps = frappe.get_all("Digital Device Workstation Map", 
            filters={"digital_device": digital_device.name, "link_status": "Linked"},
            fields=["name"])
        
        if digital_device_ws_maps:
            for map_record in digital_device_ws_maps:
                doc = frappe.get_doc("Digital Device Workstation Map", map_record.name)
                doc.link_status = "Unlinked"
                doc.save()
        
        digital_device_ws_map = frappe.new_doc("Digital Device Workstation Map")
        digital_device_ws_map.digital_device = digital_device.name
        digital_device_ws_map.workstation = ws_name
        digital_device_ws_map.link_status = "Linked"
        digital_device_ws_map.insert()



        return {
             "status": "success"
        }
    except frappe.ValidationError as e:
        frappe.log_error(frappe.get_traceback(), "device_choosen_workstation() error")
        frappe.local.response.http_status_code = 400
        return {"status": "error", "message": str(e)}
    except Exception as e:
        frappe.log_error(frappe.get_traceback(), "device_choosen_workstation() error")
        frappe.local.response.http_status_code = 500
        return {"status": "error", "message": str(e)}
            
            