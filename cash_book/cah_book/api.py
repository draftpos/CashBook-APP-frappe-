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
    # 1️⃣ Function to store bad JEs/accounts safely
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


# 2️⃣ Test function
def test():
    suspicious_entries = find_suspicious_journal_entries()
    
    bad_journal = []
    bad_account = []

    for entry in suspicious_entries:
        print(f"JE {entry['journal_entry']} has same account on both Debit and Credit: {entry['account']}")
        for r in entry['rows']:
            print(f"    Row {r['name']} → Account: {r['account']} | Debit: {r['debit']} / Credit: {r['credit']}")
        
        # Add to lists only if values exist
        if entry['journal_entry'] and entry['account']:
            bad_journal.append(entry['journal_entry'])
            bad_account.append(entry['account'])

    # Call the store function
    store_bad_journals(bad_journal, bad_account)
