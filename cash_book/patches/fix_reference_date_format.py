import frappe
from frappe.utils import getdate

def execute():
    if not frappe.db.table_exists("Cash Book Entry"):
        return

    # Find entries with invalid date format (containing '/')
    # This identifies strings like '05/04/2026'
    entries = frappe.db.sql("""
        SELECT name, reference_date 
        FROM `tabCash Book Entry` 
        WHERE reference_date LIKE '%%/%%/%%'
    """, as_dict=1)

    if not entries:
        return

    for d in entries:
        try:
            # getdate() is smart enough to handle various string formats
            new_date = getdate(d.reference_date)
            if new_date:
                frappe.db.sql("""
                    UPDATE `tabCash Book Entry` 
                    SET reference_date = %s 
                    WHERE name = %s
                """, (new_date, d.name))
        except Exception:
            # If parsing fails, we skip this record to avoid blocking the migration
            # The migration might still fail for this record, but we try our best.
            pass

    frappe.db.commit()
