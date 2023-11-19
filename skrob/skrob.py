from .core import Context, Select, SkrobCore
from dataclasses import dataclass
from parsel import Selector
from aiohttp import ClientSession, TCPConnector
from urllib.parse import urljoin

@dataclass
class CssSelect(Select):
    def select(self, text):
        return Selector(text).css(self.query).getall()

@dataclass
class XpathSelect(Select):
    def select(self, text):
        return Selector(text).xpath(self.query).getall()

class Skrob(SkrobCore):
    async def run(self, start_url):
        async with ClientSession(connector=TCPConnector(limit_per_host=4)) as session:
            return await self.run_with_session(session, Context(start_url, start_url))

    async def follow(self, session, url):
        async with session.get(url) as response:
            return Context(url, await response.text())

    def join(self, base, url):
        return urljoin(base, url)
