import frappe
from frappe.utils import getdate

def execute():
    if not frappe.db.table_exists("Cash Book Entry"):
        return

    # Find entries with invalid date format (not starting with YYYY-)
    # This identifies strings like '05/04/2026' or '16-03-2026'
    entries = frappe.db.sql("""
        SELECT name, reference_date 
        FROM `tabCash Book Entry` 
        WHERE reference_date IS NOT NULL 
          AND reference_date != ''
          AND reference_date NOT LIKE '20%%-%%-%%'
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
            pass

    frappe.db.commit()
