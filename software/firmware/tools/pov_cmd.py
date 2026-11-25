#!/usr/bin/env python3
"""pov_cmd.py - send phase-0 bench commands to the POV column over Wi-Fi (TCP 23), pure stdlib.

The phase-0 sketch (0.3+) runs the same command parser on TCP port 23 as on Serial, so the board can sit on the bench
supply alone (5 V on J1, no USB). Every reply the sketch prints goes to both Serial and this connection; after each
line it has handled it sends the prompt "pov> ", which is how this script knows the replies are complete.

  py pov_cmd.py "cb s8000 a"          send the commands (one line, space-separated), print the replies, exit
  py pov_cmd.py q i                   several arguments are joined into one line
  py pov_cmd.py --watch               interactive session: type commands, see replies and hall readouts live (Ctrl-C quits)
  py pov_cmd.py --watch "h"           send h first, then stay open
  py pov_cmd.py --host 192.168.1.50 q when pov.local doesn't resolve (the board prints its IP on serial at join;
                                      or set POV_HOST=192.168.1.50 once in the shell)

Long commands: t (frame time) takes ~1 s and k (column clock) 10 s; --timeout (default 20 s) covers both.
Only one client at a time: a new connection (this script, telnet, ...) takes the port over from the old one.
"""
import argparse
import os
import socket
import sys
import threading
import time

PROMPT = b"pov> "


def connect(host, port, timeout):
    try:
        return socket.create_connection((host, port), timeout=timeout)
    except OSError as e:
        sys.exit(f"pov_cmd: can't reach {host}:{port} ({e}). Is the board on Wi-Fi? Try --host <ip> (printed on serial at join).")


def read_until_prompt(sock, timeout):
    """Read until the stream ends with the prompt; returns the text before it (or what arrived before the timeout)."""
    buf = b""
    deadline = time.monotonic() + timeout
    sock.settimeout(0.25)
    while time.monotonic() < deadline:
        try:
            chunk = sock.recv(4096)
        except socket.timeout:
            continue
        if not chunk:
            raise ConnectionError("the board closed the connection (another client took the port?)")
        buf += chunk
        if buf.endswith(PROMPT):
            return buf[: -len(PROMPT)], True
    return buf, False


def show(data):
    text = data.decode("utf-8", "replace").replace("\r\n", "\n")
    if text:
        sys.stdout.write(text if text.endswith("\n") else text + "\n")
        sys.stdout.flush()


def run_once(sock, line, timeout, quiet_banner):
    banner, _ = read_until_prompt(sock, 5)
    if not quiet_banner:
        show(banner)
    sock.sendall(line.encode() + b"\n")
    reply, ok = read_until_prompt(sock, timeout)
    show(reply)
    if not ok:
        print(f"pov_cmd: no prompt within {timeout} s (reply may be incomplete)", file=sys.stderr)
        return 1
    return 0


def watch(sock, first):
    stop = threading.Event()

    def reader():
        sock.settimeout(0.25)
        while not stop.is_set():
            try:
                chunk = sock.recv(4096)
            except socket.timeout:
                continue
            except OSError:
                break
            if not chunk:
                print("\n[connection closed by the board]")
                stop.set()
                break
            sys.stdout.write(chunk.decode("utf-8", "replace").replace("\r\n", "\n"))
            sys.stdout.flush()

    t = threading.Thread(target=reader, daemon=True)
    t.start()
    if first:
        sock.sendall(first.encode() + b"\n")
    try:
        for line in sys.stdin:
            if stop.is_set():
                break
            sock.sendall(line.rstrip("\r\n").encode() + b"\n")
        stop.wait(2.0)              # stdin ended (piped input / Ctrl-Z): let the last replies arrive before closing
    except (KeyboardInterrupt, OSError):
        pass
    stop.set()
    return 0


def main():
    ap = argparse.ArgumentParser(description="Send POV phase-0 bench commands over Wi-Fi (TCP 23).")
    ap.add_argument("commands", nargs="*", help='commands, e.g. "cb s8000 a" (several arguments are joined with spaces)')
    ap.add_argument("--host", default=os.environ.get("POV_HOST", "pov.local"), help="board host or IP (default pov.local or $POV_HOST)")
    ap.add_argument("--port", type=int, default=23)
    ap.add_argument("--timeout", type=float, default=20.0, help="seconds to wait for the replies (k takes 10 s)")
    ap.add_argument("--watch", action="store_true", help="stay connected: interactive commands + live output")
    ap.add_argument("--banner", action="store_true", help="also print the connect banner (version + state)")
    a = ap.parse_args()
    line = " ".join(a.commands).strip()
    if not line and not a.watch:
        ap.error('give commands (e.g. "q") or --watch')
    sock = connect(a.host, a.port, 5)
    try:
        if a.watch:
            print(f"connected to {a.host}:{a.port}; type commands (? for help), Ctrl-C or Ctrl-Z/Enter to quit")
            return watch(sock, line)
        return run_once(sock, line, a.timeout, not a.banner)
    except ConnectionError as e:
        print(f"pov_cmd: {e}", file=sys.stderr)
        return 1
    finally:
        sock.close()


if __name__ == "__main__":
    sys.exit(main())
