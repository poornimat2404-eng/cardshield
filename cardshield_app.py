import pandas as pd
import streamlit as st
st.set_page_config(page_title="CardShield Dashboard", page_icon="🛡️", layout="wide")

# --- Add Nium logo ---
st.image("nium_logo.png", width=150)  # adjust width if needed

import smtplib
from email.message import EmailMessage
from io import BytesIO
import plotly.express as px

# ========== EMAIL CONFIG ==========
EMAIL_SENDER = "poornimat2404@gmail.com"
EMAIL_PASSWORD = "lckv gzyx ioks wrjs"  # Use Gmail App Password
EMAIL_RECEIVER = "cardshield-aaaaro7bcp7fdi3zqwxzm6fuyq@nium.org.slack.com"
SMTP_SERVER = "smtp.gmail.com"
SMTP_PORT = 587

st.set_page_config(page_title="CardShield Dashboard", page_icon="🛡️", layout="wide")
st.title("🛡️ CardShield – Real-Time Card Abuse Detection")

# ========== FILE UPLOAD ==========
uploaded_file = st.file_uploader("Upload your customer CSV file", type=["csv"])
if uploaded_file is None:
    st.info("⬆️ Upload a CSV file to begin analysis.")
    st.stop()

df = pd.read_csv(uploaded_file)

# ========== RISK SCORING ==========
def calc_risk(row):
    score = 0
    if row.get("cards_last_7_days", 0) > 3: score += 30
    if row.get("no_of_cards", 0) > 5: score += 20
    if row.get("avg_transaction_amount", 0) < 10 or row.get("avg_transaction_amount", 0) > 5000: score += 15
    if row.get("days_active_before_block", 0) < 3: score += 20
    if row.get("account_age_days", 0) < 30: score += 10
    if row.get("fraud_flag", 0) == 1: score += 50
    return score

df["risk_score"] = df.apply(calc_risk, axis=1)
df["risk_level"] = pd.cut(df["risk_score"], bins=[-1,39,59,1000], labels=["Low","Medium","High"])
high_risk = df[df["risk_level"] == "High"]
import datetime

st.subheader("⚠️ High Risk Customers – Take Action")

if not high_risk.empty:
    # Make sure customer_id is string
    high_risk = high_risk.copy()
    high_risk["customer_id"] = high_risk["customer_id"].astype(str)

    # Multi-select box to choose customers to block
    selected = st.multiselect(
        "Select customers to block",
        options=high_risk["customer_id"],
        format_func=lambda x: f"{x} - {high_risk.loc[high_risk['customer_id']==x,'Name'].values[0]}"
    )

    if st.button("🚫 Block Selected Customers"):
        if selected:
            blocked_df = high_risk[high_risk["customer_id"].isin(selected)]
            st.success(f"✅ {len(blocked_df)} customer(s) blocked.")
            st.dataframe(blocked_df)

            # Optional: save to CSV
            blocked_df.to_csv("Blocked_Customers.csv", index=False)

            # Optional: send email alert about blocked users
            # msg = EmailMessage()
            # msg["Subject"] = f"CardShield: {len(blocked_df)} Customers Blocked"
            # msg["From"] = EMAIL_SENDER
            # msg["To"] = EMAIL_RECEIVER
            # msg.set_content("These customers were blocked:\n\n" + blocked_df.to_string(index=False))
            # with smtplib.SMTP(SMTP_SERVER, SMTP_PORT) as server:
            #     server.starttls()
            #     server.login(EMAIL_SENDER, EMAIL_PASSWORD)
            #     server.send_message(msg)
        else:
            st.warning("Please select at least one customer to block.")
else:
    st.info("No high risk customers found.")


# ========== SIDEBAR FILTERS ==========
st.sidebar.header("🔎 Filters")
risk_filter = st.sidebar.multiselect(
    "Filter by Risk Level", options=df['risk_level'].dropna().unique(),
    default=df['risk_level'].dropna().unique()
)
df_filtered = df[df['risk_level'].isin(risk_filter)]

# Cost savings what-if
st.sidebar.header("💰 Cost Saving Assumptions")
card_cost = st.sidebar.slider("Card cost (SGD)", 1, 20, 7)
abuse_per_user = st.sidebar.slider("Abusive cards per high-risk user", 1, 10, 3)
estimated_savings = len(high_risk) * card_cost * abuse_per_user

# ========== KPI METRICS ==========
c1, c2, c3, c4 = st.columns(4)
c1.metric("Total Customers", len(df))
c2.metric("High Risk Customers", len(high_risk))
c3.metric("Avg Risk Score", round(df["risk_score"].mean(),1))
c4.metric("💰 Est. Cost Savings", f"${estimated_savings:,.0f} SGD")

# ========== CHARTS ==========
st.subheader("📊 Risk Level Distribution")
fig_pie = px.pie(df, names='risk_level', title='Risk Level Breakdown', color='risk_level',
                 color_discrete_map={"Low":"green","Medium":"orange","High":"red"})
st.plotly_chart(fig_pie, use_container_width=True)

if "date" in df.columns:
    try:
        df['date'] = pd.to_datetime(df['date'])
        daily = df.groupby(['date','risk_level']).size().reset_index(name='count')
        st.subheader("📈 Daily Risk Trends")
        fig_line = px.line(daily, x='date', y='count', color='risk_level', title='Risk Over Time')
        st.plotly_chart(fig_line, use_container_width=True)
    except Exception:
        st.info("Date column found but could not parse; skipping trend chart.")

# ========== TABLES ==========
st.subheader("🔥 Top 10 Highest Risk Customers")
st.dataframe(df.sort_values('risk_score', ascending=False).head(10))

st.subheader("📋 Filtered Customer Table")
st.dataframe(df_filtered)

# ========== DOWNLOAD REPORT ==========
excel_buffer = BytesIO()
df.to_excel(excel_buffer, index=False, engine="openpyxl")
st.download_button(
    "⬇️ Download Full Report (Excel)",
    excel_buffer.getvalue(),
    file_name="CardShield_Report.xlsx",
    mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
)

# ========== AUTO EMAIL ALERT WITH ATTACHMENT ==========
if "email_sent" not in st.session_state:
    st.session_state.email_sent = False

if not high_risk.empty and not st.session_state.email_sent:
    try:
        msg = EmailMessage()
        msg["Subject"] = "CardShield Alert – High Risk Customers Detected"
        msg["From"] = EMAIL_SENDER
        msg["To"] = EMAIL_RECEIVER
        msg.set_content(
            f"High risk customers detected: {len(high_risk)}\n\n"
            f"Estimated potential saving: {estimated_savings} SGD\n\n"
            f"Top high-risk:\n{high_risk[['customer_id','Name','risk_score']].head(10).to_string(index=False)}"
        )
        # Attach Excel report
        msg.add_attachment(
            excel_buffer.getvalue(),
            maintype="application",
            subtype="vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            filename="CardShield_Report.xlsx"
        )

        with smtplib.SMTP(SMTP_SERVER, SMTP_PORT) as server:
            server.starttls()
            server.login(EMAIL_SENDER, EMAIL_PASSWORD)
            server.send_message(msg)

        st.session_state.email_sent = True
        st.success("✅ Email alert (with report) sent automatically.")
    except Exception as e:
        st.error(f"❌ Email error: {e}")

