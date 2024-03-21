#!/usr/bin/env python3
"""Dummy POP3 server that accepts any login and never has any messages"""
from __future__ import annotations

import argparse
import enum
import logging
import socket
import time
import os
from itertools import count
from typing import List, Optional

import trio

connection_ids = count()
logger = logging.getLogger(__name__)


def parse_args(default_port: int):
    '''argument parsing'''
    parser = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog='Port can also be set using the VOIDPOP_PORT environment variable.'
    )
    parser.add_argument("--port", type=int, default=default_port, help="Listen on PORT")
    parser.add_argument("--verbose", action="store_true", help="Log debug messages")
    return parser.parse_args()


def main():
    '''main function'''
    default_port = os.environ.get('VOIDPOP_PORT', 110)
    args = parse_args(default_port)
    logging.basicConfig(
        datefmt="%Y-%m-%d %H:%M:%S",
        format="%(asctime)s.%(msecs)03d %(message)s",
        level=logging.DEBUG if args.verbose else logging.INFO,
    )
    try:
        trio.run(trio.serve_tcp, handler, args.port)
    except KeyboardInterrupt:
        return


def return_ok(msg: Optional[str] = None) -> bytes:
    '''return with ok'''
    if msg is None:
        return b"+OK\r\n"
    return b"+OK %b\r\n" % msg.encode("ascii", errors="replace")


def return_err(msg: Optional[str] = None) -> bytes:
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

    def handle(self, command: str, args: List[str]) -> bytes:
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


async def handler(stream: trio.SocketStream) -> None:
    '''connection handler'''
    connection_id = next(connection_ids)
    pop3 = POP3()
    logger.debug("[%s] Connection opened", connection_id)
    try:
        await stream.send_all(pop3.banner())
        async for data in stream:
            command, *args = (
                data.decode("ascii", errors="replace").rstrip("\r\n").split(" ")
            )
            command = command.upper()
            response = pop3.handle(command, args)
            await stream.send_all(response)
            logger.debug("[%s] - %r", connection_id, data)
            logger.debug("[%s]   -> %r", connection_id, response)
            if pop3.state in {State.UPDATE, State.DONE}:
                break
    except Exception:   # pylint: disable=broad-except
        logger.warning("[%s] Crashed", connection_id, exc_info=True)
    logger.debug("[%s] Connection closed", connection_id)


if __name__ == '__main__':
    main()
