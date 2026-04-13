import numpy as np
from PIL import Image, ImageFilter
import os
import logging

logger = logging.getLogger(__name__)
DEMO_DIR = os.path.join(os.path.dirname(__file__), "demo_data")


def _brain_base(size=512, seed=42):
    np.random.seed(seed)
    img = np.zeros((size, size), dtype=np.float64)
    c = size // 2
    y, x = np.ogrid[-c:size - c, -c:size - c]

    # Skull ring
    skull_o = (x ** 2 / (size * 0.42) ** 2 + y ** 2 / (size * 0.38) ** 2) <= 1
    skull_i = (x ** 2 / (size * 0.39) ** 2 + y ** 2 / (size * 0.35) ** 2) <= 1
    img[skull_o & ~skull_i] = 175 + np.random.normal(0, 5, np.sum(skull_o & ~skull_i))

    # Gray matter
    brain = skull_i
    img[brain] = np.random.normal(105, 12, np.sum(brain))

    # White matter
    wm = (x ** 2 / (size * 0.25) ** 2 + y ** 2 / (size * 0.22) ** 2) <= 1
    img[wm] = np.random.normal(142, 8, np.sum(wm))

    # Ventricles
    for vx in [size * 0.06, -size * 0.06]:
        v = ((x - vx) ** 2 / (size * 0.028) ** 2 + (y - size * 0.02) ** 2 / (size * 0.09) ** 2) <= 1
        img[v] = np.random.normal(28, 5, np.sum(v))
    v3 = (x ** 2 / (size * 0.008) ** 2 + (y - size * 0.02) ** 2 / (size * 0.035) ** 2) <= 1
    img[v3] = np.random.normal(25, 4, np.sum(v3))

    # Midline falx
    falx = (np.abs(x) < 2) & (y < size * 0.1) & (y > -size * 0.32)
    img[falx] = 165

    # Sulci
    for _ in range(6):
        ang = np.random.uniform(0, 2 * np.pi)
        r = np.random.uniform(size * 0.29, size * 0.35)
        sx, sy = int(r * np.cos(ang)), int(r * np.sin(ang))
        s = ((x - sx) ** 2 / (size * 0.012) ** 2 + (y - sy) ** 2 / (size * 0.035) ** 2) <= 1
        img[s & brain] = np.random.normal(50, 8, np.sum(s & brain))

    return img, brain, x, y


def _save(img_arr, name, blur=1.2):
    img_arr = np.clip(img_arr, 0, 255).astype(np.uint8)
    pil = Image.fromarray(img_arr, 'L')
    pil = pil.filter(ImageFilter.GaussianBlur(radius=blur))
    path = os.path.join(DEMO_DIR, name)
    pil.save(path)
    return path


DEMO_IMAGES_META = [
    {
        "id": "normal_brain",
        "filename": "normal_brain.png",
        "label": "Normal Brain MRI",
        "expected": "normal",
        "description": "Axial T2-weighted MRI showing normal brain anatomy with symmetric hemispheres, no lesions detected."
    },
    {
        "id": "hemorrhagic_stroke",
        "filename": "hemorrhagic_stroke.png",
        "label": "Hemorrhagic Stroke",
        "expected": "hemorrhagic",
        "description": "Axial MRI showing right hemisphere intracerebral hemorrhage (bright region) with surrounding edema."
    },
    {
        "id": "ischemic_stroke",
        "filename": "ischemic_stroke.png",
        "label": "Ischemic Stroke",
        "expected": "ischemic",
        "description": "Axial MRI showing left hemisphere ischemic infarction (dark region) with penumbral tissue."
    },
    {
        "id": "hemorrhagic_large",
        "filename": "hemorrhagic_large.png",
        "label": "Large Hemorrhagic Stroke",
        "expected": "hemorrhagic",
        "description": "Axial MRI showing large left hemisphere hemorrhage with significant mass effect and midline shift."
    },
    {
        "id": "normal_variant",
        "filename": "normal_variant.png",
        "label": "Normal Brain (Variant)",
        "expected": "normal",
        "description": "Axial T2-weighted MRI showing normal brain anatomy, alternate scan parameters."
    },
]


def generate_demo_images():
    os.makedirs(DEMO_DIR, exist_ok=True)

    # 1. Normal brain
    img, brain, x, y = _brain_base(512, seed=42)
    _save(img, "normal_brain.png")

    # 2. Hemorrhagic stroke (right hemisphere bright lesion)
    img, brain, x, y = _brain_base(512, seed=123)
    hx, hy = 60, -25
    core = ((x - hx) ** 2 / 28 ** 2 + (y - hy) ** 2 / 22 ** 2) <= 1
    img[core & brain] = np.random.normal(238, 6, np.sum(core & brain))
    edema = ((x - hx) ** 2 / 45 ** 2 + (y - hy) ** 2 / 38 ** 2) <= 1
    ring = edema & ~core & brain
    img[ring] = np.random.normal(158, 10, np.sum(ring))
    _save(img, "hemorrhagic_stroke.png", blur=1.0)

    # 3. Ischemic stroke (left hemisphere dark region)
    img, brain, x, y = _brain_base(512, seed=456)
    ix, iy = -55, 15
    core = ((x - ix) ** 2 / 35 ** 2 + (y - iy) ** 2 / 28 ** 2) <= 1
    img[core & brain] = np.random.normal(32, 7, np.sum(core & brain))
    penumbra = ((x - ix) ** 2 / 50 ** 2 + (y - iy) ** 2 / 42 ** 2) <= 1
    ring = penumbra & ~core & brain
    img[ring] = np.random.normal(68, 10, np.sum(ring))
    _save(img, "ischemic_stroke.png", blur=1.0)

    # 4. Large hemorrhagic (left hemisphere)
    img, brain, x, y = _brain_base(512, seed=789)
    hx2, hy2 = -45, -10
    core = ((x - hx2) ** 2 / 38 ** 2 + (y - hy2) ** 2 / 32 ** 2) <= 1
    img[core & brain] = np.random.normal(242, 5, np.sum(core & brain))
    edema = ((x - hx2) ** 2 / 55 ** 2 + (y - hy2) ** 2 / 48 ** 2) <= 1
    ring = edema & ~core & brain
    img[ring] = np.random.normal(162, 8, np.sum(ring))
    _save(img, "hemorrhagic_large.png", blur=1.0)

    # 5. Normal variant
    img, brain, x, y = _brain_base(512, seed=321)
    _save(img, "normal_variant.png", blur=1.5)

    logger.info(f"Generated {len(DEMO_IMAGES_META)} demo MRI images in {DEMO_DIR}")
    return DEMO_IMAGES_META
