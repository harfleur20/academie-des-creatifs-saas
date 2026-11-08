# Automatisation du cycle de facturation

Le workflow `.github/workflows/billing-lifecycle.yml` s'exécute toutes les heures, à la minute 17.

Il ne fait rien tant que les secrets GitHub suivants ne sont pas configurés :

- `BILLING_CRON_URL` : URL publique du backend SaaS, sans slash final ;
- `BILLING_CRON_SECRET` : même valeur que la variable backend `BILLING_CRON_SECRET`.

Le workflow appelle, dans cet ordre :

```
POST /api/v1/billing/internal/lifecycle      # abonnements des écoles
POST /api/v1/commerce/internal/lifecycle     # paiements des étudiants, puis envoi des emails en attente
POST /api/v1/assignments/internal/reminders  # rappels de devoirs et de cours (24 h et 1 h avant), de paiement (J-7 et J-1), fin de session
```

Chaque appel a un timeout de 30 secondes et deux tentatives supplémentaires en cas d'échec réseau. Une étape en échec n'empêche pas les suivantes.

Le premier passage envoie aussi les emails restés dans la file. Avant d'activer le workflow sur une base existante, vérifiez les messages `pending` ou `failed` de `communication_outbox` ; passez ceux qui ne doivent plus partir en `needs_review`, d'où un gestionnaire peut encore les relancer.

## En local

GitHub ne peut pas joindre un backend sur `localhost`. Depuis `backend`, à côté d'`uvicorn` :

```bash
python scripts/run_cron_jobs.py            # un passage
python scripts/run_cron_jobs.py --every 15 # un passage toutes les 15 minutes
```

Le script lit `BILLING_CRON_URL` et `BILLING_CRON_SECRET` dans `backend/.env` et appelle les mêmes routes que le workflow. L'intervalle ne peut pas dépasser 60 minutes, sinon le rappel de la dernière heure serait manqué.

Aucun déploiement Coolify n'est déclenché par ce workflow.
