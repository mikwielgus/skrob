import asyncio
import parsel
from dataclasses import dataclass
from abc import ABC, abstractmethod
from typing import List

@dataclass
class Context:
    locator: str
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
class Select(ABC):
    query: str

    @abstractmethod
    def select(self, text):
        raise NotImplementedError

@dataclass
class RunBlock:
    statements: List[str]

class SkrobCore(ABC):
    def __init__(self, code):
        self._code = code

    @abstractmethod
    async def run(self, start):
        raise NotImplementedError

    async def run_with_session(self, session, start_context):
        self._visited_locators = set()

        async def get_contexts():
            return [start_context]

        await self._run_block(session, self._follow_texts(session, get_contexts()), self._code)

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
                    get_contexts = self._follow_texts(session, get_contexts or get_context(context))
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

    async def _follow_texts(self, session, get_contexts):
        contexts = []

        for context in await get_contexts:
            locator = self.join(context.locator, context.text)

            if locator in self._visited_locators:
                continue

            self._visited_locators.add(locator)
            contexts.append(await self.follow(session, locator))

        return contexts

    @abstractmethod
    async def follow(self, session, locator):
        raise NotImplementedError

    @abstractmethod
    async def join(self, base, locator):
        raise NotImplementedError

    async def _select_texts(self, get_contexts, selector):
        contexts = []

        for context in await get_contexts:
            for selectee in selector.select(context.text):
                contexts.append(Context(context.locator, selectee))

        return contexts
