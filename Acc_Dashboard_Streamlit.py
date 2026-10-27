"""
RoadSafe Chicago — Dashboard Streamlit
Lancement depuis la racine du projet :  .venv/bin/python -m streamlit run Acc_Dashboard_Streamlit.py
Le script retrouve seul la racine du projet, quel que soit le dossier où il est placé.
"""

from pathlib import Path

import numpy as np
import pandas as pd
import plotly.express as px
import streamlit as st

st.set_page_config(page_title="RoadSafe Chicago", layout="wide")

def trouver_racine():
    """Remonte depuis l'emplacement du script jusqu'à la racine du projet."""
    ici = Path(__file__).resolve()
    for parent in [ici.parent, *ici.parents]:
        if (parent / "Notebooks").exists() or (parent / ".venv").exists():
            return parent
    return ici.parent


ROOT = trouver_racine()
FIG_DIR = ROOT / "reports" / "figures"

LUM_MAP = {
    "DAYLIGHT": "Jour",
    "DARKNESS, LIGHTED ROAD": "Nuit éclairée",
    "DARKNESS": "Nuit non éclairée",
    "DUSK": "Aube / crépuscule",
    "DAWN": "Aube / crépuscule",
}
JOURS = {1: "Dimanche", 2: "Lundi", 3: "Mardi", 4: "Mercredi", 5: "Jeudi", 6: "Vendredi", 7: "Samedi"}
ORDRE_JOURS = ["Lundi", "Mardi", "Mercredi", "Jeudi", "Vendredi", "Samedi", "Dimanche"]
MOIS = ["Jan", "Fév", "Mar", "Avr", "Mai", "Juin", "Juil", "Août", "Sep", "Oct", "Nov", "Déc"]


# ---------------------------------------------------------------------------
# Données
# ---------------------------------------------------------------------------
NOM_FICHIER = "fact_crashes_2024.parquet"


def trouver_fichier():
    """Cherche la table de faits (hors cache, pour détecter un fichier créé après le lancement)."""
    for dossier in ["data", "Data"]:
        chemin = ROOT / dossier / "analytics" / NOM_FICHIER
        if chemin.exists():
            return chemin
    # Recherche élargie dans le projet, si le fichier a été exporté ailleurs
    trouves = [p for p in ROOT.rglob(NOM_FICHIER) if ".venv" not in p.parts]
    return trouves[0] if trouves else None


@st.cache_data
def charger_donnees(chemin: str):
    """Lecture mise en cache : seul un fichier existant est mémorisé."""
    df = pd.read_parquet(chemin)
    df["lum_groupe"] = df["lighting_condition"].astype(str).map(LUM_MAP).fillna("Inconnue")
    df["jour"] = df["crash_day_of_week"].map(JOURS)
    df["crash_date"] = pd.to_datetime(df["crash_date"])
    return df


def wilson(k, n, z=1.96):
    p = k / n
    denom = 1 + z**2 / n
    centre = (p + z**2 / (2 * n)) / denom
    marge = z * np.sqrt(p * (1 - p) / n + z**2 / (4 * n**2)) / denom
    return centre - marge, centre + marge


def taux_par(d, col, min_n):
    """Taux d'accidents graves par modalité, avec effectif et IC à 95 %."""
    g = (d.dropna(subset=["is_severe"])
           .groupby(col, observed=True)["is_severe"]
           .agg(n="count", k="sum").astype(float))
    g = g[(g["n"] >= min_n) & (g.index.astype(str) != "UNKNOWN")].copy()
    if g.empty:
        return g
    g["taux"] = g["k"] / g["n"] * 100
    bas, haut = wilson(g["k"], g["n"])
    g["err_moins"] = g["taux"] - bas * 100
    g["err_plus"] = haut * 100 - g["taux"]
    g.index = g.index.astype(str)
    return g.sort_values("taux")


chemin_donnees = trouver_fichier()
if chemin_donnees is None:
    st.error(f"Fichier `{NOM_FICHIER}` introuvable dans le projet `{ROOT}`. "
             "Exécute d'abord la section 6 du notebook 08.")
    st.stop()

df = charger_donnees(str(chemin_donnees))


# ---------------------------------------------------------------------------
# Filtres
# ---------------------------------------------------------------------------
st.sidebar.title("Filtres")

mois = st.sidebar.slider("Mois", 1, 12, (1, 12), format="%d")
lum_options = ["Jour", "Nuit éclairée", "Nuit non éclairée", "Aube / crépuscule", "Inconnue"]
lum_choix = st.sidebar.multiselect("Luminosité", lum_options, default=lum_options)
periode = st.sidebar.radio("Période", ["Tous les jours", "Semaine", "Week-end"])

top_types = df["first_crash_type"].astype(str).value_counts().drop("UNKNOWN", errors="ignore").head(10).index
types_choix = st.sidebar.multiselect("Types de collision (vide = tous)", list(top_types))

d = df[df["crash_month"].between(*mois) & df["lum_groupe"].isin(lum_choix)]
if periode == "Semaine":
    d = d[~d["is_weekend"].astype(bool)]
elif periode == "Week-end":
    d = d[d["is_weekend"].astype(bool)]
if types_choix:
    d = d[d["first_crash_type"].astype(str).isin(types_choix)]

st.sidebar.caption(f"{len(d):,} accidents sélectionnés".replace(",", " "))
st.sidebar.markdown("---")
st.sidebar.caption("Source : City of Chicago Open Data — Traffic Crashes (API Socrata), 2024.")

if d.empty:
    st.warning("Aucun accident ne correspond aux filtres sélectionnés.")
    st.stop()


# ---------------------------------------------------------------------------
# En-tête et KPI
# ---------------------------------------------------------------------------
st.title("RoadSafe Chicago")
st.markdown("*Comment évoluent la fréquence et la gravité des accidents routiers à Chicago, "
            "et quels facteurs sont associés à leur gravité ?*")

n_total = d["crash_record_id"].nunique()
n_blesses = int(d["is_injury"].fillna(False).sum())
n_graves = int(d["is_severe"].fillna(False).sum())
n_mortels = int(d["is_fatal"].fillna(False).sum())
taux_global = d["is_severe"].mean() * 100

k1, k2, k3, k4, k5 = st.columns(5)
k1.metric("Accidents", f"{n_total:,}".replace(",", " "))
k2.metric("Avec blessés", f"{n_blesses:,}".replace(",", " "))
k3.metric("Graves", f"{n_graves:,}".replace(",", " "))
k4.metric("Mortels", f"{n_mortels:,}".replace(",", " "))
k5.metric("Taux d'accidents graves", f"{taux_global:.2f} %")

st.caption("Accident grave : accident mortel ou avec au moins un blessé grave (incapacitating). "
           "Le taux exclut les accidents sans information sur les blessures.")

onglet1, onglet2, onglet3, onglet4 = st.tabs(
    ["Vue d'ensemble", "Analyse spatiale", "Contexte et gravité", "Enseignements"]
)


# ---------------------------------------------------------------------------
# Onglet 1 — Vue d'ensemble
# ---------------------------------------------------------------------------
with onglet1:
    st.subheader("Évolution quotidienne des accidents")
    serie = d.groupby(d["crash_date"].dt.date).size().rename("accidents").to_frame()
    serie["moyenne mobile 7 jours"] = serie["accidents"].rolling(7, center=True).mean()
    fig = px.line(serie, labels={"value": "Accidents par jour", "crash_date": "", "variable": ""})
    fig.update_traces(selector=dict(name="accidents"), line=dict(width=1), opacity=0.4)
    st.plotly_chart(fig, use_container_width=True)

    col_a, col_b = st.columns(2)

    with col_a:
        st.subheader("Accidents par heure")
        par_heure = d["crash_hour"].value_counts().sort_index()
        fig = px.bar(x=par_heure.index, y=par_heure.values,
                     labels={"x": "Heure", "y": "Nombre d'accidents"})
        fig.update_traces(marker_color="steelblue")
        st.plotly_chart(fig, use_container_width=True)

    with col_b:
        st.subheader("Rythme de la semaine")
        heat = (d.pivot_table(index="jour", columns="crash_hour", values="crash_record_id", aggfunc="count")
                  .reindex(ORDRE_JOURS))
        fig = px.imshow(heat, color_continuous_scale="YlOrRd", aspect="auto",
                        labels={"x": "Heure", "y": "", "color": "Accidents"})
        st.plotly_chart(fig, use_container_width=True)


# ---------------------------------------------------------------------------
# Onglet 2 — Analyse spatiale
# ---------------------------------------------------------------------------
with onglet2:
    st.subheader("Où se produisent les accidents ?")
    choix = st.radio("Accidents affichés", ["Tous les accidents", "Accidents graves uniquement"], horizontal=True)

    carte = d[d["geo_valid"].fillna(False)]
    if choix == "Accidents graves uniquement":
        carte = carte[carte["is_severe"].fillna(False)]
    if len(carte) > 40000:
        carte = carte.sample(40000, random_state=0)
        st.caption("Échantillon aléatoire de 40 000 accidents affiché, pour la fluidité de la carte.")

    fig = px.density_map(carte, lat="latitude", lon="longitude", radius=6,
                         center={"lat": 41.84, "lon": -87.68}, zoom=9.6,
                         map_style="open-street-map", height=620)
    fig.update_layout(margin=dict(l=0, r=0, t=0, b=0), coloraxis_showscale=False)
    st.plotly_chart(fig, use_container_width=True)

    st.info("Une zone qui concentre beaucoup d'accidents n'est pas forcément plus dangereuse : "
            "elle est souvent simplement plus fréquentée. Sans données de trafic, "
            "on parle de concentration d'accidents, pas de risque.")

    st.subheader("Secteurs de police : volume ou gravité ?")
    min_n = st.slider("Effectif minimum par secteur", 50, 500, 100, step=50)
    secteurs = taux_par(d, "beat_of_occurrence", min_n)

    if secteurs.empty:
        st.warning("Aucun secteur n'atteint l'effectif minimum avec ces filtres.")
    else:
        col_a, col_b = st.columns(2)
        with col_a:
            top_v = secteurs.nlargest(10, "n").sort_values("n")
            fig = px.bar(top_v, x="n", y=top_v.index, orientation="h",
                         labels={"n": "Nombre d'accidents", "y": "Secteur"},
                         title="Top 10 par nombre d'accidents")
            fig.update_traces(marker_color="steelblue")
            st.plotly_chart(fig, use_container_width=True)
        with col_b:
            top_t = secteurs.nlargest(10, "taux").sort_values("taux")
            fig = px.bar(top_t, x="taux", y=top_t.index, orientation="h",
                         error_x="err_plus", error_x_minus="err_moins",
                         labels={"taux": "% d'accidents graves", "y": "Secteur"},
                         title="Top 10 par taux d'accidents graves")
            fig.update_traces(marker_color="crimson")
            fig.add_vline(x=taux_global, line_dash="dash", annotation_text="Moyenne")
            st.plotly_chart(fig, use_container_width=True)

        communs = set(top_v.index) & set(top_t.index)
        st.caption(f"Secteurs présents dans les deux classements : {', '.join(sorted(communs)) or 'aucun'}.")


# ---------------------------------------------------------------------------
# Onglet 3 — Contexte et gravité
# ---------------------------------------------------------------------------
with onglet3:
    st.subheader("Quelle part des accidents est grave, selon le contexte ?")

    variables = {
        "Luminosité": "lum_groupe",
        "Limite de vitesse affichée": "speed_class",
        "Type de collision": "first_crash_type",
        "Météo": "weather_condition",
        "État de la chaussée": "roadway_surface_cond",
        "Tranche horaire": "time_slot",
        "Saison": "season",
    }
    col_a, col_b = st.columns([3, 1])
    variable = col_a.selectbox("Variable analysée", list(variables))
    min_n_ctx = col_b.number_input("Effectif minimum", 50, 2000, 200, step=50)

    base = d[d["speed_valid"].fillna(False)] if variables[variable] == "speed_class" else d
    g = taux_par(base, variables[variable], min_n_ctx)
    g = g[g.index != "Inconnue"]

    if g.empty:
        st.warning("Pas assez d'accidents pour afficher cette variable avec ces filtres.")
    else:
        fig = px.bar(g, x="taux", y=g.index, orientation="h",
                     error_x="err_plus", error_x_minus="err_moins",
                     hover_data={"n": ":,.0f"},
                     labels={"taux": "% d'accidents graves", "y": "", "n": "Accidents"},
                     height=max(350, 45 * len(g)))
        fig.update_traces(marker_color="steelblue")
        fig.add_vline(x=taux_global, line_dash="dash", line_color="crimson",
                      annotation_text=f"Moyenne : {taux_global:.2f} %")
        st.plotly_chart(fig, use_container_width=True)
        st.caption("Barres d'erreur : intervalle de confiance à 95 % (méthode de Wilson). "
                   "Les modalités inconnues et les groupes sous l'effectif minimum sont exclus.")


# ---------------------------------------------------------------------------
# Onglet 4 — Enseignements
# ---------------------------------------------------------------------------
with onglet4:
    st.subheader("Principaux enseignements (régression logistique, 2024)")

    st.markdown("""
1. **Le type de collision est le facteur dominant.** Un accident impliquant un piéton a environ
   **8 fois plus de chances** d'être grave qu'une collision à angle droit, à autres facteurs égaux.
2. **La limite de vitesse affichée suit un gradient de gravité.** Les voies à 45 mph et plus
   présentent une gravité près de 2 fois supérieure aux voies à 25-30 mph ; les voies à 20 mph
   ou moins, une gravité divisée par plus de deux.
3. **La nuit reste associée à une gravité plus élevée** après ajustement sur la vitesse,
   le type de collision, la météo et la période.
4. **L'éclairage public n'apparaît pas protecteur**, mais ce résultat reflète probablement un
   facteur de confusion : les voies éclairées sont les axes les plus fréquentés.
5. **Le mauvais temps n'aggrave pas la gravité** : la pluie et la neige ne sont pas
   significativement associées à des accidents plus graves.
""")

    forest = FIG_DIR / "07_odds_ratios.png"
    if forest.exists():
        st.image(str(forest), caption="Odds ratios et intervalles de confiance à 95 %")

    st.subheader("Pistes d'action")
    st.markdown("""
- Prioriser la **sécurisation des traversées piétonnes**, en particulier sur les axes à 35 mph et plus.
- Examiner les **secteurs à fort taux de gravité**, distincts des secteurs à fort volume d'accidents.
- Cibler les **nuits du week-end** dans les actions de prévention.
""")

    st.subheader("Limites")
    st.markdown("""
- **Pas de données d'exposition** : les résultats décrivent la gravité des accidents survenus,
  pas le risque d'avoir un accident.
- **Facteurs individuels absents** : vitesse réelle, alcool, port de la ceinture, âge des victimes.
- **Conditions et causes déclarées par la police**, sans vérification ultérieure.
- **Une seule année d'observation**, et une association statistique ne démontre pas une causalité.
""")