"""Code generator. Examples:

    python -m tools.scaffold feature order --fields "title:str amount:int note:str?" [--events]
    python -m tools.scaffold worker cleanup --interval 60
    python -m tools.scaffold consumer order_paid --broker rabbitmq --fields "order_id:str amount:int"
    python -m tools.scaffold migration add_status_to_orders

Field types: str, int, float, bool, datetime, date; `?` makes a field optional.
Nothing is written if any target file already exists or a container marker is missing.
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from tools.scaffold import generators
from tools.scaffold.naming import ScaffoldError
from tools.scaffold.project import Plan


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="python -m tools.scaffold", description=__doc__)
    parser.add_argument("--root", type=Path, default=Path.cwd(), help="project root (default: current directory)")
    commands = parser.add_subparsers(dest="command", required=True)

    feature = commands.add_parser("feature", help="CRUD feature through all layers")
    feature.add_argument("name", help="singular snake_case name, e.g. order or order_item")
    feature.add_argument("--fields", default="", help='e.g. "title:str amount:int note:str?" (default: name:str)')
    feature.add_argument("--plural", default=None, help="table/URL plural if the default is wrong")
    feature.add_argument("--events", action="store_true", help="publish created/updated/deleted via the outbox")

    worker = commands.add_parser("worker", help="periodic background worker + its service")
    worker.add_argument("name")
    worker.add_argument("--interval", type=float, default=60, help="seconds between runs")

    consumer = commands.add_parser("consumer", help="idempotent message consumer")
    consumer.add_argument("name", help="event name, e.g. order_paid")
    consumer.add_argument("--broker", choices=generators.BROKERS, default="rabbitmq")
    consumer.add_argument("--fields", default="", help='message fields, e.g. "order_id:str amount:int"')
    consumer.add_argument("--destination", default=None, help="RabbitMQ exchange / Kafka topic")
    consumer.add_argument("--routing-key", default=None, help="default: name with dots (order.paid)")
    consumer.add_argument("--queue", default=None, help="RabbitMQ queue / Kafka consumer group")

    migration = commands.add_parser("migration", help="empty numbered yoyo migration")
    migration.add_argument("name", help="snake_case description, e.g. add_status_to_orders")
    return parser


def _plan(args: argparse.Namespace) -> Plan:
    root: Path = args.root.resolve()
    if args.command == "feature":
        return generators.feature(root, args.name, args.fields, args.plural, args.events)
    if args.command == "worker":
        return generators.worker(root, args.name, args.interval)
    if args.command == "consumer":
        return generators.consumer(
            root, args.name, args.broker, args.fields, args.destination, args.routing_key, args.queue
        )
    return generators.migration(root, args.name)


def main(argv: list[str] | None = None) -> int:
    args = _parser().parse_args(argv)
    try:
        touched = _plan(args).apply()
    except ScaffoldError as exc:
        sys.stderr.write(f"error: {exc}\n")
        return 1
    sys.stdout.write("Created / updated:\n" + "".join(f"  {path}\n" for path in touched))
    sys.stdout.write("Next: fill in the TODOs, then `make check` (and `make migrate` if a migration was added).\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
