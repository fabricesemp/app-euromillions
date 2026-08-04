import streamlit as st
import pandas as pd
import urllib.request
import zipfile
import io
import csv
import random
import os
import time
import requests
import altair as alt
from collections import Counter
from datetime import datetime

st.set_page_config(page_title="EuroMillions Pro", page_icon="💎", layout="wide")

class EuroMillionsWeb:
    def __init__(self):
        self.numeros_possibles = list(range(1, 51))
        self.etoiles_possibles = list(range(1, 13))
        self.tirages_numeros = []
        self.tirages_etoiles = []
        self.dates_tirages = []
        self.nombres_premiers = [2, 3, 5, 7, 11, 13, 17, 19, 23, 29, 31, 37, 41, 43, 47]
        self.fichier_cache = "historique_euromillions_master.csv"
        self.fichier_tickets = "mes_tickets_sauvegardes.csv"

    def charger_donnees(self):
        with open(self.fichier_cache, 'r', encoding='utf-8') as f:
            lecteur = list(csv.DictReader(f.readlines(), delimiter=';'))
            lecteur.reverse()
            for ligne in lecteur:
                try:
                    num = [int(ligne[f'boule_{i}']) for i in range(1, 6)]
                    et = [int(ligne[f'etoile_{i}']) for i in range(1, 3)]
                    date = ligne.get('date_de_tirage', 'Date Inconnue')
                    self.tirages_numeros.append(num)
                    self.tirages_etoiles.append(et)
                    self.dates_tirages.append(date)
                except:
                    continue

    def filtres_experts(self, numeros, configs):
        if configs['somme'] and not (90 <= sum(numeros) <= 160): return False
        if configs['pair']:
            pairs = sum(1 for n in numeros if n % 2 == 0)
            if pairs not in [2, 3]: return False
        if configs['consecutif']:
            cons = 1
            for i in range(len(numeros) - 1):
                if numeros[i+1] == numeros[i] + 1:
                    cons += 1
                    if cons >= 3: return False
                else: cons = 1
        if configs['premier']:
            if sum(1 for n in numeros if n in self.nombres_premiers) < 1: return False
        return True

    def calculer_stats(self, historique, elements):
        stats = {num: {'freq': 0, 'ecart': 0} for num in elements}
        tous = [num for tirage in historique for num in tirage]
        compte = Counter(tous)
        for num in elements:
            stats[num]['freq'] = compte.get(num, 0)
            ecart = 0
            for tirage in reversed(historique):
                if num in tirage: break
                ecart += 1
            stats[num]['ecart'] = ecart
        return stats

    def construire_matrice_markov(self):
        matrice = {i: {j: 1 for j in self.numeros_possibles} for i in self.numeros_possibles}
        for i in range(len(self.tirages_numeros) - 1):
            tirage_courant = self.tirages_numeros[i]
            tirage_suivant = self.tirages_numeros[i+1]
            for n_courant in tirage_courant:
                for n_suivant in tirage_suivant:
                    matrice[n_courant][n_suivant] += 1
        return matrice

    def generer_grille(self, strategie, configs):
        stats_num = self.calculer_stats(self.tirages_numeros, self.numeros_possibles)
        stats_et = self.calculer_stats(self.tirages_etoiles, self.etoiles_possibles)

        p_num = [0] * len(self.numeros_possibles)
        
        if strategie == "Prédictif (IA Markov)":
            matrice = self.construire_matrice_markov()
            dernier_tirage = self.tirages_numeros[-1]
            for n in self.numeros_possibles:
                score = sum(matrice[last_n][n] for last_n in dernier_tirage)
                p_num[n-1] = score
        elif strategie == "Chauds":
            p_num = [stats_num[n]['freq'] for n in self.numeros_possibles]
        elif strategie == "Froids":
            p_num = [stats_num[n]['ecart'] for n in self.numeros_possibles]
        else:
            p_num = [stats_num[n]['freq'] * (stats_num[n]['ecart'] + 1) for n in self.numeros_possibles]

        p_et = [stats_et[e]['freq'] * (stats_et[e]['ecart'] + 1) for e in self.etoiles_possibles]

        grille_trouvee = False
        while not grille_trouvee:
            num = []
            dispos = self.numeros_possibles.copy()
            p = p_num.copy()
            while len(num) < 5:
                if sum(p) == 0: p = [1]*len(p)
                c = random.choices(dispos, weights=p, k=1)[0]
                num.append(c)
                idx = dispos.index(c)
                dispos.pop(idx)
                p.pop(idx)
            num.sort()
            
            if self.filtres_experts(num, configs):
                grille_trouvee = True
        
        et = []
        dispos_et = self.etoiles_possibles.copy()
        p_et_temp = p_et.copy()
        while len(et) < 2:
            if sum(p_et_temp) == 0: p_et_temp = [1]*len(p_et_temp)
            c = random.choices(dispos_et, weights=p_et_temp, k=1)[0]
            et.append(c)
            idx = dispos_et.index(c)
            dispos_et.pop(idx)
            p_et_temp.pop(idx)
            
        return sorted(num), sorted(et)

    def backtester(self, num, et):
        max_n, max_e = 0, 0
        for t_num, t_et in zip(self.tirages_numeros, self.tirages_etoiles):
            match_n = len(set(num) & set(t_num))
            match_e = len(set(et) & set(t_et))
            if match_n > max_n:
                max_n = match_n; max_e = match_e
            elif match_n == max_n and match_e > max_e:
                max_e = match_e
        return max_n, max_e

    def estimer_gain_officiel(self, match_n, match_e):
        if match_n == 5 and match_e == 2: return 50000000
        if match_n == 5 and match_e == 1: return 300000
        if match_n == 5 and match_e == 0: return 30000
        if match_n == 4 and match_e == 2: return 3000
        if match_n == 4 and match_e == 1: return 150
        if match_n == 4 and match_e == 0: return 50
        if match_n == 3 and match_e == 2: return 100
        if match_n == 3 and match_e == 1: return 15
        if match_n == 3 and match_e == 0: return 12
        if match_n == 2 and match_e == 2: return 20
        if match_n == 2 and match_e == 1: return 6
        if match_n == 2 and match_e == 0: return 4
        if match_n == 1 and match_e == 2: return 7
        return 0

def envoyer_telegram(token, chat_id, message):
    url = f"https://api.telegram.org/bot{token}/sendMessage"
    payload = {
        "chat_id": chat_id,
        "text": message,
        "parse_mode": "Markdown"
    }
    try:
        reponse = requests.post(url, data=payload)
        return reponse.ok
    except:
        return False

# --- INIT ---
fichier_cache = "historique_euromillions_master.csv"
if not os.path.exists(fichier_cache):
    st.title("🛡️ Initialisation")
    st.info("Veuillez glisser vos fichiers ZIP d'historique FDJ ici :")
    fichiers = st.file_uploader("Fichiers FDJ", type=['zip', 'csv'], accept_multiple_files=True)
    if fichiers and st.button("Fusionner", type="primary"):
        with open(fichier_cache, 'w', encoding='utf-8') as f_cache:
            for fichier in fichiers:
                if fichier.name.endswith('.zip'):
                    with zipfile.ZipFile(fichier, 'r') as archive:
                        for nom in archive.namelist():
                            if nom.endswith('.csv'):
                                contenu = archive.open(nom).read().decode('cp1252')
                                if not contenu.endswith('\n'): contenu += '\n'
                                f_cache.write(contenu)
        st.success("Installé ! Démarrage..."); time.sleep(1); st.rerun()
    st.stop()

app = EuroMillionsWeb()
app.charger_donnees()

if "dernieres_grilles" not in st.session_state:
    st.session_state.dernieres_grilles = []

# --- MENU LATÉRAL ---
st.sidebar.title("⚙️ Filtres d'Experts")
configs_filtres = {
    'somme': st.sidebar.checkbox("✅ Somme entre 90 et 160", value=True),
    'pair': st.sidebar.checkbox("⚖️ Équilibre Pair/Impair", value=True),
    'consecutif': st.sidebar.checkbox("❌ Pas de suites longues", value=True),
    'premier': st.sidebar.checkbox("🔢 Forcer 1 nombre premier", value=True)
}

st.sidebar.markdown("---")
st.sidebar.title("📲 Alertes Telegram")
st.sidebar.markdown("Configurez l'envoi vers votre téléphone :")
tele_token = st.sidebar.text_input("Token du Bot", type="password")
tele_chat_id = st.sidebar.text_input("Chat ID", type="password")

# --- INTERFACE PRINCIPALE ---
st.title("💎 Tableau de Bord EuroMillions Titan")
onglet1, onglet2, onglet3 = st.tabs(["🎲 Générateur", "🌡️ Heatmap & Stats", "💸 Budget & Gains"])

with onglet1:
    col1, col2 = st.columns(2)
    with col1:
        strategie = st.selectbox("Stratégie de pondération", ["Prédictif (IA Markov)", "Mixte (Recommandé)", "Chauds", "Froids"])
    with col2:
        nb_grilles = st.slider("Nombre de grilles", min_value=1, max_value=10, value=2)

    if st.button("🚀 Générer des grilles", type="primary"):
        st.session_state.dernieres_grilles = [app.generer_grille(strategie, configs_filtres) for _ in range(nb_grilles)]

    if st.session_state.dernieres_grilles:
        st.markdown("---")
        for i, (num, et) in enumerate(st.session_state.dernieres_grilles):
            hist_n, hist_e = app.backtester(num, et)
            st.info(f"**Grille {i+1} :**  \n🔢 Numéros : {', '.join(map(str, num))}  \n⭐ Étoiles : {', '.join(map(str, et))}")
            st.caption(f"🕰️ *Meilleur résultat passé : {hist_n} bon(s) numéro(s) et {hist_e} étoile(s).*")
        
        b1, b2 = st.columns(2)
        with b1:
            if st.button("💾 Enregistrer dans le portefeuille"):
                with open(app.fichier_tickets, 'a', encoding='utf-8') as ft:
                    date_str = datetime.now().strftime("%d/%m/%Y %H:%M")
                    for num, et in st.session_state.dernieres_grilles:
                        ligne = f"{date_str};{','.join(map(str, num))};{','.join(map(str, et))}\n"
                        ft.write(ligne)
                st.success("Tickets sauvegardés ! Regardez l'onglet 'Budget & Gains'.")
        
        with b2:
            if st.button("📲 M'envoyer ces grilles sur Telegram"):
                if tele_token and tele_chat_id:
                    msg = "🎲 *Vos Grilles EuroMillions (Stratégie: "+ strategie + ")* 🎲\n\n"
                    for i, (num, et) in enumerate(st.session_state.dernieres_grilles):
                        num_str = ' - '.join(map(str, num))
                        et_str = ' - '.join(map(str, et))
                        msg += f"🎫 *Grille {i+1} :* [ {num_str} ] ⭐ [ {et_str} ]\n"
                    
                    msg += "\n🍀 Bonne chance pour ce tirage !"
                    
                    if envoyer_telegram(tele_token, tele_chat_id, msg):
                        st.success("Message envoyé à votre téléphone !")
                    else:
                        st.error("Échec de l'envoi. Vérifiez le Token et le Chat ID.")
                else:
                    st.warning("⚠️ Renseignez votre Token et Chat ID dans le menu de gauche d'abord.")

with onglet2:
    st.write(f"Analyse basée sur **{len(app.tirages_numeros)} tirages officiels**.")
    stats_num = app.calculer_stats(app.tirages_numeros, app.numeros_possibles)
    
    st.subheader("🌡️ Carte Thermique des 50 Numéros (Heatmap)")
    
    data_heatmap = []
    for n in app.numeros_possibles:
        data_heatmap.append({
            "Numéro": n, 
            "X": (n-1) % 10, 
            "Y": (n-1) // 10, 
            "Sorties": stats_num[n]['freq']
        })
        
    df_heat = pd.DataFrame(data_heatmap)
    heatmap = alt.Chart(df_heat).mark_rect().encode(
        x=alt.X('X:O', axis=None),
        y=alt.Y('Y:O', axis=alt.Axis(title=None, labels=False, ticks=False)),
        color=alt.Color('Sorties:Q', scale=alt.Scale(scheme='redblue', reverse=True)),
        tooltip=['Numéro', 'Sorties']
    ).properties(height=300)
    
    texte = heatmap.mark_text(baseline='middle').encode(
        text='Numéro:O',
        color=alt.value('white')
    )
    st.altair_chart(heatmap + texte, use_container_width=True)

with onglet3:
    st.header("💸 Gestionnaire de Budget (ROI)")
    dernier_num = app.tirages_numeros[-1]
    dernier_et = app.tirages_etoiles[-1]
    date_dernier = app.dates_tirages[-1]
    
    st.markdown(f"### 🏆 Résultat FDJ de référence ({date_dernier})")
    st.info(f"**Numéros :** {', '.join(map(str, dernier_num))} | **Étoiles :** {', '.join(map(str, dernier_et))}")
    
    if os.path.exists(app.fichier_tickets):
        with open(app.fichier_tickets, 'r', encoding='utf-8') as ft:
            lignes = ft.readlines()
            
        depenses_totales = len(lignes) * 2.50
        gains_totaux = 0
        
        st.markdown("---")
        st.subheader("Vos tickets en portefeuille :")
        
        for ligne in lignes:
            try:
                date, n_str, e_str = ligne.strip().split(';')
                mes_n = [int(x) for x in n_str.split(',')]
                mes_e = [int(x) for x in e_str.split(',')]
                
                match_n = len(set(mes_n) & set(dernier_num))
                match_e = len(set(mes_e) & set(dernier_et))
                gain = app.estimer_gain_officiel(match_n, match_e)
                gains_totaux += gain
                
                if gain > 0:
                    st.success(f"🎫 [ {', '.join(map(str, mes_n))} ] ⭐ [ {', '.join(map(str, mes_e))} ] -> **Gain : + {gain} € !**")
                else:
                    st.markdown(f"🎫 [ {', '.join(map(str, mes_n))} ] ⭐ [ {', '.join(map(str, mes_e))} ] -> *Perdant*")
            except:
                pass
        
        st.markdown("---")
        bilan = gains_totaux - depenses_totales
        couleur_bilan = "normal" if bilan >= 0 else "inverse"
        
        c1, c2, c3 = st.columns(3)
        c1.metric(label="Investissement Total", value=f"- {depenses_totales:.2f} €")
        c2.metric(label="Gains Estimés", value=f"+ {gains_totaux:.2f} €")
        c3.metric(label="Bilan (ROI)", value=f"{bilan:.2f} €", delta=f"{bilan:.2f} €", delta_color=couleur_bilan)
        
        if st.button("🗑️ Vider le portefeuille"):
            os.remove(app.fichier_tickets); st.rerun()
    else:
        st.info("Aucun ticket joué. Allez dans le Générateur pour jouer vos premières grilles !")
