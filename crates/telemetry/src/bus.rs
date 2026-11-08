//! (rt) The bus thread's half of the recorder: one lock-free ring per bus, pushed once a tick.

use rtrb::{Consumer, Producer, PushError, RingBuffer};

use crate::batch::{Loss, TickBatch};

/// Two seconds of ticks at 250 Hz (logging.md section 8.4: start at two seconds; the bench soak sizes it from measured
/// storage stalls).
pub const RING_BATCHES: usize = 500;

/// What a bus thread holds to record its ticks. [`Self::record`] never blocks, allocates or makes a system call: when
/// the recorder has fallen behind it drops the batch, counts it, and hands the count over with the next batch that fits
/// (or at [`Recording::close`](crate::Recording::close)), so the hole shows in the file as a gap record.
#[derive(Debug)]
pub struct BusRecorder {
    bus: usize,
    producer: Producer<TickBatch>,
    pending: Loss,
}

impl BusRecorder {
    /// Hand over one tick's batch. Returns false if the ring was full and the batch was dropped. A recorder that has
    /// failed or stopped is not seen here; the enable gate reads [`Health`](crate::Health) for that.
    pub fn record(&mut self, mut batch: TickBatch) -> bool {
        batch.lost_before = self.pending;
        match self.producer.push(batch) {
            Ok(()) => {
                self.pending = Loss::default();
                true
            }
            Err(PushError::Full(batch)) => {
                self.pending.add(&batch);
                false
            }
        }
    }

    /// The bus's index in the session's bus table.
    #[must_use]
    pub fn bus(&self) -> usize {
        self.bus
    }

    /// Batches dropped and not yet handed to the recorder.
    #[must_use]
    pub fn pending(&self) -> Loss {
        self.pending
    }
}

/// The recorder's end of one bus's ring.
#[derive(Debug)]
pub(crate) struct BusDrain {
    pub(crate) consumer: Consumer<TickBatch>,
}

/// A ring for bus `bus` holding `capacity` batches.
pub(crate) fn ring(bus: usize, capacity: usize) -> (BusRecorder, BusDrain) {
    let (producer, consumer) = RingBuffer::new(capacity);
    (
        BusRecorder {
            bus,
            producer,
            pending: Loss::default(),
        },
        BusDrain { consumer },
    )
}
