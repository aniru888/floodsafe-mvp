# @data - Safe Data Inspection

Safely inspect large data files without exhausting context window.

## Usage
```
@data path/to/file.npz
@data path/to/file.csv
@data path/to/large.json
```

## What This Does
1. Identifies file type by extension
2. Uses safe inspection patterns (metadata, sampling)
3. Returns structured summary WITHOUT loading full content

## CRITICAL RULES

**NEVER:**
- Read entire data files into context
- Use Read tool on .npz files (binary, useless)
- Print numpy metadata arrays directly (can be 90K+ chars)
- Read "more examples" after initial sample

**ALWAYS:**
- Use Python one-liners for inspection
- Limit Read operations to 15-30 lines max
- Truncate sample values to 100 chars
- Report structure/schema before content

---

## Inspection Templates by File Type

### NumPy .npz Files (BINARY)

**Step 1: Get structure**
```bash
python -c "
import numpy as np
d = np.load('$ARGUMENTS')
print('=== NPZ FILE INSPECTION ===')
print(f'Keys: {list(d.keys())}')
for k in d.keys():
    arr = d[k]
    print(f'{k}:')
    print(f'  Shape: {arr.shape}')
    print(f'  Dtype: {arr.dtype}')
    print(f'  Size: {arr.size} elements')
"
```

**Step 2: Sample values (if needed)**
```bash
python -c "
import numpy as np
d = np.load('$ARGUMENTS')
for k in d.keys():
    arr = d[k]
    if arr.dtype.kind in ['U', 'S', 'O']:  # String types - SKIP (often huge)
        print(f'{k}: [String/Object array - skipped to save context]')
    elif arr.size > 0:
        sample = arr.flat[:5]
        print(f'{k} sample: {sample}')
"
```

**WARNING**: Never access `d['metadata']` directly if it exists - often contains 90K+ chars!

---

### CSV Files

**Step 1: Get row count**
```bash
python -c "print(f'Total rows: {sum(1 for _ in open(\"$ARGUMENTS\"))}')"
```

**Step 2: Read header + first 10 rows**
Use Read tool with `limit: 11`

**Step 3: Get column stats (optional)**
```bash
python -c "
import csv
with open('$ARGUMENTS') as f:
    reader = csv.reader(f)
    header = next(reader)
    print(f'Columns ({len(header)}): {header}')
"
```

---

### JSON Files (Arrays like GeoJSON features)

**Step 1: Get type and size**
```bash
python -c "
import json
d = json.load(open('$ARGUMENTS'))
print(f'Type: {type(d).__name__}')
if hasattr(d, '__len__'):
    print(f'Length: {len(d)}')
if isinstance(d, dict):
    print(f'Top keys: {list(d.keys())[:10]}')
"
```

**Step 2: Sample first element**
```bash
python -c "
import json
d = json.load(open('$ARGUMENTS'))
if isinstance(d, list) and len(d) > 0:
    sample = str(d[0])[:500]  # Truncate!
    print(f'First element: {sample}')
elif isinstance(d, dict):
    if 'features' in d:  # GeoJSON
        print(f'GeoJSON with {len(d[\"features\"])} features')
        if d['features']:
            props = d['features'][0].get('properties', {})
            print(f'Sample properties: {list(props.keys())}')
"
```

---

### JSON Files (Objects/Dictionaries)

**Step 1: Get keys**
```bash
python -c "
import json
d = json.load(open('$ARGUMENTS'))
print(f'Keys: {list(d.keys())[:15]}')
for k in list(d.keys())[:5]:
    v = d[k]
    vtype = type(v).__name__
    vlen = len(v) if hasattr(v, '__len__') else 'N/A'
    print(f'  {k}: {vtype} (len={vlen})')
"
```

---

## Output Format

After inspection, report:

```
## Data File Summary: <filename>

**Type**: NPZ/CSV/JSON
**Size**: X samples/rows/elements

### Schema
- field1: dtype/type, shape/length
- field2: dtype/type, shape/length

### Sample Values (truncated)
- field1: [value1, value2, ...]
- field2: [value1, value2, ...]

### Notes
- Any quality issues, anomalies, or warnings
```

---

## Common Pitfalls to Avoid

1. **NPZ metadata trap**: `hotspot_training_data.npz` has 90K char metadata field
2. **GeoJSON features**: Can have 100+ features with full geometries
3. **CSV without limit**: Some CSVs have 10K+ rows
4. **Re-reading "for more context"**: If 5 samples aren't enough, 50 won't help
