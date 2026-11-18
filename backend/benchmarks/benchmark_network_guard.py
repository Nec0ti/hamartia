"""Python-level loopback-only socket and resolver guard for offline benchmarks."""

import ipaddress
import socket
from contextlib import contextmanager


def _assert_address(address):
    host = address[0] if isinstance(address, tuple) else address
    try:
        loopback = ipaddress.ip_address(host).is_loopback
    except (TypeError, ValueError):
        loopback = False
    if not loopback:
        raise RuntimeError(f"non-loopback network address blocked: {host}")


def _assert_numeric_name(host):
    try:
        loopback = ipaddress.ip_address(host).is_loopback
    except (TypeError, ValueError):
        loopback = False
    if not loopback:
        raise RuntimeError(f"hostname resolution blocked: {host}")


def install_loopback_guard():
    socket_methods = ("connect", "connect_ex", "send", "sendall", "sendto", "sendmsg")
    resolver_methods = ("getaddrinfo", "gethostbyname", "gethostbyname_ex", "gethostbyaddr", "getnameinfo", "getfqdn")
    originals = (
        {name: getattr(socket.socket, name) for name in socket_methods if hasattr(socket.socket, name)},
        {name: getattr(socket, name) for name in resolver_methods if hasattr(socket, name)},
    )
    methods, resolvers = originals

    def connect(sock, address):
        _assert_address(address)
        return methods["connect"](sock, address)

    def connect_ex(sock, address):
        _assert_address(address)
        return methods["connect_ex"](sock, address)

    def send(sock, data, *args, **kwargs):
        _assert_address(sock.getpeername())
        return methods["send"](sock, data, *args, **kwargs)

    def sendall(sock, data, *args, **kwargs):
        _assert_address(sock.getpeername())
        return methods["sendall"](sock, data, *args, **kwargs)

    def sendto(sock, *args, **kwargs):
        _assert_address(kwargs.get("address", args[-1] if args else None))
        return methods["sendto"](sock, *args, **kwargs)

    def sendmsg(sock, *args, **kwargs):
        address = kwargs.get("address", args[3] if len(args) > 3 else None)
        _assert_address(address if address is not None else sock.getpeername())
        return methods["sendmsg"](sock, *args, **kwargs)

    for name, replacement in (
        ("connect", connect), ("connect_ex", connect_ex), ("send", send),
        ("sendall", sendall), ("sendto", sendto), ("sendmsg", sendmsg),
    ):
        if name in methods:
            setattr(socket.socket, name, replacement)

    def getaddrinfo(host, *args, **kwargs):
        _assert_numeric_name(host)
        return resolvers["getaddrinfo"](host, *args, **kwargs)

    def gethostbyname(host):
        _assert_numeric_name(host)
        return resolvers["gethostbyname"](host)

    def gethostbyname_ex(host):
        _assert_numeric_name(host)
        return resolvers["gethostbyname_ex"](host)

    def gethostbyaddr(_host):
        raise RuntimeError("reverse hostname lookup blocked")

    def getnameinfo(address, flags):
        _assert_address(address)
        flags = (flags & ~getattr(socket, "NI_NAMEREQD", 0)) | socket.NI_NUMERICHOST | socket.NI_NUMERICSERV
        return resolvers["getnameinfo"](address, flags)

    def getfqdn(_name=""):
        raise RuntimeError("fully-qualified hostname lookup blocked")

    for name, replacement in (
        ("getaddrinfo", getaddrinfo), ("gethostbyname", gethostbyname),
        ("gethostbyname_ex", gethostbyname_ex), ("gethostbyaddr", gethostbyaddr),
        ("getnameinfo", getnameinfo), ("getfqdn", getfqdn),
    ):
        if name in resolvers:
            setattr(socket, name, replacement)
    return originals


def restore_loopback_guard(originals):
    methods, resolvers = originals
    for name, original in methods.items():
        setattr(socket.socket, name, original)
    for name, original in resolvers.items():
        setattr(socket, name, original)


@contextmanager
def loopback_only():
    originals = install_loopback_guard()
    try:
        yield
    finally:
        restore_loopback_guard(originals)
