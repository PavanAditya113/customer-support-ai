import os
import streamlit as st
import requests
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go

API = os.getenv("API_URL", "http://localhost:8001")

st.set_page_config(
    page_title="Customer Support Insights",
    page_icon="🎯",
    layout="wide"
)

st.title("🎯 Customer Support Insight Platform")
st.caption("AI-powered analytics for e-commerce support operations")

# ── Sidebar ──────────────────────────────────────────────────
with st.sidebar:
    st.header("🔍 Filters")
    try:
        cats = requests.get(f"{API}/tickets/categories", timeout=5).json()
        category_options = ["All"] + cats
    except Exception:
        category_options = ["All", "Payment Problem", "Bug Report", "Login Issue",
                            "Refund Request", "Feature Request", "Account Suspension",
                            "Data Sync Issue", "Performance Issue", "Security Concern",
                            "Subscription Cancellation"]
    category_filter = st.selectbox("Category", category_options)
    sentiment_filter = st.selectbox("Sentiment", ["All", "positive", "negative", "neutral"])
    st.divider()
    st.header("⚙️ Actions")

    # Single ticket analysis
    st.subheader("Analyze New Ticket")
    new_ticket = st.text_area("Paste ticket message:", height=100)
    if st.button("🤖 Analyze", type="primary"):
        if new_ticket:
            with st.spinner("Analyzing with AI..."):
                res = requests.post(f"{API}/tickets/analyze",
                    json={"issue_description": new_ticket})
                if res.ok:
                    data = res.json()
                    st.success("Done!")
                    st.write(f"**Sentiment:** {data['sentiment']}")
                    st.write(f"**Frustration:** {data['frustration_level']}/10")
                    st.write(f"**Summary:** {data['issue_summary']}")
                    st.write(f"**Suggested Response:**")
                    st.info(data['suggested_response'])

    st.divider()
    if st.button("🔄 Run Enrichment (100 tickets)"):
        res = requests.post(f"{API}/pipeline/enrich?limit=100")
        st.success("Enrichment started in background!")


# ── KPI Row ──────────────────────────────────────────────────
try:
    sla = requests.get(f"{API}/insights/sla-stats").json()
    col1, col2, col3, col4, col5 = st.columns(5)
    col1.metric("📋 Total Tickets",      f"{sla['total_tickets']:,}")
    col2.metric("⚠️ SLA Breach Rate",    f"{sla['sla_breach_rate']}%")
    col3.metric("🔺 Escalation Rate",    f"{sla['escalation_rate']}%")
    col4.metric("⏱ Avg Resolution",      f"{sla['avg_resolution_hours']}h")
    col5.metric("⚡ Avg First Response",  f"{sla['avg_first_response_hours']}h")
except Exception as e:
    st.error(f"API not reachable: {e}. Make sure FastAPI is running.")
    st.stop()

st.divider()

# ── Row 1: Top Issues + Sentiment Trend ─────────────────────
col_left, col_right = st.columns([1, 1])

with col_left:
    st.subheader("🏆 Top Complaint Categories")
    issues = requests.get(f"{API}/insights/top-issues").json()
    if issues:
        df_issues = pd.DataFrame(issues)
        fig = px.bar(df_issues, x="count", y="category", orientation="h",
                     color="count", color_continuous_scale="Reds",
                     text="count")
        fig.update_layout(showlegend=False, height=350,
                          yaxis=dict(autorange="reversed"),
                          margin=dict(l=0, r=0, t=10, b=0))
        fig.update_traces(textposition="outside")
        st.plotly_chart(fig, use_container_width=True)

with col_right:
    st.subheader("📈 Sentiment Trend Over Time")
    trend = requests.get(f"{API}/insights/sentiment-trend").json()
    if trend:
        df_trend = pd.DataFrame(trend)
        df_trend['month'] = pd.to_datetime(df_trend['month'])
        color_map = {"positive": "#2ECC71", "negative": "#E74C3C", "neutral": "#95A5A6"}
        fig2 = px.line(df_trend, x="month", y="count", color="sentiment",
                       color_discrete_map=color_map, markers=True)
        fig2.update_layout(height=350, margin=dict(l=0, r=0, t=10, b=0))
        st.plotly_chart(fig2, use_container_width=True)
    else:
        st.info("Run enrichment to see sentiment trends.")

st.divider()

# ── Row 2: SLA Gauge + Escalation Gauge + Revenue at Risk ───
col_g1, col_g2, col_rev = st.columns([1, 1, 2])

with col_g1:
    st.subheader("🚨 SLA Breach Rate")
    fig_sla = go.Figure(go.Indicator(
        mode="gauge+number",
        value=sla['sla_breach_rate'],
        number={'suffix': "%"},
        gauge={
            'axis': {'range': [0, 100]},
            'bar': {'color': "#E74C3C"},
            'steps': [
                {'range': [0, 30],  'color': "#2ECC71"},
                {'range': [30, 60], 'color': "#F39C12"},
                {'range': [60, 100],'color': "#E74C3C"},
            ],
        }
    ))
    fig_sla.update_layout(height=250, margin=dict(l=20, r=20, t=20, b=20))
    st.plotly_chart(fig_sla, use_container_width=True)

with col_g2:
    st.subheader("🔺 Escalation Rate")
    fig_esc = go.Figure(go.Indicator(
        mode="gauge+number",
        value=sla['escalation_rate'],
        number={'suffix': "%"},
        gauge={
            'axis': {'range': [0, 100]},
            'bar': {'color': "#E67E22"},
            'steps': [
                {'range': [0, 25],  'color': "#2ECC71"},
                {'range': [25, 50], 'color': "#F39C12"},
                {'range': [50, 100],'color': "#E74C3C"},
            ],
        }
    ))
    fig_esc.update_layout(height=250, margin=dict(l=20, r=20, t=20, b=20))
    st.plotly_chart(fig_esc, use_container_width=True)

with col_rev:
    st.subheader("💸 Revenue at Risk (Negative Sentiment)")
    rev = requests.get(f"{API}/insights/revenue-at-risk").json()
    if rev:
        df_rev = pd.DataFrame(rev)
        fig_rev = px.bar(df_rev, x="category", y="revenue_at_risk",
                         color="negative_tickets", text="revenue_at_risk",
                         color_continuous_scale="Oranges")
        fig_rev.update_traces(texttemplate="$%{text:,.0f}", textposition="outside")
        fig_rev.update_layout(height=250, margin=dict(l=0, r=0, t=10, b=0))
        st.plotly_chart(fig_rev, use_container_width=True)
    else:
        st.info("Run enrichment to see revenue at risk.")

st.divider()

# ── Row 3: Channel Breakdown ─────────────────────────────────
st.subheader("📡 Tickets by Channel")
channels = requests.get(f"{API}/insights/by-channel").json()
if channels:
    df_ch = pd.DataFrame(channels)
    col_pie, col_sat = st.columns(2)
    with col_pie:
        fig_pie = px.pie(df_ch, names="channel", values="count",
                         color_discrete_sequence=px.colors.qualitative.Set2)
        fig_pie.update_layout(height=280, margin=dict(l=0, r=0, t=10, b=0))
        st.plotly_chart(fig_pie, use_container_width=True)
    with col_sat:
        fig_sat = px.bar(df_ch, x="channel", y="avg_satisfaction",
                         color="avg_satisfaction", color_continuous_scale="Greens",
                         text="avg_satisfaction")
        fig_sat.update_traces(texttemplate="%{text:.2f}", textposition="outside")
        fig_sat.update_layout(height=280, yaxis_range=[0, 5],
                              title="Avg Satisfaction Score by Channel",
                              margin=dict(l=0, r=0, t=30, b=0))
        st.plotly_chart(fig_sat, use_container_width=True)

st.divider()

# ── Row 4: Ticket Explorer ───────────────────────────────────
st.subheader("🔎 Ticket Explorer")

params = {}
if category_filter != "All": params["category"]  = category_filter
if sentiment_filter != "All": params["sentiment"] = sentiment_filter

tickets_resp = requests.get(f"{API}/tickets", params={**params, "limit": 50})
tickets = tickets_resp.json() if tickets_resp.ok else []

if tickets:
    df_tickets = pd.DataFrame(tickets)
    # Only show columns that exist (graceful if enrichment not yet run)
    display_cols = [c for c in ["ticket_id", "category", "priority", "channel",
                    "status", "sentiment", "frustration_level",
                    "sla_breached", "escalated", "order_value", "issue_summary"]
                    if c in df_tickets.columns]
    st.dataframe(df_tickets[display_cols], use_container_width=True, height=300)

    # Detail view
    selected_id = st.selectbox("Select Ticket ID for full detail:",
                               [t["ticket_id"] for t in tickets])
    if selected_id:
        sel = next((t for t in tickets if t["ticket_id"] == selected_id), None)
        if sel:
            c1, c2 = st.columns(2)
            with c1:
                st.markdown("**📝 Issue Description**")
                st.info(sel.get("issue_description", "N/A"))
                st.markdown("**🤖 AI Summary**")
                st.write(sel.get("issue_summary") or "Not enriched yet — click 'Run Enrichment' in the sidebar")
            with c2:
                st.markdown("**💬 Suggested Agent Response**")
                st.success(sel.get("suggested_response") or "Run enrichment to generate response")
                cols = st.columns(3)
                cols[0].metric("Sentiment",        sel.get("sentiment") or "—")
                cols[1].metric("Frustration",      f"{sel.get('frustration_level') or '—'}/10")
                cols[2].metric("Order Value",      f"${sel.get('order_value', 0):.2f}")
elif sentiment_filter != "All":
    st.warning(f"No enriched tickets found with **{sentiment_filter}** sentiment. "
               "Click '🔄 Run Enrichment' in the sidebar to analyze tickets first.")
else:
    st.info("No tickets found. Upload a CSV or run the pipeline first.")
