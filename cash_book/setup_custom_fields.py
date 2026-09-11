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
            "options": "\nDirect Cost\nIndirect Cost\nDistribution costs\nAdministrative expenses\nOther expenses",
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
            "options": "\nDirect Cost\nIndirect Cost\nDistribution costs\nAdministrative expenses\nOther expenses",
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
            "options": "\nDirect Cost\nIndirect Cost\nDistribution costs\nAdministrative expenses\nOther expenses",
            "in_list_view": 1,
            "in_preview": 1,
            "in_standard_filter": 1,
            "insert_after": "account_type",
            "search_index": 1
        }
    ]
}

def sync_existing_gl_and_journal_types():
    """
    Backfills and synchronizes custom_type on existing Journal Entry Accounts and GL Entries:
    1. From Cash Book Account entries linked to Journal Entries (custom_cashbook_entry_ref).
    2. From Account default custom_cost_type.
    3. Propagates custom_type from Journal Entry Account to GL Entry.
    """
    try:
        # 1. Update Journal Entry Account custom_type from Cash Book Account
        frappe.db.sql("""
            UPDATE `tabJournal Entry Account` jea
            INNER JOIN `tabJournal Entry` je ON jea.parent = je.name
            INNER JOIN `tabCash Book Account` cba ON cba.parent = je.custom_cashbook_entry_ref AND cba.account = jea.account
            SET jea.custom_type = cba.type
            WHERE (jea.custom_type IS NULL OR jea.custom_type = '')
              AND cba.type IS NOT NULL
              AND cba.type != ''
              AND cba.type NOT IN ('Direct Income', 'Indirect Income', 'Purchases')
              AND je.custom_cashbook_entry_ref IS NOT NULL
        """)

        # 2. Update Journal Entry Account custom_type from Account master default if still empty
        frappe.db.sql("""
            UPDATE `tabJournal Entry Account` jea
            INNER JOIN `tabAccount` acc ON jea.account = acc.name
            SET jea.custom_type = acc.custom_cost_type
            WHERE (jea.custom_type IS NULL OR jea.custom_type = '')
              AND acc.custom_cost_type IS NOT NULL
              AND acc.custom_cost_type != ''
        """)

        # 3. Update GL Entry custom_type from matching Journal Entry Account
        frappe.db.sql("""
            UPDATE `tabGL Entry` gl
            INNER JOIN `tabJournal Entry Account` jea ON gl.voucher_no = jea.parent AND gl.account = jea.account
            SET gl.custom_type = jea.custom_type
            WHERE gl.voucher_type = 'Journal Entry'
              AND (gl.custom_type IS NULL OR gl.custom_type = '')
              AND jea.custom_type IS NOT NULL
              AND jea.custom_type != ''
        """)

        # 4. Update GL Entry custom_type directly from Account master default if still empty
        frappe.db.sql("""
            UPDATE `tabGL Entry` gl
            INNER JOIN `tabAccount` acc ON gl.account = acc.name
            SET gl.custom_type = acc.custom_cost_type
            WHERE (gl.custom_type IS NULL OR gl.custom_type = '')
              AND acc.custom_cost_type IS NOT NULL
              AND acc.custom_cost_type != ''
        """)

        # Clean up any obsolete tags if previously assigned
        frappe.db.sql("""
            UPDATE `tabGL Entry`
            SET custom_type = NULL
            WHERE custom_type IN ('Direct Income', 'Indirect Income', 'Purchases')
        """)
        frappe.db.sql("""
            UPDATE `tabJournal Entry Account`
            SET custom_type = NULL
            WHERE custom_type IN ('Direct Income', 'Indirect Income', 'Purchases')
        """)

        frappe.db.commit()
    except Exception as e:
        frappe.log_error(f"Error in sync_existing_gl_and_journal_types: {str(e)}", "Cash Book Sync")

def setup_all_custom_fields():
    """
    Creates and updates all custom fields automatically when app is installed or migrated,
    and runs initial synchronization of existing transaction data.
    """
    create_custom_fields(CUSTOM_FIELDS, update=True)
    sync_existing_gl_and_journal_types()
    frappe.clear_cache()
