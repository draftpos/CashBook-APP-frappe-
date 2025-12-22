import frappe

def safe_before_print(doc, method=None, settings=None):
    try:
        # Debug log instead of msgprint
        # frappe.msgprint("check print now")

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
            if df:  # avoid NoneType error
                if doc.get("discount_amount") and hasattr(doc, "taxes") and not len(doc.taxes):
                    df.set("print_hide", 0)
                    doc.discount_amount = -doc.discount_amount
                else:
                    df.set("print_hide", 1)

        from erpnext.controllers.print_settings import (
            set_print_templates_for_item_table,
            set_print_templates_for_taxes,
        )

        set_print_templates_for_item_table(doc, settings)
        set_print_templates_for_taxes(doc, settings)

    except Exception as e:
        frappe.log_error(f"Safe before_print failed: {e}", "safe_before_print_patch")
