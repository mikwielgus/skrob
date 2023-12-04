import asyncio
from dataclasses import dataclass
from abc import ABC, abstractmethod


def flatten(it):
    return list(iflatten(it))


def iflatten(it):
    for e in it:
        if hasattr(e, "__iter__") and not isinstance(e, (str, bytes)):
            yield from flatten(e)
        else:
            yield e


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


"""Abstract interpreter of the BCFS (Block-Collect-Follow-Select) abstract scripting language"""


class Bcfs(ABC):
    def __init__(self, code):
        self._code = code

    @abstractmethod
    async def run(self, *args, **kwargs):
        raise NotImplementedError

    async def _run_with_session(self, session, initial_contexts):
        self._visited_locators = set()

        async def get_contexts():
            return initial_contexts

        await self._block(session, get_contexts(), self._code)

    async def _block(self, session, get_contexts, block):
        while True:
            tasks = []
            contexts = await get_contexts

            for context in contexts:

                async def get_context(context):
                    return [context]

                get_contexts = None

                for command in block.commands:
                    if isinstance(command, Block):
                        get_contexts = self._block(
                            session, get_contexts or get_context(context), command
                        )
                    elif isinstance(command, Collect):
                        tasks.append(
                            asyncio.create_task(
                                self._output_texts(get_contexts or get_context(context))
                            )
                        )
                        get_contexts = None
                    elif isinstance(command, Follow):
                        get_contexts = self._follow_contexts(
                            session, get_contexts or get_context(context)
                        )
                    elif isinstance(command, Select):
                        get_contexts = self._select_texts(
                            get_contexts or get_context(context), command
                        )
                    else:
                        raise ValueError

                if get_contexts:
                    tasks.append(asyncio.create_task(get_contexts))

            new_contexts = list(filter(None, flatten(await asyncio.gather(*tasks))))

            if not new_contexts:
                return contexts

            async def get_new_contexts(new_contexts):
                return new_contexts

            get_contexts = get_new_contexts(new_contexts)

    async def _output_texts(self, get_contexts):
        for context in await get_contexts:
            self.print(context.text)

    @abstractmethod
    def print(self, text):
        raise NotImplementedError

    async def _follow_contexts(self, session, get_contexts):
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
    def join(self, base, locator):
        raise NotImplementedError

    async def _select_texts(self, get_contexts, selector):
        contexts = []

        for context in await get_contexts:
            for selectee in selector.select(context.text):
                contexts.append(Context(context.locator, selectee))

        return contexts
