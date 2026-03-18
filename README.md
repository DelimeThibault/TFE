# Conception d’un vélo d’appartement connecté simulant la production d'énergie et l’analyse de l’effort

## Ajout des dépendances 

```
pip freeze > requirements.txt
```
## Installation IDE

```
python -m venv .venv

# MAC 
source .venv/bin/activate
pip install --upgrade pip && pip install -r requirements.txt

# Windows
.venv\Scripts\activate
pip install --upgrade pip
pip install -r requirements.txt
```

## Lancement de l'application

```
# backend Flask 
cd backend
python3 app.py

# Gateway (Pico > API)
python3 ../gateway.py

# teste avec un curl 
curl -X POST http://127.0.0.1:5000/api/cadence -H "Content-Type: application/json" -d '{"cadence":88,"total_pulses":123,"timestamp":456789}'

# Dans le navigateur
http://127.0.0.1:5000 → page live
```