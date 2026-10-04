# Serial turn-taking in the current sketch

This describes the code in `firmware/perfusion_rig/perfusion_rig.ino`; it is not
a tested transport implementation or a hardware commissioning procedure. The
Python CLI prints and simulates commands but does not open a serial port.

| Current sketch state | Command | Observed transition / reply |
|---|---|---|
| Any | `DIA`, `PITCH`, `MICRO` | Updates a setting if accepted, even during a RUN; no success acknowledgement. Current step timing is not recomputed until `FLOW`. |
| Idle | `FLOW` | Sets direction and step interval; no success acknowledgement. No steps occur until `RUN`. |
| Idle | `RUN` | Starts a timer; no immediate success acknowledgement. |
| Running | Timer expires | Stops motion, clears flow, prints `OK DONE`. This reports timer completion, not measured delivered volume. |
| Running | `FLOW` or `RUN` | Changes flow or replaces the timer while motion is active. There is no queue. |
| Any | `STOP` | Stops motion, clears flow, prints `OK STOP`; the interrupted RUN does not later print `OK DONE`. |
| Any | `STATUS` | Prints flow and step count as two unframed lines; it is not an acknowledgement for earlier settings. |
| Any | Invalid command | May print `ERR ...`; the sketch does not implement the host's full validation. |

For a future serial transport, one RUN must be treated as outstanding until
`OK DONE` arrives. It must not send the next `FLOW`, `RUN`, or final `STOP`
from an `encode()` script while that RUN is outstanding. `OK STOP` indicates an
interruption, not successful completion. A timeout or `ERR` cannot be counted
as delivered volume. Configuration commands currently have no positive
acknowledgement, so this protocol is insufficient for reliable automated
operation without firmware work and hardware testing.

The host simulator assumes completed sequential commands and ideal signed
displacement. The sketch has no measured flow feedback, occlusion detection,
pressure limit, or validated pulse-volume calibration. It is not an infusion
pump and is not for animals or people.

Run timers and pulse clocks use explicit 32-bit elapsed arithmetic. Each RUN
starts its pulse baseline at the command time, so a long preceding idle period
does not create an immediate pulse. RUN duration must be at least 0.001 seconds
and is converted to whole milliseconds; submillisecond precision is unsupported.
Native harness regressions cover clock rollover and sequential completion. These
checks do not establish timing accuracy, serial latency, or delivered volume on
a physical board.
