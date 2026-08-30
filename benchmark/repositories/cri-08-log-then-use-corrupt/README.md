# cri-08-log-then-use-corrupt

`parse_customer` logs parse failures but returns the original `raw` dict. `debit` still subtracts from it.
