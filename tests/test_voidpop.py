"""Protocol tests for voidpop"""
import pytest
import trio
from trio.testing import memory_stream_pair

import voidpop


def test_unauthenticated_commands_rejected():
    pop3 = voidpop.POP3()
    assert pop3.handle("STAT", []).startswith(b"-ERR")


def test_login_flow():
    pop3 = voidpop.POP3()
    assert pop3.handle("USER", ["x"]).startswith(b"+OK")
    assert pop3.handle("PASS", ["y"]).startswith(b"+OK")
    assert pop3.state == voidpop.State.TRANSACTION
    assert pop3.handle("STAT", []) == b"+OK 0 0\r\n"
    assert pop3.handle("LIST", []).startswith(b"+OK")
    assert pop3.handle("RETR", ["1"]).startswith(b"-ERR")
    assert pop3.handle("QUIT", []).startswith(b"+OK")
    assert pop3.state == voidpop.State.UPDATE


def test_port_from_environment(monkeypatch):
    monkeypatch.setenv("VOIDPOP_PORT", "2110")
    assert voidpop.parse_args([]).port == 2110
    assert voidpop.parse_args(["--port", "9"]).port == 9


async def test_fragmented_and_pipelined_commands():
    client, server = memory_stream_pair()
    async with trio.open_nursery() as nursery:
        nursery.start_soon(voidpop.handler, server)
        assert (await client.receive_some()).startswith(b"+OK <")
        await client.send_all(b"US")
        await client.send_all(b"ER bob\r\nPASS x\r\nSTAT\r\n")
        received = b""
        while received.count(b"\r\n") < 3:
            received += await client.receive_some()
        assert received.endswith(b"+OK 0 0\r\n")
        await client.send_all(b"QUIT\r\n")
        assert (await client.receive_some()).startswith(b"+OK")


async def test_overlong_line_closes_connection():
    client, server = memory_stream_pair()
    with trio.fail_after(5):
        async with trio.open_nursery() as nursery:
            nursery.start_soon(voidpop.handler, server)
            await client.receive_some()
            await client.send_all(b"A" * (voidpop.MAX_LINE_LENGTH + 1))
            await client.aclose()


@pytest.mark.parametrize("cmd", ["", "FOO"])
def test_unknown_command(cmd):
    assert voidpop.POP3().handle(cmd, []).startswith(b"-ERR")
