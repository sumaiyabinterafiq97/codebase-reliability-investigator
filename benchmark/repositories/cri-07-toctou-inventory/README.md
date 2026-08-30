# cri-07-toctou-inventory

`reserve` checks stock then writes without a lock. `two_customers` runs concurrent reserves on one unit.
