from fastapi import FastAPI, Request
from pydantic import BaseModel
from typing import List, Optional
import re

app = FastAPI()

# ---------------------------------------------------------------------------
# Vocabulary tables
# ---------------------------------------------------------------------------

MODALITY_GROUPS = {
    "MRI":   ["MRI", "MR ", " MR,", "MAGNETIC RESONANCE"],
    "CT":    ["CT ", " CT,", "CT/", "/CT", "CAT SCAN", "COMPUTED TOM", "CTPA"],
    "XR":    ["XR", "X-RAY", "XRAY", "RADIOGRAPH", "AP AND LAT", "PA AND LAT",
              "CHEST PA", "PORTABLE", "PLAIN FILM", "SCOUT", "KUB"],
    "US":    ["ULTRASOUND", "SONOGRAM", "SONO", "ECHO "],
    "NM":    ["NUCLEAR MED", "PET", "SPECT", "BONE SCAN", "SCINTIGRAPH", "NM "],
    "MG":    ["MAMMOGRAM", "MAMMO"],
    "FL":    ["FLUORO", "BARIUM", "SWALLOW", "ENEMA", "ESOPHAG"],
    "ANGIO": ["ANGIO", "ARTERIOGRAM", "VENOGRAM", "MYELOGRAM", "FISTULOGRAM"],
}

# Ordered: more specific terms first to avoid false matches
BODY_PARTS = {
    "BRAIN":      ["BRAIN", "CEREBR", "INTRACRANIAL", "STROKE", "NEURO"],
    "HEAD":       ["HEAD", "CRANIAL", "SKULL"],
    "ORBIT":      ["ORBIT", "OPTIC NERVE"],
    "IAC":        ["IAC", "INTERNAL AUDITORY"],
    "FACE":       ["FACE", "FACIAL", "MANDIBLE", "MAXILLA", "TMJ", "JAW"],
    "SINUS":      ["SINUS", "PARANASAL"],
    "PITUITARY":  ["PITUITARY", "SELLA"],
    "NECK":       ["SOFT TISSUE NECK", "NECK SOFT", "THYROID", "CAROTID",
                   "LARYNX", "PHARYNX", "NASOPHARYNX", "OROPHARYNX"],
    "SPINE_C":    ["CERVICAL SPINE", "C-SPINE", "C SPINE", "CSPINE"],
    "SPINE_T":    ["THORACIC SPINE", "T-SPINE", "T SPINE", "TSPINE"],
    "SPINE_L":    ["LUMBAR SPINE", "L-SPINE", "L SPINE", "LSPINE", "LUMBOSACRAL", "LUMBAR"],
    "SPINE_S":    ["SACRUM", "SACRAL", "COCCYX"],
    "WHOLE_SPINE":["WHOLE SPINE", "TOTAL SPINE", "SCOLIOSIS SURVEY", "SCOLIOSIS SERIES"],
    "CHEST":      ["CHEST", "THORAX", "THORACIC"],
    "LUNG":       ["LUNG", "PULM", "BRONCH", "PLEURAL"],
    "HEART":      ["CARDIAC", "HEART", "CORONARY", "MYOCARDIAL", "PERICARDIAL", "AORTA"],
    "MEDIASTINUM":["MEDIASTIN"],
    "BREAST":     ["BREAST", "MAMMARY"],
    "ABDOMEN":    ["ABDOMEN", "ABDOM", "ABD ", "LIVER", "PANCREAS", "SPLEEN",
                   "GALLBLADDER", "BILIARY", "BOWEL", "COLON", "STOMACH",
                   "INTESTIN", "MESENTERY", "OMENTUM", "RETROPERITON"],
    "KIDNEY":     ["RENAL", "KIDNEY", "URETER", "URINARY TRACT", "ADRENAL"],
    "PELVIS":     ["PELVIS", "PELVIC", "BLADDER", "UTERUS", "UTERINE",
                   "OVARY", "OVARIAN", "PROSTATE", "RECTUM", "PERINEUM", "SCROTUM"],
    "SHOULDER":   ["SHOULDER", "ACROMIOCLAVICULAR", "AC JOINT", "ROTATOR"],
    "HUMERUS":    ["HUMERUS"],
    "ELBOW":      ["ELBOW"],
    "FOREARM":    ["FOREARM", "RADIUS", "ULNA"],
    "WRIST":      ["WRIST"],
    "HAND":       ["HAND", "FINGER", "THUMB", "METACARP"],
    "UPPER_EXT":  ["UPPER EXTREM", "UPPER EX"],
    "HIP":        ["HIP", "FEMORAL HEAD", "ACETABUL"],
    "FEMUR":      ["FEMUR", "THIGH"],
    "KNEE":       ["KNEE", "PATELLA", "MENISCUS"],
    "TIBIA":      ["TIBIA", "FIBULA", "LOWER LEG"],
    "ANKLE":      ["ANKLE"],
    "FOOT":       ["FOOT", "FEET", "TOE ", "TOES", "CALCANEUS", "HEEL", "METATARS"],
    "LOWER_EXT":  ["LOWER EXTREM", "LOWER EX"],
    "WHOLE_BODY": ["WHOLE BODY", "TOTAL BODY", "TRAUMA SERIES"],
}

# Anatomically adjacent groups — any overlap within a group counts as related
ADJACENCY_GROUPS = [
    {"BRAIN", "HEAD", "ORBIT", "IAC", "FACE", "SINUS", "PITUITARY"},
    {"HEAD", "NECK", "SPINE_C"},
    {"NECK", "SPINE_C"},
    {"SPINE_C", "SPINE_T"},
    {"SPINE_T", "SPINE_L"},
    {"SPINE_L", "SPINE_S"},
    {"WHOLE_SPINE", "SPINE_C", "SPINE_T", "SPINE_L", "SPINE_S"},
    {"CHEST", "LUNG", "HEART", "MEDIASTINUM"},
    {"CHEST", "ABDOMEN"},   # overlap region (lower chest / upper abdomen)
    {"ABDOMEN", "KIDNEY"},
    {"ABDOMEN", "PELVIS"},
    {"PELVIS", "KIDNEY"},
    {"UPPER_EXT", "SHOULDER", "HUMERUS", "ELBOW", "FOREARM", "WRIST", "HAND"},
    {"LOWER_EXT", "HIP", "FEMUR", "KNEE", "TIBIA", "ANKLE", "FOOT"},
    {"WHOLE_BODY"},  # anything vs whole-body is relevant
]


# ---------------------------------------------------------------------------
# Feature extraction
# ---------------------------------------------------------------------------

def get_modality(desc: str) -> Optional[str]:
    u = desc.upper()
    for mod, kws in MODALITY_GROUPS.items():
        for kw in kws:
            if kw in u:
                return mod
    return None


def get_body_parts(desc: str) -> set:
    u = desc.upper()
    found = set()
    for part, kws in BODY_PARTS.items():
        for kw in kws:
            if kw in u:
                found.add(part)
                break
    return found


def parts_are_related(p1: set, p2: set) -> bool:
    if not p1 or not p2:
        return False
    # Direct intersection
    if p1 & p2:
        return True
    # Anatomical adjacency
    for grp in ADJACENCY_GROUPS:
        if (p1 & grp) and (p2 & grp):
            return True
    return False


# ---------------------------------------------------------------------------
# Relevance decision
# ---------------------------------------------------------------------------

def predict_relevance(current_desc: str, prior_desc: str) -> bool:
    c_parts = get_body_parts(current_desc)
    p_parts = get_body_parts(prior_desc)

    # Both have body-part signals → decide on anatomy
    if c_parts and p_parts:
        return parts_are_related(c_parts, p_parts)

    # At least one description yields no body part → fall back to modality
    c_mod = get_modality(current_desc)
    p_mod = get_modality(prior_desc)
    if c_mod and p_mod:
        return c_mod == p_mod

    # No signal at all → conservative: show the prior
    return True


# ---------------------------------------------------------------------------
# Pydantic models
# ---------------------------------------------------------------------------

class Study(BaseModel):
    study_id: str
    study_description: str
    study_date: str

class Case(BaseModel):
    case_id: str
    patient_id: Optional[str] = None
    patient_name: Optional[str] = None
    current_study: Study
    prior_studies: List[Study]

class PredictRequest(BaseModel):
    challenge_id: Optional[str] = None
    schema_version: Optional[int] = None
    generated_at: Optional[str] = None
    cases: List[Case]

class Prediction(BaseModel):
    case_id: str
    study_id: str
    predicted_is_relevant: bool

class PredictResponse(BaseModel):
    predictions: List[Prediction]


# ---------------------------------------------------------------------------
# Endpoint
# ---------------------------------------------------------------------------

@app.post("/predict", response_model=PredictResponse)
def predict(req: PredictRequest):
    predictions = []
    for case in req.cases:
        cur_desc = case.current_study.study_description
        for prior in case.prior_studies:
            relevant = predict_relevance(cur_desc, prior.study_description)
            predictions.append(Prediction(
                case_id=case.case_id,
                study_id=prior.study_id,
                predicted_is_relevant=relevant,
            ))
    return PredictResponse(predictions=predictions)


@app.get("/health")
def health():
    return {"status": "ok"}


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
