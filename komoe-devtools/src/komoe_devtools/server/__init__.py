from threading import Thread
from pathlib import Path
from socketserver import TCPServer

from .handler import PreviewRequestHandler
from .threading import Handler, ThreadingHTTPServer
from ..build import ProjectPaths


class Server:
    __handler: Handler
    __host: str
    __port: int
    __output_dir: Path

    def __init__(self, host, port, paths: ProjectPaths):
        self.__handler = PreviewRequestHandler
        self.__host = host
        self.__port = port
        self.__output_dir = paths.output_dir

    def serve_threaded(self) -> 'ServerContext':
        server = ThreadingHTTPServer(self.__host, self.__port, self.__handler, self.__output_dir)
        server_thread = Thread(target=server.serve_forever)
        server_thread.start()
        return ServerContext(server, server_thread)

class ServerContext:
    __running_server: TCPServer
    __server_thread: Thread

    def __init__(self, running_server: TCPServer, server_thread: Thread):
        self.__running_server = running_server
        self.__server_thread = server_thread

    def shutdown(self):
        self.__running_server.shutdown()
        self.__server_thread.join()

    def __enter__(self):
        return self

    def __exit__(self, *args):
        self.shutdown()