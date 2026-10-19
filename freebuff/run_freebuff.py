#!/usr/bin/env python3
"""
EON freebuff-cloud runner (GitHub Actions).

Drives the freebuff CLI TUI inside a PTY:
  - verifies the CLI runs
  - launches `freebuff --trust-agents` in the work directory
  - waits for boot, types the task, presses Enter
  - captures the full transcript (raw + cleaned ANSI)
  - classifies the outcome

Exit codes:
  0  task activity observed
  2  startup failure (binary missing/broken, pty error)
  3  timed out with no conclusion
  4  login required (login gate detected)
"""

import argparse
import fcntl
import os
import pty
import re
import select
import shutil
import signal
import struct
import subprocess
import sys
import termios
import time

ANSI_OSC = re.compile(rb'\x1b\][^\x07\x1b]*(?:\x07|\x1b\\)')
ANSI_CSI = re.compile(rb'\x1b\[[0-9;?]*[ -/]*[@-~]')
ANSI_2C = re.compile(rb'\x1b[()][A-Za-z0-9]')


def clean(raw: bytes) -> str:
    s = ANSI_OSC.sub(b'', raw)
    s = ANSI_CSI.sub(b'', s)
    s = ANSI_2C.sub(b'', s)
    return s.decode('utf-8', 'replace').replace('\r', '')


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument('--task', required=True)
    ap.add_argument('--cwd', default='work')
    ap.add_argument('--out-prefix', default='out/freebuff')
    ap.add_argument('--max-minutes', type=float, default=30.0)
    ap.add_argument('--boot-seconds', type=float, default=30.0)
    ap.add_argument('--idle-seconds', type=float, default=120.0)
    ap.add_argument('--cols', type=int, default=160)
    ap.add_argument('--rows', type=int, default=50)
    args = ap.parse_args()

    task = ' '.join(args.task.split())[:4000]
    if not task:
        print('ERROR: empty task')
        return 2

    cwd = os.path.abspath(args.cwd)
    os.makedirs(cwd, exist_ok=True)
    outdir = os.path.dirname(args.out_prefix) or '.'
    os.makedirs(outdir, exist_ok=True)

    exe = shutil.which('freebuff')
    if not exe:
        print('ERROR: freebuff not on PATH')
        return 2
    try:
        ver = subprocess.run([exe, '--version'], capture_output=True, text=True, timeout=240)
        print('freebuff version:', ((ver.stdout or '') + (ver.stderr or '')).strip()[:200])
    except Exception as e:
        print('ERROR: freebuff --version failed:', e)
        return 2

    pid, fd = pty.fork()
    if pid == 0:
        os.chdir(cwd)
        env = dict(os.environ, TERM='xterm-256color', COLORTERM='truecolor')
        try:
            os.execvpe(exe, [exe, '--trust-agents'], env)
        finally:
            os._exit(127)
    fcntl.ioctl(fd, termios.TIOCSWINSZ, struct.pack('HHHH', args.rows, args.cols, 0, 0))

    t0 = time.time()
    raw_fh = open(args.out_prefix + '.raw', 'wb')
    buf = bytearray()
    typed_at = None
    last_change = time.time()
    last_len = -1
    deadline = t0 + args.max_minutes * 60.0
    reason = 'timeout'

    while True:
        now = time.time()
        if now > deadline:
            reason = 'max_time'
            break
        try:
            r, _, _ = select.select([fd], [], [], 0.5)
        except InterruptedError:
            continue
        if r:
            try:
                data = os.read(fd, 65536)
            except OSError:
                data = b''
            if not data:
                reason = 'eof'
                break
            raw_fh.write(data)
            raw_fh.flush()
            buf.extend(data)
            if len(buf) > 4_000_000:
                del buf[:2_000_000]
        if typed_at is None and now - t0 >= args.boot_seconds:
            os.write(fd, task.encode('utf-8', 'replace') + b'\r')
            typed_at = now
            last_change = now
        elif typed_at is not None and now - typed_at > 5:
            cl = len(clean(bytes(buf[-200000:])))
            if cl != last_len:
                last_len = cl
                last_change = now
            elif now - last_change >= args.idle_seconds:
                reason = 'idle'
                break

    tail = clean(bytes(buf[-400000:]))
    try:
        with open(args.out_prefix + '.txt', 'w') as f:
            f.write('=== freebuff-cloud transcript (cleaned) ===\n')
            f.write('task: %s\nreason: %s\n\n' % (task[:500], reason))
            f.write(tail)
    except Exception as e:
        print('WARN: transcript write failed:', e)
    raw_fh.close()

    low = tail.lower()
    if 'waiting for login' in low or 'auth_code=' in low:
        verdict, code = 'login_required', 4
    elif typed_at is not None and len(tail) > 600:
        verdict, code = 'ran', 0
    else:
        verdict, code = 'inconclusive', 3

    print('== freebuff-cloud verdict: %s (reason=%s, exit=%d)' % (verdict, reason, code))
    print('== transcript tail ==')
    print(tail[-12000:])

    try:
        os.killpg(pid, signal.SIGKILL)
    except Exception:
        pass
    try:
        os.waitpid(pid, 0)
    except Exception:
        pass
    return code


if __name__ == '__main__':
    sys.exit(main())
