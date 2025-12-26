import uuid
from datetime import datetime, timezone

def analyze_and_create_report(vitals, patient_id):
    """
    接收參數 vitals: { 'hr', 'spo2', 'hrv', 'sys_bp', 'sleep', ... }
    回傳: FHIR Bundle, status (normal/preventive/emergency), description, risk_id
    """
    
    # 1. 初始化
    risk_id = str(uuid.uuid4())
    timestamp = datetime.now(timezone.utc).isoformat()
    
    # 預設狀態
    status_type = "normal" 
    risk_level = "low"
    description = "生理數據穩定 (Vital signs within normal range)"
    
    # 2. 安全讀取數據 (防呆)
    try:
        hr = float(vitals.get('hr', 75))
        spo2 = float(vitals.get('spo2', 98))
        hrv = float(vitals.get('hrv', 50))
        sys_bp = float(vitals.get('sys_bp', 110))
        sleep = float(vitals.get('sleep', 7))
    except Exception as e:
        return {}, "normal", f"數據錯誤: {str(e)}", risk_id

    # === 3. AI 判斷邏輯 (雙向偵測) ===
    
    reasons = []

    # --- 規則 A: 紅色緊急警報 (Critical) ---
    # 這些狀況代表生命受到威脅，需要醫生立即介入
    
    # 1. 心率異常 (過快 > 160 或 過慢 < 40)
    if hr > 160: reasons.append(f"嚴重頻脈(HR {int(hr)})")
    if hr < 40:  reasons.append(f"嚴重緩脈(HR {int(hr)})")
    
    # 2. 血氧異常 (低於 88% 為呼吸衰竭風險)
    if spo2 < 88: reasons.append(f"嚴重缺氧(SpO2 {int(spo2)}%)")
    
    # 3. 血壓異常 (過高 > 180 為危象，過低 < 90 為休克風險)
    if sys_bp > 180: reasons.append(f"高血壓危象({int(sys_bp)})")
    if sys_bp < 90:  reasons.append(f"低血壓休克({int(sys_bp)})")

    # 判定是否為緊急
    if reasons:
        status_type = "emergency"
        risk_level = "critical"
        description = f"🚨【緊急】生命徵象危急: {', '.join(reasons)}"

    else:
        # --- 規則 B: 黃色預防警報 (Preventive) ---
        # 如果不是緊急，再檢查是否有潛在風險 (疲勞、輕微異常)
        
        # 1. 輕微異常 (心率偏快/偏慢、血氧偏低)
        if hr > 110: reasons.append("心率偏快")
        if hr < 50:  reasons.append("心率偏慢")
        if spo2 < 94: reasons.append("輕微缺氧")
        
        # 2. 疲勞與壓力指標 (HRV, 睡眠)
        if hrv < 35: reasons.append("HRV過低(疲勞)")
        if sleep < 5.0: reasons.append("睡眠嚴重不足")

        # 判定是否為預防警報
        if reasons:
            status_type = "preventive"
            risk_level = "high"
            description = f"⚠️【注意】健康風險上升: {', '.join(reasons)}，建議休息或就醫檢查。"
        else:
            # --- 規則 C: 正常 ---
            status_type = "normal"
            risk_level = "low"
            description = f"✅ 健康狀況良好 (HR:{int(hr)}, SpO2:{int(spo2)}%)"

    # === 4. 產出 FHIR RiskAssessment ===
    risk_assessment = {
        "resourceType": "RiskAssessment",
        "id": risk_id,
        "status": "final",
        "subject": {"reference": f"Patient/{patient_id}"},
        "occurrenceDateTime": timestamp,
        "prediction": [{
            "outcome": {"text": description},
            "probabilityDecimal": 0.95 if status_type == "emergency" else (0.6 if status_type == "preventive" else 0.1),
            "qualitativeRisk": {
                "coding": [{
                    "system": "http://terminology.hl7.org/CodeSystem/risk-probability",
                    "code": risk_level 
                }]
            }
        }]
    }

    # === 5. 打包 ===
    entries = [{
        "fullUrl": f"urn:uuid:{risk_id}", 
        "resource": risk_assessment, 
        "request": {"method": "POST", "url": "RiskAssessment"}
    }]
    
    ai_bundle = {
        "resourceType": "Bundle", 
        "type": "transaction", 
        "entry": entries
    }
    
    return ai_bundle, status_type, description, risk_id
