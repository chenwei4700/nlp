# -*- coding: utf-8 -*-
"""
NLP 期末專案 — 新聞趨勢圖
讀取 baseball_news.csv，繪製 CPBL vs MLB 新聞數量折線圖
"""

import pandas as pd
import matplotlib.pyplot as plt
import matplotlib.dates as mdates
import os

# 設定中文字體
plt.rcParams["font.sans-serif"] = ["Microsoft JhengHei", "SimHei", "Arial Unicode MS"]
plt.rcParams["axes.unicode_minus"] = False

# 路徑
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
CSV_PATH = os.path.join(SCRIPT_DIR, "baseball_news.csv")
OUTPUT_PATH = os.path.join(SCRIPT_DIR, "trend_chart.png")


def main():
    # 讀取 CSV
    df = pd.read_csv(CSV_PATH)
    df["date"] = pd.to_datetime(df["date"], errors="coerce")
    df = df.dropna(subset=["date"])

    # 按日期 + 標籤分組計數
    daily_counts = (
        df.groupby([df["date"].dt.date, "label"])
        .size()
        .unstack(fill_value=0)
    )

    # 確保兩個標籤都有欄位
    for col in ["CPBL", "MLB"]:
        if col not in daily_counts.columns:
            daily_counts[col] = 0

    daily_counts.index = pd.to_datetime(daily_counts.index)
    daily_counts = daily_counts.sort_index()

    # ============================================================
    # 繪圖
    # ============================================================
    fig, ax = plt.subplots(figsize=(14, 6), dpi=120)

    # 折線
    ax.plot(
        daily_counts.index, daily_counts["CPBL"],
        color="#1E5AA8", linewidth=2, marker="o", markersize=3,
        label="中職 (CPBL)", alpha=0.85,
    )
    ax.plot(
        daily_counts.index, daily_counts["MLB"],
        color="#C4122F", linewidth=2, marker="s", markersize=3,
        label="美職 (MLB)", alpha=0.85,
    )

    # 填充區域
    ax.fill_between(daily_counts.index, daily_counts["CPBL"], alpha=0.1, color="#1E5AA8")
    ax.fill_between(daily_counts.index, daily_counts["MLB"], alpha=0.1, color="#C4122F")

    # 標題與標籤
    ax.set_title(
        "中職 vs 美職 — 每日新聞產出量趨勢圖",
        fontsize=16, fontweight="bold", pad=15,
    )
    ax.set_xlabel("日期", fontsize=12)
    ax.set_ylabel("新聞篇數", fontsize=12)

    # X 軸格式
    ax.xaxis.set_major_formatter(mdates.DateFormatter("%m/%d"))
    ax.xaxis.set_major_locator(mdates.DayLocator(interval=3))
    plt.xticks(rotation=45, ha="right")

    # 網格與圖例
    ax.grid(True, alpha=0.3, linestyle="--")
    ax.legend(fontsize=12, loc="upper left")

    # 統計資訊
    total_cpbl = daily_counts["CPBL"].sum()
    total_mlb = daily_counts["MLB"].sum()
    info_text = f"總篇數 — CPBL: {total_cpbl} 篇 | MLB: {total_mlb} 篇"
    ax.text(
        0.98, 0.95, info_text,
        transform=ax.transAxes, fontsize=10,
        verticalalignment="top", horizontalalignment="right",
        bbox=dict(boxstyle="round,pad=0.3", facecolor="wheat", alpha=0.5),
    )

    # 標註高峰日
    for label, color in [("CPBL", "#1E5AA8"), ("MLB", "#C4122F")]:
        if label in daily_counts.columns and len(daily_counts[label]) > 0:
            peak_date = daily_counts[label].idxmax()
            peak_val = daily_counts[label].max()
            if peak_val > 0:
                ax.annotate(
                    f"{label} 高峰\n{peak_date.strftime('%m/%d')}: {peak_val}篇",
                    xy=(peak_date, peak_val),
                    xytext=(15, 15),
                    textcoords="offset points",
                    fontsize=9,
                    arrowprops=dict(arrowstyle="->", color=color),
                    color=color,
                    fontweight="bold",
                )

    plt.tight_layout()
    plt.savefig(OUTPUT_PATH, dpi=150, bbox_inches="tight")
    print(f"[OK] Trend chart saved to: {OUTPUT_PATH}")
    plt.show()


if __name__ == "__main__":
    main()
