//! `host.mode`'s limb-mate clause (PLAN item 6, #25): while a limb is held, a drive of it that this host never enabled,
//! seen out of Reset, stops the whole limb. The bus latches such a drive's excursions in `DriveView::out_of_reset`
//! but stops nothing for a drive it never enabled, so control runs this over every drive of each held limb, on every
//! bus the limb is on, each pass.

use can::DriveView;

use crate::rule::RuleId;

/// One drive of a held limb, as the clause sees it.
#[derive(Clone, Copy, Debug)]
pub struct Mate<'a> {
    /// Its newest view, from its own bus's newest snapshot; `None` when control has none.
    pub view: Option<&'a DriveView>,
    /// Whether this host enabled it, or is enabling it: its own modes are then watched by the bus and the sequence.
    pub enabled_here: bool,
}

/// Whether the limb may go on being held.
#[derive(Clone, Copy, Debug, PartialEq, Eq)]
pub enum HoldVerdict {
    /// Every drive this host didn't enable is seen and has stayed in Reset.
    Hold,
    /// Stop the whole limb, under this rule.
    Stop(RuleId),
}

/// The verdict for a held limb over all its drives: a drive this host didn't enable that something else took out of
/// Reset (latched since the limb's last re-arm), or that can't be seen at all, stops the limb (fail closed).
#[must_use]
pub fn limb_mates<'a>(mates: impl IntoIterator<Item = Mate<'a>>) -> HoldVerdict {
    let stop = mates
        .into_iter()
        .any(|m| !m.enabled_here && m.view.is_none_or(|v| v.out_of_reset.is_some()));
    if stop {
        HoldVerdict::Stop(RuleId::HostMode)
    } else {
        HoldVerdict::Hold
    }
}

#[cfg(test)]
mod tests {
    use can::{ModeSeen, StopOutcome};
    use robstride::{DeviceId, Mode};

    use super::*;

    fn view(out_of_reset: Option<Mode>) -> DriveView {
        DriveView {
            device: DeviceId::new(12).unwrap(),
            limb: 0,
            observed: None,
            mode: None,
            out_of_reset: out_of_reset.map(|mode| ModeSeen { mode, read_ns: 5 }),
            fresh_ns: None,
            fresh_status: None,
            answered: false,
            fault_seen: false,
            misses: 0,
            last_echo: None,
            stop: StopOutcome::None,
            reporting_off_sent: false,
        }
    }

    /// Guards: safety - host.mode: a held limb stops when a drive of it this host never enabled is seen out of Reset (Run or
    /// Calibration, latched since the re-arm), or can't be seen at all, on whichever bus it is; a drive this host
    /// enabled is the bus's and the sequence's to watch, and a limb whose other drives stayed in Reset holds (PLAN item
    /// 6 host.mode row, #25: stop the whole limb).
    #[test]
    fn a_limb_mate_out_of_reset_or_unseen_stops_the_held_limb() {
        let (reset, run, calibration) = (
            view(None),
            view(Some(Mode::Run)),
            view(Some(Mode::Calibration)),
        );
        let mate = |view, enabled_here| Mate { view, enabled_here };
        let stop = HoldVerdict::Stop(RuleId::HostMode);
        let cases = [
            (
                vec![mate(Some(&run), true), mate(Some(&reset), false)],
                HoldVerdict::Hold,
            ),
            (vec![mate(Some(&run), true), mate(Some(&run), false)], stop),
            (
                vec![mate(Some(&reset), true), mate(Some(&calibration), false)],
                stop,
            ),
            (vec![mate(Some(&reset), true), mate(None, false)], stop),
            (
                vec![mate(None, true), mate(Some(&reset), false)],
                HoldVerdict::Hold,
            ),
            (vec![mate(Some(&run), true)], HoldVerdict::Hold),
        ];
        for (i, (mates, verdict)) in cases.into_iter().enumerate() {
            assert_eq!(limb_mates(mates), verdict, "case {i}");
        }
    }
}
