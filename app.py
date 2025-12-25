import streamlit as st
import requests
import uuid
import time
from datetime import datetime, timezone

# 匯入模組
from fhir_gateway import create_raw_data_bundle
from ai_engine import analyze_and_create_report

st.set_page_config(layout="wide", page_title="h1 雙軌醫療系統 (FHIR 標準版)")
FHIR_SERVER_URL = "https://server.fire.ly" 

# 初始化 Session State
if 'watch_screen' not in st.session_state: st.session_state['watch_screen'] = "normal"
if 'watch_message' not in st.session_state: st.session_state['watch_message'] = None 
if 'has_data' not in st.session_state: st.session_state['has_data'] = False
if 'vitals' not in st.session_state: st.session_state['vitals'] = {}

# --- Helper Functions ---

def send_bundle(bundle):
    headers = {"Content-Type": "application/fhir+json"}
    try:
        return requests.post(FHIR_SERVER_URL, json=bundle, headers=headers)
    except Exception as e:
        return str(e)

def send_service_request(patient_id, risk_id):
    """發送醫療處置請求 (Start CPR)"""
    req_id = str(uuid.uuid4())
    sr = {
        "resourceType": "ServiceRequest",
        "id": req_id,
        "status": "active",
        "intent": "order",
        "priority": "stat",
        "code": {"coding": [{"system": "http://snomed.info/sct", "code": "40617009", "display": "Start CPR"}]},
        "subject": {"reference": f"Patient/{patient_id}"},
        "reasonReference": [{"reference": f"RiskAssessment/{risk_id}"}]
    }
    send_bundle(sr)
    return req_id, sr

# [NEW] 專門處理醫生的溝通請求
def send_communication_request(patient_id, message_text, priority="routine"):
    """發送溝通請求 (Doctor Instruction)"""
    req_id = str(uuid.uuid4())
    timestamp = datetime.now(timezone.utc).isoformat()
    
    comm_req = {
        "resourceType": "CommunicationRequest",
        "id": req_id,
        "status": "active",
        "priority": priority, # routine 或 urgent
        "subject": {"reference": f"Patient/{patient_id}"},
        "payload": [{"contentString": message_text}], # 核心內容
        "authoredOn": timestamp,
        "category": [{"coding": [{"system": "http://terminology.hl7.org/CodeSystem/communication-category", "code": "instruction"}]}]
    }
    
    # 實際上傳到 Server
    send_bundle(comm_req)
    return req_id, comm_req

# --- UI 開始 ---
st.title("🏥 h1 智慧醫療系統：CommunicationRequest 實作")
st.caption("流程 A: 預防監測 | 流程 B: 急救回應 | 醫生溝通: CommunicationRequest")

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

        # 1. 顯示醫生的文字指令 (來自 CommunicationRequest)
        if msg:
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

        # 2. 顯示急救 CPR (來自 ServiceRequest)
        elif state == "cpr":
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

        # 3. 顯示休息提醒 (來自 AI 預防)
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
                st.metric("Heart Rate", f"{v.get('hr')} bpm")

    with col_sensor:
        st.subheader("⚙️ 生理感測")
        c1, c2 = st.columns(2)
        user_name = c1.text_input("姓名", "Wang Xiao-Mei")
        user_id = c2.text_input("ID", "A223456789")
        
        hr = st.slider("❤️ 心率", 40, 200, 75)
        spo2 = st.slider("💧 血氧", 70, 100, 98)
        hrv = st.slider("📈 HRV", 10, 100, 60)
        stress = st.slider("🤯 壓力", 0, 100, 20)

        # 為了簡化，其他參數寫死
        if st.button("📡 上傳數據"):
            # 1. 產生 FHIR 數據包
            # 注意：這裡要把所有 AI 需要的數值 (110, 70, 16, 7) 都傳進去
            raw_bundle, pid, oid = create_raw_data_bundle(
                user_id, user_name, hr, spo2, 110, 70, 16, hrv, stress, 7, 25.033, 121.565
            )
            
            # 2. 上傳到伺服器
            res = send_bundle(raw_bundle)
            
            # 3. 更新系統狀態
            st.session_state['pid'] = pid
            st.session_state['has_data'] = True
            
            # 4. 存入完整數據 (這裡最重要，縮排要對齊上面的 st.session_state)
            st.session_state['vitals'] = {
                "hr": hr, 
                "spo2": spo2, 
                "hrv": hrv, 
                "stress": stress, 
                "name": user_name,
                "sys_bp": 110,  # 補上收縮壓
                "dia_bp": 70,   # 補上舒張壓
                "resp": 16,     # 補上呼吸率
                "sleep": 7      # 補上睡眠時間
            }
            
            st.session_state['watch_screen'] = "normal"
            st.toast("上傳成功")

# ==========================================
#  TAB 2: 醫療中心 (Doctor)
# ==========================================
with tab2:
    st.header("Step 4: AI & Doctor Dashboard")
    
    if st.session_state['has_data']:
        v = st.session_state['vitals']
        st.info(f"當前病患: {v['name']} | HR: {v['hr']} | SpO2: {v['spo2']}")

        # AI 分析區塊
        if st.button("🤖 AI 風險計算"):
            bundle, status, desc, risk_id = analyze_and_create_report(v, st.session_state['pid'])
            send_bundle(bundle)
            st.session_state['ai_status'] = status
            st.session_state['risk_id'] = risk_id
            
            if status == "preventive":
                st.warning(f"預防警報: {desc}")
                st.session_state['watch_screen'] = "rest"
            elif status == "emergency":
                st.error(f"緊急警報: {desc}")
            else:
                st.success("數據正常")

        st.markdown("---")

        # [重點修改] 醫生操作區
        c_comm, c_ems = st.columns(2)

        # --- 功能 A: 醫生溝通 (使用 CommunicationRequest) ---
        with c_comm:
            st.subheader("💬 醫生遠端指令")
            st.caption("透過 CommunicationRequest 傳送訊息")
            
            doc_msg = st.text_input("輸入醫囑:", "請多喝水並保持冷靜。")
            
            if st.button("📤 發送訊息 (Send Msg)"):
                # 1. 產生並上傳 FHIR CommunicationRequest
                req_id, comm_json = send_communication_request(
                    st.session_state['pid'], 
                    doc_msg, 
                    priority="routine"
                )
                
                # 2. 模擬推播到手錶
                st.session_state['watch_message'] = doc_msg
                
                st.toast("CommunicationRequest 已發送", icon="📨")
                with st.expander("查看 FHIR 資源 (JSON)"):
                    st.json(comm_json)

        # --- 功能 B: 急救處置 (使用 ServiceRequest) ---
        with c_ems:
            st.subheader("🚀 緊急醫療處置")
            st.caption("透過 ServiceRequest 啟動 CPR")
            
            # 只有在緊急狀態才建議按
            if st.session_state.get('ai_status') == 'emergency':
                if st.button("🔴 啟動 CPR 急救"):
                    # 1. 產生並上傳 FHIR ServiceRequest
                    req_id, sr_json = send_service_request(
                        st.session_state['pid'], 
                        st.session_state.get('risk_id', 'unknown')
                    )
                    
                    # 2. 推播指令
                    st.session_state['watch_screen'] = "cpr"
                    
                    st.toast("ServiceRequest 已發送 (Start CPR)", icon="🚑")
                    with st.expander("查看 FHIR 資源 (JSON)"):
                        st.json(sr_json)
            else:
                st.button("🔴 啟動 CPR 急救", disabled=True, help="僅在緊急風險時可用")

    else:
        st.warning("等待數據...")
