import streamlit as st
import pandas as pd
from datetime import datetime
import httpx

st.set_page_config(page_title="Amatér Open Liga", page_icon="🎾", layout="wide")

if "supabase_url" in st.secrets and "supabase_key" in st.secrets:
    SUPABASE_URL = st.secrets["supabase_url"]
    SUPABASE_KEY = st.secrets["supabase_key"]
else:
    st.error("Chyba: V nastavení Streamlit Cloud chybí přístupové údaje k Supabase!")
    st.stop()

headers = {
    "apikey": SUPABASE_KEY,
    "Authorization": f"Bearer {SUPABASE_KEY}",
    "Content-Type": "application/json",
    "Prefer": "return=representation"
}

def supabase_query(table, method="GET", json_data=None, params=None):
    url = f"{SUPABASE_URL}/rest/v1/{table}"
    try:
        with httpx.Client() as client:
            if method == "GET": response = client.get(url, headers=headers, params=params)
            elif method == "POST": response = client.post(url, headers=headers, json=json_data)
            elif method == "PATCH": response = client.patch(url, headers=headers, json=json_data, params=params)
            elif method == "DELETE": response = client.delete(url, headers=headers, params=params)
            
            # --- ZDE JE 100% OPRAVA SYNTAXE ---
            if response.status_code in [200,201]:
                data = response.json()
                return [data] if isinstance(data, dict) else data
            return []
    except Exception:
        return []

ligy_data = supabase_query("ligy")
vsechny_ligy = {}
dnes = datetime.now().date()

if ligy_data and isinstance(ligy_data, list):
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
                if d_od and dnes < d_od: stav = "[NEZAČALA]"
                elif d_do and dnes > d_do: stav = "[UKONČENÁ]"
            except ValueError: pass
        vsechny_ligy[f"{nazev} {stav}"] = {"id": l_id, "nazev_puvodni": nazev, "stav": stav}

st.sidebar.title("🎾 Nastavení ligy")
if list(vsechny_ligy.keys()):
    zvolena_liga_zobrazeni = st.sidebar.selectbox("Vyberte ligu:", list(vsechny_ligy.keys()))
    liga_id = vsechny_ligy[zvolena_liga_zobrazeni]["id"]
    zvolena_liga_nazev = vsechny_ligy[zvolena_liga_zobrazeni]["nazev_puvodni"]
    liga_stav = vsechny_ligy[zvolena_liga_zobrazeni]["stav"]
else:
    zvolena_liga_nazev, liga_id, liga_stav = "Žádná aktivní liga", None, "[NEAKTIVNÍ]"

st.sidebar.markdown("---")
volba = st.sidebar.radio("Navigace:", ["📊 Žebříček ligy", "📝 Zadat výsledek", "📜 Pravidla ligy", "⚙️ Administrace"])

st.title("🏆 Amatér Open Liga")
st.subheader(f"Soutěž: {zvolena_liga_nazev} {liga_stav}")
if liga_id is None and volba != "⚙️ Administrace":
    st.warning("V systému není žádná aktivní liga. Založte ji v Administraci.")
else:
    if volba == "📊 Žebříček ligy":
        st.header("Aktuální pořadí hráčů")
        hraci_data = supabase_query("hraci", params={"liga_id": f"eq.{liga_id}", "order": "body.desc"})
        if hraci_data and isinstance(hraci_data, list) and len(hraci_data) > 0:
            df_hraci = pd.DataFrame(hraci_data)[["jmeno", "body"]]
            df_hraci.columns = ["Hráč", "Body"]
            df_hraci.index = df_hraci.index + 1
            st.table(df_hraci)
        else: st.info("V této lize zatím nejsou žádní hráči.")
        
        st.subheader("Historie odehraných zápasů")
        zapasy_data = supabase_query("zapasy", params={"liga_id": f"eq.{liga_id}", "order": "id.desc"})
        if zapasy_data and isinstance(zapasy_data, list) and len(zapasy_data) > 0:
            df_zapasy = pd.DataFrame(zapasy_data)[["id", "datum", "vitez1", "vitez2", "porazeny1", "porazeny2", "vysledek", "body_za_zapas"]]
            df_zapasy.columns = ["ID", "Datum", "Vítěz 1", "Vítěz 2", "Poražený 1", "Poražený 2", "Výsledek", "Body za zápas"]
            st.dataframe(df_zapasy, use_container_width=True, hide_index=True)
        else: st.info("Zatím žádné zápasy.")

    elif volba == "📝 Zadat výsledek":
        st.header("Zápis odehraného zápasu")
        if liga_stav == "[UKONČENÁ]": st.error("❌ Tato liga již byla oficiálně ukončena.")
        elif liga_stav == "[NEZAČALA]": st.warning("⏳ Tato liga ještě nezačala.")
        else:
            hraci_list = supabase_query("hraci", params={"liga_id": f"eq.{liga_id}", "order": "jmeno.asc"})
            seznam_hracu = [h["jmeno"] for h in hraci_list] if hraci_list else []
            if len(seznam_hracu) < 4: st.warning("Musíte mít alespoň 4 hráče.")
            else:
                col1, col2 = st.columns(2)
                with col1:
                    v1 = st.selectbox("Vítěz 1", seznam_hracu, key="v1")
                    v2 = st.selectbox("Vítěz 2", seznam_hracu, key="v2")
                with col2:
                    p1 = st.selectbox("Poražený 1", seznam_hracu, key="p1")
                    p2 = st.selectbox("Poražený 2", seznam_hracu, key="p2")
                vysledek = st.text_input("Výsledek")
                datum_zapasu = st.date_input("Datum", datetime.now())

                if st.button("Uložit zápas"):
                    if len({v1, v2, p1, p2}) < 4: st.error("Hráči musí být rozdílní!")
                    else:
                        bp1 = next((h["body"] for h in hraci_list if h["jmeno"] == p1), 1.0)
                        bp2 = next((h["body"] for h in hraci_list if h["jmeno"] == p2), 1.0)
                        zisk = (bp1 + bp2) / 2
                        supabase_query("zapasy", method="POST", json_data={"liga_id": liga_id, "datum": datum_zapasu.strftime('%d.%m.%Y'), "vitez1": v1, "vitez2": v2, "porazeny1": p1, "porazeny2": p2, "vysledek": vysledek, "body_za_zapas": zisk})
                        h1_obj = next(h for h in hraci_list if h["jmeno"] == v1)
                        h2_obj = next(h for h in hraci_list if h["jmeno"] == v2)
                        supabase_query("hraci", method="PATCH", json_data={"body": h1_obj["body"] + zisk}, params={"id": f"eq.{h1_obj['id']}"})
                        supabase_query("hraci", method="PATCH", json_data={"body": h2_obj["body"] + zisk}, params={"id": f"eq.{h2_obj['id']}"})
                        st.success("Zápas úspěšně uložen!")
                        st.rerun()

    elif volba == "📜 Pravidla ligy":
        st.header(f"Podmínky a pravidla pro: {zvolena_liga_nazev}")
        l_info = supabase_query("ligy", params={"id": f"eq.{liga_id}"})
        if l_info:
            liga_item = l_info[0] if isinstance(l_info, list) and len(l_info) > 0 else l_info
            # --- TADY JE OPRAVENÉ OBSAHUJE OCHRANU PŘED PÁDEM ---
            pravidla_text = liga_item.get("pravidla") if isinstance(liga_item, dict) else ""
            od_d = liga_item.get("od_datum") if isinstance(liga_item, dict) else ""
            do_d = liga_item.get("do_datum") if isinstance(liga_item, dict) else ""
            if od_d and do_d:
                st.info(f"📅 **Období konání ligy:** od {od_d} do {do_d}")
            st.markdown(pravidla_text if pravidla_text else "Žádný text pravidel.")
    # --- 4. ADMINISTRACE ---
if volba == "⚙️ Administrace":
    st.header("Sekce pro správce ligy")
    heslo = st.text_input("Zadejte administrátorské heslo", type="password")
    if heslo == "karanymaster":
        st.success("Přístup povolen!")
        st.subheader("🗂️ Vytvořit NOVOU ligu")
        nova_liga_nazev = st.text_input("Název nové ligy")
        c_od, c_do = st.columns(2)
        with c_od: nova_od = st.date_input("Datum zahájení", datetime.now())
        with c_do: nova_do = st.date_input("Datum ukončení", datetime.now())
        if st.button("Vytvořit ligu"):
            if nova_liga_nazev.strip() != "":
                supabase_query("ligy", method="POST", json_data={"nazev": nova_liga_nazev.strip(), "pravidla": "Zde doplňte pravidla.", "od_datum": nova_od.strftime('%d.%m.%Y'), "do_datum": nova_do.strftime('%d.%m.%Y')})
                st.success("Liga vytvořena!")
                st.rerun()

        st.markdown("---")
        st.subheader("🗑️ Definitivně smazat CELOU ligu")
        if list(vsechny_ligy.keys()):
            liga_k_odstraneni_nazev = st.selectbox("Vyberte ligu ke smazání:", list(vsechny_ligy.keys()), key="l_del")
            potvrzeni_smazani = st.checkbox(f"Potvrzuji smazání ligy: {liga_k_odstraneni_nazev}", key="l_check")
            if st.button("🔥 NEVRATNĚ SMAZAT LIGU"):
                if potvrzeni_smazani:
                    supabase_query("ligy", method="DELETE", params={"id": f"eq.{vsechny_ligy[liga_k_odstraneni_nazev]['id']}"})
                    st.success("Liga byla úspěšně smazána.")
                    st.rerun()
                else: st.error("Zaškrtněte potvrzovací políčko!")

        if liga_id is not None:
            st.markdown("---")
            st.subheader(f"📝 Upravit pravidla ligy: {zvolena_liga_nazev}")
            l_curr = supabase_query("ligy", params={"id": f"eq.{liga_id}"})
            l_curr_item = l_curr if (l_curr and len(l_curr) > 0) else None
            p_text = l_curr_item.get("pravidla") if isinstance(l_curr_item, dict) else ""
            novy_text_pravidel = st.text_area("Text pravidel", p_text, height=150)
            if st.button("Uložit změny pravidel"):
                supabase_query("ligy", method="PATCH", json_data={"pravidla": novy_text_pravidel}, params={"id": f"eq.{liga_id}"})
                st.success("Změny uloženy!")
                st.rerun()

            st.markdown("---")
            st.subheader(f"➕ Registrace hráče do: {zvolena_liga_nazev}")
            nove_jmeno = st.text_input("Jméno a příjmení")
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
                if st.button("Smazat hráče"):
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
                    supabase_query("zapasy", method="DELETE", params={"id": f"eq.{zapas_k_odstraneni['id']}"})
                    st.success("Zápas smazán.")
                    st.rerun()
    elif heslo != "": st.error("Nesprávné heslo!")
