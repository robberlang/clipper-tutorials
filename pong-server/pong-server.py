from __future__ import print_function, absolute_import
from socketserver import ThreadingMixIn
from http.server import BaseHTTPRequestHandler, HTTPServer
import mimetypes
mimetypes.init()
import os
import requests
from datetime import datetime
import logging
import json
import sys
from jinja2 import Template
cur_dir = os.path.dirname(os.path.abspath(__file__))
static_dir = os.path.join(cur_dir, "static")


PORT = 4000
JS_FILE_PATH = os.path.join(static_dir, "pong.js")


# NOTE: This is definitely not secure
def in_static_dir(file):
    # make both absolute
    directory = os.path.join(os.path.realpath(static_dir), '')
    file = os.path.realpath(file)

    # return true, if the common prefix of both is equal to directory
    # e.g. /a/b/c/d.rst and directory is /a/b, the common prefix is /a/b
    return os.path.commonprefix([file, directory]) == directory


class PongServer(BaseHTTPRequestHandler):

    def _respond_not_found(self):
        pass

    # GET requests serve the corresponding file from the "static/" subdirectory
    def do_GET(self):
        if self.path == "/pong" or self.path == "/pong/":
            self.path = "/pong/index.html"

        if self.path.startswith("/pong/"):
            self.path = self.path.replace("/pong/", "", 1)

        local_path = os.path.abspath(os.path.join(static_dir, self.path))
        logger.info("Local path: {}".format(local_path))
        if not in_static_dir(local_path):
            self.send_error(403, "Forbidden")
        elif not os.path.exists(local_path) or not os.path.isfile(local_path):
            self.send_error(404, "Not Found")
        else:
            with open(local_path, "rb") as f:
                self.send_response(200)
                mtype, encoding = mimetypes.guess_type(local_path)
                self.send_header('Content-Type', mtype)
                self.end_headers()
                self.wfile.write(f.read())
                return

    def do_POST(self):
        if not self.path == "/pong/predict":
            self.send_error(404, "Not Found")
            return
        print(self.rfile)

        clipper_url = "http://{}/pong/predict".format(self.server.clipper_addr)
        content_length = int(self.headers['Content-Length'])
        logger.info(content_length)
        logger.info(clipper_url)
        # # workaround because Javascript's JSON.stringify will turn 1.0 into 1, which
        # # Clipper's JSON parsing will parse as an integer not a double
        req_json = json.loads(self.rfile.read(content_length).decode("utf-8"))
        req_json["input"] = [float(i) for i in req_json["input"]]
        logger.info("Request JSON: {}".format(req_json))
        headers = {'Content-Type': 'application/json'}
        start = datetime.now()
        clipper_response = requests.post(clipper_url, headers=headers, data=json.dumps(req_json))
        end = datetime.now()
        latency = (end - start).total_seconds() * 1000.0
        logger.debug("Clipper responded with '{txt}' in {time} ms".format(
            txt=clipper_response.text, time=latency))
        self.send_response(clipper_response.status_code)
        # Forward headers
        logger.info("Clipper responded with '{txt}' in {time} ms".format(
            txt=clipper_response.text, time=latency))

        for k, v in clipper_response.headers.items():
            self.send_header(k, v)
        self.end_headers()
        self.wfile.write(clipper_response.text.encode())


class ThreadingServer(ThreadingMixIn, HTTPServer):
    pass


def run(clipper_addr):
    server_addr = ('0.0.0.0', PORT)
    logger.info("Starting Pong Server on localhost:{port}".format(port=PORT))
    server = ThreadingServer(server_addr, PongServer)
    server.clipper_addr = clipper_addr
    server.serve_forever()


def inject_localhost_addr(addr):
    template = Template(open(JS_FILE_PATH,'r').read())
    rendered = template.render(ip_addr=addr)
    with open(JS_FILE_PATH, 'w') as f:
        f.write(rendered)


if __name__ == '__main__':
    clipper_addr = sys.argv[1]

    localhost_addr = sys.argv[2]
    inject_localhost_addr(localhost_addr)

    log_filename = sys.argv[3]
    logging.basicConfig(
        filename=log_filename,
        format='%(asctime)s %(levelname)-8s [%(filename)s:%(lineno)d] %(message)s',
        datefmt='%y-%m-%d:%H:%M:%S',
        level=logging.INFO)
    logger = logging.getLogger(__name__)
    
    run(clipper_addr)
