use std::time::Duration;

use robstride::{DeviceId, Frame, Inbound, decode, drive};

use super::{
    BusFault, BusStop, DISABLE_WINDOW, Drain, END, OsError, Outcome, REPORT_GRACE,
    REPORTING_OFF_TRIES, RESEND, SILENCE, SendError, Wait,
};

const MS: Duration = Duration::from_millis(1);

/// Frames the stop sent, each with its time in milliseconds: `('D', n)` a Disable, `('R', n)` reporting off.
type Sent = [(u64, (char, u8))];
/// What `run` returns: every frame sent, and when the stop ended.
type Run = (Vec<(u64, (char, u8))>, Duration);

fn id(n: u8) -> DeviceId {
    DeviceId::new(u64::from(n)).unwrap()
}

fn ms(d: Duration) -> u64 {
    u64::try_from(d.as_millis()).unwrap()
}

/// A status (or report) from drive `n`: type 2 (or 24), mode in ID bits 23..22, the drive in bits 15..8.
fn from(n: u8, run: bool, report: bool) -> Inbound {
    let kind: u32 = if report { 24 } else { 2 };
    let mode: u32 = if run { 2 } else { 0 };
    decode(
        (kind << 24) | (mode << 22) | (u32::from(n) << 8) | 0xFD,
        &[0x80, 0, 0x80, 0, 0x80, 0, 0, 0xFA],
    )
    .unwrap()
}

fn what(frame: Frame) -> (char, u8) {
    let host = drive::command(frame.id(), &frame.data()).unwrap().unwrap();
    let kind = match host.command {
        drive::Command::Disable => 'D',
        drive::Command::Reporting(robstride::Reporting::Off) => 'R',
        _ => '?',
    };
    assert_ne!(kind, '?', "the stop sent {:?}", host.command);
    (kind, host.target.get())
}

/// Run `stop` a millisecond at a time to its end, `answer` giving the drives' frames at each millisecond from the
/// frames sent so far. Returns every frame sent and when the stop ended.
fn run(
    stop: &mut BusStop,
    answer: &dyn Fn(u64, &Sent) -> Vec<Inbound>,
    send: &dyn Fn(u64, (char, u8)) -> Result<(), SendError>,
) -> Run {
    let mut log = Vec::new();
    let mut now = Duration::ZERO;
    while stop.wait(now) != Wait::Done {
        for inbound in answer(ms(now), &log) {
            stop.heard(now, &inbound);
        }
        let mut out = Vec::new();
        stop.step(now, &mut |f| {
            let w = what(f);
            send(ms(now), w).map(|()| out.push((ms(now), w)))
        });
        log.extend(out);
        now += MS;
    }
    assert!(now <= END + MS, "the stop ran past its end: {now:?}");
    (log, now)
}

fn times(sent: &Sent, frame: (char, u8)) -> Vec<u64> {
    sent.iter()
        .filter(|(_, w)| *w == frame)
        .map(|(t, _)| *t)
        .collect()
}

fn outcomes(stop: &BusStop, end: Duration) -> Vec<Outcome> {
    stop.outcomes(end).into_iter().map(|(_, o)| o).collect()
}

/// Guards: safety - the independent stop's sequence (PLAN item 2, Stop): a Disable to every drive at once, sent
/// again each tick to a drive not read in Reset for 100 ms; reporting off only after the post-Disable silence (54 ms
/// after the Reset read, 150 ms for a drive never read in Reset); and the outcome is what was read: a drive read in
/// Reset is stopped, one that never answered is silent, one that answered only in Run needs a person, and one that went
/// back to Run after a Reset gets Disables again and, if its reporting off had gone, a new one after the new silence.
#[test]
fn disables_go_to_every_drive_until_reset_then_reporting_off_after_the_silence() {
    // 11 answers each Disable 1 ms later in Reset; 12 never answers; 13 answers each Disable in Run; 14 answers in
    // Reset, then reports in Run at 30 ms (another controller enabled it); 15 answers in Reset, then reports in Run at
    // 60 ms, after its first reporting off.
    let answer = |now: u64, sent: &Sent| {
        let mut out = Vec::new();
        for (t, w) in sent {
            if *t + 1 == now {
                match w {
                    ('D', 11 | 14 | 15) => out.push(from(w.1, false, false)),
                    ('D', 13) => out.push(from(13, true, false)),
                    _ => {}
                }
            }
        }
        if now == 30 {
            out.push(from(14, true, true));
        }
        if now == 60 {
            out.push(from(15, true, true));
        }
        out
    };
    let mut stop = BusStop::new([id(11), id(12), id(13), id(14), id(15)]);
    let (sent, end) = run(&mut stop, &answer, &|_, _| Ok(()));

    // Every drive's first Disable goes in the first step, before any reporting off.
    let first: Vec<(char, u8)> = sent.iter().take(5).map(|(_, w)| *w).collect();
    assert_eq!(
        first,
        [('D', 11), ('D', 12), ('D', 13), ('D', 14), ('D', 15)]
    );
    let every_tick: Vec<u64> = (0..ms(DISABLE_WINDOW)).step_by(4).collect();
    assert_eq!(times(&sent, ('D', 11)), [0]);
    assert_eq!(times(&sent, ('D', 12)), every_tick);
    assert_eq!(times(&sent, ('D', 13)), every_tick);
    // 14's Disables start again once it is seen in Run, and it is confirmed again a tick later.
    assert_eq!(times(&sent, ('D', 14)), [0, 30]);
    assert_eq!(times(&sent, ('R', 11)), [ms(MS + SILENCE + RESEND)]);
    assert_eq!(times(&sent, ('R', 12)), [ms(DISABLE_WINDOW + SILENCE)]);
    assert_eq!(times(&sent, ('R', 13)), [ms(DISABLE_WINDOW + SILENCE)]);
    assert_eq!(times(&sent, ('R', 14)), [ms(31 * MS + SILENCE + RESEND)]);
    // 15's second reporting off waits out the silence its new Disable began, rather than going inside it.
    assert_eq!(times(&sent, ('D', 15)), [0, 60]);
    assert_eq!(
        times(&sent, ('R', 15)),
        [ms(MS + SILENCE + RESEND), ms(61 * MS + SILENCE + RESEND)]
    );
    assert_eq!(
        outcomes(&stop, end),
        [
            Outcome::Stopped,
            Outcome::Silent,
            Outcome::NotReset,
            Outcome::Stopped,
            Outcome::Stopped
        ]
    );
    assert!(stop.fault().is_none());
}

/// Guards: bug - drives left reporting by a faulted session flooded every later start, marengo
/// `docs/safety.md` "Reporting Off at exit (2026-10-04)": a drive still reporting after its reporting off gets it
/// again, at most `REPORTING_OFF_TRIES` times, and is reported as needing a person if it never stops; a report
/// already on its way when reporting off went doesn't count.
#[test]
fn reporting_off_is_sent_again_while_reports_keep_coming() {
    // In Reset and reporting every 10 ms: 21 stops after its second reporting off, 22 never stops, and 23 stops
    // after its first but sends one last report just inside the grace.
    let answer = |now: u64, sent: &Sent| {
        let mut out = Vec::new();
        for (n, stops_after) in [(21, 2), (22, usize::MAX), (23, 1)] {
            let offs = times(sent, ('R', n));
            if now.is_multiple_of(10) && offs.len() < stops_after {
                out.push(from(n, false, true));
            }
            if n == 23
                && offs
                    .first()
                    .is_some_and(|off| now == off + ms(REPORT_GRACE) - 1)
            {
                out.push(from(n, false, true));
            }
        }
        out
    };
    let mut stop = BusStop::new([id(21), id(22), id(23)]);
    let (sent, end) = run(&mut stop, &answer, &|_, _| Ok(()));
    assert_eq!(times(&sent, ('R', 21)).len(), 2);
    assert_eq!(
        times(&sent, ('R', 22)).len(),
        usize::from(REPORTING_OFF_TRIES)
    );
    assert_eq!(times(&sent, ('R', 23)).len(), 1);
    assert_eq!(
        outcomes(&stop, end),
        [Outcome::Stopped, Outcome::StillReporting, Outcome::Stopped]
    );
}

/// Guards: safety - a socket failure on one bus (PLAN item 6, `host.bus`): a full queue only delays a frame to the
/// next wake; any other write error fails the bus at once and sends nothing more on it, also after a read failure; a
/// read failure lets the frames go on but confirms nothing; and a drive that never answers on a bus that went bus-off,
/// or whose errors can't be seen, isn't taken for one that is off, while lesser error frames don't count. Each failure
/// needs a person.
#[test]
fn socket_failures_and_error_frames_need_a_person() {
    let echo = |now: u64, sent: &Sent| -> Vec<Inbound> {
        sent.iter()
            .filter(|(t, w)| *t + 1 == now && w.0 == 'D')
            .map(|(_, w)| from(w.1, false, false))
            .collect()
    };
    // The queue is full for the first 2 ms: every Disable goes at 2 ms, all at once.
    let mut full = BusStop::new([id(11), id(12)]);
    let (sent, end) = run(&mut full, &echo, &|now, _| {
        if now < 2 {
            Err(SendError::Full)
        } else {
            Ok(())
        }
    });
    assert_eq!(times(&sent, ('D', 11)), [2]);
    assert_eq!(times(&sent, ('D', 12)), [2]);
    assert_eq!(outcomes(&full, end), [Outcome::Stopped, Outcome::Stopped]);

    // The interface goes away on the second Disable of the first step: nothing more is sent, the stop is over.
    let mut gone = BusStop::new([id(11), id(12)]);
    let (sent, end) = run(&mut gone, &|_, _| Vec::new(), &|_, w| {
        if w == ('D', 12) {
            Err(SendError::Failed(OsError(19)))
        } else {
            Ok(())
        }
    });
    assert_eq!(sent, [(0, ('D', 11))]);
    assert_eq!(gone.fault(), Some(BusFault::Write(OsError(19))));
    assert_eq!(
        outcomes(&gone, end),
        [Outcome::BusFailed, Outcome::BusFailed]
    );

    // Reads fail after 11 is confirmed: every frame still goes, and nothing on the bus counts as confirmed.
    let mut deaf = BusStop::new([id(11), id(12)]);
    let mut now = Duration::ZERO;
    let mut sent = 0;
    while deaf.wait(now) != Wait::Done {
        if now == MS {
            deaf.heard(now, &from(11, false, false));
            deaf.fail(BusFault::Read(OsError(5)));
        }
        deaf.step(now, &mut |_| {
            sent += 1;
            Ok(())
        });
        now += MS;
    }
    assert_eq!(sent, 1 + ms(DISABLE_WINDOW) / 4 + 2);
    assert_eq!(
        outcomes(&deaf, now),
        [Outcome::BusFailed, Outcome::BusFailed]
    );

    // Reads fail, then the interface goes: the write failure still ends the sending.
    let mut down = BusStop::new([id(11)]);
    down.fail(BusFault::Read(OsError(5)));
    let (sent, _) = run(&mut down, &|_, _| Vec::new(), &|now, _| {
        if now < 8 {
            Ok(())
        } else {
            Err(SendError::Failed(OsError(100)))
        }
    });
    assert_eq!(times(&sent, ('D', 11)), [0, 4]);
    assert_eq!(down.fault(), Some(BusFault::Write(OsError(100))));

    // Bus-off, even after a drive was confirmed, fails every drive on the bus: a late report or Run may have been
    // lost. Errors that can't be seen make a silent drive need a person. Lesser error frames (controller 0x04, ACK
    // 0x20) are what an unpowered bus sends, and don't count.
    let mut off = BusStop::new([id(11), id(12)]);
    let (_, end) = run(&mut off, &echo, &|_, _| Ok(()));
    assert_eq!(outcomes(&off, end), [Outcome::Stopped, Outcome::Stopped]);
    off.heard_error_frame(0x40, 0);
    assert!(off.bus_off());
    assert_eq!(
        outcomes(&off, end),
        [Outcome::BusFailed, Outcome::BusFailed]
    );
    let mut unseen = BusStop::new([id(11)]);
    unseen.cant_see_errors(OsError(92));
    let (_, end) = run(&mut unseen, &|_, _| Vec::new(), &|_, _| Ok(()));
    assert_eq!(outcomes(&unseen, end), [Outcome::SilentErrorsUnseen]);
    let mut lesser = BusStop::new([id(11)]);
    lesser.heard_error_frame(0x04, 0x10);
    lesser.heard_error_frame(0x20, 0);
    let (_, end) = run(&mut lesser, &|_, _| Vec::new(), &|_, _| Ok(()));
    assert_eq!(outcomes(&lesser, end), [Outcome::Silent]);
    assert_eq!(lesser.error_frames(), 2);
    // An RX overflow (controller class, data[1] 0x01): frames were lost, so no drive on the bus counts as ok.
    let mut lost = BusStop::new([id(11), id(12)]);
    let (_, end) = run(&mut lost, &echo, &|_, _| Ok(()));
    lost.heard_error_frame(0x04, 0x01);
    assert_eq!(outcomes(&lost, end), [Outcome::Unread, Outcome::Unread]);
}

/// Guards: safety - a drive is reported stopped only on what was read (PLAN item 2, Stop): frames still queued when
/// the stop ends (a drain stopped at its bound) may hold a Run that withdraws a Reset, so a confirmed drive then needs
/// a person; before the end, queued frames are read before any wait; and a stop cut before a drive's watch ends
/// doesn't report it stopped.
#[test]
fn frames_left_unread_when_the_stop_ends_need_a_person() {
    let echo = |now: u64, sent: &Sent| -> Vec<Inbound> {
        sent.iter()
            .filter(|(t, w)| *t + 1 == now && w.0 == 'D')
            .map(|(_, w)| from(w.1, false, false))
            .collect()
    };
    let mut stop = BusStop::new([id(11)]);
    let (_, end) = run(&mut stop, &echo, &|_, _| Ok(()));
    assert_eq!(outcomes(&stop, end), [Outcome::Stopped]);
    stop.drained(Drain::Capped);
    assert_eq!(stop.wait(END), Wait::Done);
    assert_eq!(outcomes(&stop, end), [Outcome::Unread]);

    let mut early = BusStop::new([id(11)]);
    early.step(Duration::ZERO, &mut |_| Ok(()));
    early.drained(Drain::Capped);
    assert_eq!(early.wait(MS), Wait::DrainAgain);
    early.drained(Drain::Emptied);
    assert_eq!(early.wait(MS), Wait::Until(RESEND));

    // Read in Reset, then cut before its reporting off's watch ends.
    let mut cut = BusStop::new([id(11)]);
    cut.step(Duration::ZERO, &mut |_| Ok(()));
    cut.heard(MS, &from(11, false, false));
    let off = MS + SILENCE + RESEND;
    cut.step(off, &mut |_| Ok(()));
    assert_eq!(outcomes(&cut, off + MS), [Outcome::WatchCut]);
}

/// Guards: safety - a drive is reported ok only on what was sent and read (PLAN item 2, Stop): one whose Disable never
/// left (and so gets no reporting off), whose reporting off left too late to be watched, or whose current reporting
/// off never left after a withdrawn Reset, needs a person rather than counting as silent or stopped.
#[test]
fn a_frame_that_never_leaves_needs_a_person() {
    // The queue is full until the Disable window ends, then empty: drive 11 never got a Disable.
    let mut never = BusStop::new([id(11)]);
    let (sent, end) = run(&mut never, &|_, _| Vec::new(), &|now, _| {
        if now < ms(DISABLE_WINDOW) {
            Err(SendError::Full)
        } else {
            Ok(())
        }
    });
    assert_eq!(times(&sent, ('D', 11)), []);
    assert_eq!(
        times(&sent, ('R', 11)),
        [],
        "no reporting off before a Disable"
    );
    assert_eq!(outcomes(&never, end), [Outcome::QueueFull]);

    // Never answers; its Disable goes at 0 ms, then the queue is full until 290 ms, so its reporting off goes too late
    // for its watch to end before the stop does.
    let mut late = BusStop::new([id(12)]);
    let (sent, end) = run(&mut late, &|_, _| Vec::new(), &|now, _| {
        if now == 0 || now >= 290 {
            Ok(())
        } else {
            Err(SendError::Full)
        }
    });
    assert_eq!(times(&sent, ('R', 12)), [290]);
    assert_eq!(outcomes(&late, end), [Outcome::WatchCut]);

    // Confirmed, its first reporting off goes, then it is seen in Run and in Reset again; from then on the queue is
    // full, so the new schedule's reporting off never leaves.
    let mut stuck = BusStop::new([id(11)]);
    let (sent, end) = run(
        &mut stuck,
        &|now, _| match now {
            1 | 61 => vec![from(11, false, false)],
            60 => vec![from(11, true, false)],
            _ => Vec::new(),
        },
        &|now, _| {
            if now < 61 {
                Ok(())
            } else {
                Err(SendError::Full)
            }
        },
    );
    assert_eq!(times(&sent, ('R', 11)), [ms(MS + SILENCE + RESEND)]);
    assert_eq!(outcomes(&stuck, end), [Outcome::QueueFull]);
}
