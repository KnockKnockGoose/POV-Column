r"""throttle_proxy.py - a TCP proxy that behaves like the sled's Wi-Fi link, for testing live senders on the PC
(Orbit Rally, 2026-11-24; report docs/2026-11-24-orbit-rally.md section 4).

    py tools\mock_board.py --http-port 18090 --no-arduino-ota [--live-rle]
    py tools\throttle_proxy.py 18091 18090 50 8       listen 18091 -> mock 18090, 50 kB/s up, 8 ms each way
    py software\games\orbit_rally.py --bench 10 --host 127.0.0.1:18091 --force

PC -> board is limited to KBPS kB/s (a bottleneck queue, like an access point) plus DELAY_MS one way; board -> PC gets
the delay only (acks are tiny). Measured link: 11-22 uploads ~50 kB/s, 11-14 OTA 10-20 kB/s, ping ~16 ms.
Note: tools/mock_board_test.py uses port 18080, so keep test mocks and proxies off it.

    py tools\throttle_proxy.py LISTEN_PORT TARGET_PORT KBPS DELAY_MS
"""
import collections
import socket
import sys
import threading
import time

LISTEN, TARGET, KBPS, DELAY = int(sys.argv[1]), int(sys.argv[2]), float(sys.argv[3]), float(sys.argv[4]) / 1000.0
RATE = KBPS * 1024.0


def pump(src, dst, rate):
    """Forward src -> dst: every chunk leaves DELAY after it arrived and, if rate, no faster than rate bytes/s."""
    q = collections.deque()
    cv = threading.Condition()

    def reader():
        while True:
            try:
                b = src.recv(1460)
            except OSError:
                b = b""
            with cv:
                q.append((time.perf_counter(), b))
                cv.notify()
            if not b:
                return

    threading.Thread(target=reader, daemon=True).start()
    last = 0.0
    while True:
        with cv:
            while not q:
                cv.wait()
            t_arr, b = q.popleft()
        if not b:
            try:
                dst.shutdown(socket.SHUT_WR)
            except OSError:
                pass
            return
        release = t_arr + DELAY
        if rate:
            release = max(release, last + len(b) / rate)
        wait = release - time.perf_counter()
        if wait > 0:
            time.sleep(wait)
        last = release
        try:
            dst.sendall(b)
        except OSError:
            return


def handle(c):
    s = socket.create_connection(("127.0.0.1", TARGET))
    for x in (c, s):
        x.setsockopt(socket.IPPROTO_TCP, socket.TCP_NODELAY, 1)
    threading.Thread(target=pump, args=(c, s, RATE), daemon=True).start()
    threading.Thread(target=pump, args=(s, c, 0), daemon=True).start()


def main():
    srv = socket.socket()
    srv.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    srv.bind(("127.0.0.1", LISTEN))
    srv.listen(8)
    print(f"proxy :{LISTEN} -> :{TARGET} at {KBPS} kB/s, {DELAY * 1000:.0f} ms one way", flush=True)
    while True:
        c, _ = srv.accept()
        threading.Thread(target=handle, args=(c,), daemon=True).start()


if __name__ == "__main__":
    main()
