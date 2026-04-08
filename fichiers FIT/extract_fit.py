# -*- coding: utf-8 -*-
import os
import fitparse
import pandas as pd
import matplotlib.pyplot as plt
import seaborn as sns
import numpy as np
from sklearn.linear_model import LinearRegression

FICHIERS = {
    0.40: "fichiers FIT/04.fit",
    0.60: "fichiers FIT/06.fit",
    0.80: "fichiers FIT/08.fit",
    1.00: "fichiers FIT/10.fit",
    1.22: "fichiers FIT/12_2.fit",
    1.41: "fichiers FIT/14_1.fit",
}

BIN_SIZE = 5
MIN_COUNT = 2
DOSSIER_GRAPHS = "fichiers FIT/graphs"

os.makedirs(DOSSIER_GRAPHS, exist_ok=True)


def extraire_fit(chemin):
    rows = []

    for record in fitparse.FitFile(chemin).get_messages("record"):
        data_dict = {}
        for data in record:
            if data.name in ["cadence", "power", "timestamp"]:
                data_dict[data.name] = data.value
        if data_dict:
            rows.append(data_dict)

    df = pd.DataFrame(rows)

    if df.empty:
        return pd.DataFrame(columns=["timestamp", "cadence", "power"])

    df["timestamp"] = pd.to_datetime(df["timestamp"], errors="coerce")
    df = df.sort_values("timestamp").reset_index(drop=True)
    df["power"] = pd.to_numeric(df["power"], errors="coerce")
    df["cadence"] = pd.to_numeric(df["cadence"], errors="coerce").ffill()

    df = df[(df["cadence"] > 0) & (df["power"] > 0)]
    df = df.dropna(subset=["timestamp", "cadence", "power"])

    return df


def binner(df):
    df = df.copy()
    df["cadence_bin"] = (df["cadence"] // BIN_SIZE) * BIN_SIZE

    bins = (
        df.groupby("cadence_bin")
        .agg(
            cadence_moy=("cadence", "mean"),
            power_moy=("power", "mean"),
            count=("power", "count"),
        )
        .reset_index()
        .sort_values("cadence_bin")
        .reset_index(drop=True)
    )

    return bins[bins["count"] >= MIN_COUNT].reset_index(drop=True)


all_data = {}

for position, chemin in FICHIERS.items():
    df = extraire_fit(chemin)
    all_data[position] = df

    if df.empty:
        print(f"Position {position} : aucune donnée exploitable dans {chemin}")
        continue

    fig, ax1 = plt.subplots(figsize=(10, 5))
    ax2 = ax1.twinx()

    ax1.plot(df["timestamp"], df["power"], color="steelblue")
    ax2.plot(df["timestamp"], df["cadence"], color="orange")

    ax1.set_xlabel("Temps")
    ax1.set_ylabel("Puissance [W]", color="steelblue")
    ax2.set_ylabel("Cadence [rpm]", color="orange")
    ax1.set_title(f"Position aimant : {position}")

    fig.tight_layout()
    plt.savefig(f"{DOSSIER_GRAPHS}/timeseries_{position}.png", dpi=100)
    plt.close()

sns.set_context("talk")
fig, ax = plt.subplots(figsize=(10, 6))
resultats = []

for position, df in all_data.items():
    if df.empty:
        continue

    bins = binner(df)

    print(f"\nPosition {position}")
    print(bins[["cadence_bin", "cadence_moy", "power_moy", "count"]])

    if len(bins) < 3:
        print(f"Position {position} ignorée : pas assez de bins ({len(bins)})")
        continue

    X = pd.DataFrame({"c": bins["cadence_moy"], "c2": bins["cadence_moy"] ** 2})
    y = bins["power_moy"]

    reg = LinearRegression(fit_intercept=False)
    reg.fit(X, y)

    a1, a2 = reg.coef_
    r2 = reg.score(X, y)

    resultats.append(
        {
            "position": position,
            "a1": round(a1, 4),
            "a2": round(a2, 6),
            "R2": round(r2, 4),
            "nb_bins": len(bins),
        }
    )

    scatter = ax.scatter(
        bins["cadence_moy"], bins["power_moy"], label=f"pos {position}", zorder=3
    )
    color = scatter.get_facecolor()[0]

    c_min = bins["cadence_moy"].min()
    c_max = bins["cadence_moy"].max()
    c_range = np.linspace(c_min, c_max, 100)

    X_pred = pd.DataFrame({"c": c_range, "c2": c_range**2})

    y_pred = reg.predict(X_pred)
    ax.plot(c_range, y_pred, color=color)

ax.set_xlabel("Cadence [rpm]")
ax.set_ylabel("Puissance [W]")
ax.set_title("Régression P = a1·c + a2·c² par position")
ax.legend(title="Position aimant")
ax.grid(True)

plt.tight_layout()
plt.savefig(f"{DOSSIER_GRAPHS}/regression_toutes_positions.png", dpi=100)
plt.close()

df_resultats = pd.DataFrame(resultats)

print("\n=== Résultats ===")
if df_resultats.empty:
    print("Aucun résultat exploitable.")
else:
    print(df_resultats.to_string(index=False))
