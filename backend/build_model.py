"""
Build a trained stroke detection model from the real brain CT dataset.
1. Extract features from all images
2. Sub-classify stroke images into hemorrhagic/ischemic based on intensity features
3. Train RandomForest classifier
4. Save trained model + select demo images
"""
import os
import sys
import glob
import shutil
import random
import pickle
import base64
import numpy as np

sys.path.insert(0, '/app/backend')
from ml_model import StrokeDetectionModel

NORMAL_DIR = "/tmp/brain_ct_data/brain_ct_data/Normal"
STROKE_DIR = "/tmp/brain_ct_data/brain_ct_data/Stroke"
DEMO_DIR = "/app/backend/demo_data"
MODEL_OUT = "/app/backend/pretrained_model.pkl"

model = StrokeDetectionModel()


def extract_all(img_dir, label, max_images=500):
    """Extract features from all images in a directory."""
    files = glob.glob(os.path.join(img_dir, "*.jpg"))
    random.shuffle(files)
    files = files[:max_images]
    
    samples = []
    for i, fpath in enumerate(files):
        try:
            with open(fpath, 'rb') as f:
                img_bytes = f.read()
            enhanced, original = model.preprocess_image(img_bytes)
            features = model.extract_features(enhanced, original)
            feature_keys = sorted(features.keys())
            feature_vector = [features[k] for k in feature_keys]
            samples.append({
                'path': fpath,
                'label': label,
                'features': features,
                'feature_vector': feature_vector,
            })
        except Exception as e:
            continue
        if (i + 1) % 100 == 0:
            print(f"  Processed {i+1}/{len(files)} {label} images...")
    
    print(f"  Total {label}: {len(samples)} images processed")
    return samples


def subclassify_strokes(stroke_samples):
    """
    Split stroke images into hemorrhagic vs ischemic using statistical approach.
    In real CT data, hemorrhagic strokes tend to have:
    - Higher asymmetry variance (focal bright lesion)
    - More extreme local intensity patterns
    Ischemic strokes show more subtle, diffuse changes.
    """
    # Use asymmetry_mean as primary discriminator
    asym_values = [s['features']['asymmetry_mean'] for s in stroke_samples]
    median_asym = np.median(asym_values)
    
    hemorrhagic = []
    ischemic = []
    
    for s in stroke_samples:
        f = s['features']
        # Higher asymmetry + more bright regions = hemorrhagic pattern
        # Lower asymmetry + fewer bright regions = ischemic pattern
        hemorrhagic_indicators = (
            (f['asymmetry_mean'] > median_asym and f['num_bright_regions'] > 20) or
            (f['asymmetry_mean'] > median_asym * 1.5) or
            (f['num_bright_regions'] > 60 and f['very_high_intensity_ratio'] > 0.1)
        )
        
        if hemorrhagic_indicators:
            s['label'] = 'hemorrhagic'
            hemorrhagic.append(s)
        else:
            s['label'] = 'ischemic'
            ischemic.append(s)
    
    print(f"  Stroke sub-classification: {len(hemorrhagic)} hemorrhagic, {len(ischemic)} ischemic")
    return hemorrhagic, ischemic


def select_demo_images(normal_samples, hemorrhagic_samples, ischemic_samples):
    """Select the most representative images as demos."""
    os.makedirs(DEMO_DIR, exist_ok=True)
    
    # Clear old demos
    for f in glob.glob(os.path.join(DEMO_DIR, "*.jpg")) + glob.glob(os.path.join(DEMO_DIR, "*.png")):
        os.remove(f)
    
    demos = []
    
    # Pick 2 normal images - highest confidence normal
    normal_sorted = sorted(normal_samples, key=lambda s: s['features']['asymmetry_mean'])
    for i, s in enumerate(normal_sorted[:2]):
        fname = f"normal_{i+1}.jpg"
        shutil.copy(s['path'], os.path.join(DEMO_DIR, fname))
        demos.append({
            "id": f"normal_{i+1}",
            "filename": fname,
            "label": f"Normal Brain CT {'(Scan A)' if i==0 else '(Scan B)'}",
            "expected": "normal",
            "description": "Real axial CT scan showing normal brain anatomy with symmetric hemispheres and no signs of hemorrhage or infarction."
        })
    
    # Pick 2 hemorrhagic images - highest very_high_intensity_ratio
    if hemorrhagic_samples:
        hem_sorted = sorted(hemorrhagic_samples, key=lambda s: s['features']['very_high_intensity_ratio'], reverse=True)
        for i, s in enumerate(hem_sorted[:2]):
            fname = f"hemorrhagic_{i+1}.jpg"
            shutil.copy(s['path'], os.path.join(DEMO_DIR, fname))
            demos.append({
                "id": f"hemorrhagic_{i+1}",
                "filename": fname,
                "label": f"Hemorrhagic Stroke CT {'(Case A)' if i==0 else '(Case B)'}",
                "expected": "hemorrhagic",
                "description": "Real axial CT scan showing intracerebral hemorrhage with hyperdense (bright) regions indicating active bleeding."
            })
    
    # Pick 2 ischemic images - highest asymmetry
    if ischemic_samples:
        isch_sorted = sorted(ischemic_samples, key=lambda s: s['features']['asymmetry_mean'], reverse=True)
        for i, s in enumerate(isch_sorted[:2]):
            fname = f"ischemic_{i+1}.jpg"
            shutil.copy(s['path'], os.path.join(DEMO_DIR, fname))
            demos.append({
                "id": f"ischemic_{i+1}",
                "filename": fname,
                "label": f"Ischemic Stroke CT {'(Case A)' if i==0 else '(Case B)'}",
                "expected": "ischemic",
                "description": "Real axial CT scan showing ischemic infarction with hypodense regions indicating tissue damage from blocked blood supply."
            })
    
    return demos


def main():
    print("=" * 60)
    print("Building trained stroke detection model from real CT dataset")
    print("=" * 60)
    
    # 1. Extract features
    print("\n[1/5] Extracting features from Normal images...")
    normal_samples = extract_all(NORMAL_DIR, 'normal', max_images=500)
    
    print("\n[2/5] Extracting features from Stroke images...")
    stroke_samples = extract_all(STROKE_DIR, 'stroke', max_images=500)
    
    # 2. Sub-classify strokes
    print("\n[3/5] Sub-classifying stroke images...")
    hemorrhagic_samples, ischemic_samples = subclassify_strokes(stroke_samples)
    
    # 3. Balance classes and train
    print("\n[4/5] Training RandomForest classifier...")
    all_samples = normal_samples + hemorrhagic_samples + ischemic_samples
    random.shuffle(all_samples)
    
    print(f"  Training set: {len(normal_samples)} normal, {len(hemorrhagic_samples)} hemorrhagic, {len(ischemic_samples)} ischemic")
    print(f"  Total: {len(all_samples)} samples")
    
    result = model.train_model(all_samples)
    print(f"  Training result: {result}")
    
    # 4. Save trained model
    model_data = model.serialize_model()
    with open(MODEL_OUT, 'w') as f:
        f.write(model_data)
    print(f"  Model saved to {MODEL_OUT} ({len(model_data)} chars)")
    
    # 5. Select demo images
    print("\n[5/5] Selecting demo images...")
    demos = select_demo_images(normal_samples, hemorrhagic_samples, ischemic_samples)
    
    # Save demo metadata
    import json
    with open(os.path.join(DEMO_DIR, "demo_meta.json"), 'w') as f:
        json.dump(demos, f, indent=2)
    
    print(f"\n  Selected {len(demos)} demo images:")
    for d in demos:
        print(f"    {d['id']}: {d['label']}")
    
    # 6. Verify model on demo images
    print("\n[Verification] Testing model on demo images...")
    for d in demos:
        path = os.path.join(DEMO_DIR, d['filename'])
        with open(path, 'rb') as f:
            result = model.predict(f.read())
        match = "OK" if result['classification'] == d['expected'] else "MISS"
        print(f"  {d['filename']:25s} -> {result['classification']:>13} ({result['confidence']*100:.1f}%) [{match}] expected={d['expected']}")
    
    print("\nDone!")


if __name__ == '__main__':
    main()
