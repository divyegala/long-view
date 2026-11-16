#!/usr/bin/env python3
"""Generate complete synthetic rides locally; never uses athlete history."""
import datetime
import json
import math
from pathlib import Path

activities = []
for i in range(12):
    date = datetime.datetime(2020, 1, 1, 9) + datetime.timedelta(days=i*14)
    rows = []
    for t in range(7500):
        if 3600 <= t < 3900:  # A known five-minute stop on the elapsed clock.
            continue
        power = 120 + i*2 + 12*math.sin(t/300)
        if 1200 <= t < 1800:
            power += 30
        hr = 110 + (power-100)*.25 + t/7500*3
        rows.append([t, round(power), round(hr), 85+round(5*math.sin(t/120)), 6.0])
    activities.append({'activity': {'id': str(i), 'start_local': date.isoformat(),
        'type': 'VirtualRide' if i%2 else 'Ride', 'name': f'Synthetic endurance {i+1}',
        'duration_minutes': 120, 'elapsed_minutes': 125},
        'recording': {'timeline': 'one_second_with_stops', 'provenance': 'Entirely synthetic demo', 'rows': rows}})

output = Path(__file__).resolve().parents[1]/'data/demo-bundle.json'
output.parent.mkdir(parents=True, exist_ok=True)
output.write_text(json.dumps({'schema': 'LONG_VIEW_IMPORT_V1', 'source': 'synthetic', 'activities': activities}))
print(output)
