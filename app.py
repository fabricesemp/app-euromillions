import streamlit as st
import pandas as pd
import zipfile
import csv
import random
import os
import time
import requests
import altair as alt
from collections import Counter
from datetime import datetime

st.set_page_config(page_title="Générer tirages", page_icon="💎", layout="wide")

class AssistantFDJ:
    def __init__(self, jeu="EuroMillions"):
        self.jeu = jeu
        # Configuration dynamique selon le jeu choisi
        if self.jeu == "EuroMillions":
            self.max_num = 50
            self.max_spe = 12
            self.nb_spe_a_tirer = 2
            self.nom_spe = "Étoile(s)"
            self.icone_spe = "⭐"
            self.fichier_cache = "historique_euromillions_master.csv"
            self.fichier_tickets = "mes_tickets_euromillions.csv"
        else: # Loto
            self.max_num = 49
            self.max_spe = 10
            self.nb_spe_a_tirer = 1
            self.nom_spe = "Chance"
            self.icone_spe = "🍀"
            self.fichier_cache = "historique_loto_master.csv"
            self.fichier_tickets = "mes_tickets_loto.csv"

        self.numeros_possibles = list(range(1, self.max_num + 1))
        self.speciaux_possibles = list(range(1, self.max_spe + 1))
        self.tirages_numeros = []
        self.tirages_speciaux = []
        self.dates_tirages = []
        self.nombres_premiers = [2, 3, 5, 7, 11, 13, 17, 19, 23, 29, 31, 37, 41, 43, 47]

    def charger_donnees(self):
        if not os.path.exists(self.fichier_cache): return False
        
        with open(self.fichier_cache, 'r', encoding='utf-8') as f:
            lecteur = list(csv.DictReader(f.readlines(), delimiter=';'))
            lecteur.reverse()
            for ligne in lecteur:
                try:
                    num = [int(ligne[f'boule_{i}']) for i in range(1, 6)]
                    if self.jeu == "EuroMillions":
                        spe = [int(ligne[f'etoile_{i}']) for i in range(1, 3)]
                    else:
                        # Gère les différentes écritures des fichiers FDJ Loto
                        cle_chance = 'numero_chance' if 'numero_chance' in ligne else 'chance'
                        spe = [int(ligne[cle_chance])]
                        
                    date = ligne.get('date_de_tirage', 'Date Inconnue')
                    self.tirages_numeros.append(num)
                    self.tirages_speciaux.append(spe)
                    self.dates_tirages.append(date)
                except:
                    continue
        return len(self.tirages_numeros) > 0

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
            t_courant, t_suivant = self.tirages_numeros[i], self.tirages_numeros[i+1]
            for n_c in t_courant:
                for n_s in t_suivant:
                    matrice[n_c][n_s] += 1
        return matrice

    def generer_grille(self, strategie, configs):
        stats_num = self.calculer_stats(self.tirages_numeros, self.numeros_possibles)
        stats_spe = self.calculer_stats(self.tirages_speciaux, self.speciaux_possibles)

        p_num = [0] * len(self.numeros_possibles)
        if strategie == "Prédictif (IA Markov)":
            matrice = self.construire_matrice_markov()
            dernier_tirage = self.tirages_numeros[-1]
            for n in self.numeros_possibles:
                p_num[n-1] = sum(matrice[last_n][n] for last_n in dernier_tirage)
        elif strategie == "Chauds": p_num = [stats_num[n]['freq'] for n in self.numeros_possibles]
        elif strategie == "Froids": p_num = [stats_num[n]['ecart'] for n in self.numeros_possibles]
        else: p_num = [stats_num[n]['freq'] * (stats_num[n]['ecart'] + 1) for n in self.numeros_possibles]

        p_spe = [stats_spe[e]['freq'] * (stats_spe[e]['ecart'] + 1) for e in self.speciaux_possibles]

        grille_trouvee = False
        while not grille_trouvee:
            num = []
            dispos, p = self.numeros_possibles.copy(), p_num.copy()
            while len(num) < 5:
                if sum(p) == 0: p = [1]*len(p)
                c = random.choices(dispos, weights=p, k=1)[0]
                num.append(c)
                idx = dispos.index(c)
                dispos.pop(idx); p.pop(idx)
            num.sort()
            if self.filtres_experts(num, configs): grille_trouvee = True
        
        spe = []
        dispos_spe, p_s = self.speciaux_possibles.copy(), p_spe.copy()
        while len(spe) < self.nb_spe_a_tirer:
            if sum(p_s) == 0: p_s = [1]*len(p_s)
            c = random.choices(dispos_spe, weights=p_s, k=1)[0]
            spe.append(c)
            idx = dispos_spe.index(c)
            dispos_spe.pop(idx); p_s.pop(idx)
            
        return sorted(num), sorted(spe)

    def backtester(self, num, spe):
        max_n, max_s = 0, 0
        for t_n, t_s in zip(self.tirages_numeros, self.tirages_speciaux):
            m_n = len(set(num) & set(t_n))
            m_s = len(set(spe) & set(t_s))
            if m_n > max_n: max_n, max_s = m_n, m_s
            elif m_n == max_n and m_s > max_s: max_s = m_s
        return max_n, max_s

    def estimer_gain_officiel(self, match_n, match_s):
        if self.jeu == "EuroMillions":
            if match_n == 5 and match_s == 2: return 50000000
            if match_n == 5 and match_s == 1: return 300000
            if match_n == 5 and match_s == 0: return 30000
            if match_n == 4 and match_s == 2: return 3000
            if match_n == 4 and match_s == 1: return 150
            if match_n == 4 and match_s == 0: return 50
            if match_n == 3 and match_s == 2: return 100
            if match_n == 3 and match_s == 1: return 15
            if match_n == 3 and match_s == 0: return 12
            if match_n == 2 and match_s == 2: return 20
            if match_n == 2 and match_s == 1: return 6
            if match_n == 2 and match_s == 0: return 4
            if match_n == 1 and match_s == 2: return 7
        else: # Loto
            if match_n == 5 and match_s == 1: return 2000000
            if match_n == 5 and match_s == 0: return 100000
            if match_n == 4 and match_s == 1: return 1000
            if match_n == 4 and match_s == 0: return 500
            if match_n == 3 and match_s == 1: return 50
            if match_n == 3 and match_s == 0: return 20
            if match_n == 2 and match_s == 1: return 10
            if match_n == 2 and match_s == 0: return 5
            if match_n == 1 and match_s == 1: return 2.20
            if match_n == 0 and match_s == 1: return 2.20
        return 0

def envoyer_telegram(token, chat_id, message):
    url = f"https://api.telegram.org/bot{token}/sendMessage"
    try:
        return requests.post(url, data={"chat_id": chat_id, "text": message, "parse_mode": "Markdown"}).ok
    except: return False

# --- UI GLOBALE ---
st.sidebar.markdown("### 🎰 Sélecteur de Jeu")
jeu_selectionne = st.sidebar.radio("Quel jeu analyser ?", ["EuroMillions", "Loto"])
st.sidebar.markdown("---")

app = AssistantFDJ(jeu=jeu_selectionne)

# Gestion du changement de jeu
if "jeu_actuel" not in st.session_state or st.session_state.jeu_actuel != jeu_selectionne:
    st.session_state.jeu_actuel = jeu_selectionne
    st.session_state.dernieres_grilles = []

# --- ECRAN D'INITIALISATION ---
if not app.charger_donnees():
    st.title(f"🛡️ Initialisation Base de Données {app.jeu}")
    st.info(f"Veuillez télécharger les archives du **{app.jeu}** sur le site de la FDJ et les glisser ici.")
    fichiers = st.file_uploader(f"Archives ZIP {app.jeu}", type=['zip', 'csv'], accept_multiple_files=True)
    if fichiers and st.button("Installer la base de données", type="primary"):
        with open(app.fichier_cache, 'w', encoding='utf-8') as f_cache:
            for fichier in fichiers:
                if fichier.name.endswith('.zip'):
                    with zipfile.ZipFile(fichier, 'r') as archive:
                        for nom in archive.namelist():
                            if nom.endswith('.csv'):
                                contenu = archive.open(nom).read().decode('cp1252')
                                if not contenu.endswith('\n'): contenu += '\n'
                                f_cache.write(contenu)
        st.success(f"Base {app.jeu} installée ! Démarrage..."); time.sleep(1); st.rerun()
    st.stop()

# --- MENU LATÉRAL ---
st.sidebar.title("⚙️ Filtres d'Experts")
configs_filtres = {
    'somme': st.sidebar.checkbox("✅ Somme (90 - 160)", value=True),
    'pair': st.sidebar.checkbox("⚖️ Équilibre Pair/Impair", value=True),
    'consecutif': st.sidebar.checkbox("❌ Pas de suites", value=True),
    'premier': st.sidebar.checkbox("🔢 Forcer 1 nb premier", value=True)
}
st.sidebar.markdown("---")
st.sidebar.title("📲 Telegram")
tele_token = st.sidebar.text_input("Token du Bot", type="password")
tele_chat_id = st.sidebar.text_input("Chat ID", type="password")

# --- INTERFACE PRINCIPALE ---
st.title(f"💎 Tableau de Bord {app.jeu} Pro")
ong1, ong2, ong3 = st.tabs(["🎲 Générateur", "🌡️ Heatmap & Stats", "💸 Budget & Gains"])

with ong1:
    c1, c2 = st.columns(2)
    with c1: strat = st.selectbox("Stratégie", ["Prédictif (IA Markov)", "Mixte (Recommandé)", "Chauds", "Froids"])
    with c2: nb_g = st.slider("Nombre de grilles", 1, 10, 1)

    if st.button("🚀 Générer des grilles", type="primary"):
        st.session_state.dernieres_grilles = [app.generer_grille(strat, configs_filtres) for _ in range(nb_g)]

    if st.session_state.dernieres_grilles:
        st.markdown("---")
        for i, (num, spe) in enumerate(st.session_state.dernieres_grilles):
            hn, hs = app.backtester(num, spe)
            st.info(f"**Grille {i+1} :**  \n🔢 Numéros : {', '.join(map(str, num))}  \n{app.icone_spe} {app.nom_spe} : {', '.join(map(str, spe))}")
            st.caption(f"🕰️ *Meilleur historique : {hn} bon(s) numéro(s) et {hs} {app.nom_spe.lower()}.*")
        
        b1, b2 = st.columns(2)
        with b1:
            if st.button("💾 Enregistrer dans le portefeuille"):
                with open(app.fichier_tickets, 'a', encoding='utf-8') as ft:
                    d_str = datetime.now().strftime("%d/%m/%Y %H:%M")
                    for num, spe in st.session_state.dernieres_grilles:
                        ft.write(f"{d_str};{','.join(map(str, num))};{','.join(map(str, spe))}\n")
                st.success("Tickets sauvegardés !")
        with b2:
            if st.button("📲 M'envoyer sur Telegram"):
                if tele_token and tele_chat_id:
                    msg = f"🎲 *Vos Grilles {app.jeu} ({strat})* 🎲\n\n"
                    for i, (n, s) in enumerate(st.session_state.dernieres_grilles):
                        msg += f"🎫 *Grille {i+1} :* [ {'-'.join(map(str, n))} ] {app.icone_spe} [ {'-'.join(map(str, s))} ]\n"
                    if envoyer_telegram(tele_token, tele_chat_id, msg): st.success("Envoyé !")
                    else: st.error("Erreur d'envoi.")

with ong2:
    st.write(f"Analyse basée sur **{len(app.tirages_numeros)} tirages**.")
    stats_n = app.calculer_stats(app.tirages_numeros, app.numeros_possibles)
    
    st.subheader("🌡️ Heatmap des Numéros")
    data_h = [{"Numéro": n, "X": (n-1)%10, "Y": (n-1)//10, "Sorties": stats_n[n]['freq']} for n in app.numeros_possibles]
    heatmap = alt.Chart(pd.DataFrame(data_h)).mark_rect().encode(
        x=alt.X('X:O', axis=None), y=alt.Y('Y:O', axis=alt.Axis(title=None, labels=False, ticks=False)),
        color=alt.Color('Sorties:Q', scale=alt.Scale(scheme='redblue', reverse=True)), tooltip=['Numéro', 'Sorties']
    ).properties(height=300)
    st.altair_chart(heatmap + heatmap.mark_text(baseline='middle').encode(text='Numéro:O', color=alt.value('white')), use_container_width=True)
    
    if st.button(f"🗑️ Réinitialiser la base {app.jeu}"):
        os.remove(app.fichier_cache); st.rerun()

with ong3:
    st.header("💸 Budget & Gains")
    d_num, d_spe = app.tirages_numeros[-1], app.tirages_speciaux[-1]
    st.info(f"🏆 **Dernier Résultat ({app.dates_tirages[-1]}) :** {', '.join(map(str, d_num))} | {app.icone_spe} {', '.join(map(str, d_spe))}")
    
    if os.path.exists(app.fichier_tickets):
        with open(app.fichier_tickets, 'r', encoding='utf-8') as ft: lignes = ft.readlines()
        cout_grille = 2.50 if app.jeu == "EuroMillions" else 2.20
        depenses, gains = len(lignes) * cout_grille, 0
        
        st.subheader("Vos tickets :")
        for ligne in lignes:
            try:
                date, n_str, s_str = ligne.strip().split(';')
                mes_n, mes_s = [int(x) for x in n_str.split(',')], [int(x) for x in s_str.split(',')]
                m_n, m_s = len(set(mes_n) & set(d_num)), len(set(mes_s) & set(d_spe))
                gain = app.estimer_gain_officiel(m_n, m_s)
                gains += gain
                if gain > 0: st.success(f"🎫 [ {','.join(map(str, mes_n))} ] {app.icone_spe} [ {','.join(map(str, mes_s))} ] -> **+ {gain} € !**")
                else: st.markdown(f"🎫 [ {','.join(map(str, mes_n))} ] {app.icone_spe} [ {','.join(map(str, mes_s))} ] -> *Perdant*")
            except: pass
        
        bilan = gains - depenses
        c1, c2, c3 = st.columns(3)
        c1.metric("Investissement", f"- {depenses:.2f} €")
        c2.metric("Gains Estimés", f"+ {gains:.2f} €")
        c3.metric("Bilan (ROI)", f"{bilan:.2f} €", delta=f"{bilan:.2f} €", delta_color="normal" if bilan>=0 else "inverse")
        if st.button("🗑️ Vider le portefeuille"): os.remove(app.fichier_tickets); st.rerun()
    else: st.info(f"Aucun ticket {app.jeu} sauvegardé.")
