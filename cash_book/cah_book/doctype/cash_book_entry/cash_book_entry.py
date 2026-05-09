import frappe
import json
from frappe.model.document import Document
from frappe.utils import getdate, flt

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
            if row.get("account") == self.account:
                missing_child_fields.append(f"Child account cannot be same as parent account ({self.account})")
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
    #     reference_date = self.get("reference_date").
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
        name=self.name
        print(f"Cash Book Entry Name: {name}")
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
                    remarks=f"Generated from Cash Book Entry {self.name}",
                    custom_cashbook_entry_ref=name,
                    cost_center=self.get("cost_center"),
                    project=self.get("project")
                )

            frappe.db.commit()
            frappe.msgprint("✅ All journals created successfully!")

        except Exception as e:
            frappe.db.rollback(save_point="before_cashbook_submit")
            frappe.throw(f"❌ Journal creation failed: {str(e)}. Cash Book not submitted.")

@frappe.whitelist()
def create_custom_journal_entry(company, account_type, main_account, posting_date, accounts, custom_cashbook_entry_ref, reference=None, reference_date=None, remarks=None, cost_center=None, project=None):
    from erpnext.setup.utils import get_exchange_rate
    
    # Detect if multi-currency is needed
    company_currency = frappe.get_cached_value("Company", company, "default_currency")
    main_acc_currency = frappe.get_cached_value("Account", main_account, "account_currency") or company_currency
    
    involved_currencies = {company_currency, main_acc_currency}
    for acc in accounts:
        acc_currency = frappe.get_cached_value("Account", acc.get("account"), "account_currency") or company_currency
        involved_currencies.add(acc_currency)
    
    # Create new Journal Entry document
    je = frappe.new_doc("Journal Entry")
    je.voucher_type = account_type
    je.company = company
    je.posting_date = getdate(posting_date)
    je.cheque_no = reference
    je.cheque_date = getdate(reference_date)
    je.remarks = remarks
    je.custom_cashbook_entry_ref = custom_cashbook_entry_ref
    
    # If multiple currencies are involved, enable multi_currency
    if len(involved_currencies) > 1:
        je.multi_currency = 1

    # Get exchange rate for the main account (Cash Book account)
    main_exchange_rate = 1.0
    if main_acc_currency != company_currency:
        main_exchange_rate = get_exchange_rate(main_acc_currency, company_currency, posting_date) or 1.0
        
    # Add accounts to the Journal Entry
    for acc in accounts:
        acc_name = acc.get("account")
        acc_currency = frappe.get_cached_value("Account", acc_name, "account_currency") or company_currency
        
        # Amounts entered in the Cash Book are in the Main Account's currency
        input_debit = flt(acc.get("debit"))
        input_credit = flt(acc.get("credit"))
        
        # Calculate base currency amounts
        base_debit = flt(input_debit * main_exchange_rate)
        base_credit = flt(input_credit * main_exchange_rate)
        
        # Get exchange rate for child account
        child_exchange_rate = 1.0
        if acc_currency != company_currency:
            child_exchange_rate = get_exchange_rate(acc_currency, company_currency, posting_date) or 1.0
            
        # Determine child account amounts in its own currency
        debit_in_account_currency = flt(base_debit / child_exchange_rate) if child_exchange_rate else base_debit
        credit_in_account_currency = flt(base_credit / child_exchange_rate) if child_exchange_rate else base_credit
        
        # Child account row
        je.append("accounts", {
            "account": acc_name,
            "debit_in_account_currency": debit_in_account_currency,
            "credit_in_account_currency": credit_in_account_currency,
            "debit": base_debit,
            "credit": base_credit,
            "exchange_rate": child_exchange_rate,
            "party_type": acc.get("party_type"),
            "party": acc.get("party"),
            "reference_": acc.get("reference"),
            "user_remark": acc.get("user_remark"),
            "account_currency": acc_currency,
            "cost_center": cost_center,
            "project": project
        })

        # Offsetting row (Main account)
        if input_debit > 0:
            je.append("accounts", {
                "account": main_account,
                "credit_in_account_currency": input_debit,
                "credit": base_debit,
                "exchange_rate": main_exchange_rate,
                "account_currency": main_acc_currency,
                "cost_center": cost_center,
                "project": project
            })
        elif input_credit > 0:
            je.append("accounts", {
                "account": main_account,
                "debit_in_account_currency": input_credit,
                "debit": base_credit,
                "exchange_rate": main_exchange_rate,
                "account_currency": main_acc_currency,
                "cost_center": cost_center,
                "project": project
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






