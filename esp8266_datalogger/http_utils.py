"""
Minimal HTTP utility functions for MicroPython (ESP8266).

Extracted so modbus_bridge.py, serial_bridge.py, and ota_client.py
can import only these functions without loading large modules.
"""
import json
import socket

try:
    from log_buffer import log_print as print
except ImportError:
    pass


def http_post_json(url, data, timeout=10):
    """
    HTTP POST with JSON body (MicroPython compatible).

    Args:
        url:     Full URL — http://host:port/path
        data:    Dict to send as JSON body
        timeout: Request timeout in seconds

    Returns:
        (status_code, response_dict_or_None)
    """
    try:
        if url.startswith("http://"):
            url = url[7:]

        if "/" in url:
            host_port, path = url.split("/", 1)
            path = "/" + path
        else:
            host_port = url
            path = "/"

        if ":" in host_port:
            host, port = host_port.split(":")
            port = int(port)
        else:
            host = host_port
            port = 80

        body = json.dumps(data)
        hdr = (
            "POST {} HTTP/1.1\r\n"
            "Host: {}:{}\r\n"
            "Content-Type: application/json\r\n"
            "Content-Length: {}\r\n"
            "Connection: close\r\n"
            "\r\n"
        ).format(path, host, port, len(body))

        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        sock.settimeout(timeout)
        sock.connect((host, port))
        # Send header and body separately — avoids hdr+body concatenation
        sock.sendall(hdr.encode())
        sock.sendall(body.encode())
        del hdr, body

        # Receive response into bytearray (no bytes+= copies)
        buf = bytearray()
        while True:
            try:
                chunk = sock.recv(512)
                if not chunk:
                    break
                buf.extend(chunk)
            except:
                break
        sock.close()

        try:
            response = buf.decode("utf-8")
        except:
            response = buf.decode("latin-1")
        del buf

        if "\r\n\r\n" in response:
            headers, resp_body = response.split("\r\n\r\n", 1)
        else:
            headers = response
            resp_body = ""

        first_line = headers.split("\r\n")[0]
        parts = first_line.split(" ")
        status_code = int(parts[1]) if len(parts) >= 2 else 0

        try:
            result = json.loads(resp_body)
        except:
            result = None

        return status_code, result

    except Exception as e:
        print("[HTTP] Error:", e)
        return 0, None


def http_get_json(url, timeout=10):
    """
    HTTP GET with JSON response (MicroPython compatible).

    Args:
        url:     Full URL — http://host:port/path
        timeout: Request timeout in seconds

    Returns:
        (status_code, response_dict_or_None)
    """
    try:
        if url.startswith("http://"):
            url = url[7:]

        if "/" in url:
            host_port, path = url.split("/", 1)
            path = "/" + path
        else:
            host_port = url
            path = "/"

        if ":" in host_port:
            host, port = host_port.split(":")
            port = int(port)
        else:
            host = host_port
            port = 80

        hdr = (
            "GET {} HTTP/1.1\r\n"
            "Host: {}:{}\r\n"
            "Connection: close\r\n"
            "\r\n"
        ).format(path, host, port)

        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        sock.settimeout(timeout)
        sock.connect((host, port))
        sock.sendall(hdr.encode())
        del hdr

        buf = bytearray()
        while True:
            try:
                chunk = sock.recv(512)
                if not chunk:
                    break
                buf.extend(chunk)
            except:
                break
        sock.close()

        try:
            response = buf.decode("utf-8")
        except:
            response = buf.decode("latin-1")
        del buf

        if "\r\n\r\n" in response:
            headers, resp_body = response.split("\r\n\r\n", 1)
        else:
            return 0, None

        first_line = headers.split("\r\n")[0]
        parts = first_line.split(" ")
        status_code = int(parts[1]) if len(parts) >= 2 else 0

        try:
            result = json.loads(resp_body)
        except:
            result = None

        return status_code, result

    except Exception as e:
        print("[HTTP] Error:", e)
        return 0, None
