from pathlib import Path
from dotenv import load_dotenv
load_dotenv(Path(__file__).parent / '.env')

from fastapi import FastAPI, APIRouter, Request, Response, HTTPException, UploadFile, File, Form
from starlette.middleware.cors import CORSMiddleware
from motor.motor_asyncio import AsyncIOMotorClient
from bson import ObjectId
import os
import logging
import bcrypt
import jwt
import base64
import uuid
from datetime import datetime, timezone, timedelta
from pydantic import BaseModel
from typing import Optional, List
from fastapi.responses import StreamingResponse, FileResponse

from ml_model import StrokeDetectionModel
from pdf_generator import generate_pdf_report
from demo_images import generate_demo_images, DEMO_IMAGES_META, DEMO_DIR

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

mongo_url = os.environ['MONGO_URL']
client = AsyncIOMotorClient(mongo_url)
db = client[os.environ['DB_NAME']]

JWT_ALGORITHM = "HS256"


def get_jwt_secret():
    return os.environ["JWT_SECRET"]


def hash_password(password: str) -> str:
    salt = bcrypt.gensalt()
    return bcrypt.hashpw(password.encode("utf-8"), salt).decode("utf-8")


def verify_password(plain_password: str, hashed_password: str) -> bool:
    return bcrypt.checkpw(plain_password.encode("utf-8"), hashed_password.encode("utf-8"))


def create_access_token(user_id: str, email: str) -> str:
    payload = {
        "sub": user_id, "email": email,
        "exp": datetime.now(timezone.utc) + timedelta(minutes=15),
        "type": "access"
    }
    return jwt.encode(payload, get_jwt_secret(), algorithm=JWT_ALGORITHM)


def create_refresh_token(user_id: str) -> str:
    payload = {
        "sub": user_id,
        "exp": datetime.now(timezone.utc) + timedelta(days=7),
        "type": "refresh"
    }
    return jwt.encode(payload, get_jwt_secret(), algorithm=JWT_ALGORITHM)


async def get_current_user(request: Request) -> dict:
    token = request.cookies.get("access_token")
    if not token:
        auth_header = request.headers.get("Authorization", "")
        if auth_header.startswith("Bearer "):
            token = auth_header[7:]
    if not token:
        raise HTTPException(status_code=401, detail="Not authenticated")
    try:
        payload = jwt.decode(token, get_jwt_secret(), algorithms=[JWT_ALGORITHM])
        if payload.get("type") != "access":
            raise HTTPException(status_code=401, detail="Invalid token type")
        user = await db.users.find_one({"_id": ObjectId(payload["sub"])})
        if not user:
            raise HTTPException(status_code=401, detail="User not found")
        user["_id"] = str(user["_id"])
        user.pop("password_hash", None)
        return user
    except jwt.ExpiredSignatureError:
        raise HTTPException(status_code=401, detail="Token expired")
    except jwt.InvalidTokenError:
        raise HTTPException(status_code=401, detail="Invalid token")


stroke_model = StrokeDetectionModel()

app = FastAPI()
api_router = APIRouter(prefix="/api")

# Role-based access control
ROLE_HIERARCHY = {"admin": 3, "doctor": 2, "nurse": 1}


def require_role(user, min_role):
    user_level = ROLE_HIERARCHY.get(user.get("role"), 0)
    required_level = ROLE_HIERARCHY.get(min_role, 0)
    if user_level < required_level:
        raise HTTPException(status_code=403, detail=f"Access denied. Requires {min_role} role or higher.")


# --- Pydantic Models ---
class RegisterInput(BaseModel):
    email: str
    password: str
    name: str


class LoginInput(BaseModel):
    email: str
    password: str


class PatientCreate(BaseModel):
    name: str
    age: int
    gender: str
    medical_history: Optional[str] = ""


class PatientUpdate(BaseModel):
    name: Optional[str] = None
    age: Optional[int] = None
    gender: Optional[str] = None
    medical_history: Optional[str] = None


class RoleUpdate(BaseModel):
    role: str


# --- Auth Routes ---
@api_router.post("/auth/register")
async def register(input_data: RegisterInput, response: Response):
    email = input_data.email.lower().strip()
    if len(input_data.password) < 6:
        raise HTTPException(status_code=400, detail="Password must be at least 6 characters")

    existing = await db.users.find_one({"email": email})
    if existing:
        raise HTTPException(status_code=400, detail="Email already registered")

    hashed = hash_password(input_data.password)
    user_doc = {
        "email": email,
        "password_hash": hashed,
        "name": input_data.name,
        "role": "doctor",
        "created_at": datetime.now(timezone.utc).isoformat()
    }
    result = await db.users.insert_one(user_doc)
    user_id = str(result.inserted_id)

    access_token = create_access_token(user_id, email)
    refresh_token = create_refresh_token(user_id)

    response.set_cookie(key="access_token", value=access_token, httponly=True, secure=False, samesite="lax", max_age=900, path="/")
    response.set_cookie(key="refresh_token", value=refresh_token, httponly=True, secure=False, samesite="lax", max_age=604800, path="/")

    return {"id": user_id, "email": email, "name": input_data.name, "role": "doctor"}


@api_router.post("/auth/login")
async def login(input_data: LoginInput, request: Request, response: Response):
    email = input_data.email.lower().strip()

    ip = request.client.host if request.client else "unknown"
    identifier = f"{ip}:{email}"
    attempts = await db.login_attempts.find_one({"identifier": identifier})
    if attempts and attempts.get("count", 0) >= 5:
        lockout_time = attempts.get("last_attempt")
        if lockout_time:
            if isinstance(lockout_time, str):
                lockout_time = datetime.fromisoformat(lockout_time)
            if datetime.now(timezone.utc) - lockout_time < timedelta(minutes=15):
                raise HTTPException(status_code=429, detail="Too many failed attempts. Try again in 15 minutes.")
            else:
                await db.login_attempts.delete_one({"identifier": identifier})

    user = await db.users.find_one({"email": email})
    if not user or not verify_password(input_data.password, user["password_hash"]):
        await db.login_attempts.update_one(
            {"identifier": identifier},
            {"$inc": {"count": 1}, "$set": {"last_attempt": datetime.now(timezone.utc).isoformat()}},
            upsert=True
        )
        raise HTTPException(status_code=401, detail="Invalid email or password")

    await db.login_attempts.delete_one({"identifier": identifier})

    user_id = str(user["_id"])
    access_token = create_access_token(user_id, email)
    refresh_token = create_refresh_token(user_id)

    response.set_cookie(key="access_token", value=access_token, httponly=True, secure=False, samesite="lax", max_age=900, path="/")
    response.set_cookie(key="refresh_token", value=refresh_token, httponly=True, secure=False, samesite="lax", max_age=604800, path="/")

    return {"id": user_id, "email": email, "name": user.get("name", ""), "role": user.get("role", "user")}


@api_router.post("/auth/logout")
async def logout(response: Response):
    response.delete_cookie("access_token", path="/")
    response.delete_cookie("refresh_token", path="/")
    return {"message": "Logged out"}


@api_router.get("/auth/me")
async def get_me(request: Request):
    user = await get_current_user(request)
    return user


@api_router.post("/auth/refresh")
async def refresh_token_endpoint(request: Request, response: Response):
    token = request.cookies.get("refresh_token")
    if not token:
        raise HTTPException(status_code=401, detail="No refresh token")
    try:
        payload = jwt.decode(token, get_jwt_secret(), algorithms=[JWT_ALGORITHM])
        if payload.get("type") != "refresh":
            raise HTTPException(status_code=401, detail="Invalid token type")
        user = await db.users.find_one({"_id": ObjectId(payload["sub"])})
        if not user:
            raise HTTPException(status_code=401, detail="User not found")
        user_id = str(user["_id"])
        access_token = create_access_token(user_id, user["email"])
        response.set_cookie(key="access_token", value=access_token, httponly=True, secure=False, samesite="lax", max_age=900, path="/")
        return {"message": "Token refreshed"}
    except jwt.ExpiredSignatureError:
        raise HTTPException(status_code=401, detail="Refresh token expired")
    except jwt.InvalidTokenError:
        raise HTTPException(status_code=401, detail="Invalid refresh token")


# --- Patient Routes ---
@api_router.get("/patients")
async def list_patients(request: Request):
    user = await get_current_user(request)
    patients = await db.patients.find({"user_id": user["_id"]}, {"_id": 0}).sort("created_at", -1).to_list(1000)
    return patients


@api_router.post("/patients")
async def create_patient(input_data: PatientCreate, request: Request):
    user = await get_current_user(request)
    require_role(user, "doctor")
    patient_doc = {
        "id": str(uuid.uuid4()),
        "user_id": user["_id"],
        "name": input_data.name,
        "age": input_data.age,
        "gender": input_data.gender,
        "medical_history": input_data.medical_history or "",
        "created_at": datetime.now(timezone.utc).isoformat()
    }
    await db.patients.insert_one(patient_doc)
    patient_doc.pop("_id", None)
    return patient_doc


@api_router.get("/patients/{patient_id}")
async def get_patient(patient_id: str, request: Request):
    user = await get_current_user(request)
    patient = await db.patients.find_one({"id": patient_id, "user_id": user["_id"]}, {"_id": 0})
    if not patient:
        raise HTTPException(status_code=404, detail="Patient not found")
    return patient


@api_router.put("/patients/{patient_id}")
async def update_patient(patient_id: str, input_data: PatientUpdate, request: Request):
    user = await get_current_user(request)
    require_role(user, "doctor")
    update_data = {k: v for k, v in input_data.model_dump().items() if v is not None}
    if not update_data:
        raise HTTPException(status_code=400, detail="No update data provided")
    result = await db.patients.update_one(
        {"id": patient_id, "user_id": user["_id"]},
        {"$set": update_data}
    )
    if result.matched_count == 0:
        raise HTTPException(status_code=404, detail="Patient not found")
    patient = await db.patients.find_one({"id": patient_id}, {"_id": 0})
    return patient


@api_router.delete("/patients/{patient_id}")
async def delete_patient(patient_id: str, request: Request):
    user = await get_current_user(request)
    require_role(user, "doctor")
    result = await db.patients.delete_one({"id": patient_id, "user_id": user["_id"]})
    if result.deleted_count == 0:
        raise HTTPException(status_code=404, detail="Patient not found")
    # Also delete associated scans
    await db.scans.delete_many({"patient_id": patient_id, "user_id": user["_id"]})
    return {"message": "Patient deleted"}


# --- Scan Routes ---
@api_router.post("/scans/analyze")
async def analyze_scan(
    request: Request,
    file: UploadFile = File(...),
    patient_id: str = Form(None),
    patient_name: str = Form(None)
):
    user = await get_current_user(request)
    require_role(user, "doctor")

    image_bytes = await file.read()
    if len(image_bytes) > 10 * 1024 * 1024:
        raise HTTPException(status_code=400, detail="File too large. Maximum 10MB.")

    patient_data = None
    if patient_id:
        patient_data = await db.patients.find_one({"id": patient_id, "user_id": user["_id"]}, {"_id": 0})

    result = stroke_model.predict(image_bytes)

    image_b64 = base64.b64encode(image_bytes).decode('utf-8')
    content_type = file.content_type or "image/png"

    scan_doc = {
        "id": str(uuid.uuid4()),
        "user_id": user["_id"],
        "patient_id": patient_id,
        "patient_name": patient_name or (patient_data.get("name") if patient_data else "Unknown"),
        "filename": file.filename,
        "content_type": content_type,
        "image_data": image_b64,
        "classification": result["classification"],
        "confidence": result["confidence"],
        "probabilities": result["probabilities"],
        "features": result["features"],
        "stroke_info": result["stroke_info"],
        "created_at": datetime.now(timezone.utc).isoformat()
    }
    await db.scans.insert_one(scan_doc)
    scan_doc.pop("_id", None)

    response_doc = {k: v for k, v in scan_doc.items() if k != "image_data"}
    response_doc["has_image"] = True
    return response_doc


@api_router.get("/scans")
async def list_scans(request: Request):
    user = await get_current_user(request)
    scans = await db.scans.find(
        {"user_id": user["_id"]},
        {"_id": 0, "image_data": 0}
    ).sort("created_at", -1).to_list(1000)
    return scans


@api_router.get("/scans/{scan_id}")
async def get_scan(scan_id: str, request: Request):
    user = await get_current_user(request)
    scan = await db.scans.find_one({"id": scan_id, "user_id": user["_id"]}, {"_id": 0})
    if not scan:
        raise HTTPException(status_code=404, detail="Scan not found")
    return scan


@api_router.delete("/scans/{scan_id}")
async def delete_scan(scan_id: str, request: Request):
    user = await get_current_user(request)
    require_role(user, "doctor")
    result = await db.scans.delete_one({"id": scan_id, "user_id": user["_id"]})
    if result.deleted_count == 0:
        raise HTTPException(status_code=404, detail="Scan not found")
    return {"message": "Scan deleted"}


@api_router.get("/scans/{scan_id}/pdf")
async def get_scan_pdf(scan_id: str, request: Request):
    user = await get_current_user(request)
    scan = await db.scans.find_one({"id": scan_id, "user_id": user["_id"]}, {"_id": 0})
    if not scan:
        raise HTTPException(status_code=404, detail="Scan not found")

    patient_data = None
    if scan.get("patient_id"):
        patient_data = await db.patients.find_one({"id": scan["patient_id"]}, {"_id": 0})

    pdf_buffer = generate_pdf_report(scan, patient_data)

    return StreamingResponse(
        pdf_buffer,
        media_type="application/pdf",
        headers={"Content-Disposition": f"attachment; filename=stroke_report_{scan_id[:8]}.pdf"}
    )


# --- Dashboard ---
@api_router.get("/dashboard/stats")
async def get_dashboard_stats(request: Request):
    user = await get_current_user(request)
    user_id = user["_id"]

    total_scans = await db.scans.count_documents({"user_id": user_id})
    total_patients = await db.patients.count_documents({"user_id": user_id})
    hemorrhagic_count = await db.scans.count_documents({"user_id": user_id, "classification": "hemorrhagic"})
    ischemic_count = await db.scans.count_documents({"user_id": user_id, "classification": "ischemic"})
    normal_count = await db.scans.count_documents({"user_id": user_id, "classification": "normal"})

    recent_scans = await db.scans.find(
        {"user_id": user_id},
        {"_id": 0, "image_data": 0}
    ).sort("created_at", -1).limit(5).to_list(5)

    return {
        "total_scans": total_scans,
        "total_patients": total_patients,
        "hemorrhagic_count": hemorrhagic_count,
        "ischemic_count": ischemic_count,
        "normal_count": normal_count,
        "recent_scans": recent_scans
    }


@api_router.get("/")
async def root():
    return {"message": "NeuroScan AI API"}


# --- Demo Images ---
@api_router.get("/demo/images")
async def list_demo_images():
    return DEMO_IMAGES_META


@api_router.get("/demo/images/{image_id}")
async def get_demo_image(image_id: str):
    meta = next((m for m in DEMO_IMAGES_META if m["id"] == image_id), None)
    if not meta:
        raise HTTPException(status_code=404, detail="Demo image not found")
    path = os.path.join(DEMO_DIR, meta["filename"])
    if not os.path.exists(path):
        raise HTTPException(status_code=404, detail="Demo image file not found")
    return FileResponse(path, media_type="image/png", filename=meta["filename"])


# --- Batch Analysis ---
@api_router.post("/scans/batch-analyze")
async def batch_analyze(
    request: Request,
    files: List[UploadFile] = File(...),
    patient_id: str = Form(None),
    patient_name: str = Form(None)
):
    user = await get_current_user(request)
    require_role(user, "doctor")

    if len(files) > 20:
        raise HTTPException(status_code=400, detail="Maximum 20 files per batch.")

    patient_data = None
    if patient_id:
        patient_data = await db.patients.find_one({"id": patient_id, "user_id": user["_id"]}, {"_id": 0})

    results = []
    for file in files:
        image_bytes = await file.read()
        if len(image_bytes) > 10 * 1024 * 1024:
            results.append({"filename": file.filename, "error": "File too large (max 10MB)"})
            continue
        try:
            result = stroke_model.predict(image_bytes)
            image_b64 = base64.b64encode(image_bytes).decode('utf-8')
            content_type = file.content_type or "image/png"
            scan_doc = {
                "id": str(uuid.uuid4()),
                "user_id": user["_id"],
                "patient_id": patient_id,
                "patient_name": patient_name or (patient_data.get("name") if patient_data else "Batch Scan"),
                "filename": file.filename,
                "content_type": content_type,
                "image_data": image_b64,
                "classification": result["classification"],
                "confidence": result["confidence"],
                "probabilities": result["probabilities"],
                "features": result["features"],
                "stroke_info": result["stroke_info"],
                "created_at": datetime.now(timezone.utc).isoformat()
            }
            await db.scans.insert_one(scan_doc)
            scan_doc.pop("_id", None)
            resp = {k: v for k, v in scan_doc.items() if k != "image_data"}
            resp["has_image"] = True
            results.append(resp)
        except Exception as e:
            logger.error(f"Batch scan error for {file.filename}: {e}")
            results.append({"filename": file.filename, "error": str(e)})

    return results


@api_router.post("/demo/analyze-all")
async def analyze_all_demos(request: Request):
    user = await get_current_user(request)
    require_role(user, "doctor")
    results = []
    for meta in DEMO_IMAGES_META:
        path = os.path.join(DEMO_DIR, meta["filename"])
        if not os.path.exists(path):
            continue
        with open(path, "rb") as f:
            image_bytes = f.read()
        result = stroke_model.predict(image_bytes)
        image_b64 = base64.b64encode(image_bytes).decode('utf-8')
        scan_doc = {
            "id": str(uuid.uuid4()),
            "user_id": user["_id"],
            "patient_id": None,
            "patient_name": f"Demo: {meta['label']}",
            "filename": meta["filename"],
            "content_type": "image/png",
            "image_data": image_b64,
            "classification": result["classification"],
            "confidence": result["confidence"],
            "probabilities": result["probabilities"],
            "features": result["features"],
            "stroke_info": result["stroke_info"],
            "created_at": datetime.now(timezone.utc).isoformat()
        }
        await db.scans.insert_one(scan_doc)
        scan_doc.pop("_id", None)
        resp = {k: v for k, v in scan_doc.items() if k != "image_data"}
        resp["has_image"] = True
        resp["demo_id"] = meta["id"]
        resp["expected"] = meta["expected"]
        results.append(resp)
    return results


# --- Admin Routes ---
@api_router.get("/admin/users")
async def list_users(request: Request):
    user = await get_current_user(request)
    require_role(user, "admin")
    users_raw = await db.users.find({}, {"password_hash": 0}).to_list(1000)
    users = []
    for u in users_raw:
        u["id"] = str(u.pop("_id"))
        users.append(u)
    return users


@api_router.put("/admin/users/{user_id}/role")
async def update_user_role(user_id: str, input_data: RoleUpdate, request: Request):
    user = await get_current_user(request)
    require_role(user, "admin")
    if input_data.role not in ROLE_HIERARCHY:
        raise HTTPException(status_code=400, detail=f"Invalid role. Must be one of: {list(ROLE_HIERARCHY.keys())}")
    target_user = await db.users.find_one({"_id": ObjectId(user_id)})
    if not target_user:
        raise HTTPException(status_code=404, detail="User not found")
    if str(target_user["_id"]) == user["_id"]:
        raise HTTPException(status_code=400, detail="Cannot change your own role")
    await db.users.update_one(
        {"_id": ObjectId(user_id)},
        {"$set": {"role": input_data.role}}
    )
    return {"message": f"Role updated to {input_data.role}", "user_id": user_id, "role": input_data.role}


@api_router.delete("/admin/users/{user_id}")
async def delete_user(user_id: str, request: Request):
    user = await get_current_user(request)
    require_role(user, "admin")
    if user_id == user["_id"]:
        raise HTTPException(status_code=400, detail="Cannot delete yourself")
    result = await db.users.delete_one({"_id": ObjectId(user_id)})
    if result.deleted_count == 0:
        raise HTTPException(status_code=404, detail="User not found")
    return {"message": "User deleted"}


# --- Training Routes ---
@api_router.post("/training/upload")
async def upload_training_data(
    request: Request,
    file: UploadFile = File(...),
    label: str = Form(...)
):
    user = await get_current_user(request)
    require_role(user, "doctor")
    if label not in ["hemorrhagic", "ischemic", "normal"]:
        raise HTTPException(status_code=400, detail="Label must be hemorrhagic, ischemic, or normal")
    image_bytes = await file.read()
    if len(image_bytes) > 10 * 1024 * 1024:
        raise HTTPException(status_code=400, detail="File too large. Maximum 10MB.")
    features = stroke_model.extract_training_features(image_bytes)
    feature_keys = sorted(features.keys())
    feature_vector = [features[k] for k in feature_keys]
    sample_doc = {
        "id": str(uuid.uuid4()),
        "user_id": user["_id"],
        "label": label,
        "features": features,
        "feature_vector": feature_vector,
        "filename": file.filename,
        "created_at": datetime.now(timezone.utc).isoformat()
    }
    await db.training_samples.insert_one(sample_doc)
    sample_doc.pop("_id", None)
    count = await db.training_samples.count_documents({})
    return {"message": "Training sample added", "total_samples": count, "label": label}


@api_router.post("/training/train")
async def trigger_training(request: Request):
    user = await get_current_user(request)
    require_role(user, "admin")
    samples = await db.training_samples.find({}, {"_id": 0}).to_list(10000)
    if len(samples) < 5:
        raise HTTPException(status_code=400, detail=f"Need at least 5 training samples. Currently have {len(samples)}.")
    labels = set(s["label"] for s in samples)
    if len(labels) < 2:
        raise HTTPException(status_code=400, detail="Need samples from at least 2 different classes.")
    result = stroke_model.train_model(samples)
    model_data = stroke_model.serialize_model()
    if model_data:
        await db.trained_models.delete_many({})
        await db.trained_models.insert_one({
            "model_data": model_data,
            "created_at": datetime.now(timezone.utc).isoformat(),
            "trained_by": user["_id"],
            "metrics": result
        })
    run_doc = {
        "id": str(uuid.uuid4()),
        "user_id": user["_id"],
        "user_name": user.get("name", ""),
        "samples_count": result["samples"],
        "classes": result["classes"],
        "accuracy": result["accuracy"],
        "feature_count": result["feature_count"],
        "created_at": datetime.now(timezone.utc).isoformat()
    }
    await db.training_runs.insert_one(run_doc)
    run_doc.pop("_id", None)
    return run_doc


@api_router.get("/training/status")
async def training_status(request: Request):
    await get_current_user(request)
    total_samples = await db.training_samples.count_documents({})
    hemorrhagic_samples = await db.training_samples.count_documents({"label": "hemorrhagic"})
    ischemic_samples = await db.training_samples.count_documents({"label": "ischemic"})
    normal_samples = await db.training_samples.count_documents({"label": "normal"})
    latest_run = await db.training_runs.find_one({}, {"_id": 0}, sort=[("created_at", -1)])
    return {
        "is_trained": stroke_model.is_trained,
        "total_samples": total_samples,
        "samples_by_class": {
            "hemorrhagic": hemorrhagic_samples,
            "ischemic": ischemic_samples,
            "normal": normal_samples
        },
        "latest_run": latest_run
    }


@api_router.get("/training/history")
async def training_history(request: Request):
    await get_current_user(request)
    runs = await db.training_runs.find({}, {"_id": 0}).sort("created_at", -1).to_list(50)
    return runs


app.include_router(api_router)

frontend_url = os.environ.get("FRONTEND_URL", "http://localhost:3000")
app.add_middleware(
    CORSMiddleware,
    allow_origins=[frontend_url, "http://localhost:3000"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


async def seed_admin():
    admin_email = os.environ.get("ADMIN_EMAIL", "admin@example.com")
    admin_password = os.environ.get("ADMIN_PASSWORD", "admin123")
    existing = await db.users.find_one({"email": admin_email})
    if existing is None:
        hashed = hash_password(admin_password)
        await db.users.insert_one({
            "email": admin_email,
            "password_hash": hashed,
            "name": "Admin",
            "role": "admin",
            "created_at": datetime.now(timezone.utc).isoformat()
        })
        logger.info(f"Admin user seeded: {admin_email}")
    elif not verify_password(admin_password, existing["password_hash"]):
        await db.users.update_one(
            {"email": admin_email},
            {"$set": {"password_hash": hash_password(admin_password)}}
        )
        logger.info(f"Admin password updated: {admin_email}")

    # Write credentials
    os.makedirs("/app/memory", exist_ok=True)
    with open("/app/memory/test_credentials.md", "w") as f:
        f.write("# Test Credentials\n\n")
        f.write(f"## Admin\n- Email: {admin_email}\n- Password: {admin_password}\n- Role: admin\n\n")
        f.write("## Auth Endpoints\n- POST /api/auth/register\n- POST /api/auth/login\n- POST /api/auth/logout\n- GET /api/auth/me\n- POST /api/auth/refresh\n")


@app.on_event("startup")
async def startup():
    await db.users.create_index("email", unique=True)
    await db.login_attempts.create_index("identifier")
    await db.scans.create_index("user_id")
    await db.patients.create_index("user_id")
    await db.training_samples.create_index("label")
    await db.training_runs.create_index("created_at")
    # Load trained model from DB if available
    saved_model = await db.trained_models.find_one({}, sort=[("created_at", -1)])
    if saved_model and saved_model.get("model_data"):
        try:
            stroke_model.deserialize_model(saved_model["model_data"])
            logger.info("Loaded trained model from database")
        except Exception as e:
            logger.warning(f"Failed to load trained model: {e}")
    await seed_admin()
    generate_demo_images()
    logger.info("NeuroScan AI started successfully")


@app.on_event("shutdown")
async def shutdown():
    client.close()
