import os
import sqlite3
import bcrypt
from datetime import datetime, date
from io import BytesIO
import calendar

import pandas as pd
import streamlit as st
import xlsxwriter
from xlsxwriter.utility import xl_col_to_name

# ============================================================
# GENEL UYGULAMA AYARLARI
# ============================================================
st.set_page_config(
    page_title="Akıllı Puantaj Yönetim Sistemi",
    page_icon="🗓️",
    layout="wide",
)

# ============================================================
# TEMA (MINIMAL DARK / LIGHT)
# ============================================================
if "dark_mode" not in st.session_state:
    st.session_state.dark_mode = True

def inject_theme_css():
    dark = st.session_state.dark_mode

    if dark:
        bg_color = "#050509"
        card_color = "#111118"
        accent = "#0A84FF"       # Apple mavi
        text_color = "#F5F5F7"
        sub_text = "#A1A1AA"
        border_color = "#1E1E2E"
        input_bg = "#181826"
    else:
        bg_color = "#F5F5F7"
        card_color = "#FFFFFF"
        accent = "#007AFF"
        text_color = "#111111"
        sub_text = "#6B7280"
        border_color = "#E5E7EB"
        input_bg = "#F9FAFB"

    st.markdown(
        f"""
        <style>
        .stApp {{
            background: radial-gradient(circle at top left, #1e293b22, transparent 55%), 
                        radial-gradient(circle at top right, #0f172a22, transparent 55%),
                        {bg_color};
            color: {text_color};
            font-family: -apple-system, BlinkMacSystemFont, system-ui, sans-serif;
        }}

        .main .block-container {{
            padding-top: 2.5rem;
            padding-bottom: 3rem;
            max-width: 1200px;
        }}

        .apple-card {{
            background-color: {card_color};
            border-radius: 24px;
            padding: 24px 26px;
            border: 1px solid {border_color};
            box-shadow: 0 32px 80px rgba(0,0,0,0.28);
        }}

        .apple-card-soft {{
            background-color: {card_color};
            border-radius: 20px;
            padding: 18px 20px;
            border: 1px solid {border_color};
        }}

        .apple-title {{
            font-size: 1.6rem;
            font-weight: 600;
            letter-spacing: -0.03em;
        }}

        .apple-subtitle {{
            font-size: 0.95rem;
            color: {sub_text};
        }}

        .apple-pill {{
            display: inline-flex;
            align-items: center;
            padding: 4px 10px;
            border-radius: 999px;
            border: 1px solid {border_color};
            font-size: 0.72rem;
            letter-spacing: 0.08em;
            text-transform: uppercase;
            color: {sub_text};
        }}

        .stTextInput > div > div > input,
        .stNumberInput > div > input,
        .stSelectbox > div > div > select,
        .stMultiSelect > div > div > div {{
            background-color: {input_bg} !important;
            border-radius: 12px !important;
            border: 1px solid {border_color} !important;
            color: {text_color} !important;
        }}

        .stButton>button {{
            border-radius: 999px !important;
            padding: 0.55rem 1.3rem;
            border: none;
            background: linear-gradient(135deg, {accent}, #34C759);
            color: white;
            font-weight: 600;
            letter-spacing: 0.02em;
            box-shadow: 0 14px 28px rgba(0,0,0,0.35);
        }}

        .stDownloadButton>button {{
            border-radius: 999px !important;
            padding: 0.55rem 1.3rem;
            border: 1px solid {border_color};
            background: transparent;
            color: {text_color};
            font-weight: 500;
        }}

        .warning-badge {{
            display: inline-flex;
            align-items: center;
            gap: 6px;
            padding: 4px 10px;
            border-radius: 999px;
            background-color: rgba(252, 211, 77, 0.14);
            border: 1px solid rgba(252, 211, 77, 0.35);
            font-size: 0.78rem;
        }}
        </style>
        """,
        unsafe_allow_html=True,
    )

inject_theme_css()

# ============================================================
# SQLITE – KALICI VERİTABANI (Streamlit Cloud UYUMLU)
# ============================================================
# Not: Streamlit Cloud'da çalışma klasörüne yazılan dosyalar
# yeniden deploy edilene kadar kalıcıdır. /tmp yerine proje klasörü
# altında (örn. data/users.db) kullanıyoruz.

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DB_DIR = os.path.join(BASE_DIR, "data")
DB_PATH = os.path.join(DB_DIR, "users.db")
ARCHIVE_DIR = os.path.join(BASE_DIR, "arsiv")
os.makedirs(DB_DIR, exist_ok=True)
os.makedirs(ARCHIVE_DIR, exist_ok=True)

@st.cache_resource
def get_connection():
    conn = sqlite3.connect(DB_PATH, check_same_thread=False)
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            username TEXT UNIQUE NOT NULL,
            password_hash BLOB NOT NULL,
            role TEXT NOT NULL CHECK(role IN ('admin','operator','unapproved')),
            created_at TIMESTAMP NOT NULL
        );
        """
    )
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS students (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL UNIQUE,
            active INTEGER NOT NULL DEFAULT 1,
            created_at TIMESTAMP NOT NULL
        );
        """
    )
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS puantaj_archives (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            year INTEGER NOT NULL,
            month INTEGER NOT NULL,
            file_path TEXT NOT NULL,
            created_at TIMESTAMP NOT NULL
        );
        """
    )
    conn.commit()
    return conn

conn = get_connection()

def get_user_count():
    cur = conn.cursor()
    cur.execute("SELECT COUNT(*) FROM users;")
    return cur.fetchone()[0]

def get_user_by_username(username: str):
    cur = conn.cursor( )
    cur.execute("SELECT id, username, password_hash, role FROM users WHERE username = ?;", (username,))
    return cur.fetchone()

def create_user(username: str, password: str, role: str):
    password_hash = bcrypt.hashpw(password.encode("utf-8"), bcrypt.gensalt())
    cur = conn.cursor()
    cur.execute(
        "INSERT INTO users (username, password_hash, role, created_at) VALUES (?, ?, ?, ?);",
        (username, password_hash, role, datetime.utcnow()),
    )
    conn.commit()

def update_user_role(user_id: int, role: str):
    cur = conn.cursor()
    cur.execute(
        "UPDATE users SET role = ? WHERE id = ?;",
        (role, user_id),
    )
    conn.commit()

def delete_user(user_id: int):
    cur = conn.cursor()
    cur.execute("DELETE FROM users WHERE id = ?;", (user_id,))
    conn.commit()

def list_unapproved_users():
    cur = conn.cursor()
    cur.execute(
        "SELECT id, username, created_at FROM users WHERE role = 'unapproved' ORDER BY created_at ASC;"
    )
    return cur.fetchall()

def list_all_users():
    cur = conn.cursor()
    cur.execute(
        "SELECT id, username, role, created_at FROM users ORDER BY created_at ASC;"
    )
    return cur.fetchall()

def add_student(name: str):
    name = name.strip()
    if not name:
        raise ValueError("Öğrenci adı boş olamaz.")
    cur = conn.cursor()
    cur.execute(
        "INSERT OR IGNORE INTO students (name, active, created_at) VALUES (?, 1, ?);",
        (name, datetime.utcnow()),
    )
    conn.commit()

def delete_student(student_id: int):
    cur = conn.cursor()
    cur.execute("DELETE FROM students WHERE id = ?;", (student_id,))
    conn.commit()

def list_students(active_only: bool = True):
    cur = conn.cursor()
    if active_only:
        cur.execute(
            "SELECT id, name FROM students WHERE active = 1 ORDER BY name ASC;"
        )
    else:
        cur.execute("SELECT id, name, active FROM students ORDER BY name ASC;")
    return cur.fetchall()

def bulk_add_students_from_names(names):
    cur = conn.cursor()
    for n in names:
        name = str(n).strip()
        if not name:
            continue
        cur.execute(
            "INSERT OR IGNORE INTO students (name, active, created_at) VALUES (?, 1, ?);",
            (name, datetime.utcnow()),
        )
    conn.commit()

def save_puantaj_archive(file_bytes: bytes, year: int, month: int) -> str:
    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    file_name = f"puantaj_{year}_{month:02d}_{ts}.xlsx"
    file_path = os.path.join(ARCHIVE_DIR, file_name)
    with open(file_path, "wb") as f:
        f.write(file_bytes)
    cur = conn.cursor()
    cur.execute(
        "INSERT INTO puantaj_archives (year, month, file_path, created_at) VALUES (?, ?, ?, ?);",
        (year, month, file_path, datetime.utcnow()),
    )
    conn.commit()
    return file_path

def list_puantaj_archives():
    cur = conn.cursor()
    cur.execute(
        "SELECT id, year, month, file_path, created_at FROM puantaj_archives ORDER BY created_at DESC;"
    )
    return cur.fetchall()

# ============================================================
# YARDIMCI FONKSİYONLAR – PUANTAJ LOGİĞİ
# (Önceki uygulamandaki mantığı fonksiyonlara böldük)
# ============================================================
def parse_int_list_from_text(text: str):
    if not text:
        return []
    parts = [p.strip() for p in text.replace(";", ",").split(",") if p.strip()]
    days = []
    for p in parts:
        if p.isdigit():
            d = int(p)
            if 1 <= d <= 31:
                days.append(d)
    return sorted(set(days))

def is_weekend(year: int, month: int, day: int) -> bool:
    try:
        return date(year, month, day).weekday() >= 5
    except ValueError:
        return False

def build_or_extend_attendance_df(df: pd.DataFrame, name_col: str):
    if name_col not in df.columns:
        raise ValueError("Seçilen öğrenci kolonu DataFrame içinde bulunamadı.")
    return df.copy()

def mark_days_for_student(
    df: pd.DataFrame,
    name_col: str,
    student_name: str,
    year: int,
    month: int,
    days: list[int],
    training_days: list[int],
    holiday_days: list[int],
    training_symbol: str = "E",
    normal_symbol: str = "X",
):
    if student_name not in list(df[name_col]):
        raise ValueError("Seçilen öğrenci DataFrame içinde bulunamadı.")

    for d in days:
        try:
            _ = date(year, month, d)
        except ValueError:
            continue
        col_name = f"{year}-{month:02d}-{d:02d}"
        if col_name not in df.columns:
            df[col_name] = ""
        symbol = training_symbol if d in training_days else normal_symbol
        mask = df[name_col] == student_name
        df.loc[mask, col_name] = symbol
    return df

def to_excel_download_bytes(df: pd.DataFrame) -> bytes:
    buffer = BytesIO()
    with pd.ExcelWriter(buffer, engine="openpyxl") as writer:
        df.to_excel(writer, index=False, sheet_name="Puantaj")
    buffer.seek(0)
    return buffer.read()

# ============================================================
# SESSION STATE
# ============================================================
if "user" not in st.session_state:
    st.session_state.user = None  # (id, username, role)
if "raw_df" not in st.session_state:
    st.session_state.raw_df = None
if "attendance_df" not in st.session_state:
    st.session_state.attendance_df = None
if "name_col" not in st.session_state:
    st.session_state.name_col = None

# ============================================================
# ORTAK ÜST BAR
# ============================================================
top_col1, top_col2 = st.columns([4, 1])

with top_col1:
    st.markdown(
        """
        <div class="apple-card">
            <div style="display:flex; justify-content:space-between; align-items:flex-start; gap:1rem;">
                <div>
                    <div class="apple-pill">AKILLI YOKLAMA</div>
                    <div style="height:0.6rem;"></div>
                    <div class="apple-title">Akıllı Puantaj Yönetim Sistemi</div>
                    <div style="height:0.35rem;"></div>
                    <div class="apple-subtitle">
                        Rol tabanlı yetkilendirme ile güvenli puantaj yönetimi.
                    </div>
                </div>
            </div>
        </div>
        """,
        unsafe_allow_html=True,
    )

with top_col2:
    with st.container():
        st.write("")
        st.write("")
        st.session_state.dark_mode = st.toggle(
            "Dark Mod",
            value=st.session_state.dark_mode,
        )
        inject_theme_css()

# ============================================================
# AUTH BÖLÜMÜ
# ============================================================
def super_admin_setup_view():
    st.markdown("### İlk Kurulum – Süper Admin Oluştur")
    st.caption(
        "Uygulama ilk kez çalıştırılıyor. Lütfen bir Süper Admin hesabı tanımlayın. "
        "Bu hesap 'admin' rolünde olacaktır."
    )
    username = st.text_input("Kullanıcı adı (admin)", key="setup_username")
    password = st.text_input("Şifre", type="password", key="setup_password")
    password2 = st.text_input("Şifre (tekrar)", type="password", key="setup_password2")

    if st.button("Süper Admin Oluştur"):
        if not username or not password:
            st.error("Kullanıcı adı ve şifre zorunludur.")
        elif password != password2:
            st.error("Şifreler uyuşmuyor.")
        else:
            try:
                create_user(username, password, "admin")
                st.success("Süper Admin başarıyla oluşturuldu. Lütfen giriş yapın.")
            except sqlite3.IntegrityError:
                st.error("Bu kullanıcı adı zaten mevcut.")

def auth_view():
    tabs = st.tabs(["Giriş", "Kayıt Ol"])

    # Giriş
    with tabs[0]:
        username = st.text_input("Kullanıcı adı", key="login_username")
        password = st.text_input("Şifre", type="password", key="login_password")
        if st.button("Giriş Yap"):
            user = get_user_by_username(username)
            if user is None:
                st.error("Kullanıcı bulunamadı.")
            else:
                user_id, uname, pw_hash, role = user
                if bcrypt.checkpw(password.encode("utf-8"), pw_hash):
                    st.session_state.user = {
                        "id": user_id,
                        "username": uname,
                        "role": role,
                    }
                    st.rerun()
                else:
                    st.error("Şifre hatalı.")

    # Kayıt
    with tabs[1]:
        st.caption("Kayıt olduktan sonra bir admin tarafından onaylanana kadar 'Beklemede' kalırsınız.")
        new_username = st.text_input("Kullanıcı adı", key="register_username")
        new_password = st.text_input("Şifre", type="password", key="register_password")
        new_password2 = st.text_input("Şifre (tekrar)", type="password", key="register_password2")

        if st.button("Kayıt Ol"):
            if not new_username or not new_password:
                st.error("Kullanıcı adı ve şifre zorunludur.")
            elif new_password != new_password2:
                st.error("Şifreler uyuşmuyor.")
            else:
                try:
                    create_user(new_username, new_password, "unapproved")
                    st.success(
                        "Kayıt başarılı! Hesabınız onay bekliyor. "
                        "Bir admin sizi 'Operatör' olarak onayladığında giriş yapabilirsiniz."
                    )
                except sqlite3.IntegrityError:
                    st.error("Bu kullanıcı adı zaten kullanılıyor.")

def logout_button():
    if st.session_state.user is not None:
        if st.button("Çıkış Yap"):
            st.session_state.user = None
            st.rerun()

# ============================================================
# PUANTAJ – DİNAMİK TAKVİM
# ============================================================
def generate_puantaj_excel(df: pd.DataFrame, year: int, month: int) -> bytes:
    buffer = BytesIO()

    # xlsxwriter ile çalışma kitabı oluştur
    workbook = xlsxwriter.Workbook(buffer, {"in_memory": True})
    worksheet = workbook.add_worksheet("Puantaj")

    # Biçimler
    header_fmt = workbook.add_format(
        {
            "bold": True,
            "bg_color": "#D9D9D9",
            "border": 1,
        }
    )
    weekend_header_fmt = workbook.add_format(
        {
            "bold": True,
            "bg_color": "#FFF4CC",
            "border": 1,
        }
    )
    cell_fmt = workbook.add_format({"border": 1})
    weekend_cell_fmt = workbook.add_format({"border": 1, "bg_color": "#FFF4CC"})

    # Hafta sonu sütunları: başlıkta "Cmt" veya "Paz" geçenler
    weekend_cols = set()
    for col_idx, col_name in enumerate(df.columns):
        if col_idx >= 4 and ("Cmt" in str(col_name) or "Paz" in str(col_name)):
            weekend_cols.add(col_idx)

    # Başlık satırı
    for col_idx, col_name in enumerate(df.columns):
        fmt = weekend_header_fmt if col_idx in weekend_cols else header_fmt
        worksheet.write(0, col_idx, col_name, fmt)

    # Veri satırları
    for row_idx, row in enumerate(df.itertuples(index=False), start=1):
        for col_idx, value in enumerate(row):
            fmt = weekend_cell_fmt if col_idx in weekend_cols else cell_fmt
            worksheet.write(row_idx, col_idx, value, fmt)

    max_row = len(df) + 1  # 0-index header + data
    max_col = len(df.columns)

    # Çalışma / eğitim / izin sütunları: 2,3,4 (index 1,2,3) – 5. sütundan itibaren günler
    for row_idx in range(1, max_row):
        excel_row = row_idx + 1  # Excel'de 1-index
        start_col_idx = 4
        end_col_idx = max_col - 1
        start_col_letter = xl_col_to_name(start_col_idx)
        end_col_letter = xl_col_to_name(end_col_idx)
        day_range = f"{start_col_letter}{excel_row}:{end_col_letter}{excel_row}"

        worksheet.write_formula(row_idx, 1, f'=COUNTIF({day_range},"X")', cell_fmt)
        worksheet.write_formula(row_idx, 2, f'=COUNTIF({day_range},"E")', cell_fmt)
        worksheet.write_formula(row_idx, 3, f'=COUNTIF({day_range},"İ")', cell_fmt)

    # Sütun genişliklerini içeriklere göre ayarla
    for col_idx, col_name in enumerate(df.columns):
        series = df.iloc[:, col_idx].astype(str)
        max_len = max([len(str(col_name))] + [len(s) for s in series]) if not series.empty else len(str(col_name))
        if col_idx == 0:
            max_len += 10  # isim sütunu daha geniş
        width = min(max_len + 2, 50)
        worksheet.set_column(col_idx, col_idx, width)

    workbook.close()
    buffer.seek(0)
    return buffer.read()


def puantaj_view():
    st.markdown('<div class="apple-card-soft">', unsafe_allow_html=True)

    # Ay / yıl seçimi
    st.markdown("**Ay / Yıl Seçimi**")
    current_year = datetime.now().year
    years = list(range(2023, 2031))
    default_year_index = years.index(current_year) if current_year in years else 0

    col_y, col_m = st.columns(2)
    with col_y:
        year = st.selectbox("Yıl", options=years, index=default_year_index)
    with col_m:
        month_names = [
            "Ocak", "Şubat", "Mart", "Nisan", "Mayıs", "Haziran",
            "Temmuz", "Ağustos", "Eylül", "Ekim", "Kasım", "Aralık",
        ]
        month = st.selectbox("Ay", options=list(range(1, 13)), format_func=lambda m: month_names[m-1])

    st.markdown("---")

    # Özel tatil / eğitim günleri
    st.markdown("**Özel Tatil ve Eğitim Günleri**")
    st.caption("Gün numaralarını virgülle ayırarak yazabilirsiniz. Örn: `1, 5, 12, 15`")

    col_ht, col_tr = st.columns(2)
    with col_ht:
        holiday_text = st.text_input("Özel Tatil Günleri", placeholder="Örn: 1, 15, 29")
    with col_tr:
        training_text = st.text_input("Eğitim Günleri", placeholder="Örn: 5, 12, 18")

    holiday_days = parse_int_list_from_text(holiday_text)
    training_days = parse_int_list_from_text(training_text)

    if holiday_days:
        st.caption(f"Seçili tatil günleri: {holiday_days}")
    if training_days:
        st.caption(f"Eğitim günleri: {training_days}")

    st.markdown("---")

    # Veritabanından öğrenciler
    students = list_students(active_only=True)
    if not students:
        st.info("Aktif öğrenci bulunamadı. Önce 'Öğrenci Yönetimi' sekmesinden öğrenci ekleyin.")
        st.markdown("</div>", unsafe_allow_html=True)
        return

    # Dinamik takvim başlıkları
    days_in_month = calendar.monthrange(year, month)[1]
    weekday_labels = ["Pzt", "Sal", "Çar", "Per", "Cum", "Cmt", "Paz"]

    columns = ["Öğrenci", "Çalışma Gün Sayısı", "Eğitim Gün Sayısı", "İzinli Gün Sayısı"]
    day_columns = []
    for d in range(1, days_in_month + 1):
        w = date(year, month, d).weekday()
        label = f"{d:02d} {weekday_labels[w]}"
        day_columns.append(label)
    columns.extend(day_columns)

    # Puantaj DataFrame'ini session_state'te tut
    df_key = f"puantaj_df_{year}_{month}"
    if df_key not in st.session_state:
        data = []
        for _id, name in students:
            row = [name, "", "", ""]  # sayım sütunları formülle Excel'de dolacak
            row.extend([""] * days_in_month)
            data.append(row)
        st.session_state[df_key] = pd.DataFrame(data, columns=columns)
    else:
        # Gün sayısı değişmişse (başka aya geçiş) yeniden oluştur
        existing_df = st.session_state[df_key]
        current_day_cols = [c for c in existing_df.columns if c not in ["Öğrenci", "Çalışma Gün Sayısı", "Eğitim Gün Sayısı", "İzinli Gün Sayısı"]]
        if len(current_day_cols) != days_in_month:
            data = []
            for _id, name in students:
                row = [name, "", "", ""]
                row.extend([""] * days_in_month)
                data.append(row)
            st.session_state[df_key] = pd.DataFrame(data, columns=columns)

    df = st.session_state[df_key]

    st.markdown("**Puantaj Tablosu (X / E / İ işaretleyin)**")
    edited_df = st.data_editor(
        df,
        num_rows="static",
        use_container_width=True,
        hide_index=True,
        disabled=["Öğrenci", "Çalışma Gün Sayısı", "Eğitim Gün Sayısı", "İzinli Gün Sayısı"],
        key=f"puantaj_{year}_{month}",
    )
    # Kullanıcı düzenlemelerini sakla
    st.session_state[df_key] = edited_df

    st.caption("Her gün sütununda: çalıştıysa `X`, eğitime katıldıysa `E`, izinliyse `İ` yazabilirsiniz.")

    st.markdown("---")
    st.markdown("**Seçili Öğrencinin Günlerini Toplu İşle**")

    # Öğrenci arama ve seçimi
    all_names = edited_df["Öğrenci"].astype(str).tolist()
    search_query = st.text_input("Öğrenci arama", placeholder="Öğrenci adını yazmaya başlayın...", key=f"search_{year}_{month}")
    if search_query:
        filtered_names = [n for n in all_names if search_query.lower() in n.lower()]
    else:
        filtered_names = all_names

    if not filtered_names:
        st.info("Arama kriterine uyan öğrenci bulunamadı.")
    else:
        col_sel, col_days, col_type = st.columns([2, 2, 1])
        with col_sel:
            selected_student = st.selectbox("Öğrenci seçin", options=filtered_names, key=f"student_sel_{year}_{month}")
        with col_days:
            days_text = st.text_input("Günler (örn: 1, 5, 12)", key=f"days_{year}_{month}")
        with col_type:
            mark_type = st.selectbox("Tür", options=["X", "E", "İ"], key=f"type_{year}_{month}")

        if st.button("Günleri İşle", key=f"apply_days_{year}_{month}"):
            days = parse_int_list_from_text(days_text)
            if not days:
                st.warning("Lütfen en az bir geçerli gün girin.")
            else:
                df_local = st.session_state[df_key].copy()
                day_cols_map = {}
                for d in range(1, days_in_month + 1):
                    w = date(year, month, d).weekday()
                    label = f"{d:02d} {weekday_labels[w]}"
                    day_cols_map[d] = label

                mask = df_local["Öğrenci"] == selected_student
                if not mask.any():
                    st.error("Seçilen öğrenci puantaj tablosunda bulunamadı.")
                else:
                    for d in days:
                        if 1 <= d <= days_in_month:
                            col_name = day_cols_map.get(d)
                            if col_name in df_local.columns:
                                df_local.loc[mask, col_name] = mark_type
                    st.session_state[df_key] = df_local
                    st.success("Günler tabloya işlendi.")
                    st.experimental_rerun()

    st.markdown("---")

    if st.button("Tamamla ve Kaydet"):
        try:
            final_df = st.session_state[df_key]
            excel_bytes = generate_puantaj_excel(final_df, year, month)
            save_puantaj_archive(excel_bytes, year, month)
            st.success("Puantaj arşive kaydedildi. Aşağıdan Excel olarak indirebilirsiniz.")

            file_name = f"puantaj_{year}_{month:02d}_{datetime.now().strftime('%Y%m%d_%H%M')}.xlsx"
            st.download_button(
                label="Excel'i İndir",
                data=excel_bytes,
                file_name=file_name,
                mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            )
        except Exception as e:
            st.error(f"Puantaj oluşturulurken hata oluştu: {e}")

    st.markdown("</div>", unsafe_allow_html=True)

# ============================================================
# ADMIN PANELİ
# ============================================================
def admin_view():
    st.markdown("### Yönetim Paneli")
    st.caption("Buradan bekleyen kullanıcıları onaylayabilir (operatör yapabilir) veya silebilirsiniz.")

    # Bekleyen kullanıcılar
    st.markdown("#### Onay Bekleyen Kullanıcılar")
    pending = list_unapproved_users()
    if not pending:
        st.info("Şu anda onay bekleyen kullanıcı yok.")
    else:
        for user_id, username, created_at in pending:
            c1, c2, c3 = st.columns([2, 1, 1])
            with c1:
                st.write(f"**{username}** – {created_at}")
            with c2:
                if st.button("Operatör Yap", key=f"approve_{user_id}"):
                    update_user_role(user_id, "operator")
                    st.success(f"{username} artık 'operator'.")
                    st.rerun()
            with c3:
                if st.button("Sil", key=f"delete_{user_id}"):
                    delete_user(user_id)
                    st.warning(f"{username} silindi.")
                    st.rerun()

    st.markdown("---")
    st.markdown("#### Tüm Kullanıcılar")
    users = list_all_users()
    if users:
        df_users = pd.DataFrame(
            users, columns=["id", "username", "role", "created_at"]
        )
        st.dataframe(df_users, use_container_width=True, hide_index=True)
    else:
        st.info("Sistemde hiç kullanıcı bulunmuyor.")


# ============================================================
# ÖĞRENCİ YÖNETİMİ
# ============================================================
def student_management_view():
    st.markdown("### Öğrenci Yönetimi")
    st.caption("Buradan öğrencileri bir defaya mahsus Excel ile veya manuel olarak ekleyip silebilirsiniz.")

    st.markdown("#### Excel'den Öğrenci Yükle")
    uploaded = st.file_uploader(
        "Öğrenci listesi içeren Excel dosyasını seçin",
        type=["xlsx", "xls"],
        help="En az bir isim kolonu içeren Excel yükleyin.",
        key="students_excel",
    )

    if uploaded is not None:
        try:
            df = pd.read_excel(uploaded)
            if df.empty:
                st.error("Yüklenen Excel boş görünüyor.")
            else:
                cols = list(df.columns)
                name_col = st.selectbox(
                    "Öğrenci isimlerinin bulunduğu kolon",
                    options=cols,
                    key="students_name_col",
                )
                if st.button("Excel'den Öğrencileri Kaydet"):
                    try:
                        bulk_add_students_from_names(df[name_col].tolist())
                        st.success("Öğrenciler başarıyla veritabanına kaydedildi.")
                    except Exception as e:
                        st.error(f"Öğrenciler kaydedilirken hata oluştu: {e}")
        except Exception as e:
            st.error(f"Excel okunurken hata oluştu: {e}")

    st.markdown("---")
    st.markdown("#### Manuel Öğrenci Ekle")

    col_add, col_btn = st.columns([3, 1])
    with col_add:
        new_student_name = st.text_input("Öğrenci Ad Soyad", key="manual_student_name")
    with col_btn:
        if st.button("Öğrenci Ekle"):
            try:
                add_student(new_student_name)
                st.success("Öğrenci eklendi (veya zaten mevcutsa atlandı).")
            except ValueError as ve:
                st.error(str(ve))
            except Exception as e:
                st.error(f"Öğrenci eklenirken hata oluştu: {e}")

    st.markdown("---")
    st.markdown("#### Kayıtlı Öğrenciler")

    students = list_students(active_only=False)
    total_count = len(students)

    st.markdown(f"**Kayıtlı öğrenci sayısı:** {total_count}")

    if not students:
        st.info("Henüz öğrenci kaydı yok.")
        return

    # Toplu silme arayüzü
    id_name_status = []
    for student in students:
        if len(student) == 3:
            student_id, name, active = student
        else:
            student_id, name = student
            active = 1
        id_name_status.append((student_id, name, active))

    name_to_id = {name: sid for sid, name, _ in id_name_status}
    all_names = [name for sid, name, _ in id_name_status]

    st.markdown("##### Toplu Öğrenci Sil")
    selected_names = st.multiselect(
        "Silmek istediğiniz öğrencileri seçin",
        options=all_names,
        key="multi_delete_students",
    )
    if st.button("Seçili Öğrencileri Sil"):
        if not selected_names:
            st.warning("Lütfen en az bir öğrenci seçin.")
        else:
            for name in selected_names:
                sid = name_to_id.get(name)
                if sid is not None:
                    delete_student(sid)
            st.success("Seçili öğrenciler silindi.")
            st.experimental_rerun()

    st.markdown("---")
    st.markdown("##### Kayıtlı Öğrenciler (Tek Tek Silme)")

    students = list_students(active_only=False)
    if not students:
        st.info("Henüz öğrenci kaydı yok.")
        return

    for student in students:
        if len(student) == 3:
            student_id, name, active = student
        else:
            student_id, name = student
            active = 1
        c1, c2, c3 = st.columns([4, 1, 1])
        with c1:
            status = "Aktif" if active else "Pasif"
            st.write(f"**{name}** ({status})")
        with c3:
            if st.button("Sil", key=f"del_student_{student_id}"):
                delete_student(student_id)
                st.warning(f"{name} silindi.")
                st.experimental_rerun()

# ============================================================
# UNAPPROVED EKRANI
# ============================================================
def unapproved_view(username: str):
    st.markdown("### Hesabınız Onay Bekliyor")
    st.markdown(
        f"Merhaba **{username}**,\
        hesabınız şu anda **'onay bekliyor (unapproved)'** durumunda. "
        "Bir admin hesabınızı 'Operatör' olarak onayladığında puantaj ekranına erişebileceksiniz."
    )
    st.info("Lütfen daha sonra tekrar giriş yapmayı deneyin veya yöneticinizle iletişime geçin.")

# ============================================================
# ANA ROUTING
# ============================================================
def main():
    user_count = get_user_count()

    # İlk kurulum: hiç kullanıcı yoksa Süper Admin ekranı
    if user_count == 0:
        super_admin_setup_view()
        return

    # Giriş yapmamışsa auth ekranı
    if st.session_state.user is None:
        auth_view()
        return

    # Giriş yapmışsa – üstte kısa bilgi & logout
    with st.sidebar:
        st.markdown("### Oturum Bilgisi")
        st.write(f"**Kullanıcı:** {st.session_state.user['username']}")
        st.write(f"**Rol:** {st.session_state.user['role']}")
        logout_button()

        st.markdown("---")
        st.markdown("### Geçmiş Puantajlar")
        archives = list_puantaj_archives()
        if not archives:
            st.caption("Henüz kaydedilmiş puantaj yok.")
        else:
            for arch_id, year, month, file_path, created_at in archives[:10]:
                label = f"{year}-{month:02d} – {created_at.strftime('%Y-%m-%d %H:%M')}"
                try:
                    with open(file_path, "rb") as f:
                        data = f.read()
                    st.download_button(
                        label=label,
                        data=data,
                        file_name=os.path.basename(file_path),
                        mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                        key=f"arch_{arch_id}",
                    )
                except Exception:
                    st.write(f"{label} (dosya bulunamadı)")

    role = st.session_state.user["role"]

    # Rol tabanlı yönlendirme
    # Not: "Süper Admin" de teknik olarak ilk oluşturulan admin'dir.
    # Bu nedenle admin rolüne hem puantaj hem de yönetim paneli yetkisi veriyoruz.
    if role in ("admin", "operator"):
        if role == "admin":
            tabs = st.tabs(["Puantaj", "Öğrenci Yönetimi", "Yönetim Paneli"])
            with tabs[0]:
                puantaj_view()
            with tabs[1]:
                student_management_view()
            with tabs[2]:
                admin_view()
        else:  # operator
            tabs = st.tabs(["Puantaj", "Öğrenci Yönetimi"])
            with tabs[0]:
                puantaj_view()
            with tabs[1]:
                student_management_view()
    elif role == "unapproved":
        unapproved_view(st.session_state.user["username"])
    else:
        st.error("Bilinmeyen rol. Lütfen yöneticinizle iletişime geçin.")

if __name__ == "__main__":
    main()