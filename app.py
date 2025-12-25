import streamlit as st
import requests
import uuid
import time
import re  # [新增] 用來解析伺服器回傳的 ID 字串
from datetime import datetime, timezone

# --- 匯入模組 ---
try:
    from fhir_gateway import create_raw_data_bundle
    from ai_engine import analyze_and_create_report
except ImportError:
    st.error("❌ 找不到必要的模組 (fhir_gateway.py 或 ai_engine.py)。")
    st.stop()

st.set_page_config(layout="wide", page_title="h1 雙軌醫療系統 (FHIR 標準版)")

# 使用 HAPI FHIR R4 公用伺服器
FHIR_SERVER_URL = "https://hapi.fhir.org/baseR4"

# --- 初始化 Session State ---
if 'watch_screen' not in st.session_state: st.session_state['watch_screen'] = "normal"
if 'watch_message' not in st.session_state: st.session_state['watch_message'] = None 
if 'has_data' not in st.session_state: st.session_state['has_data'] = False
if 'vitals' not in st.session_state: st.session_state['vitals'] = {}
if 'pid' not in st.session_state: st.session_state['pid'] = None
if 'server_pid' not in st.session_state: st.session_state['server_pid'] = None # [新增] 用來存伺服器回傳的 ID
if 'ai_status' not in st.session_state: st.session_state['ai_status'] = "unknown"
if 'risk_id' not in st.session_state: st.session_state['risk_id'] = None

# --- Helper Functions ---

def send_bundle(bundle):
    headers = {"Content-Type": "application/fhir+json"}
    if bundle.get("resourceType") == "Bundle":
        bundle["type"] = "transaction"
    
    try:
        response = requests.post(FHIR_SERVER_URL, json=bundle, headers=headers, timeout=20)
        if response.status_code not in [200, 201]:
            st.error(f"上傳失敗 (HTTP {response.status_code})")
            with st.expander("🔍 查看伺服器錯誤詳情"):
                st.text(response.text)
            return None
        return response
    except requests.exceptions.RequestException as e:
        st.error(f"連線錯誤: {e}")
        return None

def extract_id_from_response(response_json, resource_type="Patient"):
    """
    [新增] 從 Server 回傳的 Bundle Response 中提取指定資源的 ID
    格式通常為: ResourceType/ID/_history/Version
    """
    try:
        if 'entry' in response_json:
            for entry in response_json['entry']:
                # 檢查 response 欄位中的 location
                if 'response' in entry and 'location' in entry['response']:
                    location = entry['response']['location']
                    # 判斷是否為我們要找的資源類型
                    if location.startswith(resource_type):
                        # 使用正則表達式提取 ID (在 ResourceType/ 和 /_history 之間)
                        parts = location.split('/')
                        if len(parts) >= 2:
                            return parts[1] # 傳回 ID 部分
    except Exception as e:
        return None
    return None

def send_service_request(patient_id, risk_id):
    """發送醫療處置請求 (Start CPR)"""
    req_id = str(uuid.uuid4())
    safe_risk_id = risk_id if risk_id else "unknown"
    sr = {
        "resourceType": "ServiceRequest",
        "id": req_id,
        "status": "active",
        "intent": "order",
        "priority": "stat",
        "code": {"coding": [{"system": "http://snomed.info/sct", "code": "40617009", "display": "Start CPR"}]},
        "subject": {"reference": f"Patient/{patient_id}"},
        "reasonReference": [{"reference": f"RiskAssessment/{safe_risk_id}"}],
    }
    bundle = {
        "resourceType": "Bundle",
        "type": "transaction",
        "entry": [{
            "resource": sr,
            "request": {"method": "POST", "url": "ServiceRequest"}
        }]
    }
    res = send_bundle(bundle)
    return req_id, sr, res

def send_communication_request(patient_id, message_text, priority="routine"):
    """發送溝通請求"""
    req_id = str(uuid.uuid4())
    timestamp = datetime.now(timezone.utc).isoformat()
    comm_req = {
        "resourceType": "CommunicationRequest",
        "id": req_id,
        "status": "active",
        "priority": priority,
        "subject": {"reference": f"Patient/{patient_id}"},
        "payload": [{"contentString": message_text}],
        "authoredOn": timestamp,
        "category": [{"coding": [{"system": "http://terminology.hl7.org/CodeSystem/communication-category", "code": "instruction"}]}]
    }
    bundle = {
        "resourceType": "Bundle",
        "type": "transaction",
        "entry": [{
            "resource": comm_req,
            "request": {"method": "POST", "url": "CommunicationRequest"}
        }]
    }
    res = send_bundle(bundle)
    return req_id, comm_req, res

# --- UI 開始 ---
st.title("🏥 h1 智慧醫療系統：CommunicationRequest 實作")
st.caption(f"目前連線伺服器: {FHIR_SERVER_URL}")

tab1, tab2 = st.tabs(["⌚ 穿戴裝置 (User)", "👨‍⚕️ 醫療中心 (Doctor)"])

# ==========================================
#  TAB 1: 手錶端
# ==========================================
with tab1:
    col_watch, col_sensor = st.columns([1, 1.5])

    with col_watch:
        st.subheader("📱 手錶畫面")
        state = st.session_state['watch_screen']
        msg = st.session_state['watch_message']

        if state == "cpr":
            st.error("🆘 EMERGENCY - ServiceRequest Received")
            st.markdown("""
            <div style="background-color: #d32f2f; color: white; padding: 20px; border-radius: 10px; text-align: center; animation: pulse 1s infinite;">
                <h1>START CPR</h1>
                <p>🚑 Ambulance Dispatched</p>
            </div>
            <style>@keyframes pulse { 0% {transform: scale(1);} 50% {transform: scale(1.05);} 100% {transform: scale(1);} }</style>
            """, unsafe_allow_html=True)
            if st.button("🔕 解除急救"):
                st.session_state['watch_screen'] = "normal"
                st.rerun()

        elif msg:
            st.info("📩 收到新訊息 (CommunicationRequest)")
            st.markdown(f"""
            <div style="background-color: #e3f2fd; color: #0d47a1; padding: 15px; border-radius: 10px; border-left: 5px solid #2196f3;">
                <strong>👨‍⚕️ Dr. AI:</strong><br>
                <span style="font-size: 1.2em;">{msg}</span>
            </div>
            """, unsafe_allow_html=True)
            if st.button("知道了 (Dismiss Msg)"):
                st.session_state['watch_message'] = None
                st.rerun()

        elif state == "rest":
            st.warning("⚠️ 疲勞預警")
            st.write("檢測到高壓力，請休息。")
            if st.button("✅ 解除提醒"):
                st.session_state['watch_screen'] = "normal"
                st.rerun()

        else:
            st.success("✅ 監測中...")
            if st.session_state['has_data']:
                v = st.session_state['vitals']
                # [新增] 這裡顯示伺服器回傳的 ID
                server_id_display = st.session_state.get('server_pid', 'Unknown')
                st.metric("FHIR ID", server_id_display)
                st.metric("Heart Rate", f"{v.get('hr')} bpm")

    with col_sensor:
        st.subheader("⚙️ 生理感測")
        c1, c2 = st.columns(2)
        user_name = c1.text_input("姓名", "Wang Xiao-Mei")
        user_id = c2.text_input("身分證號", "A223456789")
        
        hr = st.slider("❤️ 心率", 40, 200, 75)
        spo2 = st.slider("💧 血氧", 70, 100, 98)
        hrv = st.slider("📈 HRV", 10, 100, 60)
        stress = st.slider("🤯 壓力", 0, 100, 20)
        
        sys_bp, dia_bp, resp_rate, sleep_hours = 110, 70, 16, 7

        if st.button("📡 上傳數據"):
            with st.spinner("上傳並等待伺服器確認..."):
                raw_bundle, pid, oid = create_raw_data_bundle(
                    user_id, user_name, hr, spo2, sys_bp, dia_bp, resp_rate, hrv, stress, sleep_hours, 25.033, 121.565
                )
                
                # 自動修正請求方法為 PUT
                if 'entry' in raw_bundle:
                    for entry in raw_bundle['entry']:
                        resource = entry.get('resource', {})
                        res_type = resource.get('resourceType')
                        res_id = resource.get('id')
                        if res_type == 'Patient':
                            entry['request'] = {"method": "PUT", "url": f"Patient/{res_id}"}
                        elif 'request' not in entry:
                            entry['request'] = {"method": "POST", "url": res_type}

                res = send_bundle(raw_bundle)
                
                if res and res.status_code in [200, 201]:
                    # [新增重點] 解析伺服器回傳的 ID
                    server_response = res.json()
                    confirmed_patient_id = extract_id_from_response(server_response, "Patient")
                    
                    # 如果解析失敗（防呆），就用原本我們生成的 ID
                    final_pid = confirmed_patient_id if confirmed_patient_id else pid

                    st.session_state['pid'] = final_pid
                    st.session_state['server_pid'] = final_pid # 存入 session
                    st.session_state['has_data'] = True
                    st.session_state['vitals'] = {
                        "hr": hr, "spo2": spo2, "hrv": hrv, "stress": stress, 
                        "name": user_name, "sys_bp": sys_bp, "dia_bp": dia_bp, 
                        "resp": resp_rate, "sleep": sleep_hours
                    }
                    st.session_state['watch_screen'] = "normal"
                    
                    # 顯示綠色大框框告知使用者
                    st.success(f"上傳成功！伺服器已確認病患 ID: {final_pid}")
                    with st.expander("查看 Server 回傳的 JSON (Response)"):
                        st.json(server_response)
                else:
                    pass

# ==========================================
#  TAB 2: 醫療中心 (Doctor)
# ==========================================
with tab2:
    st.header("Step 4: AI & Doctor Dashboard")
    
    if st.session_state['has_data']:
        v = st.session_state['vitals']
        # [修改] 顯示伺服器確認的 ID
        pid_display = st.session_state.get('server_pid', 'Unknown')
        st.info(f"當前病患: {v['name']} (FHIR ID: {pid_display}) | HR: {v['hr']} | SpO2: {v['spo2']}")

        if st.button("🤖 AI 風險計算"):
            with st.spinner("AI 分析中..."):
                bundle, status, desc, risk_id = analyze_and_create_report(v, st.session_state['pid'])
                res = send_bundle(bundle)
                
                if res and res.status_code in [200, 201]:
                    st.session_state['ai_status'] = status
                    st.session_state['risk_id'] = risk_id
                    
                    if status == "preventive":
                        st.warning(f"預防警報: {desc}")
                        st.session_state['watch_screen'] = "rest"
                    elif status == "emergency":
                        st.error(f"緊急警報: {desc}")
                    else:
                        st.success("數據正常")
                else:
                    st.error("AI 報告上傳失敗")

        st.markdown("---")
        c_comm, c_ems = st.columns(2)

        with c_comm:
            st.subheader("💬 醫生遠端指令")
            doc_msg = st.text_input("輸入醫囑:", "請多喝水並保持冷靜。")
            if st.button("📤 發送訊息"):
                req_id, comm_json, res = send_communication_request(
                    st.session_state['pid'], doc_msg, priority="routine"
                )
                if res and res.status_code in [200, 201]:
                    st.session_state['watch_message'] = doc_msg
                    st.toast("已發送", icon="📨")
                    with st.expander("JSON"): st.json(comm_json)

        with c_ems:
            st.subheader("🚀 緊急醫療處置")
            is_emergency = st.session_state.get('ai_status') == 'emergency'
            if st.button("🔴 啟動 CPR 急救", disabled=not is_emergency):
                req_id, sr_json, res = send_service_request(
                    st.session_state['pid'], st.session_state.get('risk_id')
                )
                if res and res.status_code in [200, 201]:
                    st.session_state['watch_screen'] = "cpr"
                    st.session_state['watch_message'] = None
                    st.toast("已發送 CPR 指令", icon="🚑")
                    with st.expander("JSON"): st.json(sr_json)

    else:
        st.warning("等待數據... 請先至「穿戴裝置」頁面上傳生理數值。")
