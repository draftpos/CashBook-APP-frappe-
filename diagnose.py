import frappe

def run():
    print('--- GL Entry custom_type distinct values ---')
    print(frappe.db.sql('SELECT DISTINCT custom_type, COUNT(*) FROM \	abGL Entry\ GROUP BY custom_type', as_dict=1))
    
    print('--- Account custom_cost_type distinct values ---')
    print(frappe.db.sql('SELECT DISTINCT custom_cost_type, COUNT(*) FROM \	abAccount\ GROUP BY custom_cost_type', as_dict=1))

    print('--- Expense Accounts in Chart of Accounts ---')
    print(frappe.db.sql('SELECT name, account_name, root_type, custom_cost_type FROM \	abAccount\ WHERE root_type=" Expense LIMIT
