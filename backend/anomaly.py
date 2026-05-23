"""
BONUS 2 — Anomaly Detection on Complaint Spikes
Z-score based detection on rolling 7-day window per category.
"""

import os
import sys
sys.path.append(os.path.dirname(__file__))

import pandas as pd
import numpy as np
from sqlalchemy import text
from database import SessionLocal


def detect_spikes(db=None, window_days: int = 7, z_threshold: float = 2.0) -> list:
    """
    Detect unusual spikes in ticket volume per category.
    Uses Z-score on a rolling window.
    """
    if db is None:
        db = SessionLocal()
        close_after = True
    else:
        close_after = False

    try:
        rows = db.execute(text("""
            SELECT
                DATE(ticket_created_date) as date,
                category,
                COUNT(*) as count
            FROM tickets_raw
            WHERE ticket_created_date IS NOT NULL
            GROUP BY DATE(ticket_created_date), category
            ORDER BY date
        """)).fetchall()

        if not rows:
            return []

        df = pd.DataFrame(rows, columns=["date", "category", "count"])
        df["date"] = pd.to_datetime(df["date"])

        alerts = []

        for category in df["category"].unique():
            cat_df = (
                df[df["category"] == category]
                .set_index("date")
                .sort_index()
            )

            if len(cat_df) < window_days + 1:
                continue

            rolling_mean = cat_df["count"].rolling(window=window_days, min_periods=3).mean()
            rolling_std  = cat_df["count"].rolling(window=window_days, min_periods=3).std()

            # Avoid division by zero
            rolling_std = rolling_std.replace(0, 0.001)

            cat_df["z_score"] = (cat_df["count"] - rolling_mean) / rolling_std

            spikes = cat_df[cat_df["z_score"] > z_threshold]

            for date, row in spikes.iterrows():
                severity = (
                    "CRITICAL" if row["z_score"] > 4.0 else
                    "HIGH"     if row["z_score"] > 3.0 else
                    "WARNING"
                )
                alerts.append({
                    "date":          str(date.date()),
                    "category":      category,
                    "ticket_count":  int(row["count"]),
                    "z_score":       round(float(row["z_score"]), 2),
                    "severity":      severity,
                    "baseline_avg":  round(float(rolling_mean[date]), 1),
                    "pct_above_avg": round(
                        (row["count"] - rolling_mean[date]) / rolling_mean[date] * 100, 1
                    ) if rolling_mean[date] > 0 else 0,
                })

        alerts.sort(key=lambda x: x["z_score"], reverse=True)
        return alerts

    finally:
        if close_after:
            db.close()


def get_trend_summary(db=None) -> list:
    """Week-over-week ticket volume change per category."""
    if db is None:
        db = SessionLocal()
        close_after = True
    else:
        close_after = False

    try:
        rows = db.execute(text("""
            SELECT
                category,
                SUM(CASE WHEN DATE(ticket_created_date) >= DATE('now', '-7 days')
                         THEN 1 ELSE 0 END) as this_week,
                SUM(CASE WHEN DATE(ticket_created_date) >= DATE('now', '-14 days')
                         AND DATE(ticket_created_date) < DATE('now', '-7 days')
                         THEN 1 ELSE 0 END) as last_week
            FROM tickets_raw
            GROUP BY category
        """)).fetchall()

        trends = []
        for row in rows:
            cat, this_w, last_w = row
            last_w = last_w or 1
            change = round((this_w - last_w) / last_w * 100, 1)
            trends.append({
                "category":   cat,
                "this_week":  this_w,
                "last_week":  last_w,
                "change_pct": change,
                "direction":  "UP" if change > 0 else "DOWN" if change < 0 else "FLAT",
            })

        trends.sort(key=lambda x: abs(x["change_pct"]), reverse=True)
        return trends

    finally:
        if close_after:
            db.close()
