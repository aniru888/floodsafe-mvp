# ML Service Testing Scripts

Instead of Jupyter notebooks, use these Python scripts to test and train the ML models.

## How to Run

Open **Command Prompt** or **PowerShell** and navigate to this directory:

```bash
cd C:\Users\Anirudh Mohan\Desktop\FloodSafe\apps\ml-service\scripts
```

Then run scripts one by one:

## Step 1: Test GEE Connection

```bash
python 01_test_gee_connection.py
```

**Expected output:**
```
============================================================
Testing Google Earth Engine Connection
============================================================

1. Initializing GEE client...
✓ GEE initialized successfully!
  Project: gen-lang-client-0669818939

2. Testing dataset access...
✓ AlphaEarth dataset accessible!
  Images available: 4

3. Testing data fetch for Delhi...
✓ Successfully fetched data!
  Location: Connaught Place, Delhi
  Sample bands: ['A00', 'A01', 'A02']...

============================================================
✓ All GEE tests passed!
============================================================
```

**If you see authentication errors:**
1. Run: `earthengine authenticate`
2. Follow the browser prompts to authenticate
3. Re-run the script

---

## Step 2: Fetch Sample Data

```bash
python 02_fetch_sample_data.py
```

This will fetch data from all 5 sources:
- AlphaEarth (64-dim embeddings)
- DEM (elevation, slope)
- Surface water (historical flooding)
- Precipitation (CHIRPS rainfall)
- Landcover (urban, vegetation)

**Takes about:** 1-2 minutes

---

## Step 3: Test Feature Extraction

```bash
python 03_test_feature_extraction.py
```

This tests the complete pipeline that builds the 79-dimensional feature vector.

**Expected output:**
```
✓ Feature extraction successful!

Feature groups:
  AlphaEarth embeddings: (64,)
  Terrain features: (6,)
  Precipitation features: (5,)
  Temporal features: (4,)
  Combined vector: (79,)
```

---

## Alternative: Use VS Code

If you prefer a visual interface:

1. **Install VS Code** (if not installed):
   - Download from https://code.microsoft.com/

2. **Install Python extension**:
   - Open VS Code
   - Click Extensions (Ctrl+Shift+X)
   - Search "Python"
   - Install the Microsoft Python extension

3. **Install Jupyter extension**:
   - Search "Jupyter"
   - Install the Microsoft Jupyter extension

4. **Open notebook**:
   - File → Open Folder → Select `apps/ml-service`
   - Open any `.ipynb` file in the `notebooks/` folder
   - VS Code will let you run cells interactively

---

## Next Steps After Testing

Once the 3 scripts above run successfully:

1. **Collect training data** - See `04_build_training_dataset.py` (to be created)
2. **Train models** - See `05_train_models.py` (to be created)
3. **Evaluate performance** - See `06_evaluate_models.py` (to be created)
4. **Deploy to production** - Restart ML service with trained models

---

## Troubleshooting

### "ModuleNotFoundError: No module named 'ee'"
**Solution:** Run `pip install -r ../requirements.txt`

### "Please authorize access to Earth Engine"
**Solution:** Run `earthengine authenticate` and follow browser prompts

### "No such file or directory"
**Solution:** Make sure you're in the `scripts/` directory:
```bash
cd C:\Users\Anirudh Mohan\Desktop\FloodSafe\apps\ml-service\scripts
```

### Script runs but shows errors fetching data
**Solution:**
1. Check internet connection
2. Verify GEE authentication: `earthengine authenticate --status`
3. Check GEE quota limits (free tier has daily limits)
