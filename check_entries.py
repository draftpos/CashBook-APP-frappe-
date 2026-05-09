import frappe

def check_entries():
    frappe.connect()
    entries = frappe.get_all("Cash Book Entry", order_by="creation desc", limit=5, fields=["name", "account", "company"])
    for entry in entries:
        print(f"--- Cash Book Entry: {entry.name} ---")
        print(f"Account: {entry.account}")
        child_entries = frappe.get_all("Cash Book Account", filters={"parent": entry.name}, fields=["account", "debit", "credit"])
        for row in child_entries:
            print(f"  Row Account: {row.account} | Debit: {row.debit} | Credit: {row.credit}")
        
        # Find Journal Entries
        jes = frappe.get_all("Journal Entry", filters={"custom_cashbook_entry_ref": entry.name}, fields=["name", "multi_currency"])
        for je in jes:
            print(f"  Resulting Journal Entry: {je.name} (Multi-Currency: {je.multi_currency})")
            je_rows = frappe.get_all("Journal Entry Account", filters={"parent": je.name}, fields=["account", "debit", "credit", "debit_in_account_currency", "credit_in_account_currency", "exchange_rate", "account_currency"])
            for r in je_rows:
                print(f"    JE Row: {r.account} ({r.account_currency})")
                print(f"      Debit: {r.debit} | Credit: {r.credit}")
                print(f"      Debit (Acc): {r.debit_in_account_currency} | Credit (Acc): {r.credit_in_account_currency}")
                print(f"      Rate: {r.exchange_rate}")

if __name__ == "__main__":
    check_entries()
