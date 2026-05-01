from fastapi import FastAPI
from pydantic import BaseModel
from typing import List, Optional
import re

app = FastAPI()

# ---------------------------------------------------------------------------
# Category definitions — ordered most specific first
# ---------------------------------------------------------------------------
CATEGORIES = [
    ("BONE_SCAN",   ["BONE SCAN", "BONE SURVEY", "BONE WHOLE BODY"]),
    ("PET_CT",      ["PET/CT", "PET-CT", "PET CT", "PET SCAN", "FDG PET"]),
    ("NM_LUNG",     ["NM PUL", "LUNG PERFUSION", "VENTILATION PERFUSION", "V/Q", "VQ SCAN", "PULMONARY PERFUSION"]),
    ("NM_LYMPH",    ["LYMPHOCNT", "LYMPHOSCINTIGRAPHY", "SENTINEL", "NM LYMPH"]),
    ("DXA",         ["BONE DENSITY", "DXA", "DEXA"]),
    ("MAMMOGRAM",   ["MAMMOGR", "MAMMOGRAPHY", "MAM ", "MAM/", "MAMM",
                     "DIGITAL SCREENER", "DIGITAL SCREEN", "BILAT-SCREENING",
                     "SCREENING - COMBO", "STANDARD SCREENING", "SCREENING COMBO",
                     "COMBOHD", "DX BILATERAL COMBO", "BILATERAL COMBO",
                     "BILATERAL TOMO", "SCREENING W/CAD"]),
    ("BREAST",      ["BREAST", "DIAG TARGET", "SCREEN COMP", "DIAG COMP",
                     "SEED LOCALIZATION", "POST BX", "BIOPSY BREAST"]),
    ("CARDIAC",     ["CARDIAC", "ECHO", "MYOCARD", "CORONARY", "PERICARDIAL",
                     "MYO PERF", "LVEF", "EJECTION FRAC", "NM MYO",
                     "NMmyo", "NMMY", " TTE", "/TTE", "LUM TTE", "CT FFR",
                     "CARDIAC CATH", "CATH LAB"]),
    ("CHEST",       ["CHEST", "LUNG", "PULM", "PLEURAL", "HEMOTHORAX",
                     "PNEUMO", "PNEUMOTHORAX", "RIB", "CXR",
                     "THORACENTESIS", "ESOPHAG", "STERNUM"]),
    ("BRAIN",       ["BRAIN", "CEREBR", "INTRACRANIAL", "STROKE", "NEURO"]),
    ("HEAD",        ["HEAD", "CRANIAL", "SKULL"]),
    ("ORBIT",       ["ORBIT", "OPTIC NERVE"]),
    ("IAC",         ["IAC", "INTERNAL AUDITORY"]),
    ("FACE_SINUS",  ["FACE", "FACIAL", "SINUS", "PARANASAL", "MANDIBLE", "MAXILLA", "TMJ"]),
    ("PITUITARY",   ["PITUITARY", "SELLA"]),
    ("NECK",        ["SOFT TISSUE NECK", "NECK SOFT", "NECK ", "THYROID", "CAROTID",
                     "LARYNX", "PHARYNX", "HYPOPHARYNX", "PAROTID", "SUBMANDIBULAR"]),
    ("ABD_PEL",     ["ABD/PEL", "ABD_PEL", "ABDOMEN PELVIS", "ABDOMINAL PELVIS",
                     "ABD PEL", "ABDPEL", "CHEST_ABD_PEL", "CHEST ABD PEL",
                     "ABD AND PEL", "ABDOMEN AND PELVIS", "ENTEROGRAPHY"]),
    ("ABDOMEN",     ["ABDOMEN", "ABDOM", "LIVER", "PANCREAS", "SPLEEN",
                     "GALLBLADDER", "BILIARY", "BOWEL", "COLON", "STOMACH",
                     "INTESTIN", "MESENTERY", "AORTA", "AAA", "HEPATIC",
                     "SPLENIC", "PORTAL", "PARACENTESIS"]),
    ("PELVIS",      ["PELVIS", "PELVIC", "BLADDER", "UTERUS", "UTERINE",
                     "OVARY", "OVARIAN", "PROSTATE", "RECTUM", "PERINEUM",
                     "SCROTUM", "TESTES", "TESTICULAR"]),
    ("KIDNEY",      ["RENAL", "KIDNEY", "URETER", "NEPHRO", "URINARY TRACT"]),
    ("SPINE_C",     ["CERVICAL SPINE", "CERVICL SPINE", "C-SPINE", "C SPINE", "CSPINE",
                     "CERV SPINE", "CERVICL"]),
    ("SPINE_T",     ["THORACIC SPINE", "T-SPINE", "T SPINE", "TSPINE"]),
    ("SPINE_L",     ["LUMBAR SPINE", "L-SPINE", "LUMBOSACRAL", "LUMBAR", "SACRUM", "COCCYX"]),
    ("SPINE_WHOLE", ["WHOLE SPINE", "TOTAL SPINE", "SCOLIOSIS SURVEY", "SCOLIOSIS SERIES",
                     "SCOLIOSIS SRVY", "SCOLIOSIS"]),
    ("SHOULDER",    ["SHOULDER", "ACROMIOCLAVICULAR", "AC JOINT", "ROTATOR"]),
    ("HUMERUS",     ["HUMERUS"]),
    ("ELBOW",       ["ELBOW"]),
    ("FOREARM",     ["FOREARM", "RADIUS", "ULNA"]),
    ("WRIST",       ["WRIST"]),
    ("HAND",        ["HAND", "FINGER", "THUMB", "METACARP"]),
    ("HIP",         ["HIP ", "FEMORAL HEAD", "ACETABUL"]),
    ("FEMUR",       ["FEMUR", "THIGH"]),
    ("KNEE",        ["KNEE", "PATELLA", "MENISCUS"]),
    ("TIBIA",       ["TIBIA", "FIBULA", "LOWER LEG"]),
    ("ANKLE",       ["ANKLE"]),
    ("FOOT",        ["FOOT", "FEET", "TOE ", "CALCANEUS", "HEEL", "METATARS"]),
    ("UPPER_EXT",   ["UPPER EXTREM", "UPPER EX"]),
    ("LOWER_EXT",   ["LOWER EXTREM", "LOWER EX"]),
    ("VASC_LE",     ["VENOUS IMAGING W", "VAS VENOUS", "DOPPLER LE ", "DOPPLER LE,",
                     "DOPPLER BILAT LEG", "VENOUS DOPPLER LE", "VENOUS LOWER"]),
    ("VASC_UE",     ["DOPPLER UE ", "VENOUS DOPPLER UE", "UP VENOUS STUDY",
                     "UPPER EXTREMITY VENOUS"]),
]

# Cross-category pairs that ARE relevant (True)
CROSS_TRUE = {
    frozenset(["MAMMOGRAM", "BREAST"]),
    frozenset(["BRAIN", "HEAD"]),
    frozenset(["ABDOMEN", "ABD_PEL"]),
    frozenset(["PELVIS", "ABD_PEL"]),
    frozenset(["ABDOMEN", "KIDNEY"]),
    frozenset(["PELVIS", "KIDNEY"]),
    frozenset(["SPINE_C", "SPINE_WHOLE"]),
    frozenset(["SPINE_T", "SPINE_WHOLE"]),
    frozenset(["SPINE_L", "SPINE_WHOLE"]),
    frozenset(["NM_LYMPH", "MAMMOGRAM"]),
    frozenset(["NM_LYMPH", "BREAST"]),
    frozenset(["NM_LUNG", "CHEST"]),
    # HEAD ↔ NECK removed: 103 FP vs 60 FN (net negative)
    # CARDIAC ↔ CHEST removed: 193 FP vs 93 TP (net negative)
}

# Whole-body nuclear medicine: relevant to most organ systems
WHOLE_BODY = {"BONE_SCAN", "PET_CT"}
# These categories are irrelevant even vs whole body
EXCLUDE_FROM_WHOLE_BODY = {"DXA"}


# ---------------------------------------------------------------------------
# Laterality extraction (for mammography)
# ---------------------------------------------------------------------------
_LAT_RIGHT = re.compile(r'\b(RT|RIGHT|R)\b', re.IGNORECASE)
_LAT_LEFT  = re.compile(r'\b(LT|LEFT|L)\b', re.IGNORECASE)
_LAT_BI    = re.compile(r'\b(BI|BILAT|BILATERAL|BOTH)\b', re.IGNORECASE)


def get_laterality(desc: str) -> str:
    """Returns 'L', 'R', 'B' (bilateral), or 'U' (unknown)."""
    u = desc.upper()
    has_bi = bool(_LAT_BI.search(u))
    has_r  = bool(_LAT_RIGHT.search(u))
    has_l  = bool(_LAT_LEFT.search(u))
    if has_bi:
        return 'B'
    if has_r and has_l:
        return 'B'
    if has_r:
        return 'R'
    if has_l:
        return 'L'
    return 'U'


def laterality_compatible(d1: str, d2: str) -> bool:
    """Two descriptions are laterality-compatible if sides don't conflict."""
    l1 = get_laterality(d1)
    l2 = get_laterality(d2)
    # If one is bilateral or unknown, always compatible
    if 'U' in (l1, l2) or 'B' in (l1, l2):
        return True
    # Both specific: must be the same side
    return l1 == l2


# ---------------------------------------------------------------------------
# Category detection
# ---------------------------------------------------------------------------

def get_category(desc: str) -> Optional[str]:
    u = desc.upper()
    for cat, kws in CATEGORIES:
        for kw in kws:
            if kw in u:
                return cat
    return None


# ---------------------------------------------------------------------------
# Relevance prediction
# ---------------------------------------------------------------------------

def predict_relevance(cur_desc: str, pri_desc: str) -> bool:
    cur_cat = get_category(cur_desc)
    pri_cat = get_category(pri_desc)

    NON_SYSTEMIC = {"SHOULDER", "HUMERUS", "ELBOW", "FOREARM", "WRIST", "HAND",
                    "HIP", "FEMUR", "KNEE", "TIBIA", "ANKLE", "FOOT",
                    "UPPER_EXT", "LOWER_EXT", "DXA"}
    STAGING_CATS = {"CHEST", "ABD_PEL", "ABDOMEN", "PELVIS", "KIDNEY",
                    "NECK", "HEAD", "BRAIN"}

    if cur_cat in WHOLE_BODY or pri_cat in WHOLE_BODY:
        if cur_cat in EXCLUDE_FROM_WHOLE_BODY or pri_cat in EXCLUDE_FROM_WHOLE_BODY:
            return False

        # BONE SCAN only cross-matches whole-body or staging CTs when it is the current study
        if cur_cat == "BONE_SCAN":
            if pri_cat in WHOLE_BODY or pri_cat in STAGING_CATS:
                return True
            return False
        if pri_cat == "BONE_SCAN":
            # As a prior, bone scan is only useful when current is also whole-body
            return cur_cat in WHOLE_BODY

        # PET/CT: relevant to most non-extremity categories
        other_cat = pri_cat if cur_cat == "PET_CT" else cur_cat
        if other_cat in NON_SYSTEMIC:
            return False
        return True

    # No category detected → conservative: False
    if cur_cat is None or pri_cat is None:
        return False

    # Same category → True, but check laterality for breast imaging
    if cur_cat == pri_cat:
        if cur_cat in ("MAMMOGRAM", "BREAST"):
            return laterality_compatible(cur_desc, pri_desc)
        return True

    # Cross-category explicit matches
    pair = frozenset([cur_cat, pri_cat])
    if pair in CROSS_TRUE:
        # For MAMMOGRAM↔BREAST cross-match, also check laterality
        if "MAMMOGRAM" in pair or "BREAST" in pair:
            return laterality_compatible(cur_desc, pri_desc)
        return True

    return False


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
