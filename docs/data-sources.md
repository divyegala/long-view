# Connecting ride-data sources

Supported paths: FIT/ZIP upload, direct Intervals.icu API downloads, and neutral JSON prepared by an agent using an authorized MCP. The neutral importer needs no service API key.

Discover available MCP tools rather than assuming tool names. Fetch permitted original streams, write a local bundle under data/, then run:

```sh
python import_rides.py data/import-bundle.json
python server.py --warm
```

Refresh the browser afterward. Sample/metadata revisions invalidate analysis caches. Restart after server code changes. Run one importer at a time, outside an active direct-download job.

## Bundle contract

```json
{
  "schema": "LONG_VIEW_IMPORT_V1",
  "source": "example-provider",
  "activities": [{
    "activity": {
      "id": "source-activity-id",
      "start_local": "2020-01-01T09:00:00",
      "type": "VirtualRide",
      "name": "Example ride",
      "duration_minutes": 120,
      "elapsed_minutes": 125,
      "timezone": "Europe/London",
      "recorded_ftp": 250,
      "power_source": "measured pedals"
    },
    "recording": {
      "timeline": "one_second_with_stops",
      "provenance": "Authorized original source; illustrative synthetic rows here",
      "rows": [
        [0, 140, 120, 85, 5.2],
        [1, 142, 121, 86, 5.3],
        [2, null, 121, 85, 5.2]
      ]
    }
  }]
}
```

These three rows illustrate shape, not a complete two-hour recording. Generate complete synthetic rides with examples/make_demo.py.

| Field | Contract |
| --- | --- |
| source | Provider slug, 1–32 letters, digits, underscore or hyphen. |
| activity.id | Source-native ID string. Importer derives a stable provider-namespaced local ID; reimport updates it. |
| start_local | ISO local wall datetime without offset. Convert UTC using the athlete's timezone, never an assumed execution-host timezone. |
| duration_minutes | Measured moving minutes, positive. Needed for eligibility and minutes of work per moving hour. Do not replace unknown duration with zero. |
| type | Ride, VirtualRide, MountainBikeRide, GravelRide, TrackRide or Cyclocross. VirtualRide or trainer=true selects the indoor reference. |
| Other metadata | Optional supplied metrics/provenance are preserved: avg_hr, avg_watts, np_watts, distance_m, recorded_ftp, device, etc. Preserve source meanings. |
| recording | Object, null or omitted for catalog-only data. Metadata-only resync preserves an existing recording. |
| rows | Strictly increasing [elapsed_seconds, watts, bpm, rpm, speed_mps]. Integer seconds since session start, including stopped time. Unknown samples are null. |
| timeline | Must be one_second_with_stops: available observations are one second apart except known stops. |

Null power at a recorded timestamp invalidates windows crossing it. Absent timestamps represent zero-power stops under this model. Continuous zero-power rows recover workload too, but are not separately counted as recording gaps.

Sparse smart recording may omit actual riding. Obtain pause events and true elapsed timestamps or implement/test an explicit source-aware adapter. Do not interpolate unknown watts into false completeness. Use catalog-only import if pause semantics are unavailable.

## Provider mapping examples

These are correspondences, not guaranteed MCP tool names or access.

| Provider | Typical mapping |
| --- | --- |
| Intervals.icu | ID, start_date_local/start_local, moving_time seconds to minutes or supplied duration_minutes; streams time, watts, heartrate, cadence, velocity_smooth. Honor connector source fences and calculation rules. |
| Strava | ID, start_date_local, moving_time seconds to minutes, sport/type and trainer flag; permitted streams time, watts, heartrate, cadence, velocity_smooth. Verify measured versus estimated watts, time-axis semantics and permitted analysis. |
| Other MCPs | Discover equivalent metadata/original samples, read units and pause semantics, then map to this contract. A summary or power curve cannot reconstruct a recording. |

Supplied provider metrics remain distinct from local analysis. Respect any quoting, recomputation or AI-use restrictions. Local curves require separately authorized original recordings; do not route around a restriction.

FIT upload uses the standard FIT power channel. A dual-recording adapter must inspect developer-field descriptions before choosing pedal/trainer power. Preserve originals; never silently blend channels.

## Local store

- data/catalog.json: all known cycling activities, including metadata-only entries.
- data/streams/<id>.json: normalized original samples (LONG_VIEW_STREAM_V1).
- data/analysis/: reproducible caches keyed by settings, model version and input revision.
- data/notes.json: athlete context, RPE and observations.
- data/originals/: optional original files.

The entire data/ directory is ignored by Git. Do not place real imports in examples/ or tests/. Settings affect only this app. Configure each athlete's own references.
