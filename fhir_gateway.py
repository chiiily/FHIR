import uuid
import json
from datetime import datetime, timezone

# 這是一個工具函式，專門用來接收參數並產出 FHIR Bundle
# 輸入：心率、緯度、經度、姓名
# 輸出：(Bundle字典, 病人ID, 觀察數據ID)
def create_raw_data_bundle(heart_rate, lat, lon, user_name="User"):
    
    # 1. 生成唯一的資源 ID (UUID)
    # 這些 ID 很重要，因為這代表這筆資料在世界上的唯一身分證
    patient_id = str(uuid.uuid4())
    obs_id = str(uuid.uuid4())
    
    # 取得目前標準時間 (UTC)
    timestamp = datetime.now(timezone.utc).isoformat()

    # --- 2. 建立 Patient (病人資源) ---
    patient = {
        "resourceType": "Patient",
        "id": patient_id,
        "name": [{"family": "Wang", "given": [user_name]}],
        "gender": "male" # 這裡簡化固定為男性，實際可改為參數傳入
    }

    # --- 3. 建立 Observation (生理數值資源) ---
    # 這是最核心的部分，使用 LOINC 8867-4 代表心率
    observation = {
        "resourceType": "Observation",
        "id": obs_id,
        "status": "final",
        "code": {
            "coding": [{
                "system": "http://loinc.org",
                "code": "8867-4",
                "display": "Heart rate"
            }]
        },
        # 建立關聯：這筆數據屬於哪位病人
        "subject": {"reference": f"Patient/{patient_id}"},
        
        # 數值與單位
        "valueQuantity": {
            "value": heart_rate,
            "unit": "beats/minute",
            "system": "http://unitsofmeasure.org",
            "code": "/min"
        },
        "effectiveDateTime": timestamp,
        
        # 把 GPS 位置藏在 component 裡 (擴充用法)
        "component": [
            {"code": {"text": "latitude"}, "valueQuantity": {"value": lat}},
            {"code": {"text": "longitude"}, "valueQuantity": {"value": lon}}
        ]
    }

    # --- 4. 打包成 Transaction Bundle ---
    # Transaction 代表這包資料要嘛全部存成功，要嘛全部失敗 (保持一致性)
    bundle = {
        "resourceType": "Bundle",
        "type": "transaction",
        "entry": [
            {
                "fullUrl": f"urn:uuid:{patient_id}", 
                "resource": patient, 
                "request": {"method": "POST", "url": "Patient"}
            },
            {
                "fullUrl": f"urn:uuid:{obs_id}", 
                "resource": observation, 
                "request": {"method": "POST", "url": "Observation"}
            }
        ]
    }
    
    # 回傳三個東西：打包好的資料, 病人ID, 數據ID (後兩個給 AI 用)
    return bundle, patient_id, obs_id

# ==========================================
#  獨立測試區 (Unit Test)
#  當你直接執行這個檔案時，會跑這段程式，用來檢查 JSON 對不對
# ==========================================
if __name__ == "__main__":
    print("正在測試 FHIR Gateway...")
    
    # 模擬輸入數據
    test_hr = 175
    test_name = "Test-User"
    
    # 呼叫函式
    bundle, pid, oid = create_raw_data_bundle(test_hr, 25.033, 121.565, test_name)
    
    # 印出結果
    print(f"✅ 轉換成功！")
    print(f"病人 ID: {pid}")
    print(f"數據 ID: {oid}")
    print("JSON 內容預覽:")
    print(json.dumps(bundle, indent=2, ensure_ascii=False))