import frappe
from erpnext.setup.utils import get_exchange_rate

def inspect():
    frappe.connect()
    company = frappe.db.get_single_value("Global Defaults", "default_company") or frappe.get_all("Company", limit=1)[0].name
    company_currency = frappe.get_cached_value("Company", company, "default_currency")
    print(f"Company: {company}")
    print(f"Company Currency: {company_currency}")
    
    currencies = ["USD", "ZWG"]
    for c1 in currencies:
        for c2 in currencies:
            if c1 != c2:
                try:
                    rate = get_exchange_rate(c1, c2)
                    print(f"Rate {c1} -> {c2}: {rate}")
                except Exception as e:
                    print(f"Rate {c1} -> {c2}: Error {e}")

if __name__ == "__main__":
    inspect()
