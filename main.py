import os
import socket
import logging
import mimetypes
from datetime import datetime
from pymongo import MongoClient
from multiprocessing import Process
from urllib.parse import urlparse, parse_qs
from http.server import HTTPServer, BaseHTTPRequestHandler

HTTP_HOST = "0.0.0.0"
HTTP_PORT = 3000

SOCKET_HOST = socket.gethostbyname(socket.gethostname())
SOCKET_PORT = 5000
CHUNK_SIZE = 1024

# Parameters for connecting to MongoDB
URI_DB = "mongodb://mongodb:27017/"
MONGO_DB = "db-mongo"
MONGO_COLLECTION = "messages"

# Connection to MongoDB
mongo_client = MongoClient(URI_DB)
db = mongo_client[MONGO_DB]
collection = db[MONGO_COLLECTION]

# Path to the resource folder
RESOURCE_DIR = "front-init"

# Mapping of routes to corresponding files
ROUTES = {
    "/": "index.html",
    "/message.html": "message.html",
    "/style.css": "style.css",
    "/logo.png": "logo.png",
}

# File of the 404 error page
ERROR_PAGE = "error.html"


class HttpHandler(BaseHTTPRequestHandler):

    def do_GET(self):
        """
        Handle the GET request.
        """
        # Get the request path
        path = urlparse(self.path).path

        # Path to the file on the server
        file_name = ROUTES.get(path)
        if file_name:
            file_path = os.path.join(RESOURCE_DIR, file_name)
            self.send_static_file(file_path)
        else:
            # Return 404 if the file is not found
            self.send_error(404, "Not Found")

    def do_POST(self):
        """
        Handle the POST request.
        """
        size = int(self.headers["Content-Length"])
        data = self.rfile.read(size)

        try:
            run_client_socket(data)
            logging.info("HTTP Server: socket client started")
        except Exception as e:
            logging.error(f"Failed to send data: {e}")

        self.send_response(302)
        self.send_header("Location", "/")
        self.end_headers()

    def send_static_file(self, file_path):
        """
        Sending static files.
        """
        try:
            with open(file_path, "rb") as file:
                self.send_response(200)
                mt = mimetypes.guess_type(file_path)[0]
                if mt:
                    self.send_header("Content-type", mt)
                else:
                    self.send_header("Content-type", "text/plain")
                self.end_headers()
                self.wfile.write(file.read())
        except FileNotFoundError:
            # If the file is not found, send an error page
            self.send_error_page()

    def send_error_page(self):
        """
        Sending the 404 error page.
        """
        try:
            error_file_path = os.path.join(RESOURCE_DIR, ERROR_PAGE)
            self.send_response(404)
            self.send_header("Content-type", "text/html")
            self.end_headers()
            with open(error_file_path, "rb") as error_file:
                self.wfile.write(error_file.read())
        except FileNotFoundError:
            # If the file is not found, send an error message to the client
            logging.error("Error sending error page.")
            self.send_error(404, "Not Found")


def run_http_server():
    """
    Run the HTTP server.
    """
    try:
        logging.basicConfig(level=logging.INFO)
        httpd = HTTPServer((HTTP_HOST, HTTP_PORT), HttpHandler)
        logging.info(f"Server started: http://{HTTP_HOST}:{HTTP_PORT}")
        httpd.serve_forever()
    except Exception as e:
        logging.error(f"Server error: {e}")
    finally:
        logging.info("Server stopped")
        httpd.server_close()


def handle_message(data):
    """
    Handle the received message and save it to MongoDB.
    """
    try:
        # Split form data into parameters
        params = parse_qs(data.decode())
        message_data = {key: value[0] for key, value in params.items()}

        # Add date to the data object
        message_data["date"] = datetime.now().strftime("%Y-%m-%d %H:%M:%S.%f")

        # Save data to MongoDB
        collection.insert_one(message_data)
        logging.info("Message saved to MongoDB: %s", message_data)

    except Exception as e:
        logging.error("Error handling message: %s", e)


def run_socket_server():
    """
    Main function of the Socket server.
    """
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as server_socket:
        server = "", SOCKET_PORT
        try:
            server_socket.bind(server)
            server_socket.listen()
            logging.info(f"Socket server listening on {SOCKET_HOST}:{SOCKET_PORT}")

            while True:
                conn, addr = server_socket.accept()
                logging.info(f"Connection from {addr}")
                with conn:
                    data = conn.recv(CHUNK_SIZE)
                    if not data:
                        break
                    handle_message(data)
        except (socket.error, Exception) as e:
            logging.error(f"Error in socket server: {e}")
        finally:
            logging.info("Server socket stopped")
            server_socket.close()


def run_client_socket(data: str):
    """
    Socket client receives data from HTTP server.
    """
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as server_socket:
        try:
            server_socket.connect(("", SOCKET_PORT))
            server_socket.sendall(data)
            logging.info("Socket Client: Data transfer completed")
        except ConnectionRefusedError:
            logging.error("Connection refused")
        except Exception as e:
            logging.error(f"Error connecting to socket server: {e}")


if __name__ == "__main__":

    try:
        http_process = Process(target=run_http_server)
        http_process.start()
        socket_process = Process(target=run_socket_server)
        socket_process.start()

        http_process.join()
        socket_process.join()

    except KeyboardInterrupt:
        http_process.terminate()
        socket_process.terminate()