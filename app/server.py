import asyncio
import re
from logging import Logger
from random import randint

from .utils import (DATETIME_FORMAT_PATTERN, LOG_MESSAGE_PATTERN,
                    configure_logger, now)


PING_MESSAGE_REGEX = re.compile(r'\[(?P<request_id>\d+)\] PING')

PONG_MESSAGE_PATTERN = '[{response_id}:{request_id}] PONG ({client_id})'
KEEPALIVE_MESSAGE_PATTERN = '[{response_id}] keepalive'
KEEPALIVE_UPDATE_TIME = 5


class ClientHandler:
    def __init__(self, client_id: int,
                 reader: asyncio.StreamReader,
                 writer: asyncio.StreamWriter,
                 logger: Logger):
        self.client_id = client_id
        self.reader = reader
        self.writer = writer
        self.logger = logger
        self._tasks: list[asyncio.Task] = list()

    def _throttle(self) -> bool:
        """С вероятностью 10% генерирует True, в остальных случаях - False"""
        if randint(1, 10) == 1:
            return True
        return False

    def _generate_pong(self, request_id):
        return PONG_MESSAGE_PATTERN.format(
            response_id=Server.get_response_id(),
            request_id=request_id,
            client_id=self.client_id
        )

    async def _keep_alive(self):
        while True:
            self.writer.write(
                (KEEPALIVE_MESSAGE_PATTERN.format(
                    response_id=Server.get_response_id()
                 ) + '\n').encode()
            )
            await asyncio.sleep(5)

    async def _process_incoming(self):
        """Корутина для обработки входящих сообщений от клиентов"""
        async for message in self.reader:
            request_datetime = now()
            message = message.decode().strip()
            ping = PING_MESSAGE_REGEX.fullmatch(message)

            if not ping:
                self.logger.warning(
                    f'Клиент отправил неожиданное сообщение: "{message}"'
                )
                continue
            if self._throttle():
                response_datetime = response_text = "(проигнорировано)"
                continue

            await asyncio.sleep(randint(100, 1000) / 1000)
            response_datetime = now()
            response_text = self._generate_pong(ping.group('request_id'))
            self.writer.write(
                (response_text + '\n').encode()
            )
            self.logger.debug(LOG_MESSAGE_PATTERN.format(
                request_datetime=request_datetime.strftime(
                    DATETIME_FORMAT_PATTERN
                ),
                request_text=message,
                response_datetime=response_datetime.strftime(
                    DATETIME_FORMAT_PATTERN
                ),
                response_text=response_text
            ))

    def spawn_tasks(self):
        for coro in (self._process_incoming(),
                     self._keep_alive()):
            self._tasks.append(asyncio.create_task(coro))

    def stop_tasks(self):
        for coro in self._tasks:
            coro.cancel()


class Server:
    """Существует в единственном экземпляре.
    Предполагается существование единственного объекта в процессе."""

    __instance = None
    __client_counter = 0
    __last_response_id = 0
    __client_handlers: list[ClientHandler] = list()

    def __new__(cls, *args, **kwargs):
        if cls.__instance is None:
            cls.__instance = super().__new__(cls)
        return cls.__instance

    def __init__(self, host: str, port: int, alive_time: float):
        for field in ('host', 'port', 'alive_time'):
            setattr(self, field, locals()[field])

    @classmethod
    def get_response_id(cls):
        cls.__last_response_id += 1
        return cls.__last_response_id

    @classmethod
    def get_client_id(cls):
        cls.__client_counter += 1
        return cls.__client_counter

    @staticmethod
    def _create_client(reader: asyncio.StreamReader,
                       writer: asyncio.StreamWriter):
        client_handler = ClientHandler(
            client_id=Server.get_client_id(),
            reader=reader, writer=writer,
            logger=Server.logger
        )
        Server.__client_handlers.append(client_handler)
        client_handler.spawn_tasks()

    @staticmethod
    def _stop_clients():
        for client in Server.__client_handlers:
            client.stop_tasks()

    async def _run(self):
        await asyncio.start_server(
            client_connected_cb=self._create_client,
            host=self.host, port=self.port
        )
        await asyncio.sleep(self.alive_time)
        Server._stop_clients()

    def run(self):
        Server.logger = configure_logger('server')
        asyncio.run(self._run())
