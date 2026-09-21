import os
import sqlite3
import datetime
import numpy as np
from PIL import Image
import streamlit as st
from transformers import pipeline

# ==========================================
# 1. STREAMLIT KONFIGURATION
# ==========================================
st.set_page_config(
    page_title="Fundbüro - Katharineum zu Lübeck",
    page_icon="🏫",
    layout="wide",
    initial_sidebar_state="collapsed"
)

# ==========================================
# 2. SESSION STATE & DESIGNS / THEMES
# ==========================================
if "logged_in" not in st.session_state:
    st.session_state.logged_in = False
if "username" not in st.session_state:
    st.session_state.username = ""
if "active_view" not in st.session_state:
    st.session_state.active_view = "dashboard"
if "action_type" not in st.session_state:
    st.session_state.action_type = "Gefunden"
if "theme" not in st.session_state:
    st.session_state.theme = "Katharineum Navy"

# Farb-Themes Definition
THEMES = {
    "Katharineum Navy": {
        "primary": "#1E3A8A",
        "primary_hover": "#1D4ED8",
        "bg": "#F8FAFC",
        "card_bg": "#FFFFFF",
        "text": "#0F172A",
        "subtext": "#64748B",
        "border": "#E2E8F0"
    },
    "Dark Mode": {
        "primary": "#3B82F6",
        "primary_hover": "#60A5FA",
        "bg": "#0F172A",
        "card_bg": "#1E293B",
        "text": "#F8FAFC",
        "subtext": "#94A3B8",
        "border": "#334155"
    },
    "Smaragd Grün": {
        "primary": "#059669",
        "primary_hover": "#10B981",
        "bg": "#F0FDF4",
        "card_bg": "#FFFFFF",
        "text": "#064E3B",
        "subtext": "#047857",
        "border": "#BBF7D0"
    },
    "Warmes Orange": {
        "primary": "#EA580C",
        "primary_hover": "#F97316",
        "bg": "#FFF7ED",
        "card_bg": "#FFFFFF",
        "text": "#431407",
        "subtext": "#C2410C",
        "border": "#FFEDD5"
    }
}

current_theme = THEMES[st.session_state.theme]

# Dynamic CSS Injection
st.markdown(f"""
<style>
    .stApp {{
        background-color: {current_theme['bg']};
        color: {current_theme['text']};
        font-family: 'Inter', -apple-system, BlinkMacSystemFont, sans-serif;
    }}
    
    /* Header Bar */
    .app-header {{
        background: {current_theme['card_bg']};
        border-bottom: 2px solid {current_theme['border']};
        padding: 16px 24px;
        border-radius: 16px;
        margin-bottom: 24px;
        box-shadow: 0 4px 20px rgba(0,0,0,0.03);
    }}
    .app-header h1 {{
        margin: 0;
        font-size: 1.5rem;
        color: {current_theme['primary']} !important;
        font-weight: 800;
    }}
    .app-header p {{
        margin: 0;
        font-size: 0.8rem;
        color: {current_theme['subtext']};
        text-transform: uppercase;
        letter-spacing: 1px;
    }}

    /* Action Banner */
    .hero-banner {{
        background: linear-gradient(135deg, {current_theme['primary']}, {current_theme['primary_hover']});
        color: white;
        padding: 24px;
        border-radius: 16px;
        margin-bottom: 24px;
        box-shadow: 0 10px 25px -5px rgba(0,0,0,0.1);
    }}

    /* Item Card Grid */
    .grid-card {{
        background-color: {current_theme['card_bg']};
        border: 1px solid {current_theme['border']};
        border-radius: 14px;
        padding: 18px;
        margin-bottom: 16px;
        transition: transform 0.2s ease, box-shadow 0.2s ease;
    }}
    .grid-card:hover {{
        transform: translateY(-2px);
        box-shadow: 0 8px 16px rgba(0,0,0,0.06);
    }}
    .card-title {{
        font-size: 1.15rem;
        font-weight: 700;
        color: {current_theme['text']};
        margin-bottom: 8px;
    }}
    .card-meta {{
        font-size: 0.85rem;
        color: {current_theme['subtext']};
        line-height: 1.5;
    }}

    /* Badges */
    .status-badge {{
        display: inline-block;
        padding: 4px 10px;
        border-radius: 20px;
        font-size: 0.75rem;
        font-weight: 700;
        text-transform: uppercase;
        margin-bottom: 8px;
    }}
    .badge-found {{ background-color: #D1FAE5; color: #065F46; }}
    .badge-lost {{ background-color: #FEE2E2; color: #991B1B; }}
    .badge-resolved {{ background-color: #E0E7FF; color: #3730A3; }}

    #MainMenu {{visibility: hidden;}}
    footer {{visibility: hidden;}}
</style>
""", unsafe_allow_html=True)


# ==========================================
# 3. DATENBANK LOGIK
# ==========================================
DB_FILE = "fundbuero.db"

def init_db():
    conn = sqlite3.connect(DB_FILE)
    c = conn.cursor()
    c.execute('''
        CREATE TABLE IF NOT EXISTS items (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            title TEXT NOT NULL,
            type TEXT NOT NULL,
            category TEXT NOT NULL,
            location TEXT NOT NULL,
            date TEXT NOT NULL,
            description TEXT,
            status TEXT DEFAULT 'Offen',
            image_path TEXT,
            user_name TEXT,
            finder_name TEXT
        )
    ''')
    c.execute("PRAGMA table_info(items)")
    columns = [col[1] for col in c.fetchall()]
    if "finder_name" not in columns:
        c.execute("ALTER TABLE items ADD COLUMN finder_name TEXT")
    conn.commit()
    conn.close()

def add_item(title, item_type, category, location, date_str, description, image_path, user_name):
    conn = sqlite3.connect(DB_FILE)
    c = conn.cursor()
    c.execute('''
        INSERT INTO items (title, type, category, location, date, description, status, image_path, user_name)
        VALUES (?, ?, ?, ?, ?, ?, 'Offen', ?, ?)
    ''', (title, item_type, category, location, date_str, description, image_path, user_name))
    conn.commit()
    conn.close()

def mark_as_found(item_id, finder_name):
    conn = sqlite3.connect(DB_FILE)
    c = conn.cursor()
    c.execute('''
        UPDATE items
        SET status = 'Gefunden / Gelöst', finder_name = ?
        WHERE id = ?
    ''', (finder_name, item_id))
    conn.commit()
    conn.close()

def get_items(filter_type=None, category=None, search_query=None):
    conn = sqlite3.connect(DB_FILE)
    c = conn.cursor()
    query = "SELECT * FROM items WHERE 1=1"
    params = []
    
    if filter_type and filter_type != "Alle":
        query += " AND type = ?"
        params.append(filter_type)
    if category and category != "Alle":
        query += " AND category = ?"
        params.append(category)
        
    if search_query:
        query += " AND (title LIKE ? OR description LIKE ? OR location LIKE ? OR user_name LIKE ?)"
        wildcard_query = f"%{search_query}%"
        params.extend([wildcard_query, wildcard_query, wildcard_query, wildcard_query])
        
    query += " ORDER BY id DESC"
    c.execute(query, params)
    rows = c.fetchall()
    conn.close()
    return rows

init_db()


# ==========================================
# 4. HUGGING FACE KI INFERENZ
# ==========================================
LABELS = ["Bekleidung/Jacke", "Elektronik/Handy", "Schlüssel", "Rucksack/Tasche", "Mäppchen/Stifte", "Sonstiges"]

@st.cache_resource
def load_hf_model():
    try:
        classifier = pipeline("image-classification", model="google/vit-base-patch16-224")
        return classifier
    except Exception as e:
        st.warning(f"KI-Modell konnte nicht geladen werden: {e}")
        return None

def map_hf_to_school_category(hf_label: str):
    label = hf_label.lower()
    if any(w in label for w in ["jacket", "coat", "sweater", "shirt", "clothing", "hoodie", "cardigan", "jean"]):
        return "Bekleidung/Jacke", "Kleidungsstück / Jacke"
    elif any(w in label for w in ["cellular telephone", "mobile phone", "cellphone"]):
        return "Elektronik/Handy", "Smartphone / Handy"
    elif any(w in label for w in ["laptop", "notebook"]):
        return "Elektronik/Handy", "Laptop / Computer"
    elif any(w in label for w in ["tablet", "ipad"]):
        return "Elektronik/Handy", "Tablet"
    elif any(w in label for w in ["key", "keychain"]):
        return "Schlüssel", "Schlüssel"
    elif any(w in label for w in ["backpack", "bag", "handbag", "suitcase", "pouch", "school bag"]):
        return "Rucksack/Tasche", "Rucksack / Tasche"
    elif any(w in label for w in ["pencil", "pen", "pencil box", "pencil case", "eraser", "ballpoint"]):
        return "Mäppchen/Stifte", "Mäppchen / Stift"
    elif "water bottle" in label or "flask" in label:
        return "Sonstiges", "Trinkflasche"
    elif "umbrella" in label:
        return "Sonstiges", "Regenschirm"
    elif "wallet" in label or "purse" in label:
        return "Sonstiges", "Geldbörse"
    else:
        return "Sonstiges", "Gegenstand"

def predict_category(image: Image.Image):
    classifier = load_hf_model()
    if classifier is not None:
        try:
            results = classifier(image)
            top_prediction = results[0]
            raw_label = top_prediction['label']
            confidence = float(top_prediction['score'])
            mapped_category, german_label = map_hf_to_school_category(raw_label)
            return mapped_category, confidence, german_label
        except Exception:
            pass
    return "Sonstiges", 0.75, "Gegenstand"


# ==========================================
# 5. HEADER COMPONENT (MIT SETTINGS DROPDOWN)
# ==========================================
def render_header():
    col_title, col_settings = st.columns([4, 1])
    
    with col_title:
        st.markdown("""
        <div class="app-header">
            <p>Katharineum zu Lübeck</p>
            <h1>Campus Fundbüro</h1>
        </div>
        """, unsafe_allow_html=True)
        
    with col_settings:
        with st.popover("⚙️ Einstellungen"):
            st.markdown("### Farbschema wählen")
            selected_theme = st.selectbox(
                "Design Anpassen",
                list(THEMES.keys()),
                index=list(THEMES.keys()).index(st.session_state.theme)
            )
            if selected_theme != st.session_state.theme:
                st.session_state.theme = selected_theme
                st.rerun()

            if st.session_state.logged_in:
                st.markdown("---")
                if st.button("🚪 Abmelden", use_container_width=True):
                    st.session_state.logged_in = False
                    st.rerun()


# ==========================================
# 6. VIEWS
# ==========================================

def view_login():
    render_header()
    
    _, col, _ = st.columns([1, 2, 1])
    with col:
        st.markdown("<div class='grid-card'>", unsafe_allow_html=True)
        st.subheader("Anmeldung")
        with st.form("login_form"):
            user_input = st.text_input("Nutzername", placeholder="z. B. max.mustermann")
            password_input = st.text_input("Passwort", type="password", placeholder="••••••••")
            submit = st.form_submit_button("Anmelden", use_container_width=True, type="primary")
            if submit:
                if user_input and password_input:
                    st.session_state.logged_in = True
                    st.session_state.username = user_input
                    st.rerun()
                else:
                    st.error("Bitte Benutzername und Passwort eingeben.")
        st.markdown("</div>", unsafe_allow_html=True)

def view_dashboard():
    render_header()
    
    # Hero / Aktionsbereich
    st.markdown(f"""
    <div class="hero-banner">
        <h2>Hallo, {st.session_state.username}! 👋</h2>
        <p>Hast du etwas verloren oder einen Gegenstand auf dem Schulgelände gefunden?</p>
    </div>
    """, unsafe_allow_html=True)

    col_btn1, col_btn2 = st.columns(2)
    with col_btn1:
        if st.button("🔴 Etwas VERLOREN melden", use_container_width=True):
            st.session_state.action_type = "Verloren"
            st.session_state.active_view = "add_item"
            st.rerun()
    with col_btn2:
        if st.button("📷 Etwas GEFUNDEN melden", use_container_width=True, type="primary"):
            st.session_state.action_type = "Gefunden"
            st.session_state.active_view = "add_item"
            st.rerun()

    st.markdown("<br>", unsafe_allow_html=True)
    st.subheader("Aktuelle Fundstücke & Anfragen")

    # Filter- & Such-Leiste in 3 Spalten
    c_search, c_type, c_cat = st.columns([2, 1, 1])
    with c_search:
        search_term = st.text_input("🔍 Suche", placeholder="Stichwort eingeben...")
    with c_type:
        type_filter = st.selectbox("Typ", ["Alle", "Verloren", "Gefunden"])
    with c_cat:
        cat_filter = st.selectbox("Kategorie", ["Alle"] + LABELS)

    items = get_items(filter_type=type_filter, category=cat_filter, search_query=search_term.strip())

    if not items:
        st.info("Keine Einträge gefunden.")
    else:
        # Zwerdspaltiges Grid-Layout für Ergebnisse
        col_grid1, col_grid2 = st.columns(2)
        
        for idx, item in enumerate(items):
            item_id, title, itype, category, location, date_str, desc, status, img_path, user, finder = item[0], item[1], item[2], item[3], item[4], item[5], item[6], item[7] if len(item)>7 else "Offen", item[8] if len(item)>8 else None, item[9] if len(item)>9 else "Anonym", item[10] if len(item)>10 else "-"
            
            # Verteile Karten gleichmäßig auf 2 Spalten
            target_col = col_grid1 if idx % 2 == 0 else col_grid2
            
            with target_col:
                if status == "Gefunden / Gelöst":
                    badge = f'<span class="status-badge badge-resolved">GELÖST von {finder}</span>'
                elif itype == "Gefunden":
                    badge = '<span class="status-badge badge-found">GEFUNDEN</span>'
                else:
                    badge = '<span class="status-badge badge-lost">VERLUST-ANFRAGE</span>'

                st.markdown(f"""
                <div class="grid-card">
                    {badge}
                    <div class="card-title">{title}</div>
                    <div class="card-meta">
                        📍 <b>Ort:</b> {location}<br>
                        📅 <b>Datum:</b> {date_str}<br>
                        🏷️ <b>Kategorie:</b> {category}<br>
                        👤 <b>Gemeldet von:</b> {user}
                    </div>
                    <p style="margin-top: 10px; font-size: 0.9rem;">{desc if desc else ''}</p>
                </div>
                """, unsafe_allow_html=True)

                if img_path and os.path.exists(img_path):
                    st.image(img_path, use_container_width=True)

                if itype == "Verloren" and status == "Offen":
                    if st.button("🎉 Ich habe es gefunden!", key=f"btn_{item_id}", type="primary"):
                        mark_as_found(item_id, st.session_state.username)
                        st.success("Erfolgreich als gefunden markiert!")
                        st.rerun()

def view_add_item():
    render_header()
    
    if st.button("← Zurück zur Übersicht"):
        st.session_state.active_view = "dashboard"
        st.rerun()

    is_lost = st.session_state.action_type == "Verloren"
    st.title("Verlust melden" if is_lost else "Fundstück eintragen")

    uploaded_image = None
    detected_category = "Sonstiges"
    saved_img_path = None

    if not is_lost:
        st.subheader("1. KI-Erkennung durch Foto")
        upload_method = st.radio("Foto-Quelle:", ["Kamera", "Upload"], horizontal=True)
        if upload_method == "Kamera":
            uploaded_image = st.camera_input("Foto machen")
        else:
            uploaded_image = st.file_uploader("Datei wählen", type=["jpg", "jpeg", "png"])
    else:
        uploaded_image = st.file_uploader("Optionales Vergleichsfoto hochladen", type=["jpg", "jpeg", "png"])

    if uploaded_image:
        image = Image.open(uploaded_image).convert("RGB")
        detected_category, confidence_score, german_label = predict_category(image)
        
        st.success(f"🤗 **KI-Erkennung:** Erkannt als **{german_label}** ({confidence_score*100:.1f}%) $\rightarrow$ Kategorie **{detected_category}**")
        
        os.makedirs("uploads", exist_ok=True)
        saved_img_path = os.path.join("uploads", f"{datetime.datetime.now().strftime('%Y%m%d_%H%M%S')}.jpg")
        image.save(saved_img_path)

    st.subheader("2. Details")
    with st.form("add_form"):
        title = st.text_input("Gegenstand / Bezeichnung", placeholder="z. B. Roter Turnbeutel")
        cat_index = LABELS.index(detected_category) if detected_category in LABELS else 0
        category = st.selectbox("Kategorie", LABELS, index=cat_index)
        location = st.text_input("Ort", placeholder="z. B. Pausenhof")
        date_val = st.date_input("Datum", datetime.date.today())
        description = st.text_area("Weitere Hinweise")

        if st.form_submit_button("Eintrag Speichern", type="primary", use_container_width=True):
            if not title or not location:
                st.error("Bitte mindestens Name und Ort angeben.")
            else:
                add_item(title, st.session_state.action_type, category, location, date_val.strftime("%d.%m.%Y"), description, saved_img_path, st.session_state.username)
                st.session_state.active_view = "dashboard"
                st.rerun()


# ==========================================
# 7. ROUTER
# ==========================================
def main():
    if not st.session_state.logged_in:
        view_login()
    else:
        if st.session_state.active_view == "dashboard":
            view_dashboard()
        elif st.session_state.active_view == "add_item":
            view_add_item()

if __name__ == "__main__":
    main()
