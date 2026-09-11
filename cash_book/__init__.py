__version__ = "0.0.1"

# Automatically apply General Ledger enhancements
try:
    from cash_book.cah_book.report_overrides import apply_gl_report_enhancements
    apply_gl_report_enhancements()
except Exception:
    pass
