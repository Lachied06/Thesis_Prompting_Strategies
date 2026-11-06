from __future__ import annotations

import argparse
from pathlib import Path

from src.audit import apply_audit, create_audit_rows, write_audit_csv


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Create and apply a pre-run benchmark quality audit"
    )
    subparsers = parser.add_subparsers(dest="command", required=True)

    create = subparsers.add_parser("create", help="Create a blind audit CSV")
    create.add_argument("--data", required=True)
    create.add_argument("--output", required=True)
    create.add_argument("--overwrite", action="store_true")

    apply = subparsers.add_parser("apply", help="Create an approved dataset from completed audit decisions")
    apply.add_argument("--data", required=True)
    apply.add_argument("--audit", required=True)
    apply.add_argument("--output", required=True)
    apply.add_argument("--overwrite", action="store_true")
    return parser


def main() -> None:
    args = build_parser().parse_args()
    if args.command == "create":
        count = write_audit_csv(
            args.output,
            create_audit_rows(args.data),
            overwrite=args.overwrite,
        )
        print(f"Audit template written to {Path(args.output)} ({count} tasks)")
        print("Complete every yes/no review field before applying the audit.")
        return

    manifest = apply_audit(
        args.data,
        args.audit,
        args.output,
        overwrite=args.overwrite,
    )
    print(f"Approved dataset written to {Path(args.output)}")
    print(
        f"Included {manifest['included_tasks']} of {manifest['total_tasks']} tasks; "
        f"excluded {manifest['excluded_tasks']}."
    )


if __name__ == "__main__":
    main()
