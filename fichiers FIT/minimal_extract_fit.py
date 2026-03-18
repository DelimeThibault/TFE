import fitparse
import pandas as pd

def extraire_donnees_fit(chemin_fichier):
    fitfile = fitparse.FitFile(chemin_fichier)
    rows = []
    
    for record in fitfile.get_messages('record'):  # 'record' = seconde par seconde
        data = {}
        for field in record:
            data[field.name] = field.value
        rows.append(data)
    
    df = pd.DataFrame(rows)
    print(f"Colonnes disponibles : {df.columns.tolist()}")  # Debug
    print(f"Nombre de lignes : {len(df)}")                  # Debug
    
    # Filtrer cadence et puissance, supprimer les lignes à 0 ou NaN
    df = df[['cadence', 'power']].dropna()
    df = df[(df['cadence'] > 0) & (df['power'] > 0)]  # Enlève les zéros de démarrage
    return df

df = extraire_donnees_fit("fichiers FIT/14_1.fit")
print(df.head(10))
