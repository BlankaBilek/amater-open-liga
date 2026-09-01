import streamlit as st
import sqlite3
import pandas as pd
import urllib.parse
from datetime import datetime

st.set_page_config(page_title="Amatér Open Liga", page_icon="🎾", layout="wide")

# --- DATABÁZE ---
conn = sqlite3.connect("tenis_liga_v3.db", check_same_thread=False)
cursor = conn.cursor()

cursor.execute("CREATE TABLE IF NOT EXISTS ligy (id INTEGER PRIMARY KEY AUTOINCREMENT, nazev TEXT UNIQUE, pravidla TEXT, od_datum TEXT, do_datum TEXT)")
cursor.execute("CREATE TABLE IF NOT EXISTS hraci (id INTEGER PRIMARY KEY AUTOINCREMENT, liga_id INTEGER, jmeno TEXT, body REAL DEFAULT 1.0, UNIQUE(liga_id, jmeno))")
cursor.execute("CREATE TABLE IF NOT EXISTS zapasy (id INTEGER PRIMARY KEY AUTOINCREMENT, liga_id INTEGER, datum TEXT, vitez1 TEXT, vitez2 TEXT, porazeny1 TEXT, porazeny2 TEXT, vysledek TEXT, body_za_zapas REAL)")
conn.commit()

try:
    cursor.execute("ALTER TABLE ligy ADD COLUMN od_datum TEXT")
    cursor.execute("ALTER TABLE ligy ADD COLUMN do_datum TEXT")
    conn.commit()
except sqlite3.OperationalError:
    pass

cursor.execute("SELECT id, nazev, od_datum, do_datum FROM ligy")
ligy_z_db = cursor.fetchall()

vsechny_ligy = {}
dnes = datetime.now().date()

for l_id, nazev, od_d, do_d in ligy_z_db:
    stav = "[AKTIVNÍ]"
    if od_d and do_d:
        try:
            d_od = datetime.strptime(od_d, "%d.%m.%Y").date()
            d_do = datetime.strptime(do_d, "%d.%m.%Y").date()
            if dnes < d_od: stav = "[NEZAČALA]"
            elif dnes > d_do: stav = "[UKONČENÁ]"
        except ValueError:
            pass
    zobrazeny_nazev = f"{nazev} {stav}"
    vsechny_ligy[zobrazeny_nazev] = {"id": l_id, "nazev_puvodni": nazev, "stav": stav}

st.sidebar.title("🎾 Nastavení ligy")

if list(vsechny_ligy.keys()):
    zvolena_liga_zobrazeni = st.sidebar.selectbox("Vyberte ligu:", list(vsechny_ligy.keys()))
    liga_id = vsechny_ligy[zvolena_liga_zobrazeni]["id"]
    zvolena_liga_nazev = vsechny_ligy[zvolena_liga_zobrazeni]["nazev_puvodni"]
    liga_stav = vsechny_ligy[zvolena_liga_zobrazeni]["stav"]
else:
    zvolena_liga_nazev = "Žádná aktivní liga"
    liga_id = None
    liga_stav = "[NEAKTIVNÍ]"

st.sidebar.markdown("---")
st.sidebar.title("Navigace")
volba = st.sidebar.radio("Kam chcete jít:", ["📊 Žebříček ligy", "📝 Zadat výsledek", "📜 Pravidla ligy", "⚙️ Administrace"])

st.title("🏆 Amatér Open Liga")
st.subheader(f"Soutěž: {zvolena_liga_nazev} {liga_stav}")

if liga_id is None:
    st.warning("V systému není žádná aktivní liga. Přejděte do Administrace.")
else:
    if volba == "📊 Žebříček ligy":
        st.header("Aktuální pořadí hráčů")
        df_hraci = pd.read_sql_query("SELECT jmeno as 'Hráč', body as 'Body' FROM hraci WHERE liga_id = ? ORDER BY body DESC", conn, params=(liga_id,))
        df_hraci.index = df_hraci.index + 1
        st.table(df_hraci)
        
        st.subheader("Historie odehraných zápasů")
        df_zapasy = pd.read_sql_query("SELECT id as 'ID', datum as 'Datum', vitez1 as 'Vítěz 1', vitez2 as 'Vítěz 2', porazeny1 as 'Poražený 1', porazeny2 as 'Poražený 2', vysledek as 'Výsledek', body_za_zapas as 'Body za zápas' FROM zapasy WHERE liga_id = ? ORDER BY id DESC", conn, params=(liga_id,))
        if not df_zapasy.empty:
            st.dataframe(df_zapasy, use_container_width=True, hide_index=True)
        else:
            st.info("Zatím žádné zápasy.")

    elif volba == "📝 Zadat výsledek":
        st.header("Zápis odehraného zápasu")
        if liga_stav == "[UKONČENÁ]":
            st.error("❌ Tato liga již byla oficiálně ukončena. Výsledky zápasů nelze zpětně zapisovat.")
        elif liga_stav == "[NEZAČALA]":
            st.warning("⏳ Tato liga ještě nezačala. Zápis výsledků bude povolen až po oficiálním datu zahájení.")
        else:
            cursor.execute("SELECT jmeno FROM hraci WHERE liga_id = ? ORDER BY jmeno", (liga_id,))
            seznam_hracu = [r[0] for r in cursor.fetchall()]
            
            if len(seznam_hracu) < 4:
                st.warning("Musíte mít alespoň 4 hráče pro zápis deblu.")
            else:
                col1, col2 = st.columns(2)
                with col1:
                    v1 = st.selectbox("Vítěz 1", seznam_hracu, key="v1")
                    v2 = st.selectbox("Vítěz 2", seznam_hracu, key="v2")
                with col2:
                    p1 = st.selectbox("Poražený 1", seznam_hracu, key="p1")
                    p2 = st.selectbox("Poražený 2", seznam_hracu, key="p2")
                vysledek = st.text_input("Výsledek (např. 6:4, 4:6, 6:2)")
                datum_zapasu = st.date_input("Datum", datetime.now())

                if st.button("Uložit zápas"):
                    if len({v1, v2, p1, p2}) < 4:
                        st.error("Chyba: Hráči musí být rozdílní!")
                    else:
                        cursor.execute("SELECT COUNT(*) FROM zapasy WHERE liga_id = ? AND ((vitez1 = ? AND vitez2 = ?) OR (vitez1 = ? AND vitez2 = ?)) AND ((porazeny1 = ? AND porazeny2 = ?) OR (porazeny1 = ? AND porazeny2 = ?))", (liga_id, v1, v2, v2, v1, p1, p2, p2, p1))
                        if cursor.fetchone()[0] > 0:
                            st.error("Chyba: Zápas ve stejném složení už existuje!")
                        else:
                            cursor.execute("SELECT body FROM hraci WHERE liga_id = ? AND jmeno = ?", (liga_id, p1))
                            bp1 = cursor.fetchone()[0]
                            cursor.execute("SELECT body FROM hraci WHERE liga_id = ? AND jmeno = ?", (liga_id, p2))
                            bp2 = cursor.fetchone()[0]
                            zisk = (bp1 + bp2) / 2
                            
                            cursor.execute("INSERT INTO zapasy (liga_id, datum, vitez1, vitez2, porazeny1, porazeny2, vysledek, body_za_zapas) VALUES (?, ?, ?, ?, ?, ?, ?, ?)", (liga_id, datum_zapasu.strftime('%d.%m.%Y'), v1, v2, p1, p2, vysledek, zisk))
                            cursor.execute("UPDATE hraci SET body = body + ? WHERE liga_id = ? AND jmeno = ?", (zisk, liga_id, v1))
                            cursor.execute("UPDATE hraci SET body = body + ? WHERE liga_id = ? AND jmeno = ?", (zisk, liga_id, v2))
                            conn.commit()
                            st.success("Zápas úspěšně uložen!")
                            st.rerun()
    # --- 3. PRAVIDLA LIGY ---
    elif volba == "📜 Pravidla ligy":
        st.header(f"Podmínky a pravidla pro: {zvolena_liga_nazev}")
        cursor.execute("SELECT pravidla, od_datum, do_datum FROM ligy WHERE id = ?", (liga_id,))
        liga_info = cursor.fetchone()
        
        if liga_info:
            pravidla_text, od_d, do_d = liga_info
            if od_d and do_d:
                st.info(f"📅 **Období konání ligy:** od {od_d} do {do_d}")
            st.markdown(pravidla_text if pravidla_text else "Zatím nebyl zadán žádný text pravidel.")

# --- 4. ADMINISTRACE ---
if volba == "⚙️ Administrace":
    st.header("Sekce pro správce ligy")
    heslo = st.text_input("Zadejte administrátorské heslo", type="password")
    
    if heslo == "karanymaster":
        st.success("Přístup povolen!")
        
        st.subheader("🗂️ Vytvořit NOVOU ligu s termínem")
        nova_liga_nazev = st.text_input("Název nové ligy (např. 'Káranská deblová liga - 2026')")
        
        c_od, c_do = st.columns(2)
        with c_od:
            nova_od = st.date_input("Datum zahájení", datetime.now())
        with c_do:
            nova_do = st.date_input("Datum ukončení", datetime.now())
            
        if st.button("Vytvořit ligu"):
            if nova_liga_nazev.strip() != "":
                try:
                    str_od = nova_od.strftime('%d.%m.%Y')
                    str_do = nova_do.strftime('%d.%m.%Y')
                    cursor.execute("INSERT INTO ligy (nazev, pravidla, od_datum, do_datum) VALUES (?, 'Zde doplňte pravidla této ligy.', ?, ?)", (nova_liga_nazev.strip(), str_od, str_do))
                    conn.commit()
                    st.success(f"Liga '{nova_liga_nazev}' byla úspěšně vytvořena!")
                    st.rerun()
                except sqlite3.IntegrityError:
                    st.error("Liga s tímto názvem již existuje!")

        if liga_id is not None:
            st.markdown("---")
            st.subheader(f"📝 Upravit termín a pravidla ligy: {zvolena_liga_nazev}")
            cursor.execute("SELECT pravidla, od_datum, do_datum FROM ligy WHERE id = ?", (liga_id,))
            res_p = cursor.fetchone()
            
            p_text = res_p[0] if res_p and res_p[0] else ""
            p_od = datetime.strptime(res_p[1], "%d.%m.%Y").date() if res_p and res_p[1] else datetime.now().date()
            p_do = datetime.strptime(res_p[2], "%d.%m.%Y").date() if res_p and res_p[2] else datetime.now().date()
            
            c_u1, c_u2 = st.columns(2)
            with c_u1:
                u_od = st.date_input("Změnit datum zahájení", p_od)
            with c_u2:
                u_do = st.date_input("Změnit datum ukončení", p_do)
                
            novy_text_pravidel = st.text_area("Text pravidel ligy (můžete používat i formátování)", p_text, height=200)
            
            if st.button("Uložit změny ligy"):
                str_u_od = u_od.strftime('%d.%m.%Y')
                str_u_do = u_do.strftime('%d.%m.%Y')
                cursor.execute("UPDATE ligy SET pravidla = ?, od_datum = ?, do_datum = ? WHERE id = ?", (novy_text_pravidel, str_u_od, str_u_do, liga_id))
                conn.commit()
                st.success("Změny ligy byly úspěšně uloženy!")
                st.rerun()

            st.markdown("---")
            st.subheader(f"➕ Registrace nového hráče do: {zvolena_liga_nazev}")
            nove_jmeno = st.text_input("Jméno a příjmení hráče")
            if st.button("Zaregistrovat hráče"):
                if nove_jmeno.strip() != "":
                    try:
                        cursor.execute("INSERT INTO hraci (liga_id, jmeno, body) VALUES (?, ?, 1.0)", (liga_id, nove_jmeno.strip()))
                        conn.commit()
                        st.success(f"Hráč byl úspěšně přidán do ligy!")
                        st.rerun()
                    except sqlite3.IntegrityError:
                        st.error("Tento hráč již v této lize existuje!")

            st.markdown("---")
            # --- NOVÁ PODSEKCE: SMAZÁNÍ HRÁČE ---
            st.subheader(f"❌ Smazat hráče z ligy: {zvolena_liga_nazev}")
            cursor.execute("SELECT jmeno FROM hraci WHERE liga_id = ? ORDER BY jmeno", (liga_id,))
            seznam_smazani = [r[0] for r in cursor.fetchall()]
            
            if seznam_smazani:
                hrac_ke_smazani = st.selectbox("Vyberte hráče, kterého chcete odstranit:", seznam_smazani)
                if st.button("Definitivně smazat hráče z ligy"):
                    cursor.execute("DELETE FROM hraci WHERE liga_id = ? AND jmeno = ?", (liga_id, hrac_ke_smazani))
                    conn.commit()
                    st.success(f"Hráč {hrac_ke_smazani} byl úspěšně vymazán z ligy.")
                    st.rerun()
            else:
                st.info("V této lize zatím nejsou žádní hráči.")

            st.markdown("---")
            st.subheader(f"🗑️ Smazat zápas z ligy: {zvolena_liga_nazev}")
            cursor.execute("SELECT id, datum, vitez1, vitez2, vysledek FROM zapasy WHERE liga_id = ? ORDER BY id DESC", (liga_id,))
            vsechny_zapasy = cursor.fetchall()
            
            if vsechny_zapasy:
                zapas_k_odstraneni = st.selectbox(
                    "Vyberte zápas ke smazání:", 
                    vsechny_zapasy, 
                    format_func=lambda x: f"ID {x[0]} (Datum: {x[1]}): {x[2]} + {x[3]} - Výsledek: {x[4]}"
                )
                if st.button("❌ Smazat zápas"):
                    zapas_id = zapas_k_odstraneni[0]
                    cursor.execute("SELECT vitez1, vitez2, body_za_zapas FROM zapasy WHERE id = ?", (zapas_id,))
                    v1, v2, odecitane_body = cursor.fetchone()
                    cursor.execute("UPDATE hraci SET body = body - ? WHERE liga_id = ? AND jmeno = ?", (odecitane_body, liga_id, v1))
                    cursor.execute("UPDATE hraci SET body = body - ? WHERE liga_id = ? AND jmeno = ?", (odecitane_body, liga_id, v2))
                    cursor.execute("DELETE FROM zapasy WHERE id = ?", (zapas_id,))
                    conn.commit()
                    st.success("Zápas byl smazán a body byly odečteny.")
                    st.rerun()
    elif heslo != "":
        st.error("Nesprávné heslo!")
