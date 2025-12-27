import streamlit as st
import requests
import uuid
import time
import pandas as pd
from datetime import datetime, timezone

# --- 匯入模組 ---
try:
    from fhir_gateway import create_raw_data_bundle
    from ai_engine import analyze_and_create_report
except ImportError:
    st.error("❌ 找不到模組，請確認 fhir_gateway.py 和 ai_engine.py 存在")
    st.stop()

st.set_page_config(layout="wide", page_title="H1 智慧手錶救護平台")
FHIR_SERVER_URL = "https://hapi.fhir.org/baseR4"

# --- 初始化 Session State ---
if 'user_identity' not in st.session_state: st.session_state['user_identity'] = {"name": "", "id": ""}
if 'watch_status' not in st.session_state: st.session_state['watch_status'] = "normal"
if 'ai_result' not in st.session_state: st.session_state['ai_result'] = ""
if 'pid' not in st.session_state: st.session_state['pid'] = None
if 'has_data' not in st.session_state: st.session_state['has_data'] = False
if 'vitals' not in st.session_state: st.session_state['vitals'] = {}
# [修正點 1] 新增 watch_message 用來存醫生的訊息
if 'watch_message' not in st.session_state: st.session_state['watch_message'] = None

# --- Helper Functions ---
def send_bundle(bundle):
    headers = {"Content-Type": "application/fhir+json"}
    if bundle.get("resourceType") == "Bundle": bundle["type"] = "transaction"
    try:
        return requests.post(FHIR_SERVER_URL, json=bundle, headers=headers, timeout=15)
    except Exception as e:
        return None

def extract_id_from_response(resp_json, res_type="Patient"):
    try:
        for entry in resp_json.get('entry', []):
            loc = entry.get('response', {}).get('location', '')
            if loc.startswith(res_type):
                return loc.split('/')[1]
    except: return None
    return None

# --- UI 開始 ---
st.title("🛡️ H1 智慧手錶救護與 PHR 平台")

# 定義四個分頁
tab_reg, tab_watch, tab_er, tab_phr = st.tabs(["📝 病患註冊 (Portal)", "⌚ 智慧手錶 (Watch)", "🚑 急診醫護 (Emergency)", "📂 PHR 病歷調閱 (History)"])

# ==========================================
#  TAB 1: 註冊與 ID 產生
# ==========================================
with tab_reg:
    st.subheader("H1 醫療服務 - 用戶註冊")
    st.info("首次使用請先註冊以產生全球唯一的 FHIR Patient ID")
    
    reg_name = st.text_input("請輸入您的姓名", "Wang Xiao-Mei")
    
    if st.button("✨ 立即註冊並產生 ID"):
        generated_id = f"H1-{str(uuid.uuid4())[:8].upper()}"
        st.session_state['user_identity'] = {"name": reg_name, "id": generated_id}
        
        st.success("註冊成功！")
        st.markdown(f"""
        <div style="background-color:#e8f5e9;padding:20px;border-radius:10px;border:2px solid #4caf50;">
            <h3>👤 您的專屬病患 ID</h3>
            <h1 style="color:#2e7d32; font-family:monospace;">{generated_id}</h1>
            <p>組織：H1 Smart Hospital (org-h1-hospital)</p>
            <p>請記下此 ID，後續可用於調閱病歷。</p>
        </div>
        """, unsafe_allow_html=True)

# ==========================================
#  TAB 2: 智慧手錶 (核心功能)
# ==========================================
with tab_watch:
    col_screen, col_input = st.columns([1, 1.2])
    
    current_name = st.session_state['user_identity']['name'] if st.session_state['user_identity']['name'] else "Guest"
    current_id = st.session_state['user_identity']['id'] if st.session_state['user_identity']['id'] else "Unknown"

    # --- 左側：手錶畫面 ---
    with col_screen:
        st.subheader("📱 手錶即時畫面")
        
        status = st.session_state['watch_status']
        ai_text = st.session_state['ai_result']
        doc_msg = st.session_state['watch_message'] # 讀取醫生訊息

        # [修正點 2] 顯示醫生傳來的訊息 (如果有)
        if doc_msg:
            st.info("📩 收到新訊息")
            st.markdown(f"""
            <div style="background-color:#e3f2fd; color:#0d47a1; padding:15px; border-radius:10px; border-left:5px solid #2196f3; margin-bottom:15px;">
                <strong>👨‍⚕️ 醫生指示:</strong><br>
                <span style="font-size:1.2em;">{doc_msg}</span>
            </div>
            """, unsafe_allow_html=True)
            if st.button("我知道了 (關閉訊息)"):
                st.session_state['watch_message'] = None
                st.rerun()

        # 1. 顯示三個數據
        if st.session_state['has_data']:
            v = st.session_state['vitals']
            st.markdown(f"""
            <div style="display:flex; justify-content:space-around; background:#222; color:white; padding:10px; border-radius:10px;">
                <div style="text-align:center;"><small>HR</small><h2>{v.get('hr')}</h2><small>bpm</small></div>
                <div style="text-align:center;"><small>SpO2</small><h2>{v.get('spo2')}</h2><small>%</small></div>
                <div style="text-align:center;"><small>HRV</small><h2>{v.get('hrv')}</h2><small>ms</small></div>
            </div>
            """, unsafe_allow_html=True)
        else:
            st.info("等待量測...")

        st.markdown("---")

        # 2. 顯示 AI 判斷結果
        if status == "emergency":
            st.error("🆘 緊急警報 (EMERGENCY)")
            st.markdown(f"""
            <div style="background-color:#d32f2f; color:white; padding:15px; border-radius:10px; text-align:center; animation: blink 1s infinite;">
                <h2>⚠️ {ai_text}</h2>
                <hr>
                <h2>📞 聯絡家人和救助單位...</h2>
                <p>已自動傳送定位與數據給急診醫生</p>
            </div>
            <style>@keyframes blink {{0% {{opacity: 1;}} 50% {{opacity: 0.4;}} 100% {{opacity: 1;}}}}</style>
            """, unsafe_allow_html=True)
            
        elif status == "preventive":
            st.warning("🛡️ 預防警報 (PREVENTIVE)")
            st.markdown(f"""
            <div style="background-color:#fff3cd; color:#856404; padding:15px; border-radius:10px; text-align:center;">
                <h3>⚠️ {ai_text}</h3>
                <p>請放慢呼吸，進行休息。</p>
            </div>
            """, unsafe_allow_html=True)
            
        elif status == "normal" and st.session_state['has_data']:
            st.success("✅ 狀況正常 (NORMAL)")
            st.caption(ai_text)

    # --- 右側：感測輸入 ---
    with col_input:
        st.subheader("⚙️ 生理感測器")
        st.caption(f"使用者: {current_name} (ID: {current_id})")
        
        hr = st.slider("❤️ 心率 (HR)", 40, 200, 75)
        spo2 = st.slider("💧 血氧 (SpO2)", 70, 100, 98)
        hrv = st.slider("📈 心率變異度 (HRV)", 10, 100, 50)
        
        # 隱藏參數
        sys_bp, dia_bp, resp, sleep = 110, 70, 16, 7
        
        if st.button("📡 上傳數據並分析", type="primary"):
            if current_id == "Unknown":
                st.error("請先至「病患註冊」分頁產生 ID")
            else:
                with st.spinner("同步雲端並執行 AI 計算中..."):
                    bundle, pid = create_raw_data_bundle(
                        current_id, current_name, hr, spo2, hrv, sys_bp, dia_bp, resp, sleep, 25.033, 121.565
                    )
                    
                    res_data = send_bundle(bundle)
                    
                    server_pid = pid
                    if res_data and res_data.status_code in [200, 201]:
                        extracted = extract_id_from_response(res_data.json(), "Patient")
                        if extracted: server_pid = extracted
                    
                    st.session_state['pid'] = server_pid
                    st.session_state['vitals'] = {"hr": hr, "spo2": spo2, "hrv": hrv, "sys_bp": sys_bp, "sleep": sleep, "name": current_name}
                    st.session_state['has_data'] = True
                    
                    ai_bundle, status, desc, risk_id = analyze_and_create_report(st.session_state['vitals'], server_pid)
                    send_bundle(ai_bundle)
                    
                    st.session_state['watch_status'] = status
                    st.session_state['ai_result'] = desc
                    st.session_state['risk_id'] = risk_id
                    
                    st.toast("分析完成！結果已同步至手錶", icon="✅")
                    time.sleep(0.5)
                    st.rerun()

# ==========================================
#  TAB 3: 急診醫護
# ==========================================
with tab_er:
    st.header("🚑 急診中心戰情室")
    
    if st.session_state['watch_status'] == 'emergency':
        st.error(f"🚨 接收到緊急求救訊號！病人 ID: {st.session_state['pid']}")
        
        col_info, col_comm = st.columns(2)
        with col_info:
            v = st.session_state['vitals']
            st.metric("心率", v['hr'], "過高/過低", delta_color="inverse")
            st.metric("血氧", v['spo2'], "危險", delta_color="inverse")
            st.warning(f"AI 診斷: {st.session_state['ai_result']}")
            
        with col_comm:
            st.subheader("👨‍⚕️ 醫生通訊")
            st.caption("您可以發送安撫訊息或指導給病患的裝置")
            msg_input = st.text_input("輸入訊息", "救護車已在路上，請保持通話。")
            
            # [修正點 3] 將訊息存入 Session State 讓手錶讀取
            if st.button("發送訊息"):
                st.session_state['watch_message'] = msg_input
                st.toast("訊息已傳送至手錶", icon="📨")
    else:
        st.success("🟢 目前無緊急事故。系統待命中...")
        st.caption("當手錶偵測到危險數據時，此畫面會自動切換為紅色警報。")

# ==========================================
#  TAB 4: PHR 病歷調閱
# ==========================================
with tab_phr:
    st.header("📂 PHR 個人健康紀錄調閱")
    st.caption("透過 FHIR 標準介面，調閱 H1 Smart Hospital 的病歷資料")
    
    search_id = st.text_input("請輸入病患 ID (可用註冊頁產生的 ID)", value=st.session_state['user_identity']['id'])
    
    if st.button("🔍 調閱全部歷史病歷"):
        if not search_id:
            st.warning("請輸入 ID")
        else:
            with st.spinner("正在向 FHIR Server 請求所有資料..."):
                # [修正點 4] 將 _count 改為 100 (或更多)，以模擬調閱"全部"
                url = f"{FHIR_SERVER_URL}/Observation?subject.identifier={search_id}&_sort=-date&_count=100"
                
                try:
                    resp = requests.get(url, timeout=10).json()
                    if 'entry' in resp:
                        data_list = []
                        for entry in resp['entry']:
                            r = entry['resource']
                            try:
                                code_text = r['code']['coding'][0]['display']
                                value = r['valueQuantity']['value']
                                unit = r['valueQuantity']['unit']
                                time_str = r['effectiveDateTime']
                                
                                # 簡化時間顯示
                                dt_obj = datetime.fromisoformat(time_str.replace('Z', '+00:00'))
                                pretty_time = dt_obj.strftime("%Y-%m-%d %H:%M:%S")

                                org = "H1 Smart Hospital"
                                data_list.append({"時間": pretty_time, "項目": code_text, "數值": value, "單位": unit, "來源": org})
                            except: pass
                        
                        if data_list:
                            df = pd.DataFrame(data_list)
                            st.success(f"調閱成功！共找到 {len(data_list)} 筆歷史資料")
                            st.dataframe(df, use_container_width=True)
                        else:
                            st.info("找到病歷結構，但無法解析數據。")
                    else:
                        st.warning("查無此 ID 的相關病歷資料 (可能是新註冊用戶尚無數據)。")
                except Exception as e:
                    st.error(f"連線錯誤: {e}")



