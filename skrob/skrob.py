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
        def node_join(context, nodeset):
            if len(nodeset) == 1:
                return nodeset[0]

            joined_node = etree.Element("joined")

            for node in nodeset:
                joined_node.append(node)

            return joined_node

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

        def url_parse(context, nodeset):
            url = URL(string_join(context, nodeset))
            url_node = etree.Element("url")

            scheme_node = etree.SubElement(url_node, "scheme")
            scheme_node.text = str(url.scheme or "")

            user_node = etree.SubElement(url_node, "user")
            user_node.text = url.user or None

            password_node = etree.SubElement(url_node, "password")
            password_node.text = url.password or None

            host_node = etree.SubElement(url_node, "host")
            host_node.text = str(url.host or "")

            port_node = etree.SubElement(url_node, "port")
            port_node.text = url.explicit_port or None

            path_node = etree.SubElement(url_node, "path")
            path_node.text = str(url.path or "")

            query_node = etree.SubElement(url_node, "query")

            for key, value in url.query.items():
                query_subnode = etree.SubElement(query_node, key)
                query_subnode.text = value

            fragment_node = etree.SubElement(url_node, "fragment")
            fragment_node.text = url.fragment

            return url_node

        def url_unparse(context, nodeset):
            node = node_join(context, nodeset)

            scheme_node = node.find("scheme")
            scheme = scheme_node.text if scheme_node is not None else ""

            user_node = node.find("user")
            user = user_node.text if user_node is not None else None

            password_node = node.find("password")
            password = password_node.text if password_node is not None else None

            host_node = node.find("host")
            host = host_node.text if host_node is not None else ""

            port_node = node.find("port")
            port = port_node.text if port_node is not None else None

            path_node = node.find("path")
            path = path_node.text if path_node is not None else ""

            query = []
            if (query_node := node.find("query")) is not None:
                for query_subnode in query_node:
                    query.append((query_subnode.tag, query_subnode.text))

            fragment_node = node.find("fragment")
            fragment = fragment_node.text if fragment_node is not None else ""

            return str(
                URL.build(
                    scheme=scheme,
                    user=user,
                    password=password,
                    host=host,
                    port=port,
                    path=path,
                    query=query,
                    fragment=fragment,
                )
            )

        def url_join(context, base, url):
            return str(
                URL(string_join(context, base)).join(URL(string_join(context, url)))
            )

        parsel.xpathfuncs.set_xpathfunc("node-join", string_join)
        parsel.xpathfuncs.set_xpathfunc("string-join", string_join)
        parsel.xpathfuncs.set_xpathfunc("split", split)
        parsel.xpathfuncs.set_xpathfunc("url-parse", url_parse)
        parsel.xpathfuncs.set_xpathfunc("url-unparse", url_unparse)
        parsel.xpathfuncs.set_xpathfunc("url-join", url_join)

        result = Selector(text).xpath(self.query).getall()

        parsel.xpathfuncs.set_xpathfunc("node-join", None)
        parsel.xpathfuncs.set_xpathfunc("string-join", None)
        parsel.xpathfuncs.set_xpathfunc("split", None)
        parsel.xpathfuncs.set_xpathfunc("url-parse", None)
        parsel.xpathfuncs.set_xpathfunc("url-unparse", None)
        parsel.xpathfuncs.set_xpathfunc("url-join", None)

        return result


@dataclass
class CssSelect(Select):
    def select(self, text):
        query = re.sub(r"(^|(?<=[^\\]))!", ":not(*)", self.query)
        return Selector(text).css(query).getall()


class Skrob(Bcfs):
    def __init__(self, code, output_stream=sys.stdout, follow_stream=sys.stderr):
        if isinstance(code, str):
            self._code = parse(code)
        else:
            self._code = code

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
