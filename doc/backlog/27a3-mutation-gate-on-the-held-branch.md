Task 27a3: the mutation gate on the held branch.

Runs on `task/27a-qa-round-3-inputs`, which now holds tasks 27a and 27a2: reviewed and
approved, lint, tests and the comment gate green. `make mutate` fails on it, and the
run of 27a2 had no repair pass left (run `01M82GCRE3JK`, three reviews). This task
changes tests and `mutation-equivalents.txt` only. A mutant that survives because the
code has a branch nobody needs is a finding: name it in the review under "Later", do
not delete product code here.

`scripts/mutation_survivors.py` on that branch reports:

```
stale entry in mutation-equivalents.txt: scheduling.domain.fhir_search.x_parse_search__mutmut_98
stale entry in mutation-equivalents.txt: scheduling.domain.fhir_search.x_parse_search__mutmut_134
unlisted survivor: scheduling.domain.fhir_search.x_parse_search__mutmut_96
unlisted survivor: scheduling.domain.fhir_search.x_parse_search__mutmut_132
unlisted survivor: scheduling.domain.time_off_rules.x_time_off_failures__mutmut_16
unlisted survivor: scheduling.domain.time_off_rules.x_time_off_failures__mutmut_22
unlisted survivor: scheduling.domain.time_off_rules.x_time_off_failures__mutmut_23
unlisted survivor: scheduling.domain.record_fields.x_check_code__mutmut_5
unlisted survivor: scheduling.domain.record_fields.x_check_code__mutmut_17
unlisted survivor: scheduling.domain.fhir_role_write.x_role_values__mutmut_98
unlisted survivor: scheduling.domain.fhir_role_write.x_role_values__mutmut_99
unlisted survivor: scheduling.domain.fhir_role_write.x_role_values__mutmut_103 to 107, 109 to 111
```

1. Run `make mutate` first and work from what it prints now, not from this list.
2. Each survivor is killed by a test of the domain module it lives in, written from
   what the function promises (`returns_X_when_Y`), or it is equivalent and
   `mutation-equivalents.txt` says why in one line. The two `parse_search` survivors
   stand where two listed entries stood before the function gained lines: check that
   they are the same mutants before moving the entries, and say so.
3. The nine survivors in `fhir_role_write.role_values` come with item 7 of task 27a2
   (the type of an extension's value): the rule has no test of its own in the domain
   layer. Give it one for every extension of the declaration: the declared type
   accepted, each other `value[x]` refused naming the element.
4. `make mutate` passes; a mutant no longer listed has no entry left in
   `mutation-equivalents.txt`.

Done when `make setup && make lint && make test && make gate && make mutate` and
`make fhir-validate` pass from a fresh clone.
