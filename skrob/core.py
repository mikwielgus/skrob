import logging
import aiohttp
import asyncio
import parsel
from dataclasses import dataclass
from urllib.parse import urljoin
from typing import List

@dataclass
class Context:
    url: str
    text: str

@dataclass
class Collect:
    pass

@dataclass
class Discard:
    pass

@dataclass
class Follow:
    pass

@dataclass
class Select:
    query: str

@dataclass
class CssSelect(Select):
    def select(self, text):
        return parsel.Selector(text).css(self.query).getall()

@dataclass
class XpathSelect(Select):
    def select(self, text):
        return parsel.Selector(text).xpath(self.query).getall()

@dataclass
class RunBlock:
    statements: List[str]

class Skrob:
    def __init__(self, start_url, code):
        self._entry_url = start_url
        self._code = code
        self._visited_urls = set()

    async def run(self):
        async with aiohttp.ClientSession(connector=aiohttp.TCPConnector(limit_per_host=4)) as session:
            async def get_contexts():
                return [Context(self._entry_url, self._entry_url)]

            await self._run_block(session, self._fetch_contexts(session, get_contexts()), self._code)

    async def _run_block(self, session, get_contexts, block):
        tasks = []

        for context in await get_contexts:
            async def get_context(context):
                return [context]

            get_contexts = None

            for token in block.statements:
                if isinstance(token, Collect):
                    tasks.append(asyncio.create_task(self._output_texts(get_contexts or
                                                                        get_context(context))))
                    get_contexts = None
                elif isinstance(token, Discard):
                    tasks.append(asyncio.create_task(self._discard_texts(get_contexts or
                                                                         get_context(context))))
                    get_contexts = None
                elif isinstance(token, Follow):
                    get_contexts = self._fetch_contexts(session, get_contexts or
                                                                 get_context(context))
                elif isinstance(token, Select):
                    get_contexts = self._select_texts(get_contexts or get_context(context), token)
                elif isinstance(token, RunBlock):
                    get_contexts = self._run_block(session, get_contexts or get_context(context), token)
                else:
                    raise

            if get_contexts:
                tasks.append(asyncio.create_task(self._mux_block_result(self._run_block(session,
                                                                                        get_contexts,
                                                                                        block),
                                                                        context)))

        return list(filter(None, parsel.utils.flatten(await asyncio.gather(*tasks))))

    async def _mux_block_result(self, run_block, context):
        if block_result := await run_block:
            return block_result

        return context

    async def _discard_texts(self, get_contexts):
        await get_contexts

    async def _output_texts(self, get_contexts):
        for context in await get_contexts:
            print(context.text)

    async def _fetch_contexts(self, session, get_contexts):
        contexts = []

        for context in await get_contexts:
            url = urljoin(context.url, context.text)

            if url in self._visited_urls:
                continue

            self._visited_urls.add(url)

            async with session.get(url) as response:
                contexts.append(Context(url, await response.text()))

        return contexts

    async def _select_texts(self, get_contexts, selector):
        contexts = []

        for context in await get_contexts:
            for selectee in selector.select(context.text):
                contexts.append(Context(context.url, selectee))

        return contexts
