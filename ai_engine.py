import uuid
import json
from datetime import datetime, timezone

# 這是 AI 核心函式
# 輸入：心率數值, 病人ID, 原始數據ID (因為 AI 需要知道是針對哪筆資料做分析)
# 輸出：(AI分析包 Bundle, 風險等級字串)
def analyze_and_create_report(heart_rate, patient_id, obs_id):
    
    # 1. 生成這次分析報告的 ID
    risk_id = str(uuid.uuid4())
    timestamp = datetime.now(timezone.utc).isoformat()

    # ==========================================
    #  🧠 AI 判斷邏輯 (這裡是你可以自由發揮的地方)
    #  目前使用規則基礎 (Rule-based)，未來可換成機器學習模型
    # ==========================================
    risk_level = "low"
    probability = 0.1
    description = "Vital signs within normal limits"
    action_needed = False

    if heart_rate > 150:
        risk_level = "high"
        probability = 0.85
        description = "CRITICAL: Tachycardia detected. Risk of Cardiac Arrest."
        action_needed = True # 需要急救！
        
    elif heart_rate < 50:
        risk_level = "moderate"
        probability = 0.45
        description = "WARNING: Bradycardia detected. Monitor required."
        
    else:
        # 正常數值
        risk_level = "low"
        probability = 0.12
        description = "Normal Sinus Rhythm."

    # ==========================================
    #  📝 產出 FHIR Resource: RiskAssessment (風險評估報告)
    # ==========================================
    risk_assessment = {
        "resourceType": "RiskAssessment",
        "id": risk_id,
        "status": "final",
        "subject": {"reference": f"Patient/{patient_id}"}, # 指向那位病人
        "basis": [{"reference": f"Observation/{obs_id}"}], # 憑據：我是根據剛剛那筆心率判斷的
        "occurrenceDateTime": timestamp,
        "prediction": [{
            "outcome": {"text": description}, # AI 的文字診斷
            "probabilityDecimal": probability, # AI 算出的機率 (0.0~1.0)
            "qualitativeRisk": {
                "coding": [{
                    "system": "http://terminology.hl7.org/CodeSystem/risk-probability",
                    "code": risk_level, # low / moderate / high
                    "display": risk_level.capitalize() + " likelihood"
                }]
            }
        }]
    }

    # 開始準備要打包的清單
    entries = [
        {
            "fullUrl": f"urn:uuid:{risk_id}", 
            "resource": risk_assessment, 
            "request": {"method": "POST", "url": "RiskAssessment"}
        }
    ]

    # ==========================================
    #  🚑 產出 FHIR Resource: ServiceRequest (如果需要急救)
    #  這是 "閉鎖迴路" 的關鍵：AI 自動幫你掛號或叫救護車
    # ==========================================
    if action_needed:
        req_id = str(uuid.uuid4())
        
        service_request = {
            "resourceType": "ServiceRequest",
            "id": req_id,
            "status": "active",
            "intent": "order", # 這是一個命令
            "priority": "stat", # STAT = 立刻執行！
            "code": {
                "coding": [{
                    "system": "http://snomed.info/sct",
                    "code": "40617009", 
                    "display": "Emergency medical intervention" # 緊急醫療介入
                }]
            },
            "subject": {"reference": f"Patient/{patient_id}"},
            "reasonReference": [{"reference": f"urn:uuid:{risk_id}"}] # 理由：因為上面的風險評估
        }
        
        # 把急救請求也加進包裹裡
        entries.append({
            "fullUrl": f"urn:uuid:{req_id}", 
            "resource": service_request, 
            "request": {"method": "POST", "url": "ServiceRequest"}
        })

    # ==========================================
    #  📦 最終打包
    # ==========================================
    ai_bundle = {
        "resourceType": "Bundle",
        "type": "transaction",
        "entry": entries
    }
    
    # 回傳 Bundle 給 app.py 去上傳，同時回傳 risk_level 給 app.py 決定要不要讓手錶震動
    return ai_bundle, risk_level


# 獨立測試區
if __name__ == "__main__":
    print("🤖 正在測試 AI Engine...")
    
    # 模擬狀況：心率飆到 180
    test_hr = 180
    test_pid = str(uuid.uuid4())
    test_oid = str(uuid.uuid4())
    
    bundle, risk = analyze_and_create_report(test_hr, test_pid, test_oid)
    
    print(f"心率: {test_hr}")
    print(f"AI 判定風險等級: {risk}")
    
    if risk == "high":
        print("🚨 AI 已自動生成急救指令 (ServiceRequest)！")
        
    print(json.dumps(bundle, indent=2))