import asyncio
import parsel
from dataclasses import dataclass
from abc import ABC, abstractmethod

@dataclass
class Context:
    locator: str
    text: str

@dataclass
class Block:
    commands: list

@dataclass
class Collect:
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

        await self._block(session, self._follow_texts(session, get_contexts()), self._code)

    async def _block(self, session, get_contexts, block):
        tasks = []

        for context in await get_contexts:
            async def get_context(context):
                return [context]

            get_contexts = None

            for command in block.commands:
                if isinstance(command, Block):
                    get_contexts = self._block(session, get_contexts or get_context(context), command)
                elif isinstance(command, Collect):
                    tasks.append(asyncio.create_task(self._output_texts(get_contexts or
                                                                        get_context(context))))
                    get_contexts = None
                elif isinstance(command, Follow):
                    get_contexts = self._follow_texts(session, get_contexts or get_context(context))
                elif isinstance(command, Select):
                    get_contexts = self._select_texts(get_contexts or get_context(context), command)
                else:
                    raise

            if get_contexts:
                tasks.append(asyncio.create_task(self._mux_block_result(self._block(session,
                                                                                        get_contexts,
                                                                                        block),
                                                                        context)))

        return list(filter(None, parsel.utils.flatten(await asyncio.gather(*tasks))))

    async def _mux_block_result(self, block, context):
        if block_result := await block:
            return block_result

        return context

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
