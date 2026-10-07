#!/usr/bin/env python3
"""Dummy POP3 server that accepts any login and never has any messages"""
import argparse
import contextlib
import enum
import logging
import os
import socket
import time
from importlib import metadata
from itertools import count

import trio

DEFAULT_PORT = 110
# RFC 1939 limits commands to 255 octets; be generous but bounded
MAX_LINE_LENGTH = 1024

connection_ids = count()
logger = logging.getLogger(__name__)


def get_version() -> str:
    '''installed package version'''
    try:
        return metadata.version("voidpop")
    except metadata.PackageNotFoundError:
        return "unknown"


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    '''argument parsing'''
    parser = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog='Port can also be set using the VOIDPOP_PORT environment variable.'
    )
    parser.add_argument(
        "--port", type=int, default=os.environ.get("VOIDPOP_PORT", DEFAULT_PORT),
        help="Listen on PORT (default: %(default)s)",
    )
    parser.add_argument("--verbose", action="store_true", help="Log debug messages")
    parser.add_argument("--version", action="version", version=f"%(prog)s {get_version()}")
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> None:
    '''main function'''
    args = parse_args(argv)
    logging.basicConfig(
        datefmt="%Y-%m-%d %H:%M:%S",
        format="%(asctime)s.%(msecs)03d %(message)s",
        level=logging.DEBUG if args.verbose else logging.INFO,
    )
    with contextlib.suppress(KeyboardInterrupt):
        trio.run(trio.serve_tcp, handler, args.port)


def return_ok(msg: str | None = None) -> bytes:
    '''return with ok'''
    if msg is None:
        return b"+OK\r\n"
    return b"+OK %b\r\n" % msg.encode("ascii", errors="replace")


def return_err(msg: str | None = None) -> bytes:
    '''return with error'''
    if msg is None:
        return b"-ERR\r\n"
    return b"-ERR %b\r\n" % msg.encode("ascii", errors="replace")


class State(enum.Enum):
    '''POP3 connection states'''
    AUTHORIZATION = enum.auto()
    TRANSACTION = enum.auto()
    UPDATE = enum.auto()
    DONE = enum.auto()


class POP3:
    '''POP3 server implementation'''

    def __init__(self) -> None:
        '''class initialization'''
        self.state = State.AUTHORIZATION

    def banner(self) -> bytes:
        '''construct welcome banner'''
        return return_ok(f"<{time.monotonic()}@{socket.gethostname()}>")

    def handle(self, command: str, args: list[str]) -> bytes:
        '''command handler'''
        if self.state == State.AUTHORIZATION:
            if command == "USER":
                return return_ok("pretending your mailbox exists")
            if command == "PASS":
                self.state = State.TRANSACTION
                return return_ok("how did you know")
            if command == "QUIT":
                self.state = State.DONE
                return return_ok("goodbye")
            if command == "APOP":
                self.state = State.TRANSACTION
                return return_ok("pretending your mailbox exists")

        if self.state == State.TRANSACTION:
            if command == "STAT":
                return return_ok("0 0")
            if command == "LIST":
                return return_err("no such message") if args else return_ok("\r\n.")
            if command == "RETR":
                return return_err("no such message")
            if command == "DELE":
                return return_err("no such message")
            if command == "NOOP":
                return return_ok()
            if command == "RSET":
                return return_ok()
            if command == "QUIT":
                self.state = State.UPDATE
                return return_ok("goodbye")
            if command == "TOP":
                return return_err("no such message")
            if command == "UIDL":
                return return_err("no such message") if args else return_ok("\r\n.")

        return return_err("unrecognized command")


async def read_lines(stream: trio.SocketStream):
    '''yield complete CRLF/LF terminated lines, however TCP chunked them'''
    buffer = b""
    async for data in stream:
        buffer += data
        while (end := buffer.find(b"\n")) != -1:
            line, buffer = buffer[:end], buffer[end + 1:]
            yield line.rstrip(b"\r")
        if len(buffer) > MAX_LINE_LENGTH:
            raise ValueError("command line too long")


async def handler(stream: trio.SocketStream) -> None:
    '''connection handler'''
    connection_id = next(connection_ids)
    pop3 = POP3()
    logger.debug("[%s] Connection opened", connection_id)
    try:
        await stream.send_all(pop3.banner())
        async for line in read_lines(stream):
            command, *args = line.decode("ascii", errors="replace").split(" ")
            response = pop3.handle(command.upper(), args)
            await stream.send_all(response)
            logger.debug("[%s] - %r", connection_id, line)
            logger.debug("[%s]   -> %r", connection_id, response)
            if pop3.state in {State.UPDATE, State.DONE}:
                break
    except Exception:   # pylint: disable=broad-except
        logger.warning("[%s] Crashed", connection_id, exc_info=True)
    logger.debug("[%s] Connection closed", connection_id)


if __name__ == '__main__':
    main()
