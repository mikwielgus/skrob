from skrob import Skrob
from argparse import ArgumentParser
from aiohttp import ClientTimeout
from contextlib import nullcontext
import importlib.metadata
import asyncio
import sys


class Tee:
    def __init__(self, stream1, stream2):
        self._stream1 = stream1
        self._stream2 = stream2

    def write(self, data):
        self._stream1.write(data)

        if self._stream2:
            self._stream2.write(data)

    def flush(self):
        self._stream1.flush()

        if self._stream2:
            self._stream2.flush()


def main():
    with open_fd(3) as follow_stream:
        with open_fd(4) as result_stream:
            run(sys.argv, sys.stdout, sys.stderr, follow_stream, result_stream)


def open_fd(fd):
    try:
        return open(fd, "w")
    except OSError:
        return nullcontext()


def run(
    argv,
    output_stream=sys.stdout,
    log_stream=sys.stderr,
    follow_stream=None,
    result_stream=None,
):
    parser = build_parser()
    args = parser.parse_args(argv[1:])

    log_and_follow_stream = Tee(log_stream, follow_stream)

    skrob = Skrob(args.code, output_stream, log_and_follow_stream)
    result = asyncio.run(
        skrob.run(
            args.url or sys.stdin.read(),
            limit_per_host=args.max_connections_per_host,
            limit=args.max_connections,
            timeout=ClientTimeout(
                connect=args.connect_timeout, total=args.total_timeout
            ),
        )
    )

    if result and result_stream:
        for context in result:
            result_stream.write(context.text + "\n")


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
        "-n",
        "--max-connections-per-host",
        metavar="N",
        dest="max_connections_per_host",
        default="4",
        type=int,
        help="Maximum number of simultaneous connections to the same endpoint (default: %(default)s)",
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
        "-t",
        "--connect-timeout",
        metavar="SECONDS",
        dest="connect_timeout",
        default="0.0",
        type=float,
        help="Maximum time in seconds available to establish a connection. Can be fractional, pass 0 to disable (default: %(default)s)",
    )
    parser.add_argument(
        "-T",
        "--total-timeout",
        metavar="SECONDS",
        dest="total_timeout",
        default="0.0",
        type=float,
        help="Maximum time in seconds available for each transfer, i.e. the maximum sum of time spent on establishing connection, sending the request, and reading the response. Can be fractional, pass 0 to disable (default: %(default)s)",
    )

    return parser
