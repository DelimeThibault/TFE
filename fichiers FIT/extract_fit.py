# -*- coding: utf-8 -*-
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
BIN_SIZE  = 10
MIN_COUNT = 2

def extraire_fit(chemin):
    rows = []
    for record in fitparse.FitFile(chemin).get_messages("record"):
        data_dict = {}
        for data in record:
            if data.name in ['cadence', 'power', 'timestamp']:
                data_dict[data.name] = data.value
        if data_dict:
            rows.append(data_dict)

    df = pd.DataFrame(rows)
    df['timestamp'] = pd.to_datetime(df['timestamp'])
    df = df.sort_values('timestamp').reset_index(drop=True)
    df['power']   = pd.to_numeric(df['power'],   errors='coerce')
    df['cadence'] = pd.to_numeric(df['cadence'], errors='coerce').ffill()
    return df[(df['cadence'] > 0) & (df['power'] > 0)].dropna(subset=['cadence', 'power'])

def binner(df):
    df = df.copy()
    df['cadence_bin'] = (df['cadence'] // BIN_SIZE) * BIN_SIZE
    bins = df.groupby('cadence_bin').agg(
        cadence_moy=('cadence', 'mean'),
        power_moy=('power',   'mean'),
        count=('power', 'count')
    ).reset_index()
    return bins[bins['count'] >= MIN_COUNT]

# ─── PARTIE 1 : Time series par position ────────────────────────────────────

all_data = {}

for position, chemin in FICHIERS.items():
    df = extraire_fit(chemin)
    all_data[position] = df

    fig, ax1 = plt.subplots()
    ax2 = ax1.twinx()
    ax1.plot(df['timestamp'], df['power'],   color='steelblue', label='Puissance (W)')
    ax2.plot(df['timestamp'], df['cadence'], color='orange',    label='Cadence (rpm)')
    ax1.set_xlabel('Temps')
    ax1.set_ylabel('Puissance [W]',  color='steelblue')
    ax2.set_ylabel('Cadence [rpm]',  color='orange')
    ax1.set_title(f'Position aimant : {position}')
    fig.tight_layout()
    plt.savefig(f'fichiers FIT/graphs/timeseries_{position}.png', dpi=100)
    plt.close()

# ─── PARTIE 2 : Binning + régression ────────────────────────────────────────

sns.set_context('talk')
fig, ax = plt.subplots(figsize=(10, 6))
resultats = []

for position, df in all_data.items():
    bins = binner(df)

    X = pd.DataFrame({'c': bins['cadence_moy'], 'c2': bins['cadence_moy'] ** 2})
    y = bins['power_moy']

    reg = LinearRegression(fit_intercept=False).fit(X, y)
    a1, a2 = reg.coef_
    r2     = reg.score(X, y)
    resultats.append({'position': position, 'a1': round(a1, 4), 'a2': round(a2, 6), 'R2': round(r2, 4)})

    scatter = ax.scatter(bins['cadence_moy'], bins['power_moy'], label=f'pos {position}', zorder=3)
    color   = scatter.get_facecolor()[0]

    c_range = np.linspace(bins['cadence_moy'].min(), bins['cadence_moy'].max(), 100)
    X_pred  = pd.DataFrame({'c': c_range, 'c2': c_range ** 2})
    ax.plot(c_range, reg.predict(X_pred), color=color)

ax.set_xlabel('Cadence [rpm]')
ax.set_ylabel('Puissance [W]')
ax.set_title('Régression P = a1·c + a2·c² par position')
ax.legend(title='Position aimant')
ax.grid(True)
plt.tight_layout()
plt.savefig('fichiers FIT/graphs/regression_toutes_positions.png', dpi=100)
plt.show()

print("\n=== Résultats ===")
print(pd.DataFrame(resultats).to_string(index=False))
