import streamlit as st
import sqlite3
import pandas as pd
import urllib.parse
from datetime import datetime

st.set_page_config(page_title="Amatér Open Liga", page_icon="🎾", layout="wide")

# --- NAČTENÍ PŘÍSTUPŮ K SUPABASE ZE STREAMLIT SECRETS ---
if "supabase_url" in st.secrets and "supabase_key" in st.secrets:
    SUPABASE_URL = st.secrets["supabase_url"]
    SUPABASE_KEY = st.secrets["supabase_key"]
else:
    st.error("Chyba: V nastavení Streamlit Cloud chybí přístupové údaje (Secrets) k databázi Supabase!")
    st.stop()

headers = {
    "apikey": SUPABASE_KEY,
    "Authorization": f"Bearer {SUPABASE_KEY}",
    "Content-Type": "application/json",
    "Prefer": "return=representation"
}

# --- FUNKCE PRO KOMUNIKACI S DATABÁZÍ ---
def supabase_query(table, method="GET", json_data=None, params=None):
    url = f"{SUPABASE_URL}/rest/v1/{table}"
    try:
        with httpx.Client() as client:
            if method == "GET":
                response = client.get(url, headers=headers, params=params)
            elif method == "POST":
                response = client.post(url, headers=headers, json=json_data)
            elif method == "PATCH":
                response = client.patch(url, headers=headers, json=json_data, params=params)
            elif method == "DELETE":
                response = client.delete(url, headers=headers, params=params)
            return response.json() if response.status_code in [200, 201] else []
    except Exception:
        return []

# Načtení seznamu lig
ligy_data = supabase_query("ligy")
vsechny_ligy = {}
dnes = datetime.now().date()

for l in ligy_data:
    l_id = l.get("id")
    nazev = l.get("nazev")
    od_d = l.get("od_datum")
    do_d = l.get("do_datum")
    
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

# --- NAVIGACE A VÝBĚR LIGY ---
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
    # --- 1. ŽEBŘÍČEK ---
    if volba == "📊 Žebříček ligy":
        st.header("Aktuální pořadí hráčů")
        hraci_data = supabase_query("hraci", params={"liga_id": f"eq.{liga_id}", "order": "body.desc"})
        if hraci_data:
            df_hraci = pd.DataFrame(hraci_data)[["jmeno", "body"]]
            df_hraci.columns = ["Hráč", "Body"]
            df_hraci.index = df_hraci.index + 1
            st.table(df_hraci)
        else:
            st.info("V této lize zatím nejsou žádní hráči.")
        
        st.subheader("Historie odehraných zápasů")
        zapasy_data = supabase_query("zapasy", params={"liga_id": f"eq.{liga_id}", "order": "id.desc"})
        if zapasy_data:
            df_zapasy = pd.DataFrame(zapasy_data)[["id", "datum", "vitez1", "vitez2", "porazeny1", "porazeny2", "vysledek", "body_za_zapas"]]
            df_zapasy.columns = ["ID", "Datum", "Vítěz 1", "Vítěz 2", "Poražený 1", "Poražený 2", "Výsledek", "Body za zápas"]
            st.dataframe(df_zapasy, use_container_width=True, hide_index=True)
        else:
            st.info("Zatím žádné zápasy.")
 # --- 2. ZÁPIS VÝSLEDKŮ ---
    elif volba == "📝 Zadat výsledek":
        st.header("Zápis odehraného zápasu")
        if liga_stav == "[UKONČENÁ]":
            st.error("❌ Tato liga již byla oficiálně ukončena. Výsledky zápasů nelze zpětně zapisovat.")
        elif liga_stav == "[NEZAČALA]":
            st.warning("⏳ Tato liga ještě nezačala. Zápis výsledků bude povolen až po oficiálním datu zahájení.")
        else:
            hraci_list = supabase_query("hraci", params={"liga_id": f"eq.{liga_id}", "order": "jmeno.asc"})
            seznam_hracu = [h["jmeno"] for h in hraci_list]
            
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
                        dup = supabase_query("zapasy", params={
                            "liga_id": f"eq.{liga_id}",
                            "vitez1": f"in.(\"{v1}\",\"{v2}\")",
                            "vitez2": f"in.(\"{v1}\",\"{v2}\")",
                            "porazeny1": f"in.(\"{p1}\",\"{p2}\")",
                            "porazeny2": f"in.(\"{p1}\",\"{p2}\")"
                        })
                        if dup:
                            st.error("Chyba: Zápas ve stejném složení už existuje!")
                        else:
                            bp1 = next((h["body"] for h in hraci_list if h["jmeno"] == p1), 1.0)
                            bp2 = next((h["body"] for h in hraci_list if h["jmeno"] == p2), 1.0)
                            zisk = (bp1 + bp2) / 2
                            
                            novy_zapas = {
                                "liga_id": liga_id, "datum": datum_zapasu.strftime('%d.%m.%Y'),
                                "vitez1": v1, "vitez2": v2, "porazeny1": p1, "porazeny2": p2,
                                "vysledek": vysledek, "body_za_zapas": zisk
                            }
                            supabase_query("zapasy", method="POST", json_data=novy_zapas)
                            
                            h1_obj = next(h for h in hraci_list if h["jmeno"] == v1)
                            h2_obj = next(h for h in hraci_list if h["jmeno"] == v2)
                            supabase_query("hraci", method="PATCH", json_data={"body": h1_obj["body"] + zisk}, params={"id": f"eq.{h1_obj['id']}"})
                            supabase_query("hraci", method="PATCH", json_data={"body": h2_obj["body"] + zisk}, params={"id": f"eq.{h2_obj['id']}"})
                            
                            st.success("Zápas úspěšně uložen!")
                            st.rerun()

    # --- 3. PRAVIDLA LIGY ---
    elif volba == "📜 Pravidla ligy":
        st.header(f"Podmínky a pravidla pro: {zvolena_liga_nazev}")
        l_info = supabase_query("ligy", params={"id": f"eq.{liga_id}"})
        if l_info and len(l_info) > 0:
            liga_item = l_info[0]
            pravidla_text = liga_item.get("pravidla")
            od_d = liga_item.get("od_datum")
            do_d = liga_item.get("do_datum")
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
        nova_liga_nazev = st.text_input("Název nové ligy")
        c_od, c_do = st.columns(2)
        with c_od: nova_od = st.date_input("Datum zahájení", datetime.now())
        with c_do: nova_do = st.date_input("Datum ukončení", datetime.now())
            
        if st.button("Vytvořit ligu"):
            if nova_liga_nazev.strip() != "":
                str_od = nova_od.strftime('%d.%m.%Y')
                str_do = nova_do.strftime('%d.%m.%Y')
                novaliga = {"nazev": nova_liga_nazev.strip(), "pravidla": "Zde doplňte pravidla.", "od_datum": str_od, "do_datum": str_do}
                supabase_query("ligy", method="POST", json_data=novaliga)
                st.success("Liga vytvořena!")
                st.rerun()

        if liga_id is not None:
            st.markdown("---")
            st.subheader(f"📝 Upravit termín a pravidla ligy: {zvolena_liga_nazev}")
            l_curr = supabase_query("ligy", params={"id": f"eq.{liga_id}"})
            p_text = l_curr[0].get("pravidla") if l_curr else ""
            novy_text_pravidel = st.text_area("Text pravidel ligy", p_text, height=200)
            if st.button("Uložit změny ligy"):
                supabase_query("ligy", method="PATCH", json_data={"pravidla": novy_text_pravidel}, params={"id": f"eq.{liga_id}"})
                st.success("Uloženo!")
                st.rerun()

            st.markdown("---")
            st.subheader(f"➕ Registrace nového hráče do: {zvolena_liga_nazev}")
            nove_jmeno = st.text_input("Jméno a příjmení hráče")
            if st.button("Zaregistrovat hráče"):
                if nove_jmeno.strip() != "":
                    supabase_query("hraci", method="POST", json_data={"liga_id": liga_id, "jmeno": nove_jmeno.strip(), "body": 1.0})
                    st.success("Hráč přidán!")
                    st.rerun()

            st.markdown("---")
            st.subheader(f"❌ Smazat hráče z ligy: {zvolena_liga_nazev}")
            hraci_del = supabase_query("hraci", params={"liga_id": f"eq.{liga_id}", "order": "jmeno.asc"})
            if hraci_del:
                hrac_ke_smazani = st.selectbox("Vyberte hráče k odstranění:", [h["jmeno"] for h in hraci_del])
                if st.button("Definitivně smazat hráče"):
                    h_obj = next(h for h in hraci_del if h["jmeno"] == hrac_ke_smazani)
                    supabase_query("hraci", method="DELETE", params={"id": f"eq.{h_obj['id']}"})
                    st.success("Hráč vymazán.")
                    st.rerun()

            st.markdown("---")
            st.subheader(f"🗑️ Smazat zápas z ligy: {zvolena_liga_nazev}")
            zapasy_del = supabase_query("zapasy", params={"liga_id": f"eq.{liga_id}", "order": "id.desc"})
            if zapasy_del:
                zapas_k_odstraneni = st.selectbox("Vyberte zápas ke smazání:", zapasy_del, format_func=lambda x: f"ID {x['id']} ({x['datum']}): {x['vitez1']} + {x['vitez2']}")
                if st.button("❌ Smazat zápas"):
                    z_id = zapas_k_odstraneni['id']
                    v1 = zapas_k_odstraneni['vitez1']
                    v2 = zapas_k_odstraneni['vitez2']
                    o_body = zapas_k_odstraneni['body_za_zapas']
                    
                    hraci_list = supabase_query("hraci", params={"liga_id": f"eq.{liga_id}"})
                    h1_obj = next((h for h in hraci_list if h["jmeno"] == v1), None)
                    h2_obj = next((h for h in hraci_list if h["jmeno"] == v2), None)
                    
                    if h1_obj: supabase_query("hraci", method="PATCH", json_data={"body": max(1.0, h1_obj["body"] - o_body)}, params={"id": f"eq.{h1_obj['id']}"})
                    if h2_obj: supabase_query("hraci", method="PATCH", json_data={"body": max(1.0, h2_obj["body"] - o_body)}, params={"id": f"eq.{h2_obj['id']}"})
                    
                    supabase_query("zapasy", method="DELETE", params={"id": f"eq.{z_id}"})
                    st.success("Zápas smazán a body odečteny.")
                    st.rerun()
    elif heslo != "":
        st.error("Nesprávné heslo!")
