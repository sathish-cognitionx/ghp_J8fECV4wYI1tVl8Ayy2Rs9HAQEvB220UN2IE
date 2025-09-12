# api.py - Place this in your Frappe app's api folder
import frappe
import json
from frappe import _
from frappe.utils import cstr


@frappe.whitelist(allow_guest=True)
def get_screen_labels_by_locale(screen_id=None, sequence_id=None, domain_name=None, locale_id=None):
    """
    API endpoint to get screen labels by locale
    
    Args:
        screen_id (str): The screen identifier (name field in tabLive Screen)
        locale_id (str, optional): The locale identifier. Defaults to 'en' if not provided.
    
    Returns:
        dict: Screen labels for the specified locale
    """
    try:
        # Validate required parameter
        if not screen_id and not (sequence_id or domain_name):
            frappe.throw(_("Screen ID or Sequence Id is required"), frappe.ValidationError)
        
        # Get screen labels using the service function
        if not screen_id:
            screen_id = get_screen_id_based_on_sequence_id_and_domain(sequence_id, domain_name)

        result = get_screen_labels_by_locale_with_cache(screen_id, locale_id)
        
        return {
            "message": "Fetch successful",
            "data": result
        }
        
    except Exception as e:
        frappe.log_error(f"Error in get_screen_labels_by_locale: {str(e)}")
        frappe.throw(_("Failed to fetch screen labels: {0}").format(str(e)))

def get_screen_id_based_on_sequence_id_and_domain(sequence_id, domain_name):
    """
    Service function to get screen_id based on sequence_id and domain_name
    
    Args:
        sequence_id (int): The sequence identifier
        domain_name (str): The domain name
    
    Returns:
        str: Screen ID (name field) or None if not found
    """
    try:
        # Convert sequence_id to int if it's a string
        if isinstance(sequence_id, str):
            sequence_id = int(sequence_id)
        
        # Method 1: Using frappe.get_all (Recommended)
        screens = frappe.get_all(
            "Live Screen",
            fields=["name"],
            filters={
                "sequence_id": sequence_id,
                "domain_name": domain_name,
                "docstatus": ["!=", 2]  # Exclude cancelled documents
            },
            limit=1
        )
        
        if screens:
            return screens[0].name
        
        return None
        
    except ValueError:
        frappe.throw(_("Invalid sequence ID: must be a number"))
    except Exception as e:
        frappe.log_error(f"Error in get_screen_id_service: {str(e)}")
        raise


def get_screen_labels_by_locale_service(screen_id, locale_id=None):
    """
    Service function to get screen labels by locale (equivalent to your service layer)
    
    Args:
        screen_id (str): The screen identifier
        locale_id (str, optional): The locale identifier
    
    Returns:
        dict: Parsed JSON labels for the specified locale
    """
    try:
        # Default locale if not provided
        default_locale = "en"  # Equivalent to your ftyEnLang
        
        if not locale_id or locale_id.strip() == "":
            locale_id = default_locale
        
        # Get the screen record
        screen_doc = frappe.get_doc("Live Screen", screen_id)
        
        if not screen_doc:
            frappe.throw(_("Screen not found with ID: {0}").format(screen_id))
        
        # Parse the label_locale JSON
        label_locale_json = {}
        
        if screen_doc.label_locale:
            try:
                # Parse the JSON from the database
                all_locales = json.loads(screen_doc.label_locale)
                
                # Try to get the requested locale
                if locale_id in all_locales:
                    label_locale_json = all_locales[locale_id]
                # If requested locale not found and it's not the default, try default locale
                elif locale_id != default_locale and default_locale in all_locales:
                    label_locale_json = all_locales[default_locale]
                # If no specific locale found, return the entire structure
                else:
                    # Check if the JSON structure uses the $.locale format like in your Java code
                    locale_key = locale_id
                    default_locale_key = default_locale
                    
                    if locale_key in all_locales:
                        label_locale_json = all_locales[locale_key]
                    elif default_locale_key in all_locales:
                        label_locale_json = all_locales[default_locale_key]
                    else:
                        # Return empty dict if no matching locale found
                        label_locale_json = {}
                        
            except json.JSONDecodeError as e:
                frappe.log_error(f"Invalid JSON in label_locale field for screen {screen_id}: {str(e)}")
                label_locale_json = {}
        
        return label_locale_json
        
    except frappe.DoesNotExistError:
        frappe.throw(_("Screen not found with ID: {0}").format(screen_id))
    except Exception as e:
        frappe.log_error(f"Error in get_screen_labels_by_locale_service: {str(e)}")
        raise


# Alternative implementation with database query (more similar to your Spring Boot approach)
def get_screen_labels_by_locale_service_db_query(screen_id, locale_id=None):
    """
    Alternative service function using direct database query
    (More similar to your Spring Boot repository approach)
    """
    try:
        # Default locale if not provided
        default_locale = "en"
        
        if not locale_id or locale_id.strip() == "":
            locale_id = default_locale
        
        # Direct database query to get the locale
        # Using JSON_EXTRACT function similar to your findLocaleById method
        locale_path = f"$.{locale_id}"
        
        query = """
            SELECT JSON_EXTRACT(label_locale, %s) as locale_data
            FROM `tabLive Screen`
            WHERE name = %s
        """
        
        result = frappe.db.sql(query, (locale_path, screen_id), as_dict=True)
        
        locale_data = None
        if result and result[0].get('locale_data'):
            locale_data = result[0]['locale_data']
        
        # If locale is unknown and not default locale, try default locale
        if locale_id != default_locale and (not locale_data or str(locale_data).strip() in ['', 'null']):
            default_locale_path = f"$.{default_locale}"
            result = frappe.db.sql(query, (default_locale_path, screen_id), as_dict=True)
            if result and result[0].get('locale_data'):
                locale_data = result[0]['locale_data']
        
        # Parse the JSON result
        label_locale_json = {}
        if locale_data and str(locale_data).strip() not in ['', 'null']:
            if isinstance(locale_data, str):
                try:
                    label_locale_json = json.loads(locale_data)
                except json.JSONDecodeError:
                    label_locale_json = {}
            elif isinstance(locale_data, dict):
                label_locale_json = locale_data
        
        return label_locale_json
        
    except Exception as e:
        frappe.log_error(f"Error in get_screen_labels_by_locale_service_db_query: {str(e)}")
        raise


# hooks.py - Add this to enable caching (optional, similar to your @Cacheable)
# You would add this to your app's hooks.py file if you want caching

def setup_cache():
    """
    Setup Redis cache for screen labels (equivalent to Spring Boot @Cacheable)
    """
    pass  # Frappe has built-in caching mechanisms you can use

# utils.py - Helper functions
def is_null_or_empty(value):
    """
    Utility function similar to your NullEmptyUtil.isNullorEmpty
    """
    if value is None:
        return True
    if isinstance(value, str) and value.strip() == "":
        return True
    return False


# If you want to add caching similar to Spring Boot @Cacheable
from frappe.utils.redis_wrapper import RedisWrapper
import hashlib

def get_screen_labels_by_locale_with_cache(screen_id, locale_id=None):
    """
    Service function with Redis caching (equivalent to @Cacheable)
    """
    try:
        # Create cache key
        cache_key = f"screen_labels:{screen_id}:{locale_id or 'en'}"
        
        # Try to get from cache
        redis = RedisWrapper.from_url(frappe.conf.redis_cache or "redis://localhost:13000")
        cached_result = redis.get(cache_key)
        
        if cached_result:
            return json.loads(cached_result)
        
        # If not in cache, get from database
        result = get_screen_labels_by_locale_service(screen_id, locale_id)
        
        # Store in cache (expire after 1 hour)
        redis.setex(cache_key, 3600, json.dumps(result))
        
        return result
        
    except Exception as e:
        # Fallback to non-cached version if Redis fails
        frappe.log_error(f"Cache error: {str(e)}")
        return get_screen_labels_by_locale_service(screen_id, locale_id)