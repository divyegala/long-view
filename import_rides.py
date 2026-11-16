#!/usr/bin/env python3
"""Import provider-neutral ride bundles prepared from an authorized data source."""
import argparse
import datetime
import hashlib
import json
import math
import os
import re
from pathlib import Path


def number(value):
    return isinstance(value, (int, float)) and not isinstance(value, bool) and math.isfinite(value)


def prepare_bundle(bundle):
    """Validate the complete bundle before modifying the local store."""
    if not isinstance(bundle, dict) or bundle.get('schema') != 'LONG_VIEW_IMPORT_V1':
        raise ValueError('Expected schema LONG_VIEW_IMPORT_V1.')
    source = bundle.get('source')
    if not isinstance(source, str) or not re.fullmatch(r'[a-zA-Z0-9_-]{1,32}', source):
        raise ValueError('source must be a short provider slug.')
    activities = bundle.get('activities')
    if not isinstance(activities, list) or not activities:
        raise ValueError('activities must be a non-empty list.')
    prepared = []
    seen = set()
    for entry in activities:
        meta = entry.get('activity') if isinstance(entry, dict) else None
        if not isinstance(meta, dict):
            raise ValueError('Each entry needs an activity object.')
        native_id = meta.get('id')
        if not isinstance(native_id, str) or not native_id:
            raise ValueError('Each activity needs a non-empty source id string.')
        key = source + '_' + hashlib.sha256(native_id.encode()).hexdigest()[:20]
        if key in seen:
            raise ValueError('Duplicate source id in bundle.')
        seen.add(key)
        try:
            date = datetime.datetime.fromisoformat(meta['start_local'])
        except (KeyError, TypeError, ValueError):
            raise ValueError('start_local must be an ISO local datetime.') from None
        if date.tzinfo is not None:
            raise ValueError('start_local must use local wall time without an offset.')
        if not number(meta.get('duration_minutes')) or meta['duration_minutes'] <= 0:
            raise ValueError('duration_minutes must be measured moving time, greater than zero.')
        if meta.get('type') not in {'Ride', 'VirtualRide', 'MountainBikeRide', 'GravelRide', 'TrackRide', 'Cyclocross'}:
            raise ValueError('Unsupported cycling activity type.')
        activity = dict(meta, id=key, source=source, source_id=native_id,
                        start_local=date.isoformat())
        activity.setdefault('name', 'Ride')
        recording = entry.get('recording')
        if recording is not None:
            if not isinstance(recording, dict) or recording.get('timeline') != 'one_second_with_stops':
                raise ValueError('Recording must declare timeline=one_second_with_stops; see docs/data-sources.md.')
            rows = recording.get('rows')
            if not isinstance(rows, list) or not rows:
                raise ValueError('Recording needs non-empty rows, or use recording=null for catalog-only data.')
            previous = -1
            for row in rows:
                if not isinstance(row, list) or len(row) != 5:
                    raise ValueError('Each row must be [elapsed_s, watts, hr, cadence, speed_mps].')
                elapsed = row[0]
                if not isinstance(elapsed, int) or isinstance(elapsed, bool) or not previous < elapsed < 7*86400:
                    raise ValueError('Elapsed seconds must be strictly increasing nonnegative integers under seven days.')
                if any(value is not None and (not number(value) or value < 0) for value in row[1:]):
                    raise ValueError('Samples must be nonnegative finite numbers or null.')
                previous = elapsed
            if not any(number(row[1]) for row in rows):
                raise ValueError('No measured power samples; import the activity as catalog-only instead.')
            recording = dict(recording, schema='LONG_VIEW_STREAM_V1', id=key,
                             source=source, columns=['elapsed_s', 'power_w', 'heart_rate', 'cadence', 'speed_mps'])
        prepared.append((activity, recording))
    return prepared


def import_bundle(bundle):
    prepared = prepare_bundle(bundle)
    import server
    with server.LOCK:
        catalog = {r['id']: r for r in server.catalog()}
        for activity, recording in prepared:
            catalog[activity['id']] = activity
            if recording is not None:
                server.write(server.recording_path(activity['id']), recording)
            for key in list(server.CACHE):
                if key.startswith(activity['id']):
                    del server.CACHE[key]
            for path in (server.DATA/'analysis').glob(activity['id']+'*.json'):
                path.unlink()
        server.write(server.DATA/'catalog.json', sorted(catalog.values(), key=lambda r: r['start_local']))
    return [activity['id'] for activity, _ in prepared]


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('bundle', type=Path)
    parser.add_argument('--data-dir', type=Path, help='Separate local store, e.g. data/demo')
    args = parser.parse_args()
    if args.data_dir:
        os.environ['LONG_VIEW_DATA_DIR'] = str(args.data_dir.resolve())
    try:
        result = import_bundle(json.loads(args.bundle.read_text()))
    except (ValueError, KeyError, OSError) as error:
        parser.exit(1, str(error)+'\n')
    print(json.dumps({'imported': len(result), 'ids': result}))


if __name__ == '__main__':
    main()
