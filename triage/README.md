# Triage toolkit (Phase 2)

Python pipeline that turns a directory of raw crashes into a report:

```
ingest -> dedup (ASan stack hash) -> minimize -> classify -> report.html
```

Planned CLI:

```sh
kala triage ./crashes --target bmp_parser
```

Not implemented in Phase 0. Phase 1 crashes are triaged manually; this
toolkit is validated in Phase 2 against the Phase 1 answer key (L2:
50 raw crashes -> at most 5 clean groups, classification at least 80%
correct, idempotent output).
