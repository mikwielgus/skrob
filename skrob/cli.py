from skrob import Skrob
from argparse import ArgumentParser
from http.cookiejar import MozillaCookieJar
from aiohttp import ClientTimeout, CookieJar
from contextlib import nullcontext
import importlib.metadata
import asyncio
import sys


class SkrobCookieJar(CookieJar):
    def save(self, file_path):
        jar = MozillaCookieJar(file_path)
        for name, cookie in self._cookies.items():
            jar.set_cookie(cookie)

        jar.save()

    def load(self, file_path):
        jar = MozillaCookieJar(file_path)
        jar.load()

        for cookie in jar:
            self._cookies[cookie.name] = cookie


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
    with open_fd(3) as url_stream:
        with open_fd(4) as passforward_stream:
            run(sys.argv, sys.stdout, sys.stderr, url_stream, passforward_stream)


def open_fd(fd):
    try:
        return open(fd, "w")
    except OSError:
        return nullcontext()


def run(
    argv,
    output_stream=sys.stdout,
    log_stream=sys.stderr,
    url_stream=None,
    passforward_stream=None,
):
    parser = build_parser()
    args = parser.parse_args(argv[1:])

    log_and_url_stream = Tee(log_stream, url_stream)

    if args.get_urls:
        url_stream, output_stream = output_stream, url_stream
        log_and_url_stream = Tee(log_stream, None)
    elif args.pass_forward:
        passforward_stream, output_stream = output_stream, passforward_stream

    headers = {}

    if args.add_headers:
        for field_value in args.add_headers:
            (field, value) = field_value.split(":", maxsplit=1)
            headers[field] = value

    cookie_jar = SkrobCookieJar()

    if args.cookie_jar:
        cookie_jar.load(args.cookie_jar)

    skrob = Skrob(args.code, output_stream, log_and_url_stream)
    result = asyncio.run(
        skrob.run(
            args.url or (sys.stdin.read() if not sys.stdin.isatty() else ""),
            limit_per_host=args.max_connections_per_host,
            limit=args.max_connections,
            headers=headers,
            cookie_jar=SkrobCookieJar(),
            timeout=ClientTimeout(
                connect=args.connect_timeout, total=args.total_timeout
            ),
        )
    )

    if args.cookie_jar:
        cookie_jar.save(args.cookie_jar)

    if result and passforward_stream:
        for context in result:
            passforward_stream.write(context.text + "\n")


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

    stream_group = parser.add_mutually_exclusive_group()
    stream_group.add_argument(
        "-u",
        "--get-urls",
        dest="get_urls",
        action="store_true",
        help="Print visited URLs (supressing tem from stderr) instead of the extracted results, and write the latter to fd 3 instead. Mutually exclusive with -p (default: %(default)s)",
    )
    stream_group.add_argument(
        "-p",
        "--pass-forward",
        dest="pass_forward",
        action="store_true",
        help="Print the output of the last command instead of the extracted results, and write the latter to fd 4 instead. Mutually exclusive with -u (default: %(default)s)",
    )

    parser.add_argument(
        "-H",
        "--add-header",
        metavar="FIELD:VALUE",
        dest="add_headers",
        action="append",
        help='Specify a custom HTTP header and its value, separated by a colon ":". This option can be used multiple times',
    )
    parser.add_argument(
        "--cookie-jar",
        metavar="FILE",
        dest="cookie_jar",
        help="Netscape-formatted (aka cookies.txt) file to read cookies from and overwrite afterwards",
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
        default="300.0",
        type=float,
        help="Maximum time in seconds available for each transfer, i.e. the maximum sum of time spent on establishing connection, sending the request, and reading the response. Can be fractional, pass 0 to disable (default: %(default)s)",
    )

    return parser
