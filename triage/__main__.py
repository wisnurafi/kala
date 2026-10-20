"""Allow `python3 -m triage <crash-dir> ...` as the triage CLI."""

from .cli import main

if __name__ == "__main__":
    raise SystemExit(main())
