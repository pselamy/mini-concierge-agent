# tests/fakes.py
from typing import Any, Callable, Coroutine


class FakeGenAiClient:
    """A fake Google GenAI Client that replaces MagicMock for unit tests."""

    vertexai = False

    def __init__(self, generate_content_fn: Callable[..., Coroutine[Any, Any, Any]]):
        self.aio = self.FakeAio(generate_content_fn)

    class FakeAio:
        def __init__(
            self, generate_content_fn: Callable[..., Coroutine[Any, Any, Any]]
        ):
            self.models = self.FakeModels(generate_content_fn)

        class FakeModels:
            def __init__(
                self, generate_content_fn: Callable[..., Coroutine[Any, Any, Any]]
            ):
                self._generate_content_fn = generate_content_fn

            async def generate_content(self, *args: Any, **kwargs: Any) -> Any:
                return await self._generate_content_fn(*args, **kwargs)

            async def generate_content_stream(self, *args: Any, **kwargs: Any) -> Any:
                response = await self._generate_content_fn(*args, **kwargs)

                async def _stream():
                    yield response


class FakeRunner:
    """A fake WorkflowRunner that can simulate execution errors."""

    def __init__(self, should_raise: bool = False):
        self.should_raise = should_raise

    async def run_async(self, *args: Any, **kwargs: Any) -> Any:
        if self.should_raise:
            raise Exception("Test agent error")
