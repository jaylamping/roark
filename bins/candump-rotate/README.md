# candump-rotate

The CAN black box ([PLAN "Observability"](https://github.com/jaylamping/roark/blob/main/PLAN.md#observability-tenet-8),
logging.md section 8.6): one per bus, run by `candump@<bus>.service`. It starts `candump`, and writes everything
`candump` prints to compressed files that it cuts on a timer and deletes after a set number of days. It sees what the
kernel saw on the bus whether the runtime is running, hung, crashed or buggy, so a frame the runtime's recording lost is
still here.

## What it does

- **Runs the command after `--`** (in the unit, `candump -L -x -d -D` on the bus with every error frame) with its output
  on a pipe, and reads it a line at a time. `candump` can't cut its own files, and restarting it to cut one would leave
  a gap; one long-running `candump` and a cut on a line boundary leave none.
- **Writes `<dir>/<bus>-<UTC start>.log.zst`**, zstd at the default level, with the start in ISO 8601 basic form
  (`can0-20261112T032642Z.log.zst`). A restart in the same second gets `-1`, `-2`, never overwriting a file. A file is
  opened at the first line after a cut, so a quiet bus makes no empty files.
- **Ends a zstd block every second.** A file cut off by a crash or a power loss still reads back (`zstdcat` prints
  everything up to the last block, then complains about the end), losing at most the last second.
- **Cuts every `--cut-secs`** on the next line or the next second's check, whichever is first: the zstd frame is ended,
  the file synced, and the next line opens the next file. A file that ends cleanly decompresses without error.
- **Deletes this bus's files last written more than `--keep-days` ago**, at start and after every cut, and says each one
  it deleted in the journal. Other buses' files and anything else in the directory are left alone. The session's MCAP
  holds the same frames (logging.md section 8.7).
- **Holds up to 65,536 lines** between reading and writing, so a disk stall of a few seconds costs nothing. Past that,
  `candump` waits, the kernel drops frames, and `candump -d` writes the drop count into the log as a `DROPCOUNT` line.
- **Ends when the command does,** closing its file cleanly. SIGTERM, SIGINT and SIGHUP are passed on to the command, so
  stopping the unit ends `candump`, then this. A failed write (a full disk) stops `candump` and exits non-zero;
  systemd starts it again after its `RestartSec`, which prunes first.

Reading a file back: `zstdcat can0-20261112T032642Z.log.zst`, or feed it to `canplayer -I -` to replay it onto `vcan`
(logging.md section 8.8).

## Must never

- **Send on a bus or open a CAN socket.** It only reads what the command prints; `candump` listens and never sends.
- **Depend on the runtime.** No lock, no session, no skeleton: it runs whether or not the runtime does.
- **Overwrite or delete a file it didn't make for this bus.** Names are matched exactly (`can1-` never matches `can10-`).

## Talks to

No workspace crate: only `zstd` and `nix` (signals), so a bug in the runtime's code can't reach the black box. Its input is
`candump` from can-utils. See the [map](https://github.com/jaylamping/roark/blob/main/conventions/architecture.md).

## Using it

On the Pi, enable one unit per skeleton bus. Each starts when its interface appears and stops when it goes away:

```bash
sudo systemctl enable --now candump@can0.service candump@can1.service
journalctl -u candump@can0.service            # cuts, prunes, and anything candump said
ls /var/lib/robot/candump/
zstdcat /var/lib/robot/candump/can0-20261112T032642Z.log.zst | less
```

By hand, on `vcan`, cutting every 10 seconds:

```bash
candump-rotate --bus vcan0 --dir /tmp/blackbox --cut-secs 10 --keep-days 1 -- candump -L -x -d -D 'vcan0,0:0,#FFFFFFFF'
```

The sim suite runs it against `candump` on `vcan` (`crates/sim-suite/tests/blackbox.rs`).
