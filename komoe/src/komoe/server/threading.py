from http.server import HTTPServer, BaseHTTPRequestHandler
from pathlib import Path
from socketserver import ThreadingMixIn
from typing import Any, Callable

Handler = Callable[[Any, Any, HTTPServer], BaseHTTPRequestHandler]

class ThreadingHTTPServer(ThreadingMixIn, HTTPServer):
    __output_dir: Path

    def __init__(self, host: str, port: int, handler: Handler, output_dir: Path):
        super().__init__((host, port), handler)
        self.__output_dir = output_dir
        
    @property
    def output_dir(self):
        return self.__output_dir