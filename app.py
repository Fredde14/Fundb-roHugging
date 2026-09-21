import os
import sqlite3
import datetime
import numpy as np
from PIL import Image
import streamlit as st
from transformers import pipeline

# ==========================================
# 1. STREAMLIT KONFIGURATION & SESSION STATE
# ==========================================
st.set_page_config(
    page_title="Fundbüro - Katharineum zu Lübeck",
    page_icon="🏫",
    layout="centered",
    initial_sidebar_state="collapsed"
)

if "logged_in" not in st.session_state:
    st.session_state.logged_in = False
if "username" not in st.session_state:
    st.session_state.username = ""
if "active_view" not in st.session_state:
    st.session_state.active_view = "dashboard"
if "action_type" not in st.session_state:
    st.session_state.action_type = "Gefunden"
if "dark_mode" not in st.session_state:
    st.session_state.dark_mode = False

# Dynamic CSS Injection (Light vs. Dark Mode)
if st.session_state.dark_mode:
    bg_color = "#0F172A"
    card_bg = "#1E293B"
    text_color = "#F8FAFC"
    border_color = "#334155"
    subtext_color = "#94A3B8"
    navy_header = "#1E3A8A"
else:
    bg_color = "#F8FAFC"
    card_bg = "#FFFFFF"
    text_color = "#1E293B"
    border_color = "#E2E8F0"
    subtext_color = "#64748B"
    navy_header = "#1E3A8A"

st.markdown(f"""
<style>
    .stApp {{
        background-color: {bg_color};
        color: {text_color};
        font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif;
    }}

    .brand-header {{
        background-color: {navy_header};
        color: white;
        padding: 20px;
        border-radius: 12px;
        text-align: center;
        margin-bottom: 24px;
        box-shadow: 0 4px 12px rgba(30, 58, 138, 0.15);
        width: 100%;
    }}
    .brand-header h1 {{
        margin: 0;
        font-size: 1.6rem;
        font-weight: 700;
        color: #FFFFFF !important;
    }}
    .brand-header p {{
        margin: 4px 0 0 0;
        font-size: 0.85rem;
        color: #93C5FD;
        text-transform: uppercase;
        letter-spacing: 1.5px;
    }}

    .login-container {{
        background-color: {card_bg};
        border: 1px solid {border_color};
        border-radius: 12px;
        padding: 24px;
        box-shadow: 0 4px 12px rgba(0, 0, 0, 0.05);
        margin-top: 10px;
    }}

    .item-card {{
        background-color: {card_bg};
        border: 1px solid {border_color};
        border-radius: 10px;
        padding: 16px;
        margin-bottom: 12px;
        box-shadow: 0 2px 4px rgba(0,0,0,0.02);
        color: {text_color};
    }}
    .item-card strong {{
        color: {text_color};
    }}
    .badge-found {{
        background-color: #DEF7EC;
        color: #03543F;
        padding: 4px 10px;
        border-radius: 6px;
        font-size: 0.75rem;
        font-weight: 600;
    }}
    .badge-lost {{
        background-color: #FDE8E8;
        color: #9B1C1C;
        padding: 4px 10px;
        border-radius: 6px;
        font-size: 0.75rem;
        font-weight: 600;
    }}
    .badge-resolved {{
        background-color: #E0E7FF;
        color: #3730A3;
        padding: 4px 10px;
        border-radius: 6px;
        font-size: 0.75rem;
        font-weight: 600;
    }}

    div.stButton > button[kind="primary"] {{
        background-color: {navy_header};
        color: white;
    }}

    #MainMenu {{visibility: hidden;}}
    footer {{visibility: hidden;}}
</style>
""", unsafe_allow_html=True)


# ==========================================
# 2. DATENBANK LOGIK & MIGRATION
# ==========================================
DB_FILE = "fundbuero.db"

def init_db():
    """Initialisiert die SQLite-Datenbank und führt Migrationen durch."""
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
    """Lädt Einträge aus der Datenbank unter Berücksichtigung von Typ, Kategorie und Suchbegriffen."""
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
# 3. HUGGING FACE KI INFERENZ & TRANSLATOR
# ==========================================
LABELS = ["Bekleidung/Jacke", "Elektronik/Handy", "Schlüssel", "Rucksack/Tasche", "Mäppchen/Stifte", "Sonstiges"]

@st.cache_resource
def load_hf_model():
    """Lädt ein vortrainiertes Hugging Face Bildklassifikations-Modell."""
    try:
        classifier = pipeline("image-classification", model="google/vit-base-patch16-224")
        return classifier
    except Exception as e:
        st.warning(f"Hugging Face Modell konnte nicht geladen werden: {e}")
        return None

def map_hf_to_school_category(hf_label: str):
    """Mappt englische Hugging Face Labels auf deutsche Schulkategorien + deutsche Bezeichnung."""
    label = hf_label.lower()
    
    if any(w in label for w in ["jacket", "coat", "sweater", "shirt", "clothing", "hoodie", "cardigan", "jean", "jersey"]):
        return "Bekleidung/Jacke", "Kleidungsstück / Jacke"
    elif any(w in label for w in ["cellular telephone", "mobile phone", "cellphone"]):
        return "Elektronik/Handy", "Smartphone / Handy"
    elif any(w in label for w in ["laptop", "notebook"]):
        return "Elektronik/Handy", "Laptop / Computer"
    elif any(w in label for w in ["tablet", "ipad"]):
        return "Elektronik/Handy", "Tablet"
    elif any(w in label for w in ["key", "keychain"]):
        return "Schlüssel", "Schlüssel"
    elif any(w in label for w in ["backpack", "bag", "handbag", "suitcase", "pouch", "school bag", "knapsack"]):
        return "Rucksack/Tasche", "Rucksack / Tasche"
    elif any(w in label for w in ["pencil", "pen", "pencil box", "pencil case", "eraser", "ballpoint"]):
        return "Mäppchen/Stifte", "Mäppchen / Stift"
    elif "water bottle" in label or "flask" in label or "pop bottle" in label:
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
# 4. HEADER COMPONENT MIT EINSTELLUNGEN
# ==========================================
def render_header(show_settings=True):
    col_header, col_settings = st.columns([5, 1])
    
    with col_header:
        st.markdown("""
        <div class="brand-header">
            <p>Katharineum zu Lübeck</p>
            <h1>DIGITALES FUNDBÜRO</h1>
        </div>
        """, unsafe_allow_html=True)

    with col_settings:
        if show_settings:
            with st.popover("⚙️"):
                st.markdown("### Einstellungen")
                dark_mode_active = st.checkbox("🌙 Dark Mode", value=st.session_state.dark_mode)
                if dark_mode_active != st.session_state.dark_mode:
                    st.session_state.dark_mode = dark_mode_active
                    st.rerun()

                if st.session_state.logged_in:
                    st.markdown("---")
                    if st.button("Abmelden", key="logout_settings_btn", use_container_width=True):
                        st.session_state.logged_in = False
                        st.rerun()


# ==========================================
# 5. UI COMPONENTS & VIEWS
# ==========================================

# --- LOGIN SCREEN ---
def view_login():
    # Zentrierter Container für Login und Header
    _, center_col, _ = st.columns([1, 4, 1])
    
    with center_col:
        # Header innerhalb der zentrierten Spalte
        st.markdown("""
        <div class="brand-header">
            <p>Katharineum zu Lübeck</p>
            <h1>DIGITALES FUNDBÜRO</h1>
        </div>
        """, unsafe_allow_html=True)
        
        # Einstellungen-Button für den Login-Screen direkt über der Box
        c_space, c_opt = st.columns([4, 1])
        with c_opt:
            with st.popover("⚙️"):
                st.markdown("### Einstellungen")
                dark_mode_active = st.checkbox("🌙 Dark Mode", value=st.session_state.dark_mode)
                if dark_mode_active != st.session_state.dark_mode:
                    st.session_state.dark_mode = dark_mode_active
                    st.rerun()

        # Saubere, zentrierte Anmeldebox direkt darunter
        st.markdown("<div class='login-container'>", unsafe_allow_html=True)
        st.markdown("<h3 style='text-align: center; margin-bottom: 20px;'>Anmeldung</h3>", unsafe_allow_html=True)
        
        with st.form("login_form"):
            user_input = st.text_input("Anmeldename", placeholder="z. B. s.müller")
            password_input = st.text_input("Passwort", type="password", placeholder="••••••••")
            submit = st.form_submit_button("Anmelden", use_container_width=True, type="primary")
            
            if submit:
                if user_input and password_input:
                    st.session_state.logged_in = True
                    st.session_state.username = user_input
                    st.rerun()
                else:
                    st.error("Bitte gib Anmeldename und Passwort ein.")
                    
        c1, c2 = st.columns(2)
        with c1:
            st.caption("[Anmeldename vergessen?](#)")
        with c2:
            st.caption("[Passwort vergessen?](#)")
            
        st.markdown("</div>", unsafe_allow_html=True)

# --- DASHBOARD ---
def view_dashboard():
    render_header()
    
    st.write(f"Angemeldet als: **{st.session_state.username}**")
    st.markdown("---")

    col_lost, col_found = st.columns(2)
    with col_lost:
        if st.button("🔴 Anfrage: Ich habe etwas VERLOREN", use_container_width=True):
            st.session_state.action_type = "Verloren"
            st.session_state.active_view = "add_item"
            st.rerun()
            
    with col_found:
        if st.button("📷 Ich habe etwas GEFUNDEN", use_container_width=True, type="primary"):
            st.session_state.action_type = "Gefunden"
            st.session_state.active_view = "add_item"
            st.rerun()

    st.markdown("<br>", unsafe_allow_html=True)
    st.subheader("Übersicht & Suche")
    
    # Schlagwortsuche
    search_term = st.text_input("🔍 Schlagwortsuche", placeholder="z. B. Schulschlüssel, blau, Turnhalle...")

    col_f1, col_f2 = st.columns([1, 1])
    with col_f1:
        type_filter = st.selectbox("Filter nach Typ", ["Alle", "Verloren", "Gefunden"])
    with col_f2:
        cat_filter = st.selectbox("Kategorie", ["Alle"] + LABELS)

    items = get_items(filter_type=type_filter, category=cat_filter, search_query=search_term.strip())
    
    if not items:
        st.info("Keine passenden Einträge oder Anfragen vorhanden.")
    else:
        for item in items:
            item_id = item[0]
            title = item[1]
            itype = item[2]
            category = item[3]
            location = item[4]
            date_str = item[5]
            desc = item[6]
            status = item[7] if len(item) > 7 else "Offen"
            img_path = item[8] if len(item) > 8 else None
            user = item[9] if len(item) > 9 else "Anonym"
            finder = item[10] if len(item) > 10 else "-"
            
            if status == "Gefunden / Gelöst":
                badge_html = f'<span class="badge-resolved">GELÖST (Gefunden von {finder})</span>'
            elif itype == "Gefunden":
                badge_html = '<span class="badge-found">GEFUNDEN</span>'
            else:
                badge_html = '<span class="badge-lost">VERLUST-ANFRAGE</span>'

            with st.container():
                st.markdown(f"""
                <div class="item-card">
                    {badge_html}
                    <strong style="margin-left: 8px; font-size: 1.1rem;">{title}</strong>
                    <p style="color: {subtext_color}; margin: 6px 0 2px 0; font-size: 0.85rem;">
                        📍 <b>Ort:</b> {location} | 📅 <b>Datum:</b> {date_str} | 🏷️ <b>Kategorie:</b> {category} | 👤 <b>Von:</b> {user}
                    </p>
                    <p style="margin-top: 6px; font-size: 0.95rem;">{desc if desc else 'Keine Beschreibung vorhanden.'}</p>
                </div>
                """, unsafe_allow_html=True)
                
                if img_path and os.path.exists(img_path):
                    st.image(img_path, width=220)

                if itype == "Verloren" and status == "Offen":
                    col_act1, col_act2 = st.columns([2, 1])
                    with col_act2:
                        if st.button("🎉 Ich habe das gefunden!", key=f"found_btn_{item_id}", type="primary"):
                            mark_as_found(item_id, st.session_state.username)
                            st.success(f"Danke! Die Anfrage '{title}' wurde als gefunden markiert.")
                            st.rerun()
                st.markdown("---")

# --- ANFRAGE / FUNDSTÜCK ERSTELLEN ---
def view_add_item():
    render_header()
    
    if st.button("← Zurück zum Dashboard"):
        st.session_state.active_view = "dashboard"
        st.rerun()

    is_lost = st.session_state.action_type == "Verloren"
    action_title = "Verlustanfrage stellen" if is_lost else "Gefundenen Gegenstand melden"
    st.title(action_title)

    uploaded_image = None
    detected_category = "Sonstiges"
    saved_img_path = None

    if not is_lost:
        st.subheader("1. Foto aufnehmen / hochladen (für KI-Erkennung)")
        upload_method = st.radio("Foto-Quelle wählen:", ["Kamera-Scanner", "Datei-Upload"], horizontal=True)
        if upload_method == "Kamera-Scanner":
            uploaded_image = st.camera_input("Kamera zum Sache detektieren")
        else:
            uploaded_image = st.file_uploader("Bild auswählen", type=["jpg", "jpeg", "png"])
    else:
        st.info("💡 Wenn du ein Vergleichsfoto oder Beispielbild hast, kannst du es optional hochladen.")
        uploaded_image = st.file_uploader("Foto hinzufügen (optional)", type=["jpg", "jpeg", "png"])

    if uploaded_image:
        image = Image.open(uploaded_image).convert("RGB")
        detected_category, confidence_score, german_label = predict_category(image)
        
        st.success(f"🤗 **KI-Erkennung:** Erkannt als **{german_label}** ({confidence_score*100:.1f}%) $\rightarrow$ Kategorie **{detected_category}**")
        
        os.makedirs("uploads", exist_ok=True)
        saved_img_path = os.path.join("uploads", f"{datetime.datetime.now().strftime('%Y%m%d_%H%M%S')}.jpg")
        image.save(saved_img_path)

    st.subheader("2. Details eingeben")
    with st.form("add_item_form"):
        title = st.text_input("Was wurde " + ("verloren?" if is_lost else "gefunden?"), 
                              placeholder="z. B. Blauer Schulrucksack, Schlüsselbund mit rotem Band...")
        
        cat_index = LABELS.index(detected_category) if detected_category in LABELS else 0
        category = st.selectbox("Kategorie", LABELS, index=cat_index)
        
        location = st.text_input("Vermuteter Ort", placeholder="z. B. Sporthalle, Mensa, Raum 204")
        date_val = st.date_input("Datum", datetime.date.today())
        description = st.text_area("Beschreibung & Merkmale", 
                                   placeholder="Genauere Beschreibung, damit Besitzer/Finder den Gegenstand zuordnen können.")

        button_text = "Verlustanfrage veröffentlichen" if is_lost else "Fundstück eintragen"
        submit = st.form_submit_button(button_text, type="primary", use_container_width=True)

        if submit:
            if not title or not location:
                st.error("Bitte gib mindestens den Namen des Gegenstands und den Ort an.")
            else:
                add_item(
                    title=title,
                    item_type=st.session_state.action_type,
                    category=category,
                    location=location,
                    date_str=date_val.strftime("%d.%m.%Y"),
                    description=description,
                    image_path=saved_img_path,
                    user_name=st.session_state.username
                )
                st.success("Erfolgreich eingetragen!")
                st.session_state.active_view = "dashboard"
                st.rerun()


# ==========================================
# 6. HAUPT-ROUTER
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
