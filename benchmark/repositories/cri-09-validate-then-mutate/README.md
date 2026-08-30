# cri-09-validate-then-mutate

`parse_line` rejects only empty strings, then `split(":")` / `int` on the derived parts (missing colon, extra colons, non-int qty).
