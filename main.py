from multiprocessing import Process

from app.client import Client
from app.server import Server


EXECUTION_TIME = 300  # Время жизни сервера и клиентов в секундах
CLIENTS_NUMBER = 2   # Количество клиентов
HOST = 'localhost'
PORT = 32465


if __name__ == '__main__':
    server = Server(host=HOST, port=PORT, alive_time=EXECUTION_TIME)
    clients = [
        Client(host=HOST, port=PORT,
               alive_time=EXECUTION_TIME, name=f'client_{index}')
        for index in range(1, CLIENTS_NUMBER + 1)
    ]

    processes = [Process(None, actor.run)
                 for actor in ([server] + clients)]
    for process in processes:
        process.start()
    for process in processes:
        process.join()
