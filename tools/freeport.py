# -*- coding: utf-8 -*-
"""Print the first port in a range that can actually be bound.

A connect() probe is not a reliable availability test on Windows: a socket
that is bound and listening but not accepting still answers WSAECONNREFUSED,
so connect_ex reports the port as free and the server then fails to start with
WSAEADDRINUSE. Binding is the authoritative test, and it is exactly what
uvicorn does, so this matches its behaviour including the failure mode.

Usage:  python tools/freeport.py [start] [end]
Prints the port and exits 0, or prints nothing and exits 1.
"""
import socket
import sys


def can_bind(port: int, host: str = "127.0.0.1") -> bool:
    s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    # Deliberately no SO_REUSEADDR: uvicorn does not set it on Windows, and
    # setting it here would let the probe succeed on a port uvicorn cannot take.
    try:
        s.bind((host, port))
        return True
    except OSError:
        return False
    finally:
        s.close()


def main() -> int:
    start = int(sys.argv[1]) if len(sys.argv) > 1 else 8000
    end = int(sys.argv[2]) if len(sys.argv) > 2 else start + 25
    for port in range(start, end + 1):
        if can_bind(port):
            print(port)
            return 0
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
