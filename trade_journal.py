import streamlit as st
import pandas as pd
from datetime import datetime
import os
from PIL import Image
from streamlit_gsheets import GSheetsConnection  # NEW: Import connector

# 1. MUST BE FIRST: Page Config
st.set_page_config(page_title="Stonk Logger Pro", layout="wide")

# --- AUTHENTICATION CHECK ---
if not st.user.get("is_logged_in", False):
    st.title("🔒 Stonk Journal Pro")
    st.info("Welcome! Please log in with your Google account to access your private trading journal.")
    if st.button("Log in with Google"):
        st.login()
    st.stop() 

# --- NEW: GOOGLE SHEETS CONNECTION ---
# This replaces the local LOG_FILE logic
conn = st.connection("gsheets", type=GSheetsConnection)

# Sanitize email for worksheet (Tab) name compatibility
user_email = st.user.email.replace("@", "_").replace(".", "_")
IMAGE_DIR = f"charts_{user_email}"

if not os.path.exists(IMAGE_DIR):
    os.makedirs(IMAGE_DIR)

# Sidebar User Info
st.sidebar.write(f"👋 Hello, {st.user.name}")
if st.sidebar.button("Logout"):
    st.logout()

# --- NEW: LOAD DATA FROM GOOGLE SHEETS ---
try:
    # This reads the specific "Tab" for the logged-in user
    df = conn.read(worksheet=user_email)
except Exception:
    # If the user is new and their tab doesn't exist yet, create an empty structure
    df = pd.DataFrame(columns=[
        "Date", "Symbol", "Type", "Confidence", "Entry", "Exit", "Qty", 
        "StopLoss", "Target", "Net_PnL", "Return_Pct", "Status", "Notes", "Chart_Path"
    ])

# --- SIDEBAR: TRADE ENTRY ---
with st.sidebar:
    st.title("➕ New Trade")
    with st.form("trade_form", clear_on_submit=True):
        # Convert date to string for Google Sheets compatibility
        date = st.date_input("Date", datetime.now()).strftime('%Y-%m-%d')
        symbol = st.text_input("Ticker").upper()
        trade_type = st.selectbox("Type", ["LONG", "SHORT"])
        qty = st.number_input("Quantity", min_value=1)
        
        col1, col2 = st.columns(2)
        with col1:
            entry_p = st.number_input("Entry Price", min_value=0.0, format="%.2f")
            sl_p = st.number_input("Stop Loss", min_value=0.0, format="%.2f")
        with col2:
            exit_p = st.number_input("Exit Price (0 if open)", min_value=0.0, format="%.2f")
            target_p = st.number_input("Target", min_value=0.0, format="%.2f")
            
        conf = st.slider("Confidence %", 0, 100, 80)
        uploaded_file = st.file_uploader("Upload Chart Screenshot", type=["png", "jpg", "jpeg"])
        notes = st.text_area("Trade Notes")
        
        submit = st.form_submit_button("Add to Journal")
        
        if submit and symbol and entry_p > 0:
            chart_path = ""
            if uploaded_file is not None:
                chart_path = os.path.join(IMAGE_DIR, f"{symbol}_{date}_{datetime.now().strftime('%H%M%S')}.png")
                img = Image.open(uploaded_file)
                img.save(chart_path)

            status = "Closed" if exit_p > 0 else "Open"
            net_pnl = (exit_p - entry_p) * qty if exit_p > 0 else 0
            if trade_type == "SHORT" and exit_p > 0: net_pnl = (entry_p - exit_p) * qty
            ret_pct = (net_pnl / (entry_p * qty)) * 100 if exit_p > 0 else 0
            
            new_row = {
                "Date": date, "Symbol": symbol, "Type": trade_type, "Confidence": conf, 
                "Entry": entry_p, "Exit": exit_p, "Qty": qty, "StopLoss": sl_p, 
                "Target": target_p, "Net_PnL": round(net_pnl, 2), 
                "Return_Pct": round(ret_pct, 2), "Status": status, 
                "Notes": notes, "Chart_Path": chart_path
            }
            
            # --- NEW: UPDATE GOOGLE SHEETS ---
            # Add the new row to the current dataframe and push to the cloud
            updated_df = pd.concat([df, pd.DataFrame([new_row])], ignore_index=True)
            conn.update(worksheet=user_email, data=updated_df)
            
            st.success(f"Trade for {symbol} saved to Google Sheets!")
            st.rerun()

# --- MAIN DASHBOARD (Rest remains mostly the same) ---
st.title("🚀 Portfolio Overview")

if not df.empty:
    m1, m2, m3, m4 = st.columns(4)
    # Ensure numeric types for calculations
    df["Net_PnL"] = pd.to_numeric(df["Net_PnL"])
    df["Return_Pct"] = pd.to_numeric(df["Return_Pct"])
    
    closed_trades = df[df['Status'] == 'Closed']
    total_pnl = closed_trades['Net_PnL'].sum()
    win_rate = (closed_trades['Net_PnL'] > 0).mean() * 100 if len(closed_trades) > 0 else 0
    
    m1.metric("Net Profit", f"₹{total_pnl:,.2f}")
    m2.metric("Win Rate", f"{win_rate:.1f}%")
    m3.metric("Avg Return", f"{closed_trades['Return_Pct'].mean():.2f}%" if len(closed_trades) > 0 else "0%")
    m4.metric("Active Trades", len(df[df['Status'] == 'Open']))

    tab1, tab2, tab3 = st.tabs(["📜 Trade Log", "🖼️ Chart Gallery", "📊 Stats"])

    with tab1:
        st.dataframe(df.sort_values(by="Date", ascending=False), use_container_width=True)

    with tab2:
        st.subheader("Visual Playbook")
        image_trades = df[df['Chart_Path'].notna() & (df['Chart_Path'] != "")]
        if not image_trades.empty:
            for i in range(0, len(image_trades), 3):
                cols = st.columns(3)
                for j, col in enumerate(cols):
                    if i + j < len(image_trades):
                        row = image_trades.iloc[i + j]
                        with col:
                            if os.path.exists(str(row['Chart_Path'])):
                                st.image(row['Chart_Path'], caption=f"{row['Symbol']} - {row['Date']}")
        else:
            st.info("No charts uploaded yet.")

    with tab3:
        st.subheader("Performance by Confidence")
        st.bar_chart(data=df, x='Confidence', y='Return_Pct')
else:
    st.info("Log your first trade to see the analytics.")
