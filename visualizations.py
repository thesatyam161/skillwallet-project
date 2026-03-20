import json
import os
import sqlite3
import warnings

import pandas as pd
import plotly
import plotly.express as px
from paths import DB_PATH

CHART_COLORS = ["#0f766e", "#ea580c", "#1d4ed8", "#be123c", "#7c3aed", "#334155"]
GRID_COLOR = "rgba(83, 68, 55, 0.12)"
TEXT_COLOR = "#201a17"
PLOT_BG = "rgba(255,255,255,0)"
PAPER_BG = "rgba(255,255,255,0)"

POSITION_ORDER = ["Aisle", "Front of Store", "End-cap"]
TRAFFIC_ORDER = ["Low", "Medium", "High"]
BOOL_LABELS = {True: "Promoted", False: "Standard"}
SEASON_LABELS = {True: "Seasonal", False: "Core"}

warnings.filterwarnings(
    "ignore",
    message="When grouping with a length-1 list-like.*",
    category=FutureWarning,
)
warnings.filterwarnings(
    "ignore",
    category=FutureWarning,
    module="plotly\\.express\\._core",
)


def get_data():
    try:
        conn = sqlite3.connect(DB_PATH)
        df = pd.read_sql_query("SELECT * FROM retail_sales", conn)
        conn.close()
        return _normalize_dataframe(df)
    except sqlite3.OperationalError:
        return None


def _to_bool(value):
    if pd.isna(value):
        return False
    if isinstance(value, bool):
        return value
    if isinstance(value, (int, float)):
        return bool(int(value))
    return str(value).strip().lower() in {"1", "true", "yes", "y"}


def _normalize_dataframe(df):
    if df is None or df.empty:
        return df

    normalized = df.copy()

    text_columns = [
        "Product ID",
        "Product Category",
        "Product Position",
        "Foot Traffic",
        "Consumer Demographics",
    ]
    for column in text_columns:
        if column in normalized.columns:
            normalized[column] = normalized[column].fillna("Unknown").astype(str).str.strip()

    numeric_columns = [
        "Price",
        "Competitor Price",
        "Sales Volume",
        "Price Difference",
        "Traffic Weight",
        "Traffic Conversion Index",
    ]
    for column in numeric_columns:
        if column in normalized.columns:
            normalized[column] = pd.to_numeric(normalized[column], errors="coerce")

    for column in ["Promotion", "Seasonal"]:
        if column in normalized.columns:
            normalized[column] = normalized[column].apply(_to_bool)

    if "Price Difference" not in normalized.columns or normalized["Price Difference"].isna().all():
        normalized["Price Difference"] = normalized["Price"] - normalized["Competitor Price"]

    if "Traffic Weight" not in normalized.columns or normalized["Traffic Weight"].isna().all():
        normalized["Traffic Weight"] = normalized["Foot Traffic"].map(
            {"Low": 1, "Medium": 2, "High": 3}
        )

    if "Traffic Conversion Index" not in normalized.columns or normalized["Traffic Conversion Index"].isna().all():
        normalized["Traffic Conversion Index"] = normalized["Sales Volume"] / normalized["Traffic Weight"].replace(0, pd.NA)

    normalized["Promotion Label"] = normalized["Promotion"].map(BOOL_LABELS)
    normalized["Season Label"] = normalized["Seasonal"].map(SEASON_LABELS)
    normalized["Price Status"] = normalized["Price Difference"].apply(
        lambda value: "Below or matched competitor" if value <= 0 else "Priced above competitor"
    )

    return normalized


def _serialize_figure(fig):
    return json.dumps(fig, cls=plotly.utils.PlotlyJSONEncoder)


def _apply_chart_style(fig, title):
    fig.update_layout(
        title={"text": title, "x": 0, "xanchor": "left"},
        paper_bgcolor=PAPER_BG,
        plot_bgcolor=PLOT_BG,
        font={"family": "Space Grotesk, sans-serif", "color": TEXT_COLOR},
        title_font={"size": 20},
        margin={"l": 16, "r": 16, "t": 56, "b": 16},
        hoverlabel={"bgcolor": "#fffdf8", "font_color": TEXT_COLOR},
        colorway=CHART_COLORS,
        legend={
            "orientation": "h",
            "yanchor": "bottom",
            "y": 1.02,
            "xanchor": "right",
            "x": 1,
            "bgcolor": "rgba(255,255,255,0)",
        },
    )
    fig.update_xaxes(showgrid=False, zeroline=False)
    fig.update_yaxes(showgrid=True, gridcolor=GRID_COLOR, zeroline=False)
    return fig


def build_summary(df):
    if df is None or df.empty:
        return None

    total_records = int(len(df))
    total_units = int(df["Sales Volume"].sum())
    avg_price = round(float(df["Price"].mean()), 2)
    avg_conversion = round(float(df["Traffic Conversion Index"].mean()), 1)

    position_sales = (
        df.groupby("Product Position", as_index=False)["Sales Volume"]
        .sum()
        .sort_values("Sales Volume", ascending=False)
    )
    category_sales = (
        df.groupby("Product Category", as_index=False)["Sales Volume"]
        .sum()
        .sort_values("Sales Volume", ascending=False)
    )
    demographic_sales = (
        df.groupby("Consumer Demographics", as_index=False)["Sales Volume"]
        .sum()
        .sort_values("Sales Volume", ascending=False)
    )
    promotion_sales = (
        df.groupby("Promotion Label", as_index=False)["Sales Volume"]
        .mean()
        .sort_values("Sales Volume", ascending=False)
    )
    traffic_sales = (
        df.groupby("Foot Traffic", as_index=False)["Sales Volume"]
        .mean()
        .sort_values("Sales Volume", ascending=False)
    )
    price_status_sales = (
        df.groupby("Price Status", as_index=False)["Sales Volume"]
        .mean()
        .sort_values("Sales Volume", ascending=False)
    )

    promoted_sales = promotion_sales.loc[promotion_sales["Promotion Label"] == "Promoted", "Sales Volume"]
    standard_sales = promotion_sales.loc[promotion_sales["Promotion Label"] == "Standard", "Sales Volume"]
    promo_lift = 0.0
    if not promoted_sales.empty and not standard_sales.empty and float(standard_sales.iloc[0]) != 0:
        promo_lift = round(
            ((float(promoted_sales.iloc[0]) - float(standard_sales.iloc[0])) / float(standard_sales.iloc[0])) * 100,
            1,
        )

    top_position = position_sales.iloc[0]
    top_category = category_sales.iloc[0]
    top_demographic = demographic_sales.iloc[0]
    price_winner = price_status_sales.iloc[0]
    traffic_winner = traffic_sales.iloc[0]

    top_products = (
        df.groupby(["Product ID", "Product Category"], as_index=False)
        .agg(
            sales_volume=("Sales Volume", "sum"),
            avg_price=("Price", "mean"),
            avg_gap=("Price Difference", "mean"),
        )
        .sort_values("sales_volume", ascending=False)
        .head(5)
    )
    top_products["avg_price"] = top_products["avg_price"].round(2)
    top_products["avg_gap"] = top_products["avg_gap"].round(2)

    category_mix = category_sales.copy()
    category_mix["sales_share"] = (category_mix["Sales Volume"] / total_units * 100).round(1)

    recommendations = [
        {
            "title": f"Scale the {top_position['Product Position']} playbook",
            "body": (
                f"{top_position['Product Position']} placements generate {int(top_position['Sales Volume']):,} units, "
                "so prime facings should be reserved for margin-rich products or launch campaigns."
            ),
        },
        {
            "title": "Use promotions selectively",
            "body": (
                f"Promoted items outperform standard items by {promo_lift:.1f}% on average. "
                "Keep the offer engine focused on hero SKUs instead of discounting the whole aisle."
            ),
        },
        {
            "title": "Price to the winning benchmark",
            "body": (
                f"{price_winner['Price Status']} products currently average {price_winner['Sales Volume']:.1f} units. "
                "Use that price stance as the default for traffic-driving categories."
            ),
        },
    ]

    return {
        "total_records": total_records,
        "total_units": total_units,
        "avg_price": avg_price,
        "avg_conversion": avg_conversion,
        "promo_lift": promo_lift,
        "top_position": top_position.to_dict(),
        "top_category": top_category.to_dict(),
        "top_demographic": top_demographic.to_dict(),
        "traffic_winner": traffic_winner.to_dict(),
        "price_winner": price_winner.to_dict(),
        "top_products": top_products.to_dict("records"),
        "category_mix": category_mix.to_dict("records"),
        "promotion_sales": promotion_sales.to_dict("records"),
        "price_status_sales": price_status_sales.to_dict("records"),
        "recommendations": recommendations,
    }


def generate_dashboard_charts(df=None):
    df = df if df is not None else get_data()
    if df is None or df.empty:
        return None

    charts = {}

    position_sales = (
        df.groupby("Product Position", as_index=False)["Sales Volume"]
        .sum()
        .sort_values("Sales Volume", ascending=False)
    )
    fig1 = px.bar(
        position_sales,
        x="Product Position",
        y="Sales Volume",
        category_orders={"Product Position": POSITION_ORDER},
        color_discrete_sequence=[CHART_COLORS[0]],
    )
    fig1.update_traces(marker_line_color="#ffffff", marker_line_width=1.5)
    charts["sales_by_position"] = _serialize_figure(_apply_chart_style(fig1, "Sales by Product Position"))

    category_sales = (
        df.groupby("Product Category", as_index=False)["Sales Volume"]
        .sum()
        .sort_values("Sales Volume", ascending=False)
    )
    fig2 = px.pie(
        category_sales,
        names="Product Category",
        values="Sales Volume",
        hole=0.58,
        color_discrete_sequence=CHART_COLORS,
    )
    fig2.update_traces(textposition="inside", textinfo="percent+label")
    charts["sales_by_category"] = _serialize_figure(_apply_chart_style(fig2, "Category Contribution"))

    fig3 = px.scatter(
        df,
        x="Competitor Price",
        y="Price",
        color="Product Category",
        size="Sales Volume",
        size_max=18,
        opacity=0.72,
        hover_data=["Product ID", "Product Position", "Promotion Label"],
        color_discrete_sequence=CHART_COLORS,
    )
    fig3.update_traces(marker_line_width=0)
    charts["price_vs_competitor"] = _serialize_figure(_apply_chart_style(fig3, "Pricing vs Competitors"))

    promo_sales = (
        df.groupby("Promotion Label", as_index=False)["Sales Volume"]
        .mean()
        .sort_values("Sales Volume", ascending=False)
    )
    fig4 = px.bar(
        promo_sales,
        x="Promotion Label",
        y="Sales Volume",
        color_discrete_sequence=[CHART_COLORS[1]],
    )
    fig4.update_traces(marker_line_color="#ffffff", marker_line_width=1.5)
    charts["promotion_impact"] = _serialize_figure(_apply_chart_style(fig4, "Average Sales by Promotion"))

    traffic_sales = (
        df.groupby("Foot Traffic", as_index=False)["Sales Volume"]
        .mean()
        .sort_values("Sales Volume", ascending=False)
    )
    fig5 = px.bar(
        traffic_sales,
        x="Foot Traffic",
        y="Sales Volume",
        category_orders={"Foot Traffic": TRAFFIC_ORDER},
        color_discrete_sequence=[CHART_COLORS[2]],
    )
    fig5.update_traces(marker_line_color="#ffffff", marker_line_width=1.5)
    charts["traffic_impact"] = _serialize_figure(_apply_chart_style(fig5, "Average Sales by Foot Traffic"))

    demo_sales = (
        df.groupby("Consumer Demographics", as_index=False)["Sales Volume"]
        .sum()
        .sort_values("Sales Volume", ascending=False)
    )
    fig6 = px.bar(
        demo_sales,
        x="Consumer Demographics",
        y="Sales Volume",
        color_discrete_sequence=[CHART_COLORS[3]],
    )
    fig6.update_traces(marker_line_color="#ffffff", marker_line_width=1.5)
    charts["demographics"] = _serialize_figure(_apply_chart_style(fig6, "Demand by Consumer Group"))

    seasonal_sales = (
        df.groupby("Season Label", as_index=False)["Sales Volume"]
        .sum()
        .sort_values("Sales Volume", ascending=False)
    )
    fig7 = px.bar(
        seasonal_sales,
        x="Season Label",
        y="Sales Volume",
        color_discrete_sequence=[CHART_COLORS[4]],
    )
    fig7.update_traces(marker_line_color="#ffffff", marker_line_width=1.5)
    charts["seasonal"] = _serialize_figure(_apply_chart_style(fig7, "Seasonal vs Core Sales"))

    top10 = (
        df.groupby("Product ID", as_index=False)["Sales Volume"]
        .sum()
        .sort_values("Sales Volume", ascending=False)
        .head(10)
        .sort_values("Sales Volume", ascending=True)
    )
    fig8 = px.bar(
        top10,
        x="Sales Volume",
        y="Product ID",
        orientation="h",
        color_discrete_sequence=[CHART_COLORS[5]],
    )
    fig8.update_traces(marker_line_color="#ffffff", marker_line_width=1.5)
    charts["top_10"] = _serialize_figure(_apply_chart_style(fig8, "Top Products by Sales Volume"))

    return charts


def generate_story_charts(df=None):
    return generate_dashboard_charts(df=df)


def get_analysis_snapshot():
    df = get_data()
    if df is None or df.empty:
        return None

    return {
        "summary": build_summary(df),
        "charts": generate_dashboard_charts(df=df),
    }
