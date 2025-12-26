import streamlit as st
import requests
import uuid
import time
import re
from datetime import datetime, timezone

# --- 匯入模組 (請確保您的資料夾中有這兩個檔案) ---
try:
    from fhir_gateway import create_raw_data_bundle
    from ai_engine import analyze_and_create_report
except ImportError:
    st.error("❌ 找不到必要的模組 (fhir_gateway.py 或 ai_engine.py)。請確認檔案是否在同一目錄下。")
    st.stop()

st.set_page_config(layout="wide", page_title="h1 雙軌醫療系統 (FHIR 標準版)")

# [設定] 使用 HAPI FHIR R4 公用伺服器 (穩定且公開)
FHIR_SERVER_URL = "https://hapi.fhir.org/baseR4"

# --- 初始化 Session State ---
if 'watch_screen' not in st.session_state: st.session_state['watch_screen'] = "normal"
if 'watch_message' not in st.session_state: st.session_state['watch_message'] = None 
if 'has_data' not in st.session_state: st.session_state['has_data'] = False
if 'vitals' not in st.session_state: st.session_state['vitals'] = {}
if 'pid' not in st.session_state: st.session_state['pid'] = None
if 'server_pid' not in st.session_state: st.session_state['server_pid'] = None 
if 'ai_status' not in st.session_state: st.session_state['ai_status'] = "unknown"
if 'risk_id' not in st.session_state: st.session_state['risk_id'] = None

# --- Helper Functions ---

def send_bundle(bundle):
    """將 Bundle 上傳至 FHIR Server"""
    headers = {"Content-Type": "application/fhir+json"}
    
    # 強制將 Bundle 類型設為 transaction (允許 Create/Update/Delete 混合操作)
    if bundle.get("resourceType") == "Bundle":
        bundle["type"] = "transaction"
    
    try:
        # 設定 timeout 避免卡死
        response = requests.post(FHIR_SERVER_URL, json=bundle, headers=headers, timeout=20)
        
        # 檢查 HTTP 狀態碼
        if response.status_code not in [200, 201]:
            st.error(f"上傳失敗 (HTTP {response.status_code})")
            with st.expander("🔍 查看伺服器錯誤詳情 (Server Response)"):
                st.text(response.text)  # 印出伺服器具體報錯原因
            return None
            
        return response
    except requests.exceptions.RequestException as e:
        st.error(f"連線錯誤: {e}")
        return None

def extract_id_from_response(response_json, resource_type="Patient"):
    """解析 Server 回傳的 Location header 以取得真實 ID"""
    try:
        if 'entry' in response_json:
            for entry in response_json['entry']:
                if 'response' in entry and 'location' in entry['response']:
                    location = entry['response']['location']
                    # 格式通常為 "ResourceType/ID/_history/ver"
                    if location.startswith(resource_type):
                        parts = location.split('/')
                        if len(parts) >= 2:
                            return parts[1]
    except Exception:
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
    
    # 包裝成 Bundle 發送
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
    """發送溝通請求 (Doctor Instruction)"""
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
    
    # 包裝成 Bundle 發送
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

    # --- 左側：手錶畫面 ---
    with col_watch:
        st.subheader("📱 手錶畫面")
        state = st.session_state['watch_screen']
        msg = st.session_state['watch_message']

        # [優先級 1] 緊急急救 (最高優先)
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

        # [優先級 2] 醫生訊息
        elif msg:
            st.info("📩 收到新訊息")
            st.markdown(f"""
            <div style="background-color: #e3f2fd; color: #0d47a1; padding: 15px; border-radius: 10px; border-left: 5px solid #2196f3;">
                <strong>👨‍⚕️ Dr. AI:</strong><br>
                <span style="font-size: 1.2em;">{msg}</span>
            </div>
            """, unsafe_allow_html=True)
            if st.button("知道了 (Dismiss)"):
                st.session_state['watch_message'] = None
                st.rerun()

        # [優先級 3] 疲勞預警
        elif state == "rest":
            st.warning("⚠️ 疲勞預警")
            st.write("檢測到高壓力，請休息。")
            if st.button("✅ 解除提醒"):
                st.session_state['watch_screen'] = "normal"
                st.rerun()

        # [優先級 4] 一般監測 (顯示完整數據)
        else:
            st.success("✅ 監測中 (Normal Mode)")
            
            if st.session_state['has_data']:
                v = st.session_state['vitals']
                
                # 顯示伺服器 ID
                server_id_display = st.session_state.get('server_pid', 'Unknown')
                st.caption(f"FHIR ID: {server_id_display}")

                # 2x2 矩陣顯示四項數據
                w1, w2 = st.columns(2)
                w1.metric("❤️ 心率", f"{v.get('hr')} bpm")
                w2.metric("💧 血氧", f"{v.get('spo2')} %")
                
                w3, w4 = st.columns(2)
                w3.metric("📈 HRV", f"{v.get('hrv')} ms")
                w4.metric("🤯 壓力", f"{v.get('stress')}")
            else:
                st.info("等待數據上傳...")

    # --- 右側：感測器模擬 ---
    with col_sensor:
        st.subheader("⚙️ 生理感測 (模擬器)")
        c1, c2 = st.columns(2)
        user_name = c1.text_input("姓名", "Wang Xiao-Mei")
        user_id = c2.text_input("身分證號", "A223456789")
        
        # 四項滑桿
        hr = st.slider("❤️ 心率 (HR)", 40, 200, 95)
        spo2 = st.slider("💧 血氧 (SpO2)", 70, 100, 97)
        hrv = st.slider("📈 心率變異度 (HRV)", 10, 100, 25)
        stress = st.slider("🤯 壓力指數 (Stress)", 0, 100, 80)
        
        # 固定參數 (血壓、呼吸、睡眠)
        sys_bp, dia_bp, resp_rate, sleep_hours = 110, 70, 16, 7

        if st.button("📡 上傳數據"):
            with st.spinner("上傳並等待伺服器確認..."):
                # 1. 產生原始 FHIR Bundle
                raw_bundle, pid, oid = create_raw_data_bundle(
                    user_id, user_name, hr, spo2, sys_bp, dia_bp, resp_rate, hrv, stress, sleep_hours, 25.033, 121.565
                )
                
                # [關鍵修正] 強制將 Patient 的 request method 改為 PUT
                # 這能避免 HAPI-1094 錯誤，確保 Server 使用我們提供的 ID 建立病患
                if 'entry' in raw_bundle:
                    for entry in raw_bundle['entry']:
                        resource = entry.get('resource', {})
                        res_type = resource.get('resourceType')
                        res_id = resource.get('id')
                        
                        if res_type == 'Patient':
                            entry['request'] = {"method": "PUT", "url": f"Patient/{res_id}"}
                        elif 'request' not in entry:
                            # 其他資源 (Observation) 使用 POST
                            entry['request'] = {"method": "POST", "url": res_type}

                # 2. 發送至伺服器
                res = send_bundle(raw_bundle)
                
                if res and res.status_code in [200, 201]:
                    # 3. 解析伺服器回傳的 ID (雙重確認)
                    server_response = res.json()
                    confirmed_patient_id = extract_id_from_response(server_response, "Patient")
                    
                    # 如果解析失敗，使用原本生成的 pid
                    final_pid = confirmed_patient_id if confirmed_patient_id else pid

                    # 4. 更新 Session State
                    st.session_state['pid'] = final_pid
                    st.session_state['server_pid'] = final_pid
                    st.session_state['has_data'] = True
                    st.session_state['vitals'] = {
                        "hr": hr, "spo2": spo2, "hrv": hrv, "stress": stress, 
                        "name": user_name, "sys_bp": sys_bp, "dia_bp": dia_bp, 
                        "resp": resp_rate, "sleep": sleep_hours
                    }
                    st.session_state['watch_screen'] = "normal"
                    
                    st.toast("上傳成功！數據已同步", icon="✅")
                    
                    # [關鍵修正] 強制刷新頁面，確保左側手錶畫面立即顯示數據
                    time.sleep(0.5) 
                    st.rerun()
                else:
                    # 錯誤已在 send_bundle 處理
                    pass

# ==========================================
#  TAB 2: 醫療中心 (Doctor)
# ==========================================
with tab2:
    st.header("Step 4: AI & Doctor Dashboard")
    
    if st.session_state['has_data']:
        v = st.session_state['vitals']
        pid_display = st.session_state.get('server_pid', 'Unknown')
        
        st.info(f"當前病患: {v['name']} (FHIR ID: {pid_display}) | HR: {v['hr']} | SpO2: {v['spo2']}")

        # AI 分析區塊
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
                    st.error("AI 報告上傳失敗，請檢查 Server 回應")

        st.markdown("---")

        c_comm, c_ems = st.columns(2)

        # --- 功能 A: 醫生溝通 ---
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

        # --- 功能 B: 急救處置 ---
        with c_ems:
            st.subheader("🚀 緊急醫療處置")
            is_emergency = st.session_state.get('ai_status') == 'emergency'
            
            # 按鈕狀態：只有在 AI 判定緊急時才啟用
            if st.button("🔴 啟動 CPR 急救", disabled=not is_emergency, help="僅緊急風險可用"):
                req_id, sr_json, res = send_service_request(
                    st.session_state['pid'], st.session_state.get('risk_id')
                )
                if res and res.status_code in [200, 201]:
                    st.session_state['watch_screen'] = "cpr"
                    st.session_state['watch_message'] = None # 清除文字訊息，避免干擾
                    st.toast("已發送 CPR 指令", icon="🚑")
                    with st.expander("JSON"): st.json(sr_json)

    else:
        st.warning("等待數據... 請先至「穿戴裝置」頁面上傳生理數值。")
