# Enclosure revisions

| Rev | Date (2026) | Change |
|---|---|---|
| A–C | to 27 Aug | Early geometry: a 178–180 mm cube with a fixed back panel. Superseded |
| D–E | 28 Aug | Back panel made to slide in glued rails; independent DXF audit added; time-of-flight geometry removed from the panels |
| F | 29 Aug | Finger slot moved off the top edge; six toggle holes added to the lid; engrave-layer checks added to the audit |
| G | 29 Aug | Apertures resized from stated dimensions; display clamp frame reworked; flame reducer ring added |
| H | 29 Aug | First revision in which apertures are derived from measured parts. Speaker returned to Ø46 from Ø53 by arithmetic on the driver's flange. Test-cut card and partial nests added |
| **J** | **30 Aug** | **The five faults found by the physical test cut, fixed.** Microphone Ø15.5, two square display frames with corner pads, one DHT11 relief, flame Ø5.5 direct, reducer ring deleted. Audit 21 / 21. See [`TEST_CUT_POSTMORTEM.md`](TEST_CUT_POSTMORTEM.md) |

Rev J is the released, audited design, and it is what the generator in this folder produces.

## After Rev J — the 3 September re-cut

Three plates — front, left and right — were re-issued on 3 September with apertures taken from fresh hand measurements. They are kept in [`recut_2026-09-03/`](recut_2026-09-03/) exactly as issued.

| Feature | Rev J | 3 September plates |
|---|---|---|
| Speaker cut-out | Ø46 | Ø53 |
| Speaker bolts | 4 × M3 on a 40 × 40 square | 4 × M3 on a 45 × 45 square |
| Microphone | Ø15.5 | Ø11 |
| Flame | Ø5.5 | Ø5 |
| Display retention | Two cross-opening clamp frames | One 108 × 96 back-support plate with a 67 × 53 recess, plus a 5 × 10 slot beside the window for the shield's button |

The finger joints on these plates are unchanged, so they mate with the top, bottom, back panel, rails and stop strip from the Rev J sheet.

Two of these choices reverse Rev J on the same two parts the post-mortem discusses. The plates were issued with a small test piece to be cut and checked first. They are not produced by the generator in this folder and were not run through the full-sheet audit, so treat Rev J as the reproducible reference and these as a recorded variant.
