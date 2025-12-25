import uuid
import json
from datetime import datetime, timezone

# 接收全套生理參數：包含基礎生命徵象 + 進階身心指標
def create_raw_data_bundle(user_id, user_name, hr, spo2, sys_bp, dia_bp, resp, hrv, stress, sleep, lat, lon):
    
    # 1. 生成唯一 ID
    patient_uuid = str(uuid.uuid4())
    timestamp = datetime.now(timezone.utc).isoformat()

    # --- 2. 建立 Patient (病人資源) ---
    patient = {
        "resourceType": "Patient",
        "id": patient_uuid,
        "identifier": [
            {
                "system": "http://hospital.org/id", # 模擬醫院的身分證系統
                "value": user_id
            }
        ],
        "name": [{"family": "Wang", "given": [user_name]}],
        "gender": "unknown" # 這裡可設參數，暫時預設
    }

    observations = []

    # --- Helper: 快速建立 Observation 的小工具 ---
    def make_obs(code, display, value, unit, unit_code):
        return {
            "resourceType": "Observation",
            "id": str(uuid.uuid4()),
            "status": "final",
            "code": {
                "coding": [{
                    "system": "http://loinc.org", 
                    "code": code, 
                    "display": display
                }]
            },
            "subject": {"reference": f"Patient/{patient_uuid}"},
            "valueQuantity": {
                "value": value,
                "unit": unit,
                "system": "http://unitsofmeasure.org",
                "code": unit_code
            },
            "effectiveDateTime": timestamp
        }

    # --- 3. 建立各項 Observation (生理數據資源) ---
    
    # [生命徵象 Vital Signs]
    observations.append(make_obs("8867-4", "Heart rate", hr, "beats/minute", "/min"))
    observations.append(make_obs("2708-6", "Oxygen saturation", spo2, "%", "%"))
    observations.append(make_obs("9279-1", "Respiratory rate", resp, "breaths/minute", "/min"))
    
    # [進階指標 Advanced Metrics]
    # HRV (使用 LOINC 80404-7 R-R interval SD)
    observations.append(make_obs("80404-7", "Heart rate variability (SDNN)", hrv, "ms", "ms"))
    # 睡眠時間 (LOINC 9383-2)
    observations.append(make_obs("9383-2", "Sleep duration", sleep, "h", "h"))
    # 壓力指數 (LOINC 70-5 General stress score)
    observations.append(make_obs("70-5", "General stress score", stress, "score", "{score}"))

    # [血壓面板 Blood Pressure Panel]
    # 血壓比較特殊，是一個 Panel 包含收縮壓與舒張壓
    bp_obs = {
        "resourceType": "Observation",
        "id": str(uuid.uuid4()),
        "status": "final",
        "code": {"coding": [{"system": "http://loinc.org", "code": "85354-9", "display": "Blood pressure panel"}]},
        "subject": {"reference": f"Patient/{patient_uuid}"},
        "effectiveDateTime": timestamp,
        "component": [
            {
                "code": {"coding": [{"system": "http://loinc.org", "code": "8480-6", "display": "Systolic blood pressure"}]},
                "valueQuantity": {"value": sys_bp, "unit": "mmHg", "system": "http://unitsofmeasure.org", "code": "mm[Hg]"}
            },
            {
                "code": {"coding": [{"system": "http://loinc.org", "code": "8462-4", "display": "Diastolic blood pressure"}]},
                "valueQuantity": {"value": dia_bp, "unit": "mmHg", "system": "http://unitsofmeasure.org", "code": "mm[Hg]"}
            }
        ],
        # [定位資訊] 將 GPS 藏在 Extension 裡，供緊急救援定位用
        "extension": [
            {
                "url": "http://hl7.org/fhir/StructureDefinition/geolocation", 
                "valueAddress": {"text": f"{lat},{lon}"}
            }
        ]
    }
    observations.append(bp_obs)

    # --- 4. 打包成 Transaction Bundle ---
    entries = []
    
    # 加入 Patient 的寫入請求
    entries.append({
        "fullUrl": f"urn:uuid:{patient_uuid}", 
        "resource": patient, 
        "request": {"method": "POST", "url": "Patient"}
    })
    
    # 加入所有 Observation 的寫入請求
    for obs in observations:
        entries.append({
            "fullUrl": f"urn:uuid:{obs['id']}", 
            "resource": obs, 
            "request": {"method": "POST", "url": "Observation"}
        })

    bundle = {
        "resourceType": "Bundle",
        "type": "transaction",
        "entry": entries
    }
    
    # 回傳：打包好的 Bundle, 病人ID (給Session用), 第一筆數據ID (給AI追溯用)
    return bundle, patient_uuid, observations[0]['id']

# 測試區
if __name__ == "__main__":
    b, pid, oid = create_raw_data_bundle("A123", "TestUser", 75, 98, 110, 70, 16, 50, 20, 7, 25.0, 121.0)
    print(json.dumps(b, indent=2))
