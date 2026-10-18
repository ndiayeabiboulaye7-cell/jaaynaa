from __future__ import annotations
import sqlite3, shutil, io, csv
from pathlib import Path
from datetime import datetime, date, timedelta
import pandas as pd
import streamlit as st

APP_DIR = Path(__file__).resolve().parent
DATA_DIR = APP_DIR / "data"
DATA_DIR.mkdir(exist_ok=True)
DB_PATH = DATA_DIR / "jaaynaa.db"

st.set_page_config(page_title="JAAYNAA PRO | Gestion commerciale", page_icon="🇸🇳", layout="wide", initial_sidebar_state="expanded")

TRANSLATIONS = {
    "Français": {
        "Dashboard":"Tableau de bord", "Produits & stocks":"Produits & stocks", "Ventes":"Ventes", "Achats":"Achats",
        "Clients":"Clients", "Fournisseurs":"Fournisseurs", "Dépenses":"Dépenses", "Rapports":"Rapports",
        "Paramètres":"Paramètres", "Règlements":"Règlements", "Nouvelle vente":"Nouvelle vente", "Enregistrer":"Enregistrer", "Nom":"Nom",
        "Référence":"Référence", "Catégorie":"Catégorie", "Prix d'achat":"Prix d'achat", "Prix détail":"Prix détail",
        "Prix gros":"Prix gros", "Quantité":"Quantité", "Seuil d'alerte":"Seuil d'alerte", "Unité":"Unité",
        "Ajouter un produit":"Ajouter un produit", "Rechercher":"Rechercher", "Montant":"Montant", "Date":"Date",
        "Moyen de paiement":"Moyen de paiement", "Montant payé":"Montant payé", "Client":"Client", "Fournisseur":"Fournisseur",
        "Ajouter":"Ajouter", "Télécharger CSV":"Télécharger CSV", "Mode sombre":"Mode sombre", "Langue":"Langue",
    },
    "Wolof": {
        "Dashboard":"Tabel bu njëkk", "Produits & stocks":"Mala yi ak stock", "Ventes":"Jaay yi", "Achats":"Jënd yi",
        "Clients":"Kiliyaŋ yi", "Fournisseurs":"Jaaykat yi", "Dépenses":"Fay yi", "Rapports":"Rapoor yi",
        "Paramètres":"Tànneef yi", "Règlements":"Fay yi ak solde", "Nouvelle vente":"Jaay bu bees", "Enregistrer":"Denc", "Nom":"Tur",
        "Référence":"Rëfërans", "Catégorie":"Xeet", "Prix d'achat":"Njëg jënd", "Prix détail":"Njëg jaay",
        "Prix gros":"Njëg jaay bu bari", "Quantité":"Limu", "Seuil d'alerte":"Limite bu xelal", "Unité":"Benn-benn",
        "Ajouter un produit":"Yokk benn mala", "Rechercher":"Wut", "Montant":"Limu xaalis", "Date":"Bés",
        "Moyen de paiement":"Yoonu fay", "Montant payé":"Limu buñ fay", "Client":"Kiliyaŋ", "Fournisseur":"Jaaykat",
        "Ajouter":"Yokk", "Télécharger CSV":"Yebbi CSV", "Mode sombre":"Nataal bu ñuul", "Langue":"Làkk",
    }
}

def tr(text: str) -> str:
    lang = st.session_state.get("lang", "Français")
    return TRANSLATIONS.get(lang, {}).get(text, text)

def connect():
    con = sqlite3.connect(DB_PATH, timeout=20)
    con.row_factory = sqlite3.Row
    con.execute("PRAGMA foreign_keys = ON")
    return con

def init_db():
    with connect() as c:
        c.executescript("""
        CREATE TABLE IF NOT EXISTS settings (key TEXT PRIMARY KEY, value TEXT NOT NULL);
        CREATE TABLE IF NOT EXISTS products (
            id INTEGER PRIMARY KEY AUTOINCREMENT, name TEXT NOT NULL, reference TEXT UNIQUE,
            category TEXT DEFAULT '', purchase_price REAL NOT NULL DEFAULT 0, retail_price REAL NOT NULL DEFAULT 0,
            wholesale_price REAL NOT NULL DEFAULT 0, quantity REAL NOT NULL DEFAULT 0,
            min_stock REAL NOT NULL DEFAULT 0, unit TEXT NOT NULL DEFAULT 'pièce', active INTEGER NOT NULL DEFAULT 1,
            created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP);
        CREATE TABLE IF NOT EXISTS clients (id INTEGER PRIMARY KEY AUTOINCREMENT, name TEXT NOT NULL, phone TEXT DEFAULT '', email TEXT DEFAULT '', address TEXT DEFAULT '', created_at TEXT DEFAULT CURRENT_TIMESTAMP);
        CREATE TABLE IF NOT EXISTS suppliers (id INTEGER PRIMARY KEY AUTOINCREMENT, name TEXT NOT NULL, phone TEXT DEFAULT '', email TEXT DEFAULT '', address TEXT DEFAULT '', created_at TEXT DEFAULT CURRENT_TIMESTAMP);
        CREATE TABLE IF NOT EXISTS sales (id INTEGER PRIMARY KEY AUTOINCREMENT, sale_no TEXT UNIQUE NOT NULL, sold_at TEXT NOT NULL, sale_type TEXT NOT NULL, client_id INTEGER, subtotal REAL NOT NULL, discount REAL NOT NULL DEFAULT 0, total REAL NOT NULL, paid REAL NOT NULL DEFAULT 0, payment_method TEXT DEFAULT 'Espèces', note TEXT DEFAULT '', FOREIGN KEY(client_id) REFERENCES clients(id));
        CREATE TABLE IF NOT EXISTS sale_items (id INTEGER PRIMARY KEY AUTOINCREMENT, sale_id INTEGER NOT NULL, product_id INTEGER NOT NULL, product_name TEXT NOT NULL, quantity REAL NOT NULL, unit_price REAL NOT NULL, line_total REAL NOT NULL, cost_price REAL NOT NULL DEFAULT 0, FOREIGN KEY(sale_id) REFERENCES sales(id), FOREIGN KEY(product_id) REFERENCES products(id));
        CREATE TABLE IF NOT EXISTS purchases (id INTEGER PRIMARY KEY AUTOINCREMENT, purchase_no TEXT UNIQUE NOT NULL, purchased_at TEXT NOT NULL, supplier_id INTEGER, total REAL NOT NULL, paid REAL NOT NULL DEFAULT 0, note TEXT DEFAULT '', FOREIGN KEY(supplier_id) REFERENCES suppliers(id));
        CREATE TABLE IF NOT EXISTS purchase_items (id INTEGER PRIMARY KEY AUTOINCREMENT, purchase_id INTEGER NOT NULL, product_id INTEGER NOT NULL, product_name TEXT NOT NULL, quantity REAL NOT NULL, unit_cost REAL NOT NULL, line_total REAL NOT NULL, FOREIGN KEY(purchase_id) REFERENCES purchases(id), FOREIGN KEY(product_id) REFERENCES products(id));
        CREATE TABLE IF NOT EXISTS payments (id INTEGER PRIMARY KEY AUTOINCREMENT, direction TEXT NOT NULL, reference_type TEXT NOT NULL, reference_id INTEGER NOT NULL, paid_at TEXT NOT NULL, amount REAL NOT NULL, method TEXT NOT NULL DEFAULT 'Espèces', note TEXT DEFAULT '');
        CREATE TABLE IF NOT EXISTS expenses (id INTEGER PRIMARY KEY AUTOINCREMENT, spent_at TEXT NOT NULL, category TEXT NOT NULL, description TEXT DEFAULT '', amount REAL NOT NULL, payment_method TEXT DEFAULT 'Espèces');
        CREATE TABLE IF NOT EXISTS stock_movements (id INTEGER PRIMARY KEY AUTOINCREMENT, product_id INTEGER NOT NULL, moved_at TEXT NOT NULL, movement_type TEXT NOT NULL, quantity REAL NOT NULL, note TEXT DEFAULT '', FOREIGN KEY(product_id) REFERENCES products(id));
        """)
        defaults = {"business_name":"JAAYNAA", "business_phone":"", "business_address":"Sénégal", "business_email":"", "currency":"FCFA", "language":"Français", "theme":"Clair"}
        for k,v in defaults.items(): c.execute("INSERT OR IGNORE INTO settings(key,value) VALUES(?,?)", (k,v))

def query_df(sql, params=()):
    with connect() as c: return pd.read_sql_query(sql, c, params=params)

def scalar(sql, params=()):
    with connect() as c:
        row = c.execute(sql, params).fetchone()
        return row[0] if row else 0

def money(value):
    try: return f"{float(value):,.0f}".replace(",", " ") + " FCFA"
    except (ValueError, TypeError): return "0 FCFA"

def setting(key, default=""):
    with connect() as c:
        row = c.execute("SELECT value FROM settings WHERE key=?", (key,)).fetchone()
        return row[0] if row else default

def set_setting(key, value):
    with connect() as c: c.execute("INSERT INTO settings(key,value) VALUES(?,?) ON CONFLICT(key) DO UPDATE SET value=excluded.value", (key, str(value)))

def options(table):
    df = query_df(f"SELECT id, name FROM {table} ORDER BY name")
    return {f"{r['name']} (#{r['id']})": int(r['id']) for _,r in df.iterrows()}

def next_no(prefix, table, column):
    stamp = datetime.now().strftime('%Y%m%d')
    with connect() as c:
        n = c.execute(f"SELECT COUNT(*) FROM {table} WHERE {column} LIKE ?", (f"{prefix}-{stamp}-%",)).fetchone()[0] + 1
    return f"{prefix}-{stamp}-{n:04d}"

def make_pdf(title, rows, totals=None, filename="document.pdf"):
    try:
        from reportlab.lib import colors
        from reportlab.lib.pagesizes import A4
        from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
        from reportlab.lib.units import mm
        from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle
        buf = io.BytesIO()
        doc = SimpleDocTemplate(buf, pagesize=A4, rightMargin=18*mm, leftMargin=18*mm, topMargin=16*mm, bottomMargin=16*mm)
        styles = getSampleStyleSheet(); story=[]
        story.append(Paragraph(setting("business_name", "JAAYNAA"), styles["Title"]))
        story.append(Paragraph(f"{setting('business_address','')} | {setting('business_phone','')}", styles["Normal"]))
        story.append(Spacer(1, 8*mm)); story.append(Paragraph(title, styles["Heading1"]))
        data = [list(rows[0].keys())] if rows else [["Aucune donnée"]]
        for r in rows: data.append([str(v) for v in r.values()])
        table=Table(data, repeatRows=1, hAlign="LEFT")
        table.setStyle(TableStyle([("BACKGROUND",(0,0),(-1,0),colors.HexColor('#14532d')), ("TEXTCOLOR",(0,0),(-1,0),colors.white), ("GRID",(0,0),(-1,-1),0.35,colors.HexColor('#d1d5db')), ("FONTNAME",(0,0),(-1,0),"Helvetica-Bold"), ("FONTSIZE",(0,0),(-1,-1),8), ("PADDING",(0,0),(-1,-1),6)]))
        story.append(table)
        if totals:
            story.append(Spacer(1, 5*mm))
            for k,v in totals.items(): story.append(Paragraph(f"<b>{k} :</b> {v}", styles["Normal"]))
        doc.build(story); return buf.getvalue()
    except ImportError:
        st.error("La génération PDF nécessite reportlab. Installez-le avec : pip install reportlab")
        return None

init_db()
if "lang" not in st.session_state: st.session_state.lang = setting("language", "Français")
if "theme" not in st.session_state: st.session_state.theme = setting("theme", "Clair")
# NEON FUTURE UI — interface complète JAAYNAA PRO
if st.session_state.theme == "Sombre":
    theme_background = "#070b14"
    theme_surface = "rgba(15, 23, 42, .88)"
    theme_text = "#edf7ff"
    theme_muted = "#8ea3bd"
    theme_border = "rgba(103, 232, 249, .16)"
else:
    theme_background = "#eef4f8"
    theme_surface = "rgba(255, 255, 255, .92)"
    theme_text = "#102033"
    theme_muted = "#61758b"
    theme_border = "rgba(15, 118, 110, .18)"

st.markdown(f"""
<style>
@import url('https://fonts.googleapis.com/css2?family=DM+Sans:wght@400;500;600;700;800&family=Space+Grotesk:wght@400;500;600;700&display=swap');
:root {{
 --ja-bg:{theme_background}; --ja-surface:{theme_surface}; --ja-text:{theme_text};
 --ja-muted:{theme_muted}; --ja-border:{theme_border};
 --ja-cyan:#67e8f9; --ja-green:#22c55e; --ja-lime:#bef264; --ja-gold:#facc15;
}}
html, body, [class*="css"] {{font-family:'DM Sans',sans-serif;}}
.stApp {{
 color:var(--ja-text);
 background:
  linear-gradient(rgba(103,232,249,.035) 1px,transparent 1px),
  linear-gradient(90deg,rgba(103,232,249,.035) 1px,transparent 1px),
  radial-gradient(ellipse at 5% 0%,rgba(34,197,94,.15),transparent 34%),
  radial-gradient(ellipse at 95% 12%,rgba(34,211,238,.13),transparent 32%),
  var(--ja-bg);
 background-size:34px 34px,34px 34px,auto,auto,auto;
}}
.block-container {{max-width:1750px;padding-top:1.2rem;padding-bottom:3rem;}}
h1,h2,h3,h4 {{font-family:'Space Grotesk',sans-serif!important;letter-spacing:-.035em;}}
h1 {{font-weight:700!important;}}
p, label, .stCaption {{letter-spacing:.005em;}}
section[data-testid="stSidebar"] {{
 background:linear-gradient(160deg,#061b20 0%,#092d2b 48%,#101b2d 100%);
 border-right:1px solid rgba(103,232,249,.22);
}}
section[data-testid="stSidebar"] * {{color:#e7fbff;}}
section[data-testid="stSidebar"] [data-testid="stRadio"] label {{
 padding:10px 12px;border:1px solid transparent;border-radius:12px;
 transition:all .22s ease;font-weight:600;
}}
section[data-testid="stSidebar"] [data-testid="stRadio"] label:hover {{
 background:rgba(103,232,249,.09);border-color:rgba(103,232,249,.25);transform:translateX(3px);
}}
.ja-nav-shell {{
 margin:-.25rem 0 1.35rem;padding:10px 12px;border-radius:17px;
 border:1px solid var(--ja-border);background:var(--ja-surface);
 box-shadow:0 12px 38px rgba(2,8,23,.09);backdrop-filter:blur(18px);
}}
.ja-nav-shell div[role="radiogroup"] {{display:flex;flex-wrap:wrap;gap:7px;align-items:center;}}
.ja-nav-shell div[role="radiogroup"]>label {{
 min-height:40px;padding:9px 13px!important;margin:0!important;border:1px solid transparent;
 border-radius:11px!important;color:var(--ja-text)!important;font-weight:700;font-size:.86rem;
 transition:all .2s ease;
}}
.ja-nav-shell div[role="radiogroup"]>label:hover {{
 background:rgba(34,211,238,.1);border-color:rgba(34,211,238,.28);transform:translateY(-2px);
}}
.ja-nav-shell div[role="radiogroup"]>label:has(input:checked) {{
 background:linear-gradient(120deg,#0e7490,#0f766e 55%,#15803d);
 color:#fff!important;box-shadow:0 0 22px rgba(34,211,238,.17);
}}
.ja-nav-shell div[role="radiogroup"]>label:has(input:checked) * {{color:#fff!important;}}
.ja-nav-shell div[role="radiogroup"]>label>div:first-child {{display:none;}}
div[data-testid="stMetric"] {{
 position:relative;overflow:hidden;padding:20px 21px;border-radius:18px;
 border:1px solid var(--ja-border);background:var(--ja-surface);
 box-shadow:0 12px 30px rgba(2,8,23,.06);backdrop-filter:blur(16px);
 animation:ja-enter .45s both;transition:transform .23s,border-color .23s,box-shadow .23s;
}}
div[data-testid="stMetric"]:after {{
 content:"";position:absolute;width:100px;height:100px;right:-38px;top:-48px;
 border:1px solid rgba(103,232,249,.25);border-radius:50%;
 box-shadow:0 0 0 13px rgba(103,232,249,.035),0 0 0 27px rgba(103,232,249,.025);
}}
div[data-testid="stMetric"]:hover {{transform:translateY(-4px);border-color:rgba(34,211,238,.45);box-shadow:0 16px 36px rgba(8,145,178,.12);}}
div[data-testid="stMetricLabel"] {{color:var(--ja-muted)!important;font-weight:700;font-size:.82rem;}}
div[data-testid="stMetricValue"] {{color:var(--ja-text)!important;font-family:'Space Grotesk',sans-serif;font-weight:700;letter-spacing:-.045em;}}
.stButton>button,.stDownloadButton>button,button[kind="primary"] {{
 min-height:42px;border-radius:12px!important;border:1px solid rgba(34,211,238,.28)!important;
 font-weight:700!important;transition:all .2s ease!important;
}}
.stButton>button[kind="primary"],button[kind="primary"] {{
 color:#f0fdff!important;background:linear-gradient(115deg,#0e7490,#0f766e 60%,#15803d)!important;
 box-shadow:0 8px 24px rgba(8,145,178,.19);
}}
.stButton>button:hover,.stDownloadButton>button:hover {{transform:translateY(-2px);box-shadow:0 12px 26px rgba(8,145,178,.15);}}
.stTextInput input,.stNumberInput input,.stDateInput input,.stTextArea textarea,
div[data-baseweb="select"]>div {{border-radius:11px!important;}}
div[data-testid="stDataFrame"],div[data-testid="stTable"] {{
 border:1px solid var(--ja-border);border-radius:15px;overflow:hidden;
 box-shadow:0 8px 24px rgba(2,8,23,.045);
}}
details[data-testid="stExpander"] {{border:1px solid var(--ja-border);border-radius:15px;background:var(--ja-surface);}}
details[data-testid="stExpander"]:hover {{border-color:rgba(34,211,238,.38);}}
button[data-baseweb="tab"] {{font-weight:700;border-radius:10px 10px 0 0;}}
hr {{border-color:var(--ja-border)!important;}}
.jaaynaa-topbar {{
 position:relative;display:flex;align-items:center;justify-content:space-between;gap:20px;
 overflow:hidden;margin:0 0 1.2rem;padding:24px 26px;border-radius:22px;
 color:#effcff;border:1px solid rgba(103,232,249,.32);
 background:linear-gradient(112deg,#06141f 0%,#0b3540 45%,#0d513b 100%);
 box-shadow:0 18px 50px rgba(2,8,23,.20);
}}
.jaaynaa-topbar:before {{
 content:"";position:absolute;inset:0;pointer-events:none;opacity:.38;
 background:repeating-linear-gradient(115deg,transparent 0 24px,rgba(103,232,249,.12) 25px,transparent 26px 48px);
}}
.jaaynaa-topbar:after {{
 content:"";position:absolute;width:250px;height:250px;right:-50px;top:-160px;
 border:1px solid rgba(103,232,249,.45);border-radius:50%;
 box-shadow:0 0 0 22px rgba(103,232,249,.045),0 0 0 48px rgba(103,232,249,.035);
 animation:ja-orbit 24s linear infinite;
}}
.jaaynaa-brand {{position:relative;z-index:1;font-family:'Space Grotesk',sans-serif;font-size:1.55rem;font-weight:700;letter-spacing:.06em;}}
.jaaynaa-tagline {{position:relative;z-index:1;font-size:.9rem;color:#b7d9e4;margin-top:5px;}}
.jaaynaa-live {{position:relative;z-index:1;display:inline-flex;align-items:center;gap:9px;padding:9px 13px;border:1px solid rgba(190,242,100,.32);background:rgba(4,20,25,.4);border-radius:999px;font-size:.75rem;font-weight:800;letter-spacing:.08em;white-space:nowrap;}}
.jaaynaa-dot {{width:8px;height:8px;border-radius:50%;background:#bef264;box-shadow:0 0 13px #bef264;animation:ja-pulse 1.8s infinite;}}
.ja-section-kicker {{color:var(--ja-muted);font-size:.75rem;font-weight:800;letter-spacing:.16em;text-transform:uppercase;margin-bottom:.25rem;}}
@keyframes ja-enter {{from{{opacity:0;transform:translateY(10px)}}to{{opacity:1;transform:translateY(0)}}}}
@keyframes ja-pulse {{0%,100%{{opacity:1}}50%{{opacity:.45}}}}
@keyframes ja-orbit {{from{{transform:rotate(0)}}to{{transform:rotate(360deg)}}}}
@media(max-width:850px) {{
 .block-container{{padding-left:1rem;padding-right:1rem;}}
 .jaaynaa-topbar{{align-items:flex-start;flex-direction:column;padding:20px;}}
 .ja-nav-shell div[role="radiogroup"]>label{{padding:8px 9px!important;font-size:.78rem;}}
 div[data-testid="stMetric"]{{padding:14px;border-radius:14px;}}
}}
@media(prefers-reduced-motion:reduce){{*,*::before,*::after{{animation-duration:.01ms!important;transition-duration:.01ms!important;}}}}
</style>
""", unsafe_allow_html=True)

with st.sidebar:
    st.markdown("# 🇸🇳 JAAYNAA")
    st.caption("Gestion commerciale professionnelle")
    st.session_state.lang = st.selectbox(
        tr("Langue"),
        ["Français", "Wolof"],
        index=["Français", "Wolof"].index(st.session_state.lang),
    )
    st.divider()
    st.caption("🛡️ Données conservées sur cet ordinateur")
    st.caption(f"Base locale : {DB_PATH.name}")

st.markdown("""
<div class="jaaynaa-topbar">
  <div>
    <div class="jaaynaa-brand">◈ JAAYNAA <span style="color:#bef264">/ PRO</span></div>
    <div class="jaaynaa-tagline">CENTRE DE COMMANDE COMMERCIAL · SÉNÉGAL</div>
    <div style="position:relative;z-index:1;color:#e0f2fe;font-size:1.02rem;margin-top:12px;font-weight:600">Pilotez. Analysez. Développez.</div>
  </div>
  <div class="jaaynaa-live"><span class="jaaynaa-dot"></span> SYSTÈME OPÉRATIONNEL</div>
</div>
""", unsafe_allow_html=True)

pages = ["Dashboard", "Produits & stocks", "Ventes", "Achats", "Clients",
         "Fournisseurs", "Dépenses", "Rapports", "Paramètres"]
translated_pages = [tr(item) for item in pages]
if "active_page" not in st.session_state:
    st.session_state.active_page = tr("Dashboard")
if st.session_state.active_page not in translated_pages:
    st.session_state.active_page = tr("Dashboard")

st.markdown('<div class="ja-nav-shell">', unsafe_allow_html=True)
page = st.radio(
    "Menu principal",
    translated_pages,
    index=translated_pages.index(st.session_state.active_page),
    horizontal=True,
    label_visibility="collapsed",
    key="jaaynaa_top_navigation",
)
st.session_state.active_page = page
st.markdown('</div>', unsafe_allow_html=True)

# DASHBOARD
if page == tr("Dashboard"):
    st.markdown('<div class="ja-section-kicker">Vue stratégique · Temps réel</div>', unsafe_allow_html=True)
    st.title("Centre de pilotage")
    st.caption("Les indicateurs essentiels de votre activité, réunis dans un espace de contrôle.")
    today = date.today().isoformat(); month = date.today().strftime('%Y-%m')
    sales_today = scalar("SELECT COALESCE(SUM(total),0) FROM sales WHERE date(sold_at)=date(?)", (today,))
    cash_today = scalar("SELECT COALESCE(SUM(paid),0) FROM sales WHERE date(sold_at)=date(?)", (today,))
    sales_month = scalar("SELECT COALESCE(SUM(total),0) FROM sales WHERE substr(sold_at,1,7)=?", (month,))
    due = scalar("SELECT COALESCE(SUM(total-paid),0) FROM sales")
    stock_value = scalar("SELECT COALESCE(SUM(quantity*purchase_price),0) FROM products WHERE active=1")
    expense_month = scalar("SELECT COALESCE(SUM(amount),0) FROM expenses WHERE substr(spent_at,1,7)=?", (month,))
    c1,c2,c3,c4 = st.columns(4)
    c1.metric("Ventes aujourd'hui", money(sales_today)); c2.metric("Encaissements aujourd'hui", money(cash_today)); c3.metric("Chiffre d'affaires du mois", money(sales_month)); c4.metric("Créances clients", money(due), help="Montants restant à encaisser sur les ventes enregistrées.")
    c5,c6,c7 = st.columns(3); c5.metric("Valeur du stock (coût)", money(stock_value)); c6.metric("Dépenses du mois", money(expense_month)); c7.metric("Bénéfice estimé du mois", money(scalar("SELECT COALESCE(SUM((si.unit_price-si.cost_price)*si.quantity),0) FROM sale_items si JOIN sales s ON s.id=si.sale_id WHERE substr(s.sold_at,1,7)=?", (month,))-expense_month))
    st.divider(); left,right=st.columns(2)
    with left:
        st.markdown("#### Évolution des ventes — 14 derniers jours")
        trend=query_df("SELECT date(sold_at) jour, SUM(total) ventes FROM sales WHERE date(sold_at)>=date('now','-13 day') GROUP BY date(sold_at) ORDER BY jour")
        if not trend.empty: st.line_chart(trend.set_index("jour"))
        else: st.info("Les ventes apparaîtront ici après vos premières opérations.")
    with right:
        st.markdown("#### Produits les plus vendus")
        top=query_df("SELECT product_name Produit, SUM(quantity) Quantité FROM sale_items GROUP BY product_id,product_name ORDER BY SUM(quantity) DESC LIMIT 7")
        if not top.empty: st.bar_chart(top.set_index("Produit"))
        else: st.info("Pas encore de ventes enregistrées.")
    low=query_df("SELECT name Produit, quantity Stock, min_stock Seuil, unit Unité FROM products WHERE active=1 AND quantity<=min_stock ORDER BY quantity")
    if not low.empty: st.warning("Alertes de stock bas"); st.dataframe(low, use_container_width=True, hide_index=True)
    recent=query_df("SELECT sale_no Référence, sold_at Date, sale_type Type, total Total, paid Payé, (total-paid) Reste FROM sales ORDER BY id DESC LIMIT 8")
    st.markdown("#### Dernières ventes")
    if not recent.empty: st.dataframe(recent, use_container_width=True, hide_index=True)

# PRODUCTS
elif page == tr("Produits & stocks"):
    st.title("📦 Produits & stocks")
    with st.expander("➕ Ajouter un produit", expanded=False):
        with st.form("add_product", clear_on_submit=True):
            a,b,c=st.columns(3); name=a.text_input("Nom *"); ref=b.text_input("Référence / SKU"); cat=c.text_input("Catégorie")
            d,e,f=st.columns(3); buy=d.number_input("Prix d'achat (FCFA)", min_value=0.0, step=50.0); retail=e.number_input("Prix détail (FCFA)", min_value=0.0, step=50.0); wholesale=f.number_input("Prix gros (FCFA)", min_value=0.0, step=50.0)
            g,h,i=st.columns(3); qty=g.number_input("Stock initial", min_value=0.0, step=1.0); minq=h.number_input("Seuil d'alerte", min_value=0.0, step=1.0); unit=i.selectbox("Unité", ["pièce","kg","litre","sac","carton","paquet","mètre","autre"])
            if st.form_submit_button("Enregistrer le produit", type="primary"):
                if not name.strip(): st.error("Le nom du produit est obligatoire.")
                else:
                    try:
                        with connect() as con:
                            cur=con.execute("INSERT INTO products(name,reference,category,purchase_price,retail_price,wholesale_price,quantity,min_stock,unit) VALUES(?,?,?,?,?,?,?,?,?)",(name.strip(),ref.strip() or None,cat.strip(),buy,retail,wholesale,qty,minq,unit))
                            if qty: con.execute("INSERT INTO stock_movements(product_id,moved_at,movement_type,quantity,note) VALUES(?,?,?,?,?)",(cur.lastrowid,datetime.now().isoformat(timespec='seconds'),"Stock initial",qty,"Création produit"))
                        st.success("Produit enregistré."); st.rerun()
                    except sqlite3.IntegrityError: st.error("Cette référence existe déjà. Choisissez-en une autre.")
    search=st.text_input("🔎 Rechercher un produit")
    df=query_df("SELECT id ID,name Nom,reference Référence,category Catégorie,purchase_price 'Prix achat',retail_price 'Prix détail',wholesale_price 'Prix gros',quantity Stock,min_stock Seuil,unit Unité FROM products WHERE active=1 AND (name LIKE ? OR COALESCE(reference,'') LIKE ? OR category LIKE ?) ORDER BY name",(f"%{search}%",)*3)
    st.dataframe(df, use_container_width=True, hide_index=True)
    if not df.empty:
        st.download_button(
            "⬇️ Exporter les produits en CSV",
            df.to_csv(index=False).encode("utf-8-sig"),
            file_name="jaaynaa_produits.csv",
            mime="text/csv",
            key="export_products_csv",
        )
    with st.expander("✏️ Modifier un produit / ajuster le stock"):
        pmap=options("products")
        if pmap:
            chosen=st.selectbox("Produit",list(pmap.keys())); pid=pmap[chosen]
            p=query_df("SELECT * FROM products WHERE id=?",(pid,)).iloc[0]
            with st.form("edit_product"):
                a,b,c=st.columns(3); ename=a.text_input("Nom",p.name); ecat=b.text_input("Catégorie",p.category or ""); eunit=c.selectbox("Unité",["pièce","kg","litre","sac","carton","paquet","mètre","autre"],index=["pièce","kg","litre","sac","carton","paquet","mètre","autre"].index(p.unit if p.unit in ["pièce","kg","litre","sac","carton","paquet","mètre","autre"] else "autre"))
                d,e,f=st.columns(3); ebuy=d.number_input("Prix d'achat",min_value=0.0,value=float(p.purchase_price),step=50.0); eretail=e.number_input("Prix détail",min_value=0.0,value=float(p.retail_price),step=50.0); ewholesale=f.number_input("Prix gros",min_value=0.0,value=float(p.wholesale_price),step=50.0)
                g,h=st.columns(2); emin=g.number_input("Seuil stock",min_value=0.0,value=float(p.min_stock),step=1.0); newqty=h.number_input("Quantité réelle à définir",min_value=0.0,value=float(p.quantity),step=1.0)
                if st.form_submit_button("Sauvegarder les modifications"):
                    delta=newqty-float(p.quantity)
                    with connect() as con:
                        con.execute("UPDATE products SET name=?,category=?,unit=?,purchase_price=?,retail_price=?,wholesale_price=?,min_stock=?,quantity=? WHERE id=?",(ename,ecat,eunit,ebuy,eretail,ewholesale,emin,newqty,pid))
                        if delta: con.execute("INSERT INTO stock_movements(product_id,moved_at,movement_type,quantity,note) VALUES(?,?,?,?,?)",(pid,datetime.now().isoformat(timespec='seconds'),"Ajustement",delta,"Ajustement manuel"))
                    st.success("Produit mis à jour."); st.rerun()
    with st.expander("📜 Historique des mouvements de stock"):
        movements=query_df("SELECT sm.moved_at Date,p.name Produit,sm.movement_type Mouvement,sm.quantity Quantité,sm.note Note FROM stock_movements sm JOIN products p ON p.id=sm.product_id ORDER BY sm.id DESC LIMIT 300")
        st.dataframe(movements,use_container_width=True,hide_index=True)

# SALES
elif page == tr("Ventes"):
    st.title("🛒 Ventes")
    st.caption("Une vente validée met à jour le stock et enregistre le paiement dans une transaction SQLite.")
    pmap=options("products"); cmap=options("clients")
    if not pmap: st.info("Ajoutez d'abord vos produits dans Produits & stocks.")
    else:
        with st.form("new_sale"):
            a,b,c=st.columns(3); sale_type=a.selectbox("Type de vente",["Détail","Gros"]); client_label=b.selectbox("Client (facultatif)",["Client comptant"]+list(cmap.keys())); sold_date=c.date_input("Date de vente",value=date.today())
            product_labels=list(pmap.keys()); selected=st.multiselect("Produits vendus",product_labels)
            items=[]; subtotal=0.0
            for label in selected:
                pid=pmap[label]; pr=query_df("SELECT * FROM products WHERE id=?",(pid,)).iloc[0]
                x,y=st.columns([2,1]); q=x.number_input(f"Quantité — {pr['name']}",min_value=0.01,value=1.0,step=1.0,key=f"sq{pid}")
                default_price=float(pr.wholesale_price if sale_type=="Gros" and pr.wholesale_price>0 else pr.retail_price)
                price=y.number_input(f"Prix unitaire — {pr['name']}",min_value=0.0,value=default_price,step=50.0,key=f"sp{pid}")
                items.append((pid,pr['name'],q,price,float(pr.purchase_price),float(pr['quantity'])))
                subtotal+=q*price
            d,e,f=st.columns(3); discount=d.number_input("Remise globale (FCFA)",min_value=0.0,max_value=float(subtotal),value=0.0,step=100.0); paid=e.number_input("Montant payé (FCFA)",min_value=0.0,value=float(max(0,subtotal-discount)),step=100.0); method=f.selectbox("Moyen de paiement",["Espèces","Wave","Orange Money","Free Money","Virement","Carte","Crédit / à payer plus tard"])
            note=st.text_input("Note (facultatif)")
            submit=st.form_submit_button("✅ Valider la vente",type="primary")
        if submit:
            total=max(0,subtotal-discount)
            if not items: st.error("Sélectionnez au moins un produit.")
            elif paid>total: st.error("Le montant payé ne peut pas dépasser le total de la vente.")
            elif any(q>stock for _,_,q,_,_,stock in items): st.error("Stock insuffisant pour au moins un produit.")
            else:
                try:
                    with connect() as con:
                        no=next_no("VTE","sales","sale_no")
                        cur=con.execute("INSERT INTO sales(sale_no,sold_at,sale_type,client_id,subtotal,discount,total,paid,payment_method,note) VALUES(?,?,?,?,?,?,?,?,?,?)",(no,datetime.combine(sold_date,datetime.now().time()).isoformat(timespec='seconds'),sale_type,cmap.get(client_label),subtotal,discount,total,paid,method,note))
                        sid=cur.lastrowid
                        for pid,pname,q,price,cost,stock in items:
                            con.execute("INSERT INTO sale_items(sale_id,product_id,product_name,quantity,unit_price,line_total,cost_price) VALUES(?,?,?,?,?,?,?)",(sid,pid,pname,q,price,q*price,cost))
                            con.execute("UPDATE products SET quantity=quantity-? WHERE id=?",(q,pid))
                            con.execute("INSERT INTO stock_movements(product_id,moved_at,movement_type,quantity,note) VALUES(?,?,?,?,?)",(pid,datetime.now().isoformat(timespec='seconds'),"Vente",-q,no))
                        if paid: con.execute("INSERT INTO payments(direction,reference_type,reference_id,paid_at,amount,method,note) VALUES(?,?,?,?,?,?,?)",("Entrée","vente",sid,datetime.now().isoformat(timespec='seconds'),paid,method,no))
                    st.session_state["last_sale_id"]=sid; st.success(f"Vente {no} enregistrée. Total : {money(total)} | Reste : {money(total-paid)}")
                except Exception as ex: st.error(f"La vente n'a pas pu être enregistrée : {ex}")
    st.divider(); st.markdown("#### Historique des ventes")
    sales=query_df("SELECT s.id ID,s.sale_no Référence,s.sold_at Date,s.sale_type Type,COALESCE(c.name,'Client comptant') Client,s.total Total,s.paid Payé,(s.total-s.paid) Reste,s.payment_method Paiement FROM sales s LEFT JOIN clients c ON c.id=s.client_id ORDER BY s.id DESC LIMIT 500")
    st.dataframe(sales.drop(columns=["ID"]) if not sales.empty else sales,use_container_width=True,hide_index=True)
    if not sales.empty:
        sale_ids={f"{r['Référence']} — {money(r['Total'])}":int(r['ID']) for _,r in sales.iterrows()}; chosen=st.selectbox("Document de vente",list(sale_ids.keys())); sid=sale_ids[chosen]
        items_df=query_df("SELECT product_name Produit,quantity Quantité,unit_price 'Prix unitaire',line_total Total FROM sale_items WHERE sale_id=?",(sid,))
        st.dataframe(items_df,use_container_width=True,hide_index=True)
        if st.button("Générer le reçu PDF"):
            s=query_df("SELECT * FROM sales WHERE id=?",(sid,)).iloc[0]
            pdf=make_pdf(f"REÇU {s.sale_no}",items_df.to_dict('records'),{"Sous-total":money(s.subtotal),"Remise":money(s.discount),"Total":money(s.total),"Payé":money(s.paid),"Solde":money(s.total-s.paid),"Paiement":s.payment_method})
            if pdf: st.download_button("Télécharger le reçu PDF",pdf,file_name=f"recu_{s.sale_no}.pdf",mime="application/pdf")

# PURCHASES
elif page == tr("Achats"):
    st.title("🚚 Achats & réapprovisionnement")
    pmap=options("products"); smap=options("suppliers")
    if not pmap: st.info("Ajoutez des produits avant d'enregistrer un achat.")
    else:
        with st.form("new_purchase"):
            a,b=st.columns(2); supplier_label=a.selectbox("Fournisseur",["Non renseigné"]+list(smap.keys())); pdate=b.date_input("Date d'achat",value=date.today())
            selected=st.multiselect("Produits reçus",list(pmap.keys()),key="purchase_products"); items=[]; total=0
            for label in selected:
                pid=pmap[label]; pr=query_df("SELECT * FROM products WHERE id=?",(pid,)).iloc[0]
                x,y,z=st.columns(3); q=x.number_input(f"Quantité reçue — {pr['name']}",min_value=0.01,value=1.0,step=1.0,key=f"pq{pid}"); cost=y.number_input(f"Coût unitaire — {pr['name']}",min_value=0.0,value=float(pr.purchase_price),step=50.0,key=f"pc{pid}"); line=q*cost; z.metric("Sous-total",money(line)); items.append((pid,pr['name'],q,cost)); total+=line
            paid=st.number_input("Montant payé au fournisseur",min_value=0.0,max_value=float(total),value=float(total),step=100.0); note=st.text_input("Référence facture / note")
            submit=st.form_submit_button("Enregistrer l'achat et mettre à jour le stock",type="primary")
        if submit:
            if not items: st.error("Sélectionnez au moins un produit.")
            else:
                with connect() as con:
                    no=next_no("ACH","purchases","purchase_no")
                    cur=con.execute("INSERT INTO purchases(purchase_no,purchased_at,supplier_id,total,paid,note) VALUES(?,?,?,?,?,?)",(no,datetime.combine(pdate,datetime.now().time()).isoformat(timespec='seconds'),smap.get(supplier_label),total,paid,note))
                    purchase_id=cur.lastrowid
                    for pid,pname,q,cost in items:
                        con.execute("INSERT INTO purchase_items(purchase_id,product_id,product_name,quantity,unit_cost,line_total) VALUES(?,?,?,?,?,?)",(purchase_id,pid,pname,q,cost,q*cost))
                        con.execute("UPDATE products SET quantity=quantity+?, purchase_price=? WHERE id=?",(q,cost,pid))
                        con.execute("INSERT INTO stock_movements(product_id,moved_at,movement_type,quantity,note) VALUES(?,?,?,?,?)",(pid,datetime.now().isoformat(timespec='seconds'),"Réception achat",q,no))
                    if paid: con.execute("INSERT INTO payments(direction,reference_type,reference_id,paid_at,amount,method,note) VALUES(?,?,?,?,?,?,?)",("Sortie","achat",purchase_id,datetime.now().isoformat(timespec='seconds'),paid,"Espèces",no))
                st.success(f"Achat {no} enregistré. Le stock a été augmenté.")
    st.markdown("#### Historique des achats")
    df=query_df("SELECT pu.purchase_no Référence,pu.purchased_at Date,COALESCE(s.name,'—') Fournisseur,pu.total Total,pu.paid Payé,(pu.total-pu.paid) Reste,pu.note Note FROM purchases pu LEFT JOIN suppliers s ON s.id=pu.supplier_id ORDER BY pu.id DESC")
    st.dataframe(df,use_container_width=True,hide_index=True)

# CLIENTS / SUPPLIERS
elif page in [tr("Clients"),tr("Fournisseurs")]:
    is_client = page == tr("Clients"); table="clients" if is_client else "suppliers"; label="Client" if is_client else "Fournisseur"
    st.title("👥 " + ("Clients" if is_client else "Fournisseurs"))
    with st.form("add_contact",clear_on_submit=True):
        a,b=st.columns(2); name=a.text_input("Nom / raison sociale *"); phone=b.text_input("Téléphone"); c,d=st.columns(2); email=c.text_input("E-mail"); address=d.text_input("Adresse")
        if st.form_submit_button(f"Ajouter {label.lower()}",type="primary"):
            if not name.strip(): st.error("Le nom est obligatoire.")
            else:
                with connect() as con: con.execute(f"INSERT INTO {table}(name,phone,email,address) VALUES(?,?,?,?)",(name.strip(),phone,email,address))
                st.success(f"{label} ajouté."); st.rerun()
    df = query_df(f'SELECT id AS "ID", name AS "Nom", phone AS "Téléphone", email AS "E-mail", address AS "Adresse", created_at AS "Créé le" FROM {table} ORDER BY name')
    st.dataframe(df,use_container_width=True,hide_index=True)
    if is_client:
        st.markdown("#### Soldes clients")
        balances=query_df("SELECT c.name Client,COALESCE(SUM(s.total),0) Achats,COALESCE(SUM(s.paid),0) Payé,COALESCE(SUM(s.total-s.paid),0) 'Reste dû' FROM clients c LEFT JOIN sales s ON s.client_id=c.id GROUP BY c.id ORDER BY c.name")
        st.dataframe(balances,use_container_width=True,hide_index=True)
    else:
        st.markdown("#### Soldes fournisseurs (achats enregistrés)")
        balances=query_df("SELECT sp.name Fournisseur,COALESCE(SUM(p.total),0) Achats,COALESCE(SUM(p.paid),0) Payé,COALESCE(SUM(p.total-p.paid),0) 'Reste dû' FROM suppliers sp LEFT JOIN purchases p ON p.supplier_id=sp.id GROUP BY sp.id ORDER BY sp.name")
        st.dataframe(balances,use_container_width=True,hide_index=True)


# PAYMENTS / SETTLEMENTS
elif page == tr("Règlements"):
    st.title("💳 Règlements clients & fournisseurs")
    st.caption("Enregistrez les paiements partiels ou complets et gardez une trace de chaque règlement.")

    pay_tab_sales, pay_tab_purchases, pay_tab_history = st.tabs(
        ["💰 Encaisser un client", "🚚 Régler un fournisseur", "📚 Historique des règlements"]
    )

    with pay_tab_sales:
        outstanding_sales = query_df("""
            SELECT s.id, s.sale_no AS Référence, COALESCE(c.name, 'Client comptant') AS Tiers,
                   s.sold_at AS Date, s.total AS Total, s.paid AS Déjà_payé,
                   (s.total-s.paid) AS Reste
            FROM sales s LEFT JOIN clients c ON c.id=s.client_id
            WHERE (s.total-s.paid) > 0.0001
            ORDER BY s.sold_at DESC
        """)
        if outstanding_sales.empty:
            st.success("Aucune créance client en attente.")
        else:
            sale_map = {
                f"{r['Référence']} · {r['Tiers']} · reste {money(r['Reste'])}": r
                for _, r in outstanding_sales.iterrows()
            }
            selected_sale = st.selectbox("Vente à régler", list(sale_map.keys()), key="settle_sale_choice")
            sale_row = sale_map[selected_sale]
            st.info(
                f"Total : {money(sale_row['Total'])}  ·  Déjà payé : {money(sale_row['Déjà_payé'])}  ·  "
                f"Solde : {money(sale_row['Reste'])}"
            )
            with st.form("settle_customer_form"):
                a, b, c = st.columns(3)
                amount = a.number_input(
                    "Montant reçu (FCFA)", min_value=1.0,
                    max_value=float(sale_row["Reste"]),
                    value=float(sale_row["Reste"]), step=500.0
                )
                method = b.selectbox(
                    "Moyen de paiement",
                    ["Espèces", "Wave", "Orange Money", "Free Money", "Virement", "Carte"],
                    key="customer_settlement_method"
                )
                paid_date = c.date_input("Date du règlement", value=date.today(), key="customer_settlement_date")
                note = st.text_input("Note (facultatif)", key="customer_settlement_note")
                submitted = st.form_submit_button("✅ Enregistrer l'encaissement", type="primary")
            if submitted:
                with connect() as con:
                    con.execute(
                        "UPDATE sales SET paid=MIN(total, paid+?) WHERE id=?",
                        (float(amount), int(sale_row["id"]))
                    )
                    con.execute(
                        """INSERT INTO payments(direction,reference_type,reference_id,paid_at,amount,method,note)
                           VALUES(?,?,?,?,?,?,?)""",
                        ("Entrée", "vente", int(sale_row["id"]),
                         datetime.combine(paid_date, datetime.now().time()).isoformat(timespec="seconds"),
                         float(amount), method, note or str(sale_row["Référence"]))
                    )
                st.success(f"Encaissement de {money(amount)} enregistré.")
                st.rerun()

    with pay_tab_purchases:
        outstanding_purchases = query_df("""
            SELECT p.id, p.purchase_no AS Référence, COALESCE(s.name, 'Fournisseur non renseigné') AS Tiers,
                   p.purchased_at AS Date, p.total AS Total, p.paid AS Déjà_payé,
                   (p.total-p.paid) AS Reste
            FROM purchases p LEFT JOIN suppliers s ON s.id=p.supplier_id
            WHERE (p.total-p.paid) > 0.0001
            ORDER BY p.purchased_at DESC
        """)
        if outstanding_purchases.empty:
            st.success("Aucune dette fournisseur en attente.")
        else:
            purchase_map = {
                f"{r['Référence']} · {r['Tiers']} · reste {money(r['Reste'])}": r
                for _, r in outstanding_purchases.iterrows()
            }
            selected_purchase = st.selectbox(
                "Achat à régler", list(purchase_map.keys()), key="settle_purchase_choice"
            )
            purchase_row = purchase_map[selected_purchase]
            st.info(
                f"Total : {money(purchase_row['Total'])}  ·  Déjà payé : {money(purchase_row['Déjà_payé'])}  ·  "
                f"Solde : {money(purchase_row['Reste'])}"
            )
            with st.form("settle_supplier_form"):
                a, b, c = st.columns(3)
                amount_out = a.number_input(
                    "Montant payé (FCFA)", min_value=1.0,
                    max_value=float(purchase_row["Reste"]),
                    value=float(purchase_row["Reste"]), step=500.0
                )
                method_out = b.selectbox(
                    "Moyen de paiement",
                    ["Espèces", "Wave", "Orange Money", "Free Money", "Virement", "Carte"],
                    key="supplier_settlement_method"
                )
                paid_date_out = c.date_input(
                    "Date du règlement", value=date.today(), key="supplier_settlement_date"
                )
                note_out = st.text_input("Note (facultatif)", key="supplier_settlement_note")
                submitted_out = st.form_submit_button("✅ Enregistrer le paiement", type="primary")
            if submitted_out:
                with connect() as con:
                    con.execute(
                        "UPDATE purchases SET paid=MIN(total, paid+?) WHERE id=?",
                        (float(amount_out), int(purchase_row["id"]))
                    )
                    con.execute(
                        """INSERT INTO payments(direction,reference_type,reference_id,paid_at,amount,method,note)
                           VALUES(?,?,?,?,?,?,?)""",
                        ("Sortie", "achat", int(purchase_row["id"]),
                         datetime.combine(paid_date_out, datetime.now().time()).isoformat(timespec="seconds"),
                         float(amount_out), method_out, note_out or str(purchase_row["Référence"]))
                    )
                st.success(f"Paiement de {money(amount_out)} enregistré.")
                st.rerun()

    with pay_tab_history:
        history = query_df("""
            SELECT paid_at AS Date, direction AS Sens, reference_type AS Type,
                   reference_id AS 'ID référence', amount AS Montant, method AS 'Moyen de paiement',
                   note AS Note
            FROM payments ORDER BY id DESC LIMIT 500
        """)
        if history.empty:
            st.info("Aucun règlement enregistré pour le moment.")
        else:
            st.dataframe(history, use_container_width=True, hide_index=True)
            st.download_button(
                "⬇️ Exporter l'historique CSV",
                history.to_csv(index=False).encode("utf-8-sig"),
                file_name="jaaynaa_reglements.csv",
                mime="text/csv",
                key="export_payments_csv",
            )

# EXPENSES
elif page == tr("Dépenses"):
    st.title("💸 Dépenses & caisse")
    with st.form("expense_form",clear_on_submit=True):
        a,b,c=st.columns(3); spent=a.date_input("Date",value=date.today()); category=b.selectbox("Catégorie",["Transport","Loyer","Électricité / eau","Salaire","Téléphone / Internet","Entretien","Taxes","Autre"]); amount=c.number_input("Montant (FCFA)",min_value=1.0,step=100.0)
        desc=st.text_input("Description"); method=st.selectbox("Payé par",["Espèces","Wave","Orange Money","Free Money","Virement","Carte"])
        if st.form_submit_button("Enregistrer la dépense",type="primary"):
            with connect() as con:
                con.execute("INSERT INTO expenses(spent_at,category,description,amount,payment_method) VALUES(?,?,?,?,?)",(spent.isoformat(),category,desc,amount,method))
                con.execute("INSERT INTO payments(direction,reference_type,reference_id,paid_at,amount,method,note) VALUES(?,?,?,?,?,?,?)",("Sortie","dépense",0,datetime.now().isoformat(timespec='seconds'),amount,method,desc or category))
            st.success("Dépense enregistrée."); st.rerun()
    df=query_df("SELECT spent_at Date,category Catégorie,description Description,amount Montant,payment_method Paiement FROM expenses ORDER BY id DESC")
    st.dataframe(df,use_container_width=True,hide_index=True)
    if not df.empty: st.metric("Total des dépenses affichées",money(df["Montant"].sum()))

# REPORTS
elif page == tr("Rapports"):
    st.title("📈 Rapports & exportations")
    a,b=st.columns(2); start=a.date_input("Du",value=date.today().replace(day=1)); end=b.date_input("Au",value=date.today())
    if start>end: st.error("La date de début doit précéder la date de fin.")
    else:
        params=(start.isoformat(),(end+timedelta(days=1)).isoformat())
        sales=query_df("SELECT sale_no Référence,sold_at Date,sale_type Type,total Total,paid Payé,(total-paid) Solde FROM sales WHERE date(sold_at)>=date(?) AND date(sold_at)<date(?) ORDER BY sold_at",params)
        expenses=query_df("SELECT spent_at Date,category Catégorie,description Description,amount Montant,payment_method Paiement FROM expenses WHERE date(spent_at)>=date(?) AND date(spent_at)<date(?) ORDER BY spent_at",params)
        revenue=float(sales["Total"].sum()) if not sales.empty else 0; paid_total=float(sales["Payé"].sum()) if not sales.empty else 0; exp_total=float(expenses["Montant"].sum()) if not expenses.empty else 0
        c1,c2,c3,c4=st.columns(4); c1.metric("Ventes",money(revenue)); c2.metric("Encaissé",money(paid_total)); c3.metric("Dépenses",money(exp_total)); c4.metric("Solde estimé après dépenses",money(paid_total-exp_total))
        t1,t2,t3=st.tabs(["Ventes","Dépenses","Stock"])
        with t1:
            st.dataframe(sales,use_container_width=True,hide_index=True)
            if not sales.empty: st.download_button("Télécharger ventes CSV",sales.to_csv(index=False).encode('utf-8-sig'),"ventes.csv","text/csv")
        with t2:
            st.dataframe(expenses,use_container_width=True,hide_index=True)
            if not expenses.empty: st.download_button("Télécharger dépenses CSV",expenses.to_csv(index=False).encode('utf-8-sig'),"depenses.csv","text/csv")
        with t3:
            stock=query_df("SELECT name Produit,reference Référence,category Catégorie,quantity Stock,unit Unité,purchase_price 'Prix achat',retail_price 'Prix détail',quantity*purchase_price 'Valeur stock' FROM products WHERE active=1 ORDER BY name")
            st.dataframe(stock,use_container_width=True,hide_index=True)
            if not stock.empty: st.download_button("Télécharger stock CSV",stock.to_csv(index=False).encode('utf-8-sig'),"stock.csv","text/csv")
        if st.button("Générer un rapport PDF"):
            rows=sales.head(100).to_dict('records')
            pdf=make_pdf(f"Rapport des ventes du {start} au {end}",rows,{"Chiffre d'affaires":money(revenue),"Encaissements":money(paid_total),"Dépenses":money(exp_total)})
            if pdf: st.download_button("Télécharger rapport PDF",pdf,"rapport_jaaynaa.pdf","application/pdf")

# SETTINGS
elif page == tr("Paramètres"):
    st.title("⚙️ Paramètres & sauvegarde")
    st.markdown("#### Identité du commerce")
    with st.form("settings_form"):
        name=st.text_input("Nom du commerce",setting("business_name","JAAYNAA")); phone=st.text_input("Téléphone",setting("business_phone")); address=st.text_input("Adresse",setting("business_address","Sénégal")); email=st.text_input("E-mail",setting("business_email")); currency=st.selectbox("Devise",["FCFA","EUR","USD"],index=["FCFA","EUR","USD"].index(setting("currency","FCFA") if setting("currency","FCFA") in ["FCFA","EUR","USD"] else "FCFA")); theme=st.selectbox("Thème",["Clair","Sombre"],index=["Clair","Sombre"].index(st.session_state.theme))
        if st.form_submit_button("Enregistrer les paramètres",type="primary"):
            for k,v in [("business_name",name),("business_phone",phone),("business_address",address),("business_email",email),("currency",currency),("theme",theme),("language",st.session_state.lang)]: set_setting(k,v)
            st.session_state.theme=theme; st.success("Paramètres enregistrés. Rechargez la page pour appliquer complètement le thème."); st.rerun()
    st.divider(); st.markdown("#### Sauvegarde de la base SQLite")
    st.write(f"Base active : `{DB_PATH}`")
    if st.button("Créer une sauvegarde maintenant"):
        backup_dir=APP_DIR/"backups"; backup_dir.mkdir(exist_ok=True); backup_path=backup_dir/f"jaaynaa_backup_{datetime.now().strftime('%Y%m%d_%H%M%S')}.db"
        with connect() as src, sqlite3.connect(backup_path) as dst: src.backup(dst)
        st.success(f"Sauvegarde créée : {backup_path.name}")
        st.download_button("Télécharger la sauvegarde",backup_path.read_bytes(),backup_path.name,"application/octet-stream")
    uploaded=st.file_uploader("Restaurer une sauvegarde (.db)",type=["db","sqlite","sqlite3"])
    if uploaded and st.button("Restaurer cette sauvegarde",type="secondary"):
        try:
            temp=DATA_DIR/"restore_check.db"; temp.write_bytes(uploaded.getvalue())
            with sqlite3.connect(temp) as test: test.execute("PRAGMA integrity_check"); result=test.execute("PRAGMA integrity_check").fetchone()[0]
            if result != "ok": raise ValueError("La base n'a pas passé le contrôle d'intégrité.")
            shutil.copy2(DB_PATH, DATA_DIR/f"before_restore_{datetime.now().strftime('%Y%m%d_%H%M%S')}.db") if DB_PATH.exists() else None
            shutil.copy2(temp,DB_PATH); temp.unlink(missing_ok=True); st.success("Sauvegarde restaurée. Rechargez l'application.")
        except Exception as ex: st.error(f"Restauration impossible : {ex}")
    st.divider(); st.warning("Conseil : faites régulièrement une copie du dossier data et du dossier backups sur un autre support.")

st.sidebar.divider()
st.sidebar.caption("JAAYNAA PRO • Version locale 2.0")
st.sidebar.caption("Vos données sont conservées sur cet ordinateur.")



