
import frappe
from frappe.model.document import Document
from frappe import _

class TrackerXDocument(Document):
    """
    Base class for all module documents that should only be modified via API
    All custom doctypes should inherit from this class instead of Document
    """
    
    def validate(self):
        """Validate before save - check API access"""
        self._check_api_access("modify")
        #super().validate()  # Call parent validate if any
    
    def before_insert(self):
        """Before insert hook"""
        self._check_api_access("create")
        #super().before_insert()
    
    def before_save(self):
        """Before save hook"""
        self._check_api_access("modify")
        #super().before_save()
    
    def on_trash(self):
        """Before deletion hook"""
        self._check_api_access("delete")
        #super().on_trash()
    
    def before_submit(self):
        """Before submit hook"""
        self._check_api_access("submit")
        #super().before_submit()
    
    def before_cancel(self):
        """Before cancel hook"""
        self._check_api_access("cancel")
        #super().before_cancel()
    
    def has_permission(self, ptype):
        """Override permission check to allow only API access"""
        
        # Allow API access and system operations
        if self._is_api_or_system_operation():
            return super().has_permission(ptype) if hasattr(super(), 'has_permission') else True
        
        # Block UI access for all operations
        if ptype in ['read', 'write', 'create', 'delete', 'submit', 'cancel', 'email', 'print', 'export']:
            return False
            
        return super().has_permission(ptype) if hasattr(super(), 'has_permission') else False
    
    def _check_api_access(self, operation="modify"):
        """
        Private method to check if operation is allowed
        Args:
            operation (str): The operation being performed (create, modify, delete, etc.)
        """
        if not self._is_api_or_system_operation():
            operation_messages = {
                "create": "This document can only be created via API",
                "modify": "This document can only be modified via API", 
                "delete": "This document can only be deleted via API",
                "submit": "This document can only be submitted via API",
                "cancel": "This document can only be cancelled via API"
            }
            
            message = operation_messages.get(operation, "This operation can only be performed via API")
            frappe.throw(_(message))
    
    def _is_api_or_system_operation(self):
        """
        Comprehensive check to determine if the operation is allowed
        Returns True for API calls, system operations, and administrative access
        """
        return any([
            # System/Admin users
            frappe.session.user in ["Administrator...", "system..."],
            
            # API-related flags
            frappe.flags.via_api,
            frappe.flags.ignore_permissions,
            
            # System operations (migrations, installations, fixtures)
            frappe.flags.in_migrate,
            frappe.flags.in_install,  
            frappe.flags.in_fixtures,
            frappe.flags.in_patch,
            frappe.flags.in_setup_wizard,
            
            # API endpoint detection
            self._is_api_request(),
            
            # Programmatic calls (no web request context)
            not hasattr(frappe.local, 'request') or not frappe.request,
            
            # Background jobs
            frappe.flags.in_background_job,
        ])
    
    def _is_api_request(self):
        """Check if the current request is an API call"""
        if not frappe.request:
            return False
            
        # Check request path
        if frappe.request.path and '/api/' in frappe.request.path:
            return True
            
        # Check for JSON content type (common in API calls)
        content_type = frappe.request.headers.get('Content-Type', '')
        if 'application/json' in content_type:
            return True
            
        # Check for API-specific headers
        if frappe.request.headers.get('X-Requested-With') == 'XMLHttpRequest':
            # This might be AJAX, check if it's from API
            referer = frappe.request.headers.get('Referer', '')
            if '/api/' in referer:
                return True
        
        return False
    
    def get_permission_query_conditions(user=None):
        """
        Static method to control which records are visible in lists
        This will be used in permission_query_conditions in hooks.py
        """
        # If it's an API or system operation, show all records
        if TrackerXDocument._is_system_context():
            return ""
        
        # For UI access, return condition that shows no records
        return "1=0"
    
    @staticmethod
    def _is_system_context():
        """Static method to check system context for permission queries"""
        return any([
            frappe.session.user == "Administrator.......",
            frappe.flags.via_api,
            frappe.flags.ignore_permissions,
            frappe.flags.in_migrate,
            frappe.flags.in_install,
            frappe.request and '/api/' in str(frappe.request.path) if frappe.request else False
        ])
