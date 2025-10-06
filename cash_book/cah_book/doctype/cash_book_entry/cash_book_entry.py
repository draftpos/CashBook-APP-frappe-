import frappe
import json
from frappe.model.document import Document
from frappe.utils import getdate

class CashBookEntry(Document):
    def before_save(self):
        # ✅ Required main fields
        required_fields = [
            "company",
            "account",
            "account_type",
            "reference_date",
            "reference"
        ]
        missing_main = [field for field in required_fields if not self.get(field)]
        # ✅ Validate child table
        child_table_name = "accounting_entries"
        if not self.get(child_table_name):
            frappe.throw("Please add at least one row in 'Cash Book Account' before saving.")
        missing_child_rows = []
        for idx, row in enumerate(self.get(child_table_name), start=1):
            required_child_fields = ["party_type", "party"]
            missing_child_fields = []

            debit = row.get("debit")
            credit = row.get("credit")
            # Must have one of the two
            if not debit and not credit:
                missing_child_fields.append("Missing Debit or Credit")
            # Cannot have both at once
            if debit and credit:
                missing_child_fields.append("only one of Debit or Credit (not both)")
            if missing_child_fields:
                missing_child_rows.append(f"Row {idx}: {', '.join(missing_child_fields)}")
        # ✅ Throw if anything missing
        if missing_main or missing_child_rows:
            msg = ""
            if missing_main:
                msg += f"<b>Missing in main form:</b> {', '.join(missing_main)}<br>"
            if missing_child_rows:
                msg += "<b>Issues in child table:</b><br>" + "<br>".join(missing_child_rows)
            frappe.throw(msg)

    # def on_submit(self):
    #    # -------------------
    #     # After save: create Journal Entry --------------------------------------------------------------------------------
    #     # -------------------
    #     company = self.get("company")
    #     reference_date = self.get("reference_date")
    #     reference = self.get("reference")
    #     series = self.get("series")
    #     main_account = self.get("account")
    #     print(f"acount after save -----------------{main_account}")

    #     # Prepare accounts from child table
    #     accounts = []

    #     for row in self.get("accounting_entries") or []:
    #         accounts.append({
    #             "account": row.get("account"),
    #             "debit": row.get("debit") or 0,
    #             "credit": row.get("credit") or 0,
    #             "party_type": row.get("party_type"),
    #             "party": row.get("party"),
    #             "reference":row.get("reference"),
    #             "user_remark" :row.get("remarks")
    #         })

    #         print(f"-----------------remarks here --------------{row.get("remarks")}")

    #     # Call your custom Journal Entry function
    #     try:
    #         result = create_custom_journal_entry(
    #             company=company,
    #             main_account=main_account,
    #             posting_date=str(reference_date),
    #             accounts=accounts,
    #             reference=reference,
    #             remarks=f"Auto-created from Cash Book Entry {series}"
    #         )
    #         print(result)
    #         frappe.msgprint(f"<b>{result}</b>")
    #     except Exception as e:
    #         frappe.throw(f"Error creating Journal Entry: {str(e)}")



# ---------------------------------------------custom logic to test
    def on_submit(self):
           # After save: create Journal Entry --------------------------------------------------------------------------------
    #     # -------------------
        series = self.get("series")
        frappe.db.savepoint("before_cashbook_submit")
        try:
            # Group child rows by post_date
            grouped_entries = {}
            for row in self.accounting_entries:
                grouped_entries.setdefault(row.post_date, []).append(row)

            # Create journals for each date
            for date, rows in grouped_entries.items():
                accounts = []
                for row in rows:
                    accounts.append({
                        "account": row.account,
                        "debit": row.debit or 0,
                        "credit": row.credit or 0,
                        "party_type": row.party_type,
                        "party": row.party,
                        "reference":row.get("reference"),
                        "user_remark" :row.get("remarks")
        
                    })
                create_custom_journal_entry(
                    company=self.company,
                    account_type=self.account_type,
                    main_account=self.account,
                    posting_date=date,
                    accounts=accounts,
                    reference=self.reference,
                    reference_date=self.reference_date,
                    remarks=f"Generated from Cash Book Entry {self.name}"
                )

            frappe.db.commit()
            frappe.msgprint("✅ All journals created successfully!")

        except Exception as e:
            frappe.db.rollback(save_point="before_cashbook_submit")
            frappe.throw(f"❌ Journal creation failed: {str(e)}. Cash Book not submitted.")

@frappe.whitelist()
def create_custom_journal_entry(company,account_type,main_account, posting_date, accounts, reference=None,reference_date=None, remarks=None):
    # Create new Journal Entry document
    je = frappe.new_doc("Journal Entry")
    je.voucher_type = account_type
    je.company = company
    je.posting_date = getdate(posting_date)
    je.cheque_no = reference
    je.cheque_date= getdate(reference_date)
    je.remarks = remarks

    print(f"---------------------------main account-----------{main_account}")
    # Add accounts to the Journal Entry
    for acc in accounts:
        je.append("accounts", {
            "account": acc.get("account"),
            "debit_in_account_currency": acc.get("debit") or 0,
            "credit_in_account_currency": acc.get("credit") or 0,
            "party_type": acc.get("party_type"),
            "party": acc.get("reference"),
            "party": acc.get("party"),
            "reference_": acc.get("reference"),
            "user_remark" :acc.get("user_remark")
        })

        print(f"the final either debit or credit----------------debit--{acc.get("debit")} and credit {acc.get("credit")}")
        if acc.get("debit") == 0:

            je.append("accounts", {
            "account":main_account,
            "debit_in_account_currency": acc.get("credit"),
            })
           
        else:
            je.append("accounts", {
            "account":main_account,
            "credit_in_account_currency": acc.get("debit"),
            })
    # Save and submit the Journal Entry
    je.save()
    je.submit()
    return f"Journal Entry {je.name} created successfully!"

def get_account_query(doctype, txt, searchfield, start, page_len, filters):
    print("Custom get_account_query called!-------------------------------------")
    company = filters.get("company")
    return frappe.db.sql("""
        SELECT name
        FROM `tabAccount`
        WHERE account_type IN ('Bank', 'Cash')
          AND is_group = 0
          AND disabled = 0
          AND company = %s
          AND {key} LIKE %s
        ORDER BY name
        LIMIT %s OFFSET %s
    """.format(key=searchfield),
    (company, "%%%s%%" % txt, page_len, start))






