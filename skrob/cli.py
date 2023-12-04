from skrob import Skrob
from argparse import ArgumentParser
from aiohttp import TCPConnector
import importlib.metadata
import asyncio
import sys


def main():
    run(sys.argv, sys.stdout)


def run(argv, stream):
    parser = build_parser()
    args = parser.parse_args(argv[1:])

    skrob = Skrob(args.code, stream)
    asyncio.run(
        skrob.run(
            args.url or sys.stdin.read(),
            limit=args.max_connections,
            limit_per_host=args.max_connections_per_host,
        )
    )


def build_parser():
    parser = ArgumentParser(add_help=False)

    parser.add_argument("code", metavar="CODE")
    parser.add_argument("url", metavar="URL", nargs="*")

    parser.add_argument(
        "--help",
        action="help",
        help="Show this help message and exit",
    )
    parser.add_argument(
        "--version",
        action="version",
        version=importlib.metadata.version(__package__ or __name__),
        help="Print program version and exit",
    )
    parser.add_argument(
        "-N",
        "--max-connections",
        metavar="N",
        dest="max_connections",
        default="100",
        type=int,
        help="Maximum number of simultaneous connections (default: %(default)s)",
    )
    parser.add_argument(
        "-n",
        "--max-connections-per-host",
        metavar="N",
        dest="max_connections_per_host",
        default="4",
        type=int,
        help="Maximum number of simultaneous connections to the same endpoint (default: %(default)s)",
    )

    return parser
