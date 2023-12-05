from .bcfs import Context, Block, Collect, Follow, Select, Bcfs

from dataclasses import dataclass
from parsel import Selector
from aiohttp import ClientSession, TCPConnector
from json import JSONDecodeError
from lxml import etree
from yarl import URL

from parsimonious.grammar import Grammar
from parsimonious.nodes import NodeVisitor

import dicttoxml
import parsel
import json
import sys
import re

grammar = Grammar(
    r"""
    script = commands{1}
    commands = ws_commands ws
    ws_commands = ws_command*
    ws_command = ws command
    command = block / collect / follow / select
    block = ws '{' commands '}' ws
    collect = ';'
    follow = '->'
    select = xpath_select / css_select
    xpath_select = '`' xpath '`'
    xpath = (escaped_backtick / ~'[^`]')*
    escaped_backtick = '\\`'
    css_select = (!terminal ~'.')+
    terminal = '->' / ~'[{};`]'
    ws = ~'\s*'
    """
)


class Visitor(NodeVisitor):
    def visit_script(self, node, visited_children):
        return Block(visited_children[0])

    def visit_commands(self, node, visited_children):
        return visited_children[0]

    def visit_ws_commands(self, node, visited_children):
        return visited_children

    def visit_ws_command(self, node, visited_children):
        return visited_children[1]

    def visit_command(self, node, visited_children):
        return visited_children[0]

    def visit_block(self, node, visited_children):
        return Block(visited_children[2])

    def visit_collect(self, node, visited_children):
        return Collect()

    def visit_follow(self, node, visited_children):
        return Follow()

    def visit_select(self, node, visited_children):
        return visited_children[0]

    def visit_xpath_select(self, node, visited_children):
        return visited_children[1]

    def visit_xpath(self, node, visited_children):
        return XpathSelect(node.text)

    def visit_escaped_backtick(self, node, visited_children):
        return "`"

    def visit_css_select(self, node, visited_children):
        return CssSelect(node.text)

    def generic_visit(self, node, visited_children):
        return None


def parse(code):
    tree = grammar.parse(code)

    visitor = Visitor()
    return visitor.visit(tree)


@dataclass
class XpathSelect(Select):
    def select(self, text):
        def string_join(context, nodeset, sep=""):
            return sep.join(
                map(lambda n: n if isinstance(n, str) else n.text_content(), nodeset)
            )

        def split(context, nodeset, length):
            chunks = []

            for i in range(0, len(nodeset), int(length)):
                chunk_node = etree.Element("chunk")

                for node in nodeset[i : i + int(length)]:
                    chunk_node.append(node)

                chunks.append(chunk_node)

            return chunks

        parsel.xpathfuncs.set_xpathfunc("string-join", string_join)
        parsel.xpathfuncs.set_xpathfunc("split", split)

        result = Selector(text).xpath(self.query).getall()

        parsel.xpathfuncs.set_xpathfunc("string-join", None)
        parsel.xpathfuncs.set_xpathfunc("split", None)

        return result


@dataclass
class CssSelect(Select):
    def select(self, text):
        query = re.sub(r"(^|(?<=[^\\]))!", ":not(*)", self.query)
        return Selector(text).css(query).getall()


class Skrob(Bcfs):
    def __init__(self, code, output_stream=sys.stdout, follow_stream=sys.stderr):
        if isinstance(code, str):
            code = parse(code)

        super().__init__(code)

        self._output_stream = output_stream
        self._follow_stream = follow_stream

    async def run(self, args, **kwargs):
        async with ClientSession(connector=TCPConnector(**kwargs)) as session:
            # Convenience special handling in case we get input from stdin.
            if isinstance(args, list):

                async def get_contexts():
                    return list(map(lambda url: Context(url, url), args))

                self._visited_locators = set()
                initial = await self._follow_contexts(session, get_contexts())
            elif isinstance(args, str):
                initial = [Context("", args)]
            else:
                raise ValueError

            return await self._run_with_session(session, initial)

    def print(self, text):
        self._output_stream.write(text + "\n")

    async def follow(self, session, url):
        self._follow_stream.write(url + "\n")

        async with session.get(url) as response:
            text = await response.text()

            try:
                text = dicttoxml.dicttoxml(json.loads(text), return_bytes=False)
            except JSONDecodeError:
                pass

            return Context(url, text)

    def join(self, base, url):
        return str(URL(base).join(URL(url)))
