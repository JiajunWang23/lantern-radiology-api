# Experiments: Relevant Prior Prediction

## Problem Summary

Given a current radiology examination and a list of prior examinations for the same patient, predict which priors a radiologist would want to see when reading the current study.

## Approach: Structured Category Matching

I chose a rule-based keyword categorization approach over LLM-based inference for reliability and speed (no timeout risk with 27K+ pairs, deterministic output, and no API costs).

### Method

1. **Category taxonomy**: Each study description is mapped to one of ~35 anatomical/clinical categories (CHEST, HEAD, BRAIN, MAMMOGRAM, BREAST, ABD_PEL, ABDOMEN, PELVIS, SPINE_C/T/L, CARDIAC, BONE_SCAN, PET_CT, and ~15 extremity/specialty categories).

2. **Relevance rules**:
   - **Same category → True** (with laterality check for breast imaging)
   - **Explicit cross-category pairs → True** (e.g., BRAIN↔HEAD, MAMMOGRAM↔BREAST, ABD_PEL↔ABDOMEN, ABD_PEL↔PELVIS, NM_LUNG↔CHEST, SPINE↔SPINE_WHOLE)
   - **Whole-body studies (BONE_SCAN, PET_CT)**: BONE_SCAN as current matches staging CTs (CHEST, ABD_PEL, etc.); PET_CT matches most non-extremity categories on both sides; BONE_SCAN as prior only matches other whole-body studies.
   - **No category detected → False** (conservative default)

3. **Laterality handling**: For mammography and breast studies, studies labeled left-only (LT/LEFT) do not match right-only (RT/RIGHT), but bilateral (BI/BILATERAL) or unlabeled studies match either side.

### Iteration History

| Version | Public Eval Accuracy | Key Change |
|---------|---------------------|------------|
| Baseline (keyword adjacency) | 62.5% | Broad body-region adjacency — too permissive |
| Strict categories + no adjacency | 89.9% | Dropped to conservative same-category matching |
| + Laterality for mammography | 92.3% | Removed CARDIAC↔CHEST (193 FP vs 93 TP) |
| + Bone scan directionality fix | 93.9% | BONE_SCAN as prior → only matches whole-body |
| + ABD_PEL cross-matches, PET fix | 94.2% | Added back ABD_PEL↔ABDOMEN and ABD_PEL↔PELVIS |
| + Keyword expansion | **94.9%** | Added THORACENTESIS, ESOPHAG, TTE, ABD_PEL underscore, CERVICL, vascular LE |
| Quick-check (10 public cases) | **98.27%** | — |

### What Worked
- **Conservative default (False)**: The base rate is only ~24% relevant, so defaulting to False gives 76% accuracy. Being selective and only predicting True with strong evidence beats trying to be inclusive.
- **Separating CHEST from CARDIAC**: Echocardiograms are not relevant priors for plain chest X-rays, even though both involve the thorax. Net -100 accuracy points if cross-matched.
- **Removing ABDOMEN↔PELVIS direct match**: CT abdomen alone and CT pelvis alone are often ordered for different clinical reasons; only combined ABD_PEL is consistently cross-relevant.
- **PET/CT vs BONE SCAN directionality**: PET/CT (follow-up staging) is relevant as a prior to CT chest, but bone scans as priors are only useful when the current study is also whole-body.
- **Mammography laterality**: Right-side and left-side unilateral mammograms are separate reads; bilateral mammograms are relevant to both.

### What Failed
- **Broad adjacency groups**: Treating all "chest region" studies as mutually relevant caused massive false positives (thoracic spine ≠ chest CT for most radiologists).
- **HEAD↔NECK cross-match**: Added 103 false positives for only 60 false negatives — not worth the trade.
- **PET/CT matching MAMMOGRAM**: Staging PET/CT is not relevant to routine mammography reads.

### Remaining Error Sources (Public Eval, ~5% error rate)

- **CARDIAC↔CHEST** (93 FN + 40 FN): ECHO TEE is relevant to CT chest (aorta context), but cardiac NM is not. Direction-specific matching would help.
- **NONE→CHEST (96 FN)**: Descriptions like "CT GUIDED FNA" have no detectable primary organ; some are genuinely chest-relevant.
- **NONE→NONE (85 FN)**: Abbreviation variants, misspellings, and institution-specific codes (e.g., "STANDARD SCREENING - COMBOHD") not in the keyword table.
- **SPINE_C→CHEST (42 FN)**: Cervical spine CTs appear clinically paired with chest CTs in this dataset; possibly staging for cancer patients.
- **Same-category FPs (33 CHEST, 31 HEAD, 26 MAM)**: Within-category mismatches suggest some descriptions don't describe the same primary target even when sharing a keyword.

## Next-Step Improvements

1. **LLM-based classification (batched)**: Use a medical LLM (GPT-4o, Claude 3.5) to classify each unique study description into a canonical clinical category. Send all unique descriptions in one batched call. This would handle abbreviation variants, typos, and institution-specific codes automatically. Expected improvement: ~2-4%.

2. **Direction-aware cross-category rules**: Model asymmetric relevance (e.g., ECHO TEE as current → CT chest prior is True, but CT chest as current → ECHO TTE prior is False) by passing `(cur_cat, pri_cat)` tuples rather than frozensets.

3. **Training a small classifier**: With 27K labeled pairs, a logistic regression or lightweight neural model on bag-of-words study description features could learn cross-category patterns automatically. Features: description tokens, modality tags, laterality, body region.

4. **Fine-grained cardiac sub-categories**: Split CARDIAC into TEE (transesophageal), TTE (transthoracic), NM_CARDIAC (nuclear), CT_CORONARY (coronary angio). TEE and CT_CORONARY cross-match with CHEST; TTE and NM_CARDIAC do not.

5. **Institution-specific code lookup table**: Build a lookup table from observed codes in the training data (e.g., "STANDARD SCREENING - COMBOHD" → MAMMOGRAM, "CT ABD_PEL" → ABD_PEL). Reduces NONE-category cases significantly.

6. **Temporal signal**: More recent same-category priors may be more relevant. Priors within 5 years of current may be more useful than older ones. Adding a date-based recency signal could improve ranking even if binary accuracy stays similar.
