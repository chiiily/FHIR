import uuid
import json
from datetime import datetime, timezone

def analyze_and_create_report(vitals, patient_id):
    """
    輸入 vitals 字典包含: hr, spo2, hrv, stress, sleep, sys_bp ...
    輸出: FHIR Bundle, 狀態類別(status), 描述(description), 風險評估ID(risk_id)
    """
    
    # 1. 初始化
    risk_id = str(uuid.uuid4())
    timestamp = datetime.now(timezone.utc).isoformat()
    
    # 預設狀態：正常
    status_type = "normal" 
    risk_level = "low"
    description = "All vital signs are within normal limits."
    
    # === 2. AI 判斷邏輯 (規則引擎) ===

    # [規則 A: 急救回應流程 (Emergency Response)]
    # 條件：心率極端異常、血氧過低、或血壓危象
    # 邏輯：只要中一個，就是最高級別危險
    if (vitals['hr'] > 170 or vitals['hr'] < 40) or \
       (vitals['spo2'] < 85) or \
       (vitals['sys_bp'] > 180):
           
        status_type = "emergency"
        risk_level = "critical"
        
        reasons = []
        if vitals['hr'] > 170: reasons.append("Severe Tachycardia")
        if vitals['hr'] < 40: reasons.append("Severe Bradycardia")
        if vitals['spo2'] < 85: reasons.append("Hypoxia")
        if vitals['sys_bp'] > 180: reasons.append("Hypertensive Crisis")
        
        description = f"CRITICAL: {', '.join(reasons)}. Immediate medical intervention required."

    # [規則 B: 預防監測流程 (Preventive Flow)]
    # 條件：非急救狀態，但 壓力過高、睡眠不足 或 HRV 過低
    elif (vitals['stress'] > 80) or \
         (vitals['sleep'] < 5) or \
         (vitals['hrv'] < 30):
             
        status_type = "preventive"
        risk_level = "high"
        
        reasons = []
        if vitals['stress'] > 80: reasons.append("High Stress Level")
        if vitals['sleep'] < 5: reasons.append("Sleep Deprivation")
        if vitals['hrv'] < 30: reasons.append("Low HRV (Fatigue)")
        
        description = f"WARNING: {', '.join(reasons)}. Rest recommended to prevent burnout."
    
    # === 3. 產出 RiskAssessment (風險評估報告) ===
    # 這份報告是 AI 思考後的結晶，會存回 Server
    risk_assessment = {
        "resourceType": "RiskAssessment",
        "id": risk_id,
        "status": "final",
        "subject": {"reference": f"Patient/{patient_id}"},
        "occurrenceDateTime": timestamp,
        "prediction": [
            {
                "outcome": {"text": description}, # AI 的文字診斷
                # 根據狀態給予機率值 (急救=0.95, 預防=0.6, 正常=0.1)
                "probabilityDecimal": 0.95 if status_type == "emergency" else (0.6 if status_type == "preventive" else 0.1),
                "qualitativeRisk": {
                    "coding": [{
                        "system": "http://terminology.hl7.org/CodeSystem/risk-probability",
                        "code": risk_level # critical / high / low
                    }]
                }
            }
        ]
    }

    # === 4. 打包回傳 ===
    entries = [
        {
            "fullUrl": f"urn:uuid:{risk_id}", 
            "resource": risk_assessment, 
            "request": {"method": "POST", "url": "RiskAssessment"}
        }
    ]
    
    ai_bundle = {
        "resourceType": "Bundle",
        "type": "transaction",
        "entry": entries
    }
    
    # 回傳這些資料讓 App 決定畫面要變紅色(Emergency) 還是 黃色(Preventive)
    return ai_bundle, status_type, description, risk_id

# 測試區
if __name__ == "__main__":
    # 模擬一個危險數據
    test_vitals = {"hr": 180, "spo2": 95, "sys_bp": 120, "stress": 50, "sleep": 7, "hrv": 50}
    b, s, d, rid = analyze_and_create_report(test_vitals, "test-pid")
    print(f"Status: {s}") # 應該要是 emergency
    print(json.dumps(b, indent=2))
