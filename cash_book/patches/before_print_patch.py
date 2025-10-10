import frappe
from frappe.utils.safe_exec import safe_exec

def safe_before_print(doc, method=None, settings=None):
    frappe.msgprint("print check")

    try:
        # Only patch these doctypes
        if doc.doctype in [
            "Purchase Order",
            "Sales Order",
            "Sales Invoice",
            "Purchase Invoice",
            "Supplier Quotation",
            "Purchase Receipt",
            "Delivery Note",
            "Quotation",
        ]:
            if doc.get("group_same_items"):
                doc.group_similar_items()

            df = doc.meta.get_field("discount_amount")
            if doc.get("discount_amount") and hasattr(doc, "taxes") and not len(doc.taxes):
                df.set("print_hide", 0)
                doc.discount_amount = -doc.discount_amount
            else:
                df.set("print_hide", 1)

        # Still run ERPNext’s print setup
        from erpnext.controllers.print_settings import (
            set_print_templates_for_item_table,
            set_print_templates_for_taxes,
        )

        set_print_templates_for_item_table(doc, settings)
        set_print_templates_for_taxes(doc, settings)

    except Exception as e:
        frappe.log_error(f"Safe before_print failed: {e}", "safe_before_print_patch")
