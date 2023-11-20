from .core import Context, Block, Collect, Follow, Select, SkrobCore

from dataclasses import dataclass
from parsel import Selector
from aiohttp import ClientSession, TCPConnector
from urllib.parse import urljoin
from json import JSONDecodeError
import dicttoxml
import json

from parsimonious.grammar import Grammar
from parsimonious.nodes import NodeVisitor

grammar = Grammar(
    """
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
    xpath = ~'[^`]*'
    css_select = (!terminal ~'.')+
    terminal = ~'[{};`]' / '->'
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
        return Selector(text).xpath(self.query).getall()

@dataclass
class CssSelect(Select):
    def select(self, text):
        return Selector(text).css(self.query).getall()

class Skrob(SkrobCore):
    def __init__(self, code):
        if isinstance(code, str):
            self._code = parse(code)
        else:
            self._code = code

    async def run(self, start_url, **kwargs):
        async with ClientSession(connector=TCPConnector(**kwargs)) as session:
            return await self.run_with_session(session, Context(start_url, start_url))

    async def follow(self, session, url):
        async with session.get(url) as response:
            text = await response.text()

            try:
                text = dicttoxml.dicttoxml(json.loads(text), return_bytes=False)
            except JSONDecodeError:
                pass

            return Context(url, text)

    def join(self, base, url):
        return urljoin(base, url)
