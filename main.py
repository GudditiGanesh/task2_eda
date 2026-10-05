"""
ApexPlanet Task 2 - EDA & Business Intelligence
Usage:  python main.py [path_to_dataset.xlsx|csv]
Auto-detects columns (date, sales, profit, quantity, category, product, customer, region).
If no dataset is found, a synthetic sample is generated so you can test the pipeline.
"""
import sys, re, base64, sqlite3, warnings
from pathlib import Path
import numpy as np, pandas as pd
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import seaborn as sns

warnings.filterwarnings("ignore")
BASE = Path(__file__).parent
DATA = Path(sys.argv[1]) if len(sys.argv) > 1 else BASE / "ApexPlanet_DataAnalytics_Dataset.xlsx"
OUT = BASE / "output"; CH = OUT / "charts"; SQLD = OUT / "sql_results"
for p in (CH, SQLD): p.mkdir(parents=True, exist_ok=True)
sns.set_theme(style="whitegrid")
LOG = []


# ---------------------------------------------------------------- load
def make_sample(n=500):
    r = np.random.default_rng(42)
    prods = {"Laptop": "Technology", "Phone": "Technology", "Monitor": "Technology",
             "Chair": "Furniture", "Desk": "Furniture", "Bookcase": "Furniture",
             "Paper": "Office Supplies", "Binder": "Office Supplies", "Pens": "Office Supplies"}
    p = r.choice(list(prods), n)
    qty = r.integers(1, 11, n)
    price = {"Laptop": 900, "Phone": 600, "Monitor": 250, "Chair": 180, "Desk": 320,
             "Bookcase": 150, "Paper": 20, "Binder": 12, "Pens": 8}
    sales = np.array([price[x] for x in p]) * qty * r.uniform(0.8, 1.2, n)
    disc = r.choice([0, 0.1, 0.2, 0.3], n)
    sales = sales * (1 - disc)
    margin = {"Technology": 0.22, "Furniture": 0.08, "Office Supplies": 0.30}
    profit = sales * np.array([margin[prods[x]] for x in p]) - disc * 40 * qty + r.normal(0, 15, n)
    df = pd.DataFrame({
        "Order ID": np.arange(1001, 1001 + n),
        "Order Date": pd.to_datetime("2024-01-01") + pd.to_timedelta(r.integers(0, 540, n), "D"),
        "Customer ID": [f"C{x:03d}" for x in r.integers(1, 121, n)],
        "Region": r.choice(["North", "South", "East", "West"], n),
        "Product": p, "Category": [prods[x] for x in p],
        "Quantity": qty, "Discount": disc, "Sales": sales.round(2), "Profit": profit.round(2)})
    df.loc[r.choice(n, 10, replace=False), "Sales"] = np.nan  # a few gaps to test cleaning
    return pd.concat([df, df.head(5)], ignore_index=True)       # a few duplicates


def load():
    if DATA.exists():
        df = pd.read_csv(DATA) if DATA.suffix.lower() == ".csv" else pd.read_excel(DATA)
        src = DATA.name
    else:
        print(f"!! {DATA.name} not found - using SYNTHETIC sample data. Put your file next to main.py.")
        df, src = make_sample(), "SYNTHETIC SAMPLE"
    print(f"Loaded {len(df)} rows x {df.shape[1]} columns from {src}")
    LOG.append(f"Source: {src}; raw shape {df.shape}")
    return df


# ---------------------------------------------------------------- clean
def clean(df):
    df.columns = [re.sub(r"\W+", "_", str(c).strip()).strip("_").lower() for c in df.columns]
    df = df.dropna(how="all").copy()
    for c in df.columns:
        if "date" in c:
            df[c] = pd.to_datetime(df[c], errors="coerce")
        elif not pd.api.types.is_numeric_dtype(df[c]) and not pd.api.types.is_datetime64_any_dtype(df[c]):
            s = df[c].astype("string").str.strip()
            df[c] = s.where(s != "", pd.NA).astype(object)
    dups = int(df.duplicated().sum())
    df = df.drop_duplicates().reset_index(drop=True)
    LOG.append(f"Removed {dups} duplicate rows")
    for c in df.columns:
        n = int(df[c].isna().sum())
        if not n: continue
        if pd.api.types.is_numeric_dtype(df[c]):
            df[c] = df[c].fillna(df[c].median()); how = "median"
        elif pd.api.types.is_datetime64_any_dtype(df[c]):
            df[c] = df[c].ffill().bfill(); how = "forward/back fill"
        else:
            df[c] = df[c].fillna(df[c].mode().iloc[0]); how = "mode"
        LOG.append(f"Filled {n} missing in '{c}' with {how}")
    LOG.append(f"Clean shape {df.shape}")
    df.to_csv(OUT / "cleaned_data.csv", index=False)
    df.to_excel(OUT / "cleaned_data.xlsx", index=False)
    return df


# ---------------------------------------------------------------- column detection
def find(cols, keys):
    for k in keys:
        for c in cols:
            if k in c: return c

def detect(df):
    idlike = re.compile(r"(^|_)(id|no|number|index|row|zip|postal)(_|$)")
    num_all = [c for c in df.columns if pd.api.types.is_numeric_dtype(df[c])]
    num = [c for c in num_all if not idlike.search(c)]
    dates = [c for c in df.columns if pd.api.types.is_datetime64_any_dtype(df[c])]
    cats = [c for c in df.columns if c not in num_all + dates and not idlike.search(c)
            and 1 < df[c].nunique() <= max(50, 0.2 * len(df))]
    m = dict(
        date=dates[0] if dates else None,
        sales=find(num, ["sales", "revenue", "amount", "total", "price"]),
        profit=find(num, ["profit", "margin"]),
        qty=find(num, ["quantity", "qty", "units"]),
        cat=find(cats, ["category", "segment", "type"]),
        prod=find([c for c in df.columns if c not in num_all + dates], ["product", "item"]),
        cust=find(df.columns, ["customer_id", "customer", "client"]),
        reg=find(cats, ["region", "state", "city", "country"]),
        order=find(df.columns, ["order_id", "order"]))
    LOG.append("Detected columns: " + ", ".join(f"{k}={v}" for k, v in m.items() if v))
    return m, num, cats


# ---------------------------------------------------------------- charts
def save(fig, name):
    fig.tight_layout(); fig.savefig(CH / name, dpi=110); plt.close(fig); return name

def univariate(df, num, cats):
    names = []
    for c in num:
        f, a = plt.subplots(figsize=(6, 4)); sns.histplot(df[c], kde=True, ax=a, color="#3b6fb6")
        a.set_title(f"Distribution of {c}"); names.append(save(f, f"hist_{c}.png"))
        f, a = plt.subplots(figsize=(6, 3)); sns.boxplot(x=df[c], ax=a, color="#9ecae1")
        a.set_title(f"Box plot of {c}"); names.append(save(f, f"box_{c}.png"))
    for c in cats:
        f, a = plt.subplots(figsize=(6, 4)); vc = df[c].value_counts().head(10)
        sns.barplot(x=vc.values, y=vc.index.astype(str), ax=a, color="#3b6fb6")
        a.set_title(f"Count of {c}"); names.append(save(f, f"count_{c}.png"))
    return names

def multivariate(df, num, m):
    names, corr = [], None
    if len(num) >= 2:
        corr = df[num].corr()
        f, a = plt.subplots(figsize=(7, 5.5))
        sns.heatmap(corr, annot=True, fmt=".2f", cmap="coolwarm", center=0, ax=a)
        a.set_title("Correlation heatmap"); names.append(save(f, "heatmap_correlation.png"))
        pairs = corr.where(np.triu(np.ones(corr.shape, bool), 1)).stack().abs().sort_values(ascending=False)
        for (x, y) in list(pairs.index[:3]):
            f, a = plt.subplots(figsize=(6, 4.5))
            sns.regplot(data=df, x=x, y=y, ax=a, scatter_kws={"alpha": .4, "s": 18}, line_kws={"color": "red"})
            a.set_title(f"{x} vs {y} (r={corr.loc[x, y]:.2f})"); names.append(save(f, f"scatter_{x}_vs_{y}.png"))
        cols = ([m[k] for k in ("sales", "profit", "qty") if m[k]] + [c for c in num if c not in m.values()])[:4]
        if len(cols) >= 2:
            g = sns.pairplot(df[cols].sample(min(len(df), 400), random_state=1), corner=True, plot_kws={"s": 12, "alpha": .5})
            g.savefig(CH / "pairplot.png", dpi=90); plt.close("all"); names.append("pairplot.png")
    return names, corr

def outliers(df, num):
    res = {}
    for c in num:
        q1, q3 = df[c].quantile([.25, .75]); i = q3 - q1
        res[c] = int(((df[c] < q1 - 1.5 * i) | (df[c] > q3 + 1.5 * i)).sum())
    return res


# ---------------------------------------------------------------- SQL BI
def sql_bi(df, m):
    con = sqlite3.connect(OUT / "business.db")
    d = df.copy()
    if m["date"]: d[m["date"]] = d[m["date"]].dt.strftime("%Y-%m-%d")
    d.to_sql("sales", con, if_exists="replace", index=False)
    S, P, Q, C, PR, CU, R, D = (m[k] for k in ("sales", "profit", "qty", "cat", "prod", "cust", "reg", "date"))
    if PR and C:
        d[[PR, C]].drop_duplicates(PR).to_sql("products", con, if_exists="replace", index=False)
    if CU:
        agg = {"first_order": (D, "min")} if D else {}
        cdf = d.groupby(CU).agg(**agg).reset_index() if agg else d[[CU]].drop_duplicates()
        cdf.to_sql("customers", con, if_exists="replace", index=False)
    Q_ = {}
    if S:
        Q_["01_kpis"] = (f"SELECT COUNT(*) AS rows_, ROUND(SUM({S}),2) AS total_sales, ROUND(AVG({S}),2) AS avg_sales"
                         + (f", ROUND(SUM({P}),2) AS total_profit, ROUND(100.0*SUM({P})/SUM({S}),2) AS margin_pct" if P else "")
                         + " FROM sales")
        if PR: Q_["02_top_products"] = (f"SELECT {PR}, ROUND(SUM({S}),2) AS revenue, COUNT(*) AS orders"
                                       + (f", ROUND(SUM({P}),2) AS profit" if P else "")
                                       + f" FROM sales GROUP BY {PR} ORDER BY revenue DESC LIMIT 10")
        if D: Q_["03_monthly_sales"] = (f"SELECT strftime('%Y-%m',{D}) AS month, ROUND(SUM({S}),2) AS revenue, COUNT(*) AS orders"
                                       + (f", ROUND(SUM({P}),2) AS profit" if P else "")
                                       + " FROM sales GROUP BY month ORDER BY month")
        if C: Q_["04_revenue_by_category"] = (f"SELECT {C}, ROUND(SUM({S}),2) AS revenue, ROUND(AVG({S}),2) AS avg_sale"
                                             + (f", ROUND(100.0*SUM({P})/SUM({S}),2) AS margin_pct" if P else "")
                                             + f" FROM sales GROUP BY {C} ORDER BY revenue DESC")
        if R: Q_["05_revenue_by_region"] = (f"SELECT {R}, ROUND(SUM({S}),2) AS revenue, COUNT(*) AS orders "
                                           f"FROM sales GROUP BY {R} ORDER BY revenue DESC")
        if CU: Q_["06_top_customers"] = (f"SELECT {CU}, COUNT(*) AS orders, ROUND(SUM({S}),2) AS revenue "
                                        f"FROM sales GROUP BY {CU} ORDER BY revenue DESC LIMIT 10")
        if PR and C: Q_["07_join_products_category"] = (f"SELECT p.{C}, COUNT(DISTINCT p.{PR}) AS products, ROUND(SUM(s.{S}),2) AS revenue "
                                                       f"FROM sales s JOIN products p ON s.{PR} = p.{PR} GROUP BY p.{C} ORDER BY revenue DESC")
        if CU: Q_["08_join_customer_value"] = (f"SELECT c.{CU}" + (", c.first_order" if D else "")
                                              + f", COUNT(*) AS orders, ROUND(SUM(s.{S}),2) AS lifetime_value "
                                              f"FROM customers c JOIN sales s ON s.{CU} = c.{CU} GROUP BY c.{CU} ORDER BY lifetime_value DESC LIMIT 10")
    results = {}
    with open(OUT / "sql_queries.sql", "w") as fh:
        for k, q in Q_.items():
            fh.write(f"-- {k}\n{q};\n\n")
            r = pd.read_sql_query(q, con); r.to_csv(SQLD / f"{k}.csv", index=False); results[k] = r
    con.close()
    return results


# ---------------------------------------------------------------- insights
def insights(df, m, res, corr, out):
    I = []
    S, P, C, PR, D = m["sales"], m["profit"], m["cat"], m["prod"], m["date"]
    if S:
        I.append(f"Total revenue is {df[S].sum():,.0f} across {len(df):,} records (average sale {df[S].mean():,.2f}).")
    if S and P:
        I.append(f"Overall profit margin is {100 * df[P].sum() / df[S].sum():.1f}% (total profit {df[P].sum():,.0f}).")
    if "03_monthly_sales" in res:
        t = res["03_monthly_sales"]
        I.append(f"Best month: {t.loc[t.revenue.idxmax(), 'month']} ({t.revenue.max():,.0f}); weakest: {t.loc[t.revenue.idxmin(), 'month']} ({t.revenue.min():,.0f}).")
        if len(t) >= 6:
            a, b = t.revenue.head(3).mean(), t.revenue.tail(3).mean()
            I.append(f"Last 3 months average {b:,.0f} vs first 3 months {a:,.0f} ({100 * (b - a) / a:+.1f}%).")
    if "04_revenue_by_category" in res:
        t = res["04_revenue_by_category"]
        I.append(f"'{t.iloc[0, 0]}' leads categories with {100 * t.revenue.iloc[0] / t.revenue.sum():.1f}% of revenue.")
        if "margin_pct" in t:
            lo = t.loc[t.margin_pct.idxmin()]
            I.append(f"'{lo.iloc[0]}' has the lowest margin ({lo.margin_pct:.1f}%) - review pricing/discounts there.")
    if "02_top_products" in res:
        t = res["02_top_products"]; I.append(f"Top product: '{t.iloc[0, 0]}' with {t.revenue.iloc[0]:,.0f} revenue.")
    if "06_top_customers" in res:
        t = res["06_top_customers"]
        I.append(f"Top 10 customers generate {100 * t.revenue.sum() / df[S].sum():.1f}% of revenue - consider loyalty programs.")
    if corr is not None and len(corr) >= 2:
        pr = corr.where(np.triu(np.ones(corr.shape, bool), 1)).stack().sort_values(key=abs, ascending=False)
        (a, b), v = pr.index[0], pr.iloc[0]
        I.append(f"Strongest relationship: {a} and {b} (r = {v:.2f}).")
        dc = next((c for c in corr.columns if "discount" in c), None)
        if dc and P and dc != P:
            I.append(f"Discount vs {P} correlation is {corr.loc[dc, P]:.2f}" + (" - heavier discounts erode profit." if corr.loc[dc, P] < -0.1 else "."))
    tot = sum(out.values())
    if tot: I.append(f"{tot} outlier values found (IQR rule); most in '{max(out, key=out.get)}'. Check whether they are bulk orders or errors.")
    return I


# ---------------------------------------------------------------- dashboard mock-up
def dashboard(df, m, res):
    S, P, CU, order = m["sales"], m["profit"], m["cust"], m["order"]
    if not S: return None
    kp = [("Total Revenue", f"{df[S].sum():,.0f}")]
    if P: kp += [("Total Profit", f"{df[P].sum():,.0f}"), ("Profit Margin", f"{100 * df[P].sum() / df[S].sum():.1f}%")]
    kp.append(("Orders", f"{df[order].nunique() if order else len(df):,}"))
    if CU: kp.append(("Customers", f"{df[CU].nunique():,}"))
    fig = plt.figure(figsize=(16, 9.5)); fig.suptitle("Sales Performance Dashboard (Mock-up)", fontsize=20, weight="bold")
    gs = fig.add_gridspec(3, len(kp), height_ratios=[.5, 2, 2])
    for i, (t, v) in enumerate(kp):
        a = fig.add_subplot(gs[0, i]); a.axis("off")
        a.add_patch(plt.Rectangle((0, 0), 1, 1, color="#1f3b6e", transform=a.transAxes))
        a.text(.5, .62, v, ha="center", va="center", color="white", fontsize=22, weight="bold", transform=a.transAxes)
        a.text(.5, .22, t, ha="center", va="center", color="#cfe0ff", fontsize=11, transform=a.transAxes)
    k = len(kp)
    def bar(ax, key, x, y, title, horizontal=False):
        if key in res:
            t = res[key]
            (sns.barplot(data=t, y=x, x=y, ax=ax, color="#3b6fb6") if horizontal else sns.barplot(data=t, x=x, y=y, ax=ax, color="#3b6fb6"))
        ax.set_title(title, weight="bold")
    a = fig.add_subplot(gs[1, :max(k - 2, 1)])
    if "03_monthly_sales" in res:
        t = res["03_monthly_sales"]; a.plot(t.month, t.revenue, marker="o", color="#1f3b6e")
        a.fill_between(range(len(t)), t.revenue, alpha=.15, color="#1f3b6e")
        a.set_xticks(range(0, len(t), max(1, len(t) // 8))); a.set_xticklabels(t.month[::max(1, len(t) // 8)], rotation=30)
    else: sns.histplot(df[S], ax=a, color="#3b6fb6")
    a.set_title("Revenue Trend", weight="bold")
    a = fig.add_subplot(gs[1, max(k - 2, 1):])
    if "04_revenue_by_category" in res:
        t = res["04_revenue_by_category"]; a.pie(t.revenue, labels=t.iloc[:, 0], autopct="%1.0f%%", startangle=90)
    a.set_title("Category Distribution", weight="bold")
    a = fig.add_subplot(gs[2, :max(k // 2, 1)])
    if "02_top_products" in res: bar(a, "02_top_products", res["02_top_products"].columns[0], "revenue", "Top Products by Revenue", True)
    else: a.set_title("Top Products (n/a)")
    a = fig.add_subplot(gs[2, max(k // 2, 1):])
    if "06_top_customers" in res: bar(a, "06_top_customers", res["06_top_customers"].columns[0], "revenue", "Top Customers", True)
    elif "05_revenue_by_region" in res: bar(a, "05_revenue_by_region", res["05_revenue_by_region"].columns[0], "revenue", "Revenue by Region")
    fig.tight_layout(rect=[0, 0, 1, .95]); fig.savefig(OUT / "dashboard_mockup.png", dpi=110); plt.close(fig)
    return "dashboard_mockup.png"


# ---------------------------------------------------------------- HTML report
def b64(path): return base64.b64encode(Path(path).read_bytes()).decode()

def report(df, num, desc, out, corr, imgs, I, res, dash):
    h = ["<html><head><meta charset='utf-8'><title>EDA Report</title><style>body{font-family:Arial;max-width:1100px;margin:auto;padding:20px}"
         "h1,h2{color:#1f3b6e}table{border-collapse:collapse;font-size:13px}td,th{border:1px solid #ccc;padding:4px 8px}"
         "img{max-width:48%;margin:4px}li{margin:6px 0}</style></head><body><h1>Exploratory Data Analysis Report</h1>"]
    h.append("<h2>1. Data Cleaning Log</h2><ul>" + "".join(f"<li>{x}</li>" for x in LOG) + "</ul>")
    h.append("<h2>2. Business Insights &amp; Recommendations</h2><ul>" + "".join(f"<li>{x}</li>" for x in I) + "</ul>")
    if dash: h.append(f"<h2>3. Dashboard Mock-up</h2><img style='max-width:100%' src='data:image/png;base64,{b64(OUT / dash)}'>")
    h.append("<h2>4. Summary Statistics</h2>" + desc.round(2).to_html())
    h.append("<h2>5. Outlier Counts (IQR)</h2>" + pd.Series(out, name="outliers").to_frame().to_html())
    if corr is not None: h.append("<h2>6. Correlation Matrix</h2>" + corr.round(2).to_html())
    h.append("<h2>7. SQL Business Analysis</h2>")
    for k, t in res.items(): h.append(f"<h3>{k[3:].replace('_', ' ').title()}</h3>" + t.head(10).to_html(index=False))
    h.append("<h2>8. Charts</h2>" + "".join(f"<img src='data:image/png;base64,{b64(CH / n)}'>" for n in imgs))
    h.append("</body></html>")
    (OUT / "eda_report.html").write_text("\n".join(h), encoding="utf-8")


# ---------------------------------------------------------------- main
def main():
    df = clean(load())
    m, num, cats = detect(df)
    desc = df[num].describe().T
    desc["mode"] = [df[c].mode().iloc[0] for c in num]
    print("\nSummary statistics:\n"); print(desc.round(2).to_string())
    imgs = univariate(df, num, cats)
    mv, corr = multivariate(df, num, m); imgs += mv
    out = outliers(df, num)
    if corr is not None:
        top = corr.where(np.triu(np.ones(corr.shape, bool), 1)).stack().sort_values(ascending=False).head(5)
        print("\nTop correlations:\n"); print(top.round(2).to_string())
    print("\nOutliers (IQR):", out)
    res = sql_bi(df, m)
    I = insights(df, m, res, corr, out)
    print("\nInsights:"); [print(" -", x) for x in I]
    dash = dashboard(df, m, res)
    report(df, num, desc, out, corr, imgs, I, res, dash)
    print(f"\nDone. Outputs saved in:\n{OUT.resolve()}")


if __name__ == "__main__":
    main()
