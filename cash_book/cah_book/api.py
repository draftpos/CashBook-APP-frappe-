import frappe

def find_suspicious_journal_entries():
    """
    Returns a list of Journal Entries where the same account
    appears in both Debit and Credit lines in the same JE.
    """
    suspicious_report = []

    # Get all submitted JEs
    journal_entries = frappe.get_all("Journal Entry", filters={"docstatus": 1}, fields=["name"])

    for je in journal_entries:
        rows = frappe.get_all(
            "Journal Entry Account",
            filters={"parent": je.name},
            fields=["account", "debit", "credit", "name"]
        )

        # Track accounts in debit and credit
        debit_accounts = set()
        credit_accounts = set()

        for row in rows:
            if float(row["debit"]) > 0:
                debit_accounts.add(row["account"])
            if float(row["credit"]) > 0:
                credit_accounts.add(row["account"])

        # Find accounts appearing in both debit and credit
        common_accounts = debit_accounts.intersection(credit_accounts)

        if common_accounts:
            # Add info for each offending account
            for acc in common_accounts:
                offending_rows = [r for r in rows if r["account"] == acc]
                suspicious_report.append({
                    "journal_entry": je.name,
                    "account": acc,
                    "rows": offending_rows
                })

    return suspicious_report

def store_bad_journals(bad_journal, bad_account):
    """
    Takes lists of bad_journal IDs and bad_account names,
    and stores them in bad_journal DocType.
    Only inserts non-empty values.
    """
    records_inserted = 0

    for je_id, account in zip(bad_journal, bad_account):
        # Skip empty values
        if not je_id or not account:
            continue

        doc = frappe.get_doc({
            "doctype": "bad_journal",
            "bad_journal": je_id,
            "bad_account": account
        })
        doc.insert(ignore_permissions=True)
        records_inserted += 1

    frappe.db.commit()
    print(f"Stored {records_inserted} records in bad_journal")

def test():
    suspicious_entries = find_suspicious_journal_entries()
    bad_journal = []
    bad_account = []

    for entry in suspicious_entries:
        print(f"JE {entry['journal_entry']} has same account on both Debit and Credit: {entry['account']}")
        for r in entry['rows']:
            print(f"    Row {r['name']} → Account: {r['account']} | Debit: {r['debit']} / Credit: {r['credit']}")
        
        if entry['journal_entry'] and entry['account']:
            bad_journal.append(entry['journal_entry'])
            bad_account.append(entry['account'])

    store_bad_journals(bad_journal, bad_account)

def set_gl_entry_type(doc, method=None):
    """
    Hook on GL Entry before_insert:
    Populates custom_type on GL Entry from Journal Entry Account or Account master.
    """
    try:
        if getattr(doc, "custom_type", None):
            return

        # 1. If voucher is Journal Entry, look up from Journal Entry Account row
        if doc.voucher_type == "Journal Entry" and doc.voucher_no:
            has_jea_custom_type = frappe.db.has_column("Journal Entry Account", "custom_type")
            has_jea_type = frappe.db.has_column("Journal Entry Account", "type")
            
            field_to_get = "custom_type" if has_jea_custom_type else ("type" if has_jea_type else None)
            if field_to_get:
                # Try exact match on account + debit/credit
                matched_rows = frappe.db.sql(f"""
                    SELECT {field_to_get} as ctype
                    FROM `tabJournal Entry Account`
                    WHERE parent = %s
                      AND account = %s
                      AND (ABS(debit - %s) < 0.001 OR ABS(credit - %s) < 0.001)
                      AND {field_to_get} IS NOT NULL
                      AND {field_to_get} != ''
                    LIMIT 1
                """, (doc.voucher_no, doc.account, doc.debit or 0, doc.credit or 0), as_dict=1)

                if matched_rows and matched_rows[0].get("ctype"):
                    doc.custom_type = matched_rows[0].get("ctype")
                    return

                # Try broader match on account alone
                matched_rows = frappe.db.sql(f"""
                    SELECT {field_to_get} as ctype
                    FROM `tabJournal Entry Account`
                    WHERE parent = %s
                      AND account = %s
                      AND {field_to_get} IS NOT NULL
                      AND {field_to_get} != ''
                    LIMIT 1
                """, (doc.voucher_no, doc.account), as_dict=1)

                if matched_rows and matched_rows[0].get("ctype"):
                    doc.custom_type = matched_rows[0].get("ctype")
                    return

            # Check if Journal Entry was created from Cash Book Entry
            cbe_ref = frappe.db.get_value("Journal Entry", doc.voucher_no, "custom_cashbook_entry_ref")
            if cbe_ref:
                cba_row = frappe.db.sql("""
                    SELECT type
                    FROM `tabCash Book Account`
                    WHERE parent = %s
                      AND account = %s
                      AND type IS NOT NULL
                      AND type != ''
                    LIMIT 1
                """, (cbe_ref, doc.account), as_dict=1)
                if cba_row and cba_row[0].get("type"):
                    doc.custom_type = cba_row[0].get("type")
                    return

        # 2. Fallback: Fetch default Cost Type from Account master
        if doc.account and frappe.db.has_column("Account", "custom_cost_type"):
            cost_type = frappe.db.get_value("Account", doc.account, "custom_cost_type")
            if cost_type:
                doc.custom_type = cost_type
    except Exception as e:
        frappe.log_error(f"Error in set_gl_entry_type: {str(e)}", "Cash Book GL Entry Hook")
