import email.utils
import mimetypes
import shutil
import urllib.parse
import datetime
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler
from math import floor
from pathlib import Path
from typing import BinaryIO, Optional

from komoe import __version__
from komoe.log import Log
from .threading import ThreadingHTTPServer


def guess_file_type(path: Path) -> str:
    guess, _ = mimetypes.guess_type(path)
    return guess if guess is not None else 'application/octet-stream'


class PreviewRequestHandler(BaseHTTPRequestHandler):
    server: ThreadingHTTPServer

    server_version = "KomoePreview/" + str(__version__)

    # noinspection PyPep8Naming
    def do_GET(self):
        Log.dbg('>>> ' + self.requestline)
        file = self.send_head()
        if file:
            try:
                # noinspection PyTypeChecker
                shutil.copyfileobj(file, self.wfile)
                Log.dbg('<<< 200 OK')
            finally:
                file.close()

    # noinspection PyPep8Naming
    def do_HEAD(self):
        Log.dbg('>>> ' + self.requestline)
        file = self.send_head()
        if file:
            Log.dbg('<<< 200 OK')
            file.close()

    def log_request(self, *_):
        pass

    def send_head(self) -> Optional[BinaryIO]:
        path = self.map_path(self.path)
        file = None

        if path is None:
            Log.dbg('    No matching file found')
            Log.dbg('<<< 404 Not Found')
            self.send_response(HTTPStatus.NOT_FOUND)
            self.end_headers()
            return None
        else:
            Log.dbg('    Mapped to ' + str(path))
            try:
                file = open(path, 'rb')
            except OSError:
                Log.dbg('<<< 403 Forbidden')
                self.send_response(HTTPStatus.FORBIDDEN)
                return None

        try:
            stat = path.stat()
            cached = False

            if "If-Modified-Since" in self.headers and "If-None-Match" not in self.headers:
                try:
                    ims = email.utils.parsedate_to_datetime(self.headers["If-Modified-Since"])
                except (TypeError, IndexError, OverflowError, ValueError):
                    pass
                else:
                    if ims.tzinfo is None:
                        ims = ims.replace(tzinfo=datetime.timezone.utc)
                    if ims.tzinfo is datetime.timezone.utc:
                        last_modif = datetime.datetime.fromtimestamp(floor(stat.st_mtime), datetime.timezone.utc)
                        cached = last_modif <= ims

            if cached:
                Log.dbg('<<< 304 Not Modified')
                self.send_response(HTTPStatus.NOT_MODIFIED)
                self.end_headers()
                file.close()
                return None
            else:
                self.send_response(HTTPStatus.OK)
                self.send_header("Content-Type", guess_file_type(path))
                self.send_header("Content-Length", str(stat.st_size))
                self.send_header("Last-Modified", self.date_time_string(stat.st_mtime))
                self.end_headers()
                return file

        except:
            file.close()
            raise

    def map_path(self, path: str) -> Path:
        path = path.split('?', 1)[0]
        path = path.split('#', 1)[0]

        try:
            path = urllib.parse.unquote(path, errors='strict')
        except UnicodeDecodeError:
            path = urllib.parse.unquote(path)

        segments = path.split('/')

        mapped_path = self.server.output_dir
        for seg in segments:
            mapped_path /= seg

        if mapped_path.is_file():
            return mapped_path

        if mapped_path.suffix == '':
            with_html_ext = mapped_path.with_suffix('.html')
            if with_html_ext.is_file():
                return with_html_ext

        if mapped_path.is_dir():
            index_file = mapped_path / 'index.html'
            if index_file.is_file():
                return index_file