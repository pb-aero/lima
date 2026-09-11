# EKF standing-drift dataset — 2026-09-11

Position and attitude logged from ArduPlane's EKF3 at 40 Hz for 150 s while the flight controller
sat **stationary** on the bench. `[measured]` on `Raspberry Pi 5 Model B Rev 1.1`, machine-id
`49cc4b68da3b4dfd9d10cc78207fe9eb`, native `--board=pi5`, stock driver.

| File | What it is |
|---|---|
| `ahrs_drift_track.geojson` | 3D `LineString` (CRS84, lon/lat/alt-MSL) + 151 one-per-second `Point` features carrying roll/pitch/yaw, NED velocity, GPS fix, sats and eph. **Loads directly in ArcGIS Pro / ArcGIS Online.** |
| `ahrs_drift_track.kml` | Same track, `altitudeMode=absolute` with extrusion. For ArcGIS Earth or Google Earth. |
| `ekf_drift_3d.html` | Self-contained 3D viewer, no dependencies. Also published as an Artifact. |
| `ahrs_track_raw.json` | The 6040 raw samples, for anything else. |

## The measurement

| | |
|---|---|
| samples | 6040 over 150 s (40 Hz) |
| drift E–W | 0.71 m |
| drift N–S | 2.34 m |
| drift vertical | **3.45 m** — the largest axis |
| radial from centroid | mean 0.96 m, p95 1.96 m, **max 2.45 m** |
| GPS | 3D fix, 21 sats, **eph 0.73 m** |
| EKF flags | `0x00A7` — `CONST_POS_MODE` **set**, `POS_HORIZ_ABS` **clear** |

**The filter drifted 2.45 m while the receiver feeding it was accurate to 0.73 m.** That is not a GPS
problem. EKF3 was in constant-position mode: with no calibrated compass there is no usable yaw
reference, so it refused to fuse GPS horizontally and coasted on an uncalibrated accelerometer
(10.28 m/s² against g = 9.807, a 4.8 % scale error, plus a 0.217 m/s² offset on X).

**Do not read the variances as reassurance.** `velVar 0.00119, posVar 0.00149` look excellent, but in
constant-position mode the position variance is small because position is *held*, not *known*.

## A note on ArcGIS

The ArcGIS Maps SDK for JavaScript cannot run inside a published Artifact: the sandbox CSP admits
scripts only from a short allowlist that does not include `js.arcgis.com`, and it blocks the
stylesheet and the runtime asset fetches the SDK makes. Hence the split — Esri-native **data** files
for ArcGIS proper, and a dependency-free viewer for looking at it immediately.
