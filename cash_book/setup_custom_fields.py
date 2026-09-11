import frappe
from frappe.custom.doctype.custom_field.custom_field import create_custom_fields

CUSTOM_FIELDS = {
    "Journal Entry": [
        {
            "fieldname": "custom_cashbook_entry_ref",
            "fieldtype": "Link",
            "label": "Cashbook Entry Ref",
            "options": "Cash Book Entry",
            "insert_after": "voucher_type"
        }
    ],
    "Journal Entry Account": [
        {
            "fieldname": "custom_type",
            "fieldtype": "Select",
            "label": "Type",
            "options": "\nDirect Cost\nIndirect Cost\nDirect Income\nIndirect Income\nDistribution costs\nAdministrative expenses\nOther expenses\nPurchases",
            "in_list_view": 1,
            "in_preview": 1,
            "in_standard_filter": 1,
            "insert_after": "party",
            "search_index": 1
        }
    ],
    "GL Entry": [
        {
            "fieldname": "custom_type",
            "fieldtype": "Select",
            "label": "Type",
            "options": "\nDirect Cost\nIndirect Cost\nDirect Income\nIndirect Income\nDistribution costs\nAdministrative expenses\nOther expenses\nPurchases",
            "in_list_view": 1,
            "in_preview": 1,
            "in_standard_filter": 1,
            "insert_after": "voucher_detail_no",
            "search_index": 1
        }
    ],
    "Account": [
        {
            "fieldname": "custom_cost_type",
            "fieldtype": "Select",
            "label": "Cost Type",
            "options": "\nDirect Cost\nIndirect Cost\nDirect Income\nIndirect Income\nDistribution costs\nAdministrative expenses\nOther expenses\nPurchases",
            "in_list_view": 1,
            "in_preview": 1,
            "in_standard_filter": 1,
            "insert_after": "account_type",
            "search_index": 1
        }
    ]
}

def setup_all_custom_fields():
    """
    Creates and updates all custom fields automatically when app is installed or migrated.
    """
    create_custom_fields(CUSTOM_FIELDS, update=True)
    frappe.clear_cache()
