import asyncio
import re
from datetime import datetime
from random import randint

from dataclasses import dataclass

from .utils import (DATETIME_FORMAT_PATTERN, LOG_MESSAGE_PATTERN,
                    configure_logger, now)


PING_MESSAGE_PATTERN = '[{request_id}] PING'
PONG_MESSAGE_REGEX = re.compile(
    r'\[(?P<response_id>\d+):(?P<request_id>\d+)\] PONG \((?P<client_id>\d+)\)'
)
KEEPALIVE_MESSAGE_REGEX = re.compile(
    r'\[(?P<response_id>\d+)\] keepalive'
)


@dataclass
class Request:
    id: int
    open: datetime
    closed: datetime = None
    response_text = None

    @property
    def request_text(self):
        return PING_MESSAGE_PATTERN.format(request_id=self.id)

    def log_message(self):
        return LOG_MESSAGE_PATTERN.format(
            request_datetime=self.open.strftime(DATETIME_FORMAT_PATTERN),
            request_text=self.request_text,
            response_datetime=self.closed.strftime(DATETIME_FORMAT_PATTERN),
            response_text=self.response_text
        )


class Client:
    def __init__(self, host: str, port: int,
                 alive_time: float, name: str) -> None:
        for field in ('host', 'port', 'alive_time', 'name'):
            setattr(self, field, locals()[field])
        self.request_id = 0
        self.requests = asyncio.Queue()
        self._tasks: list[asyncio.Task] = list()

    def _get_request_id(self):
        self.request_id += 1
        return self.request_id

    async def _send_requests(self):
        while True:
            request = Request(self._get_request_id(),
                              now())
            await self.requests.put(request)
            self.writer.write(
                (request.request_text + '\n').encode()
            )
            await asyncio.sleep(randint(300, 3000) / 1000)

    async def _process_incoming(self):
        async for message in self.reader:
            message = message.decode().strip()
            if KEEPALIVE_MESSAGE_REGEX.fullmatch(message):
                continue

            pong = PONG_MESSAGE_REGEX.fullmatch(message)
            if not pong:
                self.logger.warning(
                    f'Сервер отправил нераспознанное сообщение: "{message}"'
                )
                continue

            pong_request_id = int(pong.group('request_id'))
            while True:
                request: Request = await self.requests.get()
                request.closed = now()
                if request.id < pong_request_id:
                    request.response_text = 'таймаут'
                else:
                    request.response_text = message
                self.logger.debug(request.log_message())
                if request.id == pong_request_id:
                    break

    def _spawn_tasks(self):
        for coro in (self._send_requests(),
                     self._process_incoming()):
            self._tasks.append(asyncio.create_task(coro))

    def _stop_tasks(self):
        for coro in self._tasks:
            coro.cancel()

    async def _run(self):
        self.reader, self.writer = await asyncio.open_connection(
            host=self.host, port=self.port
        )
        self._spawn_tasks()
        await asyncio.sleep(self.alive_time)
        self._stop_tasks()

    def run(self):
        self.logger = configure_logger(self.name)
        asyncio.run(self._run())
