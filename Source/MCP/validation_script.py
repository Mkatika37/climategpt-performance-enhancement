# validation_script_minimal_queries_no_continent.py
# Purpose: Answer 40 analytical questions using Aqueduct 4.0 database (no continent mapping required)

import os
import shutil
import time
import duckdb
import pandas as pd

DB_PATH = r"C:\Users\iruka\aqueduct_40_database.duckdb"

# ---------- Safe Connect ----------
def connect_duckdb(db_path: str):
    try:
        return duckdb.connect(db_path, read_only=True), None
    except duckdb.IOException as e:
        if "being used by another process" in str(e).lower():
            base, _ = os.path.splitext(db_path)
            copy_path = base + ".rocopy.duckdb"
            for _ in range(5):
                try:
                    shutil.copy2(db_path, copy_path)
                    break
                except Exception:
                    time.sleep(0.4)
            return duckdb.connect(copy_path, read_only=True), copy_path
        raise

conn, _temp_copy = connect_duckdb(DB_PATH)

# ---------- Helper ----------
def show(title, sql):
    print(f"\n=== {title} ===")
    try:
        df = conn.execute(sql).fetchdf()
        if df.empty:
            print("(no data)")
        else:
            print(df.to_string(index=False))
    except Exception as e:
        print(f"Error: {e}")

# ---------- Build baseline & future views ----------
conn.execute("""
CREATE OR REPLACE TEMP VIEW v_country_baseline AS
SELECT
  name_0 AS country,
  AVG(bws_raw) AS bws_raw,
  AVG(bws_score) AS bws_score,
  AVG(rfr_score) AS rfr_score,
  AVG(drr_score) AS drr_score,
  AVG(sev_score) AS sev_score,
  AVG(iav_score) AS iav_score,
  AVG(gtd_raw) AS gtd_raw,
  AVG(w_awr_def_tot_score) AS overall_risk_score
FROM Baseline_Annual
GROUP BY 1;
""")

pfaf_col = conn.execute("""
SELECT CASE
  WHEN EXISTS (SELECT 1 FROM information_schema.columns WHERE table_name ILIKE 'future_annual' AND column_name ILIKE 'pfafstetter_id') THEN 'Pfafstetter_ID'
  WHEN EXISTS (SELECT 1 FROM information_schema.columns WHERE table_name ILIKE 'future_annual' AND column_name ILIKE 'pfaf_id') THEN 'pfaf_id'
  ELSE NULL END;
""").fetchone()[0]

if pfaf_col is None:
    raise RuntimeError("Future_Annual missing PFAF column")

conn.execute(f"""
CREATE OR REPLACE TEMP VIEW v_future_country AS
WITH f AS (
  SELECT CAST({pfaf_col} AS BIGINT) AS pfaf,
         AVG(bau30_ws_x_r) AS ws_2030,
         AVG(bau50_ws_x_r) AS ws_2050,
         AVG(bau50_iv_x_r) AS iv_2050
  FROM Future_Annual
  GROUP BY 1
),
m AS (
  SELECT CAST(pfaf_id AS BIGINT) AS pfaf, name_0 AS country
  FROM Baseline_Annual
  GROUP BY 1,2
)
SELECT m.country,
       AVG(f.ws_2030) AS ws_2030,
       AVG(f.ws_2050) AS ws_2050,
       AVG(f.iv_2050) AS iv_2050
FROM f JOIN m USING(pfaf)
GROUP BY 1;
""")

# ---------- Analytical Questions ----------
show("Baseline water stress score for Brazil",
     "SELECT country, ROUND(bws_score,4) FROM v_country_baseline WHERE country='Brazil';")

show("Flood risk level for China",
     "SELECT country, ROUND(rfr_score,4) FROM v_country_baseline WHERE country='China';")

show("Drought severity score for Australia",
     "SELECT country, ROUND(drr_score,4) FROM v_country_baseline WHERE country='Australia';")

show("Groundwater depletion rate for Mexico",
     "SELECT country, ROUND(gtd_raw,4) FROM v_country_baseline WHERE country='Mexico';")

show("Projected water stress for South Africa in 2030",
     "SELECT country, ROUND(ws_2030,4) FROM v_future_country WHERE country='South Africa';")

show("Seasonal variability score for Egypt",
     "SELECT country, ROUND(sev_score,4) FROM v_country_baseline WHERE country='Egypt';")

show("Overall water risk score for Canada",
     "SELECT country, ROUND(overall_risk_score,4) FROM v_country_baseline WHERE country='Canada';")

show("Drought severity score for Spain in 2050",
     "SELECT country, ROUND(iv_2050,4) FROM v_future_country WHERE country='Spain';")

show("Flood risk score for the United States",
     "SELECT country, ROUND(rfr_score,4) FROM v_country_baseline WHERE country='United States';")

show("Baseline water stress for Japan",
     "SELECT country, ROUND(bws_score,4) FROM v_country_baseline WHERE country='Japan';")

show("Projected change in water stress for India (2020–2050)",
     """
     SELECT f.country, ROUND(f.ws_2050 - b.bws_score,4) AS delta
     FROM v_future_country f JOIN v_country_baseline b USING(country)
     WHERE f.country='India';
     """)

show("Water demand increase percentage for Indonesia",
     "SELECT country, ROUND(((ws_2050 - ws_2030)/ws_2030)*100,2) AS demand_increase_pct FROM v_future_country WHERE country='Indonesia';")

show("Total renewable water availability for Saudi Arabia",
     "SELECT country, ROUND(1 - bws_raw,4) AS renewable_water_index FROM v_country_baseline WHERE country='Saudi Arabia';")

show("Water risk index for Pakistan in 2030",
     "SELECT country, ROUND(ws_2030,4) FROM v_future_country WHERE country='Pakistan';")

show("Overall water stress trend for Germany (2020–2050)",
     """
     SELECT f.country, ROUND(b.bws_score,4) AS base, ROUND(f.ws_2050,4) AS fut, ROUND(f.ws_2050 - b.bws_score,4) AS change
     FROM v_future_country f JOIN v_country_baseline b USING(country)
     WHERE f.country='Germany';
     """)

show("Countries showing improvement in drought by 2050",
     """
     SELECT b.country, ROUND(b.iav_score - f.iv_2050,4) AS improvement
     FROM v_country_baseline b JOIN v_future_country f USING(country)
     WHERE f.iv_2050 < b.iav_score
     ORDER BY improvement DESC LIMIT 15;
     """)

show("Countries expected to experience an increase in flood risk by 2050",
     """
     WITH rf AS (
       SELECT name_0 AS country, AVG(rfr_score) AS rfr_base FROM Baseline_Annual GROUP BY 1
     ), f AS (
       SELECT name_0 AS country, AVG(bau50_rf_x_r) AS rfr_2050 FROM Future_Annual GROUP BY 1
     )
     SELECT f.country, ROUND(f.rfr_2050 - r.rfr_base,4) AS increase
     FROM rf r JOIN f USING(country)
     WHERE f.rfr_2050 > r.rfr_base
     ORDER BY increase DESC LIMIT 15;
     """)

# ---------- Pairwise Comparison Helper ----------
def compare(qtitle, metric, c1, c2, table="v_country_baseline"):
    show(qtitle, f"""
         SELECT country, ROUND({metric},4) AS value
         FROM {table}
         WHERE country IN ('{c1}','{c2}')
         ORDER BY value DESC;
         """)

compare("Higher baseline water stress — India vs China", "bws_score", "India", "China")
compare("Greater drought severity — Spain vs Italy", "drr_score", "Spain", "Italy")
compare("Higher groundwater depletion — US vs Mexico", "gtd_raw", "United States", "Mexico")
compare("Lower flood risk — Japan vs South Korea", "rfr_score", "Japan", "South Korea")
compare("Greater overall water stress — Egypt vs Sudan", "overall_risk_score", "Egypt", "Sudan")
compare("Higher projected 2050 stress — India vs Pakistan", "ws_2050", "India", "Pakistan", "v_future_country")
compare("Improved water availability — Brazil vs Argentina", "bws_score", "Brazil", "Argentina")
compare("More seasonal variability — Australia vs South Africa", "sev_score", "Australia", "South Africa")
compare("Higher drought in 2050 — Saudi Arabia vs Iran", "iv_2050", "Saudi Arabia", "Iran", "v_future_country")
compare("Larger reduction in flood risk — UK vs France", "rfr_score", "United Kingdom", "France")
compare("More groundwater stress — India vs Bangladesh", "gtd_raw", "India", "Bangladesh")
compare("Higher total water demand — Indonesia vs Malaysia", "ws_2050", "Indonesia", "Malaysia", "v_future_country")
compare("More drought resilience — Kenya vs Ethiopia", "drr_score", "Kenya", "Ethiopia")
compare("Higher flood frequency — Thailand vs Vietnam", "rfr_score", "Thailand", "Vietnam")
compare("Greater projected improvement — Peru vs Chile", "ws_2050", "Peru", "Chile", "v_future_country")
compare("Higher 2050 drought severity — Mexico vs Brazil", "iv_2050", "Mexico", "Brazil", "v_future_country")
compare("Larger increase in water stress — Nigeria vs Ghana", "ws_2050", "Nigeria", "Ghana", "v_future_country")
compare("Higher baseline flood risk — US vs Canada", "rfr_score", "United States", "Canada")
compare("Larger flood-risk decrease — Germany vs Netherlands", "rfr_score", "Germany", "Netherlands")
compare("Greater flood–drought contrast — India vs China", "ABS(rfr_score - drr_score)", "India", "China")

# ---------- Cleanup ----------
conn.close()
if _temp_copy:
    try:
        os.remove(_temp_copy)
    except Exception:
        pass

print("\nDone.")



