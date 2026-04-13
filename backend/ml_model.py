import cv2
import numpy as np
from PIL import Image
import io
import logging
import pickle
import base64

logger = logging.getLogger(__name__)

STROKE_INFO = {
    "hemorrhagic": {
        "name": "Hemorrhagic Stroke",
        "description": "A hemorrhagic stroke occurs when a blood vessel in the brain ruptures and bleeds into the surrounding tissue. This bleeding damages brain cells and increases pressure inside the skull.",
        "types": ["Intracerebral Hemorrhage (ICH)", "Subarachnoid Hemorrhage (SAH)"],
        "symptoms": [
            "Sudden, severe headache (often described as the worst headache of your life)",
            "Nausea and vomiting",
            "Seizures",
            "Loss of consciousness",
            "Weakness or numbness on one side of the body",
            "Difficulty speaking or understanding speech",
            "Vision problems"
        ],
        "treatment": [
            "Emergency surgical intervention to stop bleeding",
            "Blood pressure management and stabilization",
            "Endovascular coiling or surgical clipping for aneurysms",
            "Medications to reduce brain swelling",
            "Intensive care monitoring"
        ],
        "risk_factors": [
            "High blood pressure (most common cause)",
            "Blood-thinning medications",
            "Aneurysms or arteriovenous malformations",
            "Head trauma",
            "Liver disease",
            "Bleeding disorders"
        ],
        "prevalence": "Approximately 13% of all strokes",
        "severity": "high"
    },
    "ischemic": {
        "name": "Ischemic Stroke",
        "description": "An ischemic stroke occurs when a blood clot blocks or narrows an artery leading to the brain, cutting off blood supply. This deprives brain tissue of oxygen and nutrients, causing cells to die within minutes.",
        "types": ["Thrombotic Stroke", "Embolic Stroke", "Lacunar Stroke"],
        "symptoms": [
            "Sudden numbness or weakness in face, arm, or leg (especially one side)",
            "Sudden confusion or trouble speaking",
            "Sudden trouble seeing in one or both eyes",
            "Sudden trouble walking, dizziness, or loss of balance",
            "Sudden severe headache with no known cause"
        ],
        "treatment": [
            "tPA (tissue plasminogen activator) - clot-busting medication within 4.5 hours",
            "Mechanical thrombectomy - surgical removal of the clot",
            "Antiplatelet therapy (aspirin)",
            "Anticoagulant medications",
            "Carotid endarterectomy or stenting for prevention"
        ],
        "risk_factors": [
            "High blood pressure",
            "Diabetes",
            "High cholesterol",
            "Atrial fibrillation",
            "Smoking",
            "Obesity and physical inactivity",
            "Previous stroke or TIA"
        ],
        "prevalence": "Approximately 87% of all strokes",
        "severity": "high"
    },
    "normal": {
        "name": "No Stroke Detected",
        "description": "The MRI scan analysis did not detect significant indicators of either hemorrhagic or ischemic stroke. The brain tissue appears to have normal characteristics within the parameters of this screening tool.",
        "note": "This automated screening result should not replace professional medical evaluation. Always consult with a qualified neurologist or radiologist for definitive diagnosis.",
        "recommendations": [
            "Maintain regular check-ups with your healthcare provider",
            "Monitor blood pressure and cholesterol levels",
            "Maintain a healthy diet and exercise routine",
            "Be aware of stroke warning signs (FAST: Face, Arms, Speech, Time)"
        ],
        "severity": "low"
    }
}


class StrokeDetectionModel:
    """
    ML-based stroke detection model using computer vision feature extraction.
    Analyzes MRI images for indicators of hemorrhagic stroke, ischemic stroke,
    or normal brain tissue using intensity analysis, asymmetry detection,
    texture features, and spatial distribution.
    """

    def __init__(self):
        self.target_size = (256, 256)
        self.trained_model = None
        self.is_trained = False
        self.feature_keys = None
        logger.info("Stroke Detection Model initialized")

    def preprocess_image(self, image_bytes):
        nparr = np.frombuffer(image_bytes, np.uint8)
        img = cv2.imdecode(nparr, cv2.IMREAD_COLOR)

        if img is None:
            pil_img = Image.open(io.BytesIO(image_bytes))
            img = np.array(pil_img.convert('RGB'))
            img = cv2.cvtColor(img, cv2.COLOR_RGB2BGR)

        if img is None:
            raise ValueError("Could not decode image")

        gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
        resized = cv2.resize(gray, self.target_size)

        clahe = cv2.createCLAHE(clipLimit=2.0, tileGridSize=(8, 8))
        enhanced = clahe.apply(resized)

        return enhanced, resized

    def extract_features(self, enhanced, original):
        features = {}
        h, w = enhanced.shape

        # Intensity Statistics
        features['mean_intensity'] = float(np.mean(enhanced))
        features['std_intensity'] = float(np.std(enhanced))
        features['median_intensity'] = float(np.median(enhanced))
        features['p25_intensity'] = float(np.percentile(enhanced, 25))
        features['p75_intensity'] = float(np.percentile(enhanced, 75))
        features['iqr'] = features['p75_intensity'] - features['p25_intensity']

        mean_val = np.mean(enhanced)
        std_val = np.std(enhanced)
        features['skewness'] = float(np.mean(((enhanced - mean_val) / (std_val + 1e-6)) ** 3))

        # Histogram Features
        hist = cv2.calcHist([enhanced], [0], None, [256], [0, 256]).flatten()
        hist_norm = hist / (hist.sum() + 1e-6)
        features['hist_entropy'] = float(-np.sum(hist_norm[hist_norm > 0] * np.log2(hist_norm[hist_norm > 0])))
        features['hist_peak'] = float(np.argmax(hist))
        non_zero = np.where(hist > hist.max() * 0.1)[0]
        features['hist_spread'] = float(np.std(non_zero)) if len(non_zero) > 0 else 0.0

        # Intensity Ratios
        features['high_intensity_ratio'] = float(np.sum(enhanced > 200) / enhanced.size)
        features['very_high_intensity_ratio'] = float(np.sum(enhanced > 230) / enhanced.size)
        features['low_intensity_ratio'] = float(np.sum(enhanced < 50) / enhanced.size)
        features['very_low_intensity_ratio'] = float(np.sum(enhanced < 20) / enhanced.size)
        features['mid_intensity_ratio'] = float(np.sum((enhanced > 80) & (enhanced < 180)) / enhanced.size)

        # Asymmetry Features
        left_half = enhanced[:, :w // 2]
        right_half = cv2.flip(enhanced[:, w // 2:], 1)
        min_w = min(left_half.shape[1], right_half.shape[1])
        left_half = left_half[:, :min_w]
        right_half = right_half[:, :min_w]

        asymmetry = np.abs(left_half.astype(float) - right_half.astype(float))
        features['asymmetry_mean'] = float(np.mean(asymmetry))
        features['asymmetry_std'] = float(np.std(asymmetry))
        features['asymmetry_max'] = float(np.max(asymmetry))
        features['asymmetry_ratio'] = float(np.sum(asymmetry > 30) / (asymmetry.size + 1e-6))

        # Edge Features
        edges = cv2.Canny(enhanced, 50, 150)
        features['edge_density'] = float(np.mean(edges) / 255)
        features['edge_std'] = float(np.std(edges) / 255)

        sobelx = cv2.Sobel(enhanced, cv2.CV_64F, 1, 0, ksize=3)
        sobely = cv2.Sobel(enhanced, cv2.CV_64F, 0, 1, ksize=3)
        gradient_magnitude = np.sqrt(sobelx ** 2 + sobely ** 2)
        features['gradient_mean'] = float(np.mean(gradient_magnitude))
        features['gradient_std'] = float(np.std(gradient_magnitude))

        # Texture Features
        kernel = np.ones((5, 5), np.float32) / 25
        blur = cv2.filter2D(enhanced, -1, kernel)
        local_contrast = np.abs(enhanced.astype(float) - blur.astype(float))
        features['texture_contrast'] = float(np.mean(local_contrast))
        features['texture_uniformity'] = float(np.std(local_contrast))

        # Spatial Distribution
        features['q1_mean'] = float(np.mean(enhanced[:h // 2, :w // 2]))
        features['q2_mean'] = float(np.mean(enhanced[:h // 2, w // 2:]))
        features['q3_mean'] = float(np.mean(enhanced[h // 2:, :w // 2]))
        features['q4_mean'] = float(np.mean(enhanced[h // 2:, w // 2:]))

        center = enhanced[h // 4:3 * h // 4, w // 4:3 * w // 4]
        features['center_mean'] = float(np.mean(center))
        features['center_std'] = float(np.std(center))
        features['center_peripheral_ratio'] = float(np.mean(center) / (np.mean(enhanced) + 1e-6))

        # Connected components for lesion detection
        _, thresh_high = cv2.threshold(enhanced, 200, 255, cv2.THRESH_BINARY)
        _, thresh_low = cv2.threshold(enhanced, 50, 255, cv2.THRESH_BINARY_INV)

        num_bright, _ = cv2.connectedComponents(thresh_high)
        num_dark, _ = cv2.connectedComponents(thresh_low)
        features['num_bright_regions'] = float(num_bright - 1)
        features['num_dark_regions'] = float(num_dark - 1)

        return features

    def classify(self, features):
        if self.is_trained and self.trained_model is not None:
            return self._classify_trained(features)
        return self._classify_heuristic(features)

    def _classify_trained(self, features):
        feature_keys = sorted(features.keys())
        feature_vector = [features[k] for k in feature_keys]
        prediction = self.trained_model.predict([feature_vector])[0]
        proba = self.trained_model.predict_proba([feature_vector])[0]
        classes = list(self.trained_model.classes_)
        probabilities = {c: round(float(p), 4) for c, p in zip(classes, proba)}
        for c in ['hemorrhagic', 'ischemic', 'normal']:
            if c not in probabilities:
                probabilities[c] = 0.0
        classification = max(probabilities, key=probabilities.get)
        confidence = probabilities[classification]
        return classification, confidence, probabilities

    def _classify_heuristic(self, features):
        # Key discriminators from feature analysis:
        # - asymmetry_max: hemorrhagic>>ischemic>>normal
        # - very_high_intensity_ratio: hemorrhagic>0, others~0
        # - asymmetry_ratio/mean: stroke>normal
        # - num_dark_regions: ischemic>others
        # - quadrant imbalance for stroke lateralization

        asym_mean = features['asymmetry_mean']
        asym_ratio = features['asymmetry_ratio']
        asym_max = features['asymmetry_max']
        hi_ratio = features['high_intensity_ratio']
        vhi_ratio = features['very_high_intensity_ratio']
        lo_ratio = features['low_intensity_ratio']
        vlo_ratio = features['very_low_intensity_ratio']
        mid_ratio = features['mid_intensity_ratio']
        n_bright = features['num_bright_regions']
        n_dark = features['num_dark_regions']
        edge_d = features['edge_density']
        tex_c = features['texture_contrast']
        center_r = features['center_peripheral_ratio']

        # Hemorrhagic: bright lesion + asymmetry + high max asymmetry
        has_bright = 1.0 if vhi_ratio > 0.001 else 0.0
        hemorrhagic_score = (
            vhi_ratio * 200.0 +
            has_bright * 4.0 +
            hi_ratio * 10.0 +
            (asym_max / 200.0) * 4.0 +
            asym_ratio * 4.0 +
            max(0, asym_mean - 5.0) / 10.0 * 2.0 +
            n_bright / 80.0 * 1.5
        )

        # Ischemic: dark regions + asymmetry + no bright spots
        ischemic_score = (
            max(0, n_dark - 8) * 2.0 +
            asym_ratio * 5.0 +
            max(0, asym_mean - 5.0) / 8.0 * 3.5 +
            (1 - mid_ratio) * 2.0 +
            edge_d * 5.0 +
            (1.0 - has_bright) * 3.0 +
            max(0, lo_ratio - 0.51) * 30.0
        )

        # Normal: symmetric + balanced + low anomalies
        normal_score = (
            max(0, 1.0 - asym_ratio * 15.0) * 5.0 +
            max(0, 1.0 - (asym_mean - 4.0) / 8.0) * 4.0 +
            (1 - vhi_ratio * 50.0) * 2.0 +
            mid_ratio * 3.0 +
            min(features['hist_entropy'] / 7.0, 1.0) * 1.5 +
            max(0, 6.0 - n_dark) / 6.0 * 2.0
        )

        hemorrhagic_score = max(hemorrhagic_score, 0.01)
        ischemic_score = max(ischemic_score, 0.01)
        normal_score = max(normal_score, 0.01)

        total = hemorrhagic_score + ischemic_score + normal_score
        probabilities = {
            'hemorrhagic': round(float(hemorrhagic_score / total), 4),
            'ischemic': round(float(ischemic_score / total), 4),
            'normal': round(float(normal_score / total), 4)
        }

        classification = max(probabilities, key=probabilities.get)
        confidence = probabilities[classification]

        return classification, confidence, probabilities

    def predict(self, image_bytes):
        try:
            enhanced, original = self.preprocess_image(image_bytes)
            features = self.extract_features(enhanced, original)
            classification, confidence, probabilities = self.classify(features)

            stroke_info = STROKE_INFO.get(classification, {})

            key_features = {
                'mean_intensity': round(features['mean_intensity'], 2),
                'std_intensity': round(features['std_intensity'], 2),
                'high_intensity_ratio': round(features['high_intensity_ratio'], 4),
                'low_intensity_ratio': round(features['low_intensity_ratio'], 4),
                'asymmetry_score': round(features['asymmetry_mean'], 2),
                'edge_density': round(features['edge_density'], 4),
                'texture_contrast': round(features['texture_contrast'], 2),
                'histogram_entropy': round(features['hist_entropy'], 2),
                'symmetry_index': round(1 - features['asymmetry_ratio'], 4),
                'num_anomalous_regions': int(features['num_bright_regions'] + features['num_dark_regions'])
            }

            return {
                'classification': classification,
                'confidence': confidence,
                'probabilities': probabilities,
                'features': key_features,
                'stroke_info': stroke_info
            }
        except Exception as e:
            logger.error(f"Prediction error: {e}")
            raise

    def extract_training_features(self, image_bytes):
        """Extract full feature dict for training storage"""
        enhanced, original = self.preprocess_image(image_bytes)
        return self.extract_features(enhanced, original)

    def train_model(self, training_data):
        """Train RandomForest on collected training data"""
        from sklearn.ensemble import RandomForestClassifier
        from sklearn.model_selection import cross_val_score

        X = [d['feature_vector'] for d in training_data]
        y = [d['label'] for d in training_data]

        model = RandomForestClassifier(n_estimators=100, random_state=42, max_depth=10)

        accuracy = 0.0
        if len(X) >= 10:
            cv_folds = min(5, len(set(y)))
            if cv_folds >= 2:
                scores = cross_val_score(model, X, y, cv=cv_folds, scoring='accuracy')
                accuracy = float(scores.mean())

        model.fit(X, y)
        self.trained_model = model
        self.is_trained = True
        self.feature_keys = sorted(training_data[0]['features'].keys()) if training_data else None

        return {
            'samples': len(X),
            'classes': list(set(y)),
            'accuracy': accuracy,
            'feature_count': len(X[0]) if X else 0
        }

    def serialize_model(self):
        if self.trained_model:
            return base64.b64encode(pickle.dumps(self.trained_model)).decode('utf-8')
        return None

    def deserialize_model(self, model_b64):
        self.trained_model = pickle.loads(base64.b64decode(model_b64))
        self.is_trained = True
        logger.info("Trained model loaded from database")
