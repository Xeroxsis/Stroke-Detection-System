# NeuroScan AI — Brain Stroke Detection from MRI/CT Scans

A full-stack web application that uses an **ensemble ML model (ResNet18 CNN + RandomForest)** to detect and classify brain strokes from CT/MRI images. Trained on **2,501 real brain CT scans**. No cloud AI APIs — the entire ML pipeline runs locally.

![Python](https://img.shields.io/badge/Python-3.10+-blue?logo=python&logoColor=white)
![React](https://img.shields.io/badge/React-19-61DAFB?logo=react&logoColor=black)
![PyTorch](https://img.shields.io/badge/PyTorch-2.11-EE4C2C?logo=pytorch&logoColor=white)
![FastAPI](https://img.shields.io/badge/FastAPI-0.115-009688?logo=fastapi&logoColor=white)
![MongoDB](https://img.shields.io/badge/MongoDB-7.0-47A248?logo=mongodb&logoColor=white)
![License](https://img.shields.io/badge/License-MIT-green)

---

## What It Does

Upload a brain CT or MRI image → the app runs it through a dual-model ensemble → classifies it as **Hemorrhagic Stroke**, **Ischemic Stroke**, or **Normal** → returns confidence scores, probability breakdown, detailed medical info, and a downloadable PDF report.

### Classification Examples (Real CT Scans)

| Normal Brain | Hemorrhagic Stroke | Ischemic Stroke |
|:---:|:---:|:---:|
| Symmetric hemispheres | Hyperdense bright lesion | Hypodense dark region |
| ✅ 83–88% confidence | ✅ 49–67% confidence | ✅ 87–96% confidence |

---

## Features

- **Ensemble ML Model** — ResNet18 CNN (85.5% accuracy) + RandomForest (73%) blended at inference
- **Real Dataset** — Trained on 2,501 brain CT images from the Brain Stroke CT Dataset
- **Batch Upload** — Analyze up to 20 scans simultaneously
- **6 Demo Images** — One-click "Analyze All Demos" with real CT scans
- **Scan Comparison** — Side-by-side view with probability charts and feature deltas
- **PDF Reports** — Downloadable reports with classification, symptoms, treatment info
- **Patient Management** — Full CRUD for patient records
- **Role-Based Access** — Admin / Doctor / Nurse permission tiers
- **Model Training** — Upload labeled images and retrain the RandomForest via the UI
- **JWT Auth** — httpOnly cookies, refresh token rotation, brute-force protection

---

## Tech Stack

| Layer | Technology |
|-------|-----------|
| Frontend | React 19, TailwindCSS, Shadcn/UI, Recharts |
| Backend | FastAPI, Uvicorn, Motor (async MongoDB) |
| ML | PyTorch (ResNet18), scikit-learn (RandomForest), OpenCV, Pillow |
| Database | MongoDB |
| Auth | JWT + bcrypt, httpOnly cookies |
| PDF | ReportLab |

---

## Project Structure

```
├── backend/
│   ├── server.py              # FastAPI app (auth, CRUD, scan analysis, admin, training)
│   ├── ml_model.py            # Ensemble model (CNN + RF + feature extraction)
│   ├── pdf_generator.py       # ReportLab PDF generation
│   ├── demo_images.py         # Demo image metadata loader
│   ├── build_model.py         # RandomForest training script
│   ├── train_cnn.py           # ResNet18 CNN training script
│   ├── cnn_model.pt           # Trained CNN weights (43 MB)
│   ├── pretrained_model.pkl   # Trained RandomForest (2.8 MB)
│   ├── demo_data/             # 6 real CT demo images + metadata
│   └── .env                   # MONGO_URL, JWT_SECRET, etc.
├── frontend/
│   ├── src/
│   │   ├── App.js             # HashRouter + routes
│   │   ├── contexts/          # AuthContext
│   │   ├── components/        # DashboardLayout, ProtectedRoute, Shadcn UI
│   │   ├── pages/             # Landing, Auth, Dashboard, Scan, Compare, Patients, Admin, Training
│   │   └── lib/api.js         # Axios instance with interceptors
│   └── .env                   # REACT_APP_BACKEND_URL
└── README.md
```

---

## ML Model Details

### Feature Extraction (34 features per image)
- Intensity statistics (mean, std, quartiles, skewness)
- Histogram entropy, peak position, spread
- High/low intensity ratios (hemorrhage/ischemia indicators)
- Hemispheric asymmetry (mean, max, ratio)
- Canny edge density, Sobel gradient magnitude
- Local texture contrast, spatial quadrant means
- Connected component counts (bright/dark regions)

### Ensemble Architecture
```
Input Image
    ├──→ [Resize 224×224] → ResNet18 CNN → softmax → P_cnn (weight: 0.4)
    └──→ [CLAHE + 34 features] → RandomForest → P_rf  (weight: 0.6)
                                                          ↓
                                          P_final = 0.4·P_cnn + 0.6·P_rf
```

### Training Data
- **Source**: [Brain Stroke CT Dataset](https://github.com/Peco602/brain-stroke-detection-3d-cnn) (2,501 images)
- **Split**: 870 balanced (290 per class) for CNN, 1,000 for RandomForest
- **Sub-classification**: Stroke images split into hemorrhagic/ischemic via feature analysis

---

## Setup & Run Locally

### Prerequisites
- Python 3.10+
- Node.js 18+
- MongoDB running locally
- ~500 MB disk space (for PyTorch + model weights)

### Backend
```bash
cd backend
pip install -r requirements.txt
# Set environment variables
cp .env.example .env  # Edit with your MONGO_URL, JWT_SECRET, etc.
uvicorn server:app --host 0.0.0.0 --port 8001 --reload
```

### Frontend
```bash
cd frontend
yarn install
# Set backend URL
echo 'REACT_APP_BACKEND_URL=http://localhost:8001' > .env
yarn start
```

### Train Models (Optional — pre-trained weights included)
```bash
# Download dataset
wget https://github.com/Peco602/brain-stroke-detection-3d-cnn/releases/download/v0.0.1/brain_ct_data.zip
unzip brain_ct_data.zip -d /tmp/brain_ct_data

# Train RandomForest
cd backend && python build_model.py

# Train CNN (takes ~5 min on CPU)
python train_cnn.py
```

---

## Environment Variables

### Backend (`backend/.env`)
```
MONGO_URL=mongodb://localhost:27017
DB_NAME=neuroscan
JWT_SECRET=your-random-secret-here
ADMIN_EMAIL=admin@example.com
ADMIN_PASSWORD=your-admin-password
FRONTEND_URL=http://localhost:3000
```

### Frontend (`frontend/.env`)
```
REACT_APP_BACKEND_URL=http://localhost:8001
```

---

## API Endpoints

| Method | Endpoint | Auth | Role | Description |
|--------|----------|------|------|-------------|
| POST | `/api/auth/register` | — | — | Register (default: doctor role) |
| POST | `/api/auth/login` | — | — | Login |
| POST | `/api/auth/logout` | ✅ | — | Logout |
| GET | `/api/auth/me` | ✅ | — | Current user |
| GET | `/api/patients` | ✅ | all | List patients |
| POST | `/api/patients` | ✅ | doctor+ | Create patient |
| POST | `/api/scans/analyze` | ✅ | doctor+ | Upload & classify single scan |
| POST | `/api/scans/batch-analyze` | ✅ | doctor+ | Batch classify multiple scans |
| GET | `/api/scans/{id}` | ✅ | all | Get scan with image |
| GET | `/api/scans/{id}/pdf` | ✅ | all | Download PDF report |
| GET | `/api/scans/compare/{a}/{b}` | ✅ | all | Compare two scans |
| POST | `/api/demo/analyze-all` | ✅ | doctor+ | Analyze all demo images |
| GET | `/api/admin/users` | ✅ | admin | List all users |
| PUT | `/api/admin/users/{id}/role` | ✅ | admin | Change user role |
| POST | `/api/training/upload` | ✅ | doctor+ | Upload labeled training sample |
| POST | `/api/training/train` | ✅ | admin | Trigger model retraining |
| GET | `/api/dashboard/stats` | ✅ | all | Dashboard statistics |

---

## Deployment

> **GitHub Pages can only host the frontend.** The backend (FastAPI + PyTorch + MongoDB) requires a server.

### Frontend → GitHub Pages
```bash
cd frontend
REACT_APP_BACKEND_URL=https://your-backend.com yarn build
# Push contents of build/ to your gh-pages branch
```

### Backend → Any Server
Railway, Render, DigitalOcean, AWS EC2, or any host with Python 3.10+ and MongoDB access.

---

## Disclaimer

This is a **research and educational prototype**. It is **NOT** a certified medical device and should **NOT** be used for clinical diagnosis. Always consult a qualified healthcare professional. The model's accuracy (85.5%) is insufficient for clinical use — it serves as a demonstration of applied ML in medical imaging.

---

## License

MIT License — see [LICENSE](LICENSE) below.

```
MIT License

Copyright (c) 2025

Permission is hereby granted, free of charge, to any person obtaining a copy
of this software and associated documentation files (the "Software"), to deal
in the Software without restriction, including without limitation the rights
to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
copies of the Software, and to permit persons to whom the Software is
furnished to do so, subject to the following conditions:

The above copyright notice and this permission notice shall be included in all
copies or substantial portions of the Software.

THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE
SOFTWARE.
```
