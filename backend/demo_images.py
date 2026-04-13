import os
import json
import logging

logger = logging.getLogger(__name__)
DEMO_DIR = os.path.join(os.path.dirname(__file__), "demo_data")
META_FILE = os.path.join(DEMO_DIR, "demo_meta.json")

# Default metadata (overridden by demo_meta.json if it exists)
DEMO_IMAGES_META = []


def load_demo_metadata():
    global DEMO_IMAGES_META
    if os.path.exists(META_FILE):
        with open(META_FILE, 'r') as f:
            data = json.load(f)
        DEMO_IMAGES_META.clear()
        DEMO_IMAGES_META.extend(data)
        logger.info(f"Loaded {len(DEMO_IMAGES_META)} demo images from {META_FILE}")
    else:
        logger.warning(f"No demo metadata found at {META_FILE}. Run build_model.py to generate.")
    return DEMO_IMAGES_META


def generate_demo_images():
    """Load demo image metadata from pre-built dataset."""
    return load_demo_metadata()
