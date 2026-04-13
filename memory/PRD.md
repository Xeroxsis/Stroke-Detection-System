# NeuroScan AI - Stroke Detection WebApp PRD

## Problem Statement
Build a stroke detection webapp that scans MRI/CT images and detects stroke type using a real ML model trained on actual brain CT data.

## Architecture
- **Frontend**: React 19 + TailwindCSS + Shadcn UI (HashRouter for GitHub Pages)
- **Backend**: FastAPI (Python)
- **Database**: MongoDB
- **ML Model**: RandomForest trained on 1,000 real brain CT images (73% accuracy)
- **Dataset**: Brain Stroke CT Image Dataset (Peco602/Kaggle - 2,501 images)
- **PDF Generation**: ReportLab

## Training Data
- **Source**: Brain Stroke CT Dataset (github.com/Peco602/brain-stroke-detection-3d-cnn)
- **Location**: Pre-trained model at `/app/backend/pretrained_model.pkl`
- **Demo images**: `/app/backend/demo_data/` (6 real CT images)
- **Training script**: `/app/backend/build_model.py`
- **Features**: 34 OpenCV-extracted features (intensity, asymmetry, edges, texture, spatial)
- **Split**: 500 normal, 201 hemorrhagic, 299 ischemic

## What's Been Implemented
### Phase 1 - MVP: Auth, scan, patients, PDF, dashboard
### Phase 2 - RBAC (admin/doctor/nurse), model training page, HashRouter
### Phase 3 - Real dataset integration
- [x] Downloaded 2,501 real brain CT images
- [x] Trained RandomForest on 1,000 images (73% accuracy)
- [x] 6 real CT demo images (2 per class)
- [x] Batch upload (up to 20 files)
- [x] "Analyze All Demos" one-click demo
- [x] Pre-trained model loads on startup

## Prioritized Backlog
### P1: DICOM support, scan comparison, model accuracy improvements
### P2: Deep learning (CNN/ResNet), PACS integration, mobile optimization
