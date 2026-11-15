# Abonnements — Lot 3

La grille actuelle, le forfait gratuit et la commission sont décrits dans [FORFAITS.md](FORFAITS.md).

## Objectif

Le moteur d'abonnement est indépendant du fournisseur de paiement.

Tara pourra être branché dans une couche de paiement sans que les règles de plans, quotas ou droits dépendent de son API.

## Modèles

### plans

Contient :

- code stable ;
- nom ;
- description ;
- prix mensuel et annuel en centimes ;
- devise ;
- durée d'essai ;
- visibilité publique ;
- activation.

Les prix peuvent être nuls tant que la grille commerciale n'est pas validée.

### plan_entitlements

Chaque droit est une donnée :

- `feature_key` ;
- `enabled` ;
- `limit_value`.

Exemples possibles :

- `students` + limite ;
- `teachers` + limite ;
- `active_formations` + limite ;
- `live` + nombre maximal d'étudiants connectés par classe ;
- `live_rooms` + nombre de cours en live en même temps ;
- `custom_domain` ;
- `automations` ;
- `advanced_reporting`.

Aucun quota commercial n'est codé en dur dans l'interface.

Les quatre forfaits publics incluent les classes live : 10 étudiants par classe en Découverte,
15 en Starter, 25 en Pro et 30 en Business. Cette limite est vérifiée côté serveur au moment de rejoindre la salle.

### subscriptions

États supportés :

- `trialing` ;
- `active` ;
- `past_due` ;
- `suspended` ;
- `cancelled`.

La table accepte des identifiants de fournisseur externes mais ne dépend pas de Tara.

### usage_counters

Permet de confronter une consommation réelle à une limite de plan.

Exemples :

- nombre d'étudiants ;
- nombre de professeurs ;
- formations actives ;
- stockage ;
- automatisations exécutées.

## Sécurité

Le contrôle des quotas se fait côté backend avec `require_entitlement`.

Masquer un bouton dans le frontend ne suffit jamais.

## Création d'une école

Si un plan `starter` actif existe, une nouvelle école reçoit automatiquement un essai selon `trial_days`.

La migration initiale crée les coquilles Starter, Pro et Business avec 14 jours d'essai, mais sans prix ni quotas imposés.
