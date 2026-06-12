from __future__ import annotations

from dataclasses import dataclass

from cli.commands import Command, CommandRegistry


@dataclass
class _Ctx:
    called: list[str]


class _Echo(Command):
    def __init__(self):
        super().__init__(name="echo", description="x", usage="echo <args>", aliases=["e"])

    def execute(self, args: str, context: _Ctx) -> bool:
        context.called.append(args)
        return True


def test_command_registry__alias_match_and_execute() -> None:
    reg = CommandRegistry()
    reg.register(_Echo())
    ctx = _Ctx(called=[])
    out = reg.execute("e hello", ctx)
    assert out is True
    assert ctx.called == ["hello"]


def test_command_registry__non_command_returns_none() -> None:
    reg = CommandRegistry()
    ctx = _Ctx(called=[])
    assert reg.execute("unknown stuff", ctx) is None

