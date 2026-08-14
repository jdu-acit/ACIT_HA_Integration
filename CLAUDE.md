# ACIT_HA_Integration — repères de travail

Intégration Home Assistant (custom component HACS) pour les cartes ACIT de
l'écosystème ThermACEC. Communication **locale** : JSON-RPC 2.0 sur HTTP
(`/rpc`), notifications WebSocket (`/ws`), découverte mDNS `_acit._tcp`.

## Structure

- `custom_components/acit/` — tout le code de l'intégration
  - `models.py` — enum `ACITModel`, `ACITFeature`, table `MODEL_CONFIGS`,
    résolveur central `resolve_model()` / `get_model_config()` /
    `get_supported_features()`
  - `coordinator.py` — `DataUpdateCoordinator`, client RPC/WebSocket
  - `config_flow.py` — ajout manuel + découverte Zeroconf
  - plateformes : `sensor.py`, `climate.py`, `number.py`, `update.py`
    (déclarées dans `__init__.py:PLATFORMS`)
  - `strings.json` + `translations/{en,fr}.json` — toujours mises à jour ensemble
- `docs_internal/THERMACEC_DATA_CONTRACT.md` — contrat de données firmware ↔ HA
- `.github/workflows/` — `validate.yml` (HACS, hassfest, ruff), `release.yml`

## Règle produit : un appareil n'expose que ce qu'il possède

Le modèle est celui que le firmware **annonce lui-même** (TXT mDNS `model=`,
`Thermostat.GetConfig`, `/api/v1/discovery` → `deviceType`) et il est résolu par
correspondance **exacte** dans `resolve_model()`. Pas de match partiel : c'est ce
qui avait donné un ventilateur et une charge de noyau fantômes au NOS (issue #5).

Un modèle inconnu reçoit un profil minimal (température + consigne) et un
avertissement dans le log — jamais les entités d'un autre produit.

Ne jamais deviner un contrat de données absent du firmware : si l'appareil
n'expose pas la donnée ou la méthode RPC, l'issue attend le firmware.

## Suivi des issues

Le dépôt est rattaché au projet GitHub **ACIT — SmartEnergy** (`gh project`
n° 5, owner `jdu-acit`), champ `Status` : `Todo` / `In Progress` / `Done`.

**Quand on commence à travailler sur une issue, la passer en `In Progress`**, et
la repasser en `Done` (ou laisser la fermeture de l'issue le faire) une fois le
travail livré. Une issue laissée en `Todo` alors qu'on est dedans fausse la vue
du projet.

```powershell
# retrouver l'ID de l'item projet d'une issue
gh project item-list 5 --owner jdu-acit --format json
```

Une issue en attente d'un préalable externe (typiquement un jalon firmware)
reste **ouverte et en `Todo`**, avec un commentaire d'état expliquant ce qui
manque exactement — pas de code écrit à l'avance sur un contrat supposé.

## Git

- **Commiter directement sur `main`.** Pas de branche de travail, pas de PR pour
  le flux normal.
- Messages de commit en **français**, format conventionnel :
  `feat(models):`, `fix(ota):`, `chore:`, `ci:` — sujet descriptif, à
  l'impératif ou au constat, pas un simple « update ».
- Ne commiter que sur demande explicite.

## Langue

- Interface utilisateur et documentation produit : FR **et** EN (les deux
  fichiers de traduction restent synchronisés avec `strings.json`).
- Code, docstrings, commentaires et messages de log : **anglais** (le dépôt a été
  traduit en ce sens, cf. `c92ac88`).
- Issues, commentaires d'issue et messages de commit : **français**.

## Qualité

```powershell
ruff check custom_components/acit/
```

Le workflow `validate.yml` fait tourner ruff (`pyproject.toml`, ligne 88,
cible py311), la validation HACS et hassfest sur chaque push `main`/`dev` et
chaque PR. Pas de suite de tests unitaires dans le dépôt à ce jour.
