"""`python -m vilvik` / `vilvik` CLI entry point."""
from __future__ import annotations

import argparse
import sys

from vilvik._http import DEFAULT_BASE_URL
from vilvik.login import login
from vilvik.exceptions import VilvikError


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(prog="vilvik")
    sub = parser.add_subparsers(dest="command")
    p_login = sub.add_parser("login", help="Authorize this machine via your browser.")
    p_login.add_argument("--base-url", default=DEFAULT_BASE_URL)
    p_login.add_argument("--no-browser", action="store_true")
    args = parser.parse_args(argv)
    if args.command == "login":
        try:
            login(base_url=args.base_url, open_browser=not args.no_browser)
        except VilvikError as exc:
            print(f"login failed: {exc}", file=sys.stderr)
            return 1
        return 0
    parser.print_help()
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
