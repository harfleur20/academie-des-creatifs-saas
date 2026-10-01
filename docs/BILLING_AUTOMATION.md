# Automatisation du cycle de facturation

Le workflow `.github/workflows/billing-lifecycle.yml` s'exécute toutes les heures, à la minute 17.

Il ne fait rien tant que les secrets GitHub suivants ne sont pas configurés :

- `BILLING_CRON_URL` : URL publique du backend SaaS, sans slash final ;
- `BILLING_CRON_SECRET` : même valeur que la variable backend `BILLING_CRON_SECRET`.

Le workflow appelle :

```
POST /api/v1/billing/internal/lifecycle
```

avec un timeout de 30 secondes et deux tentatives supplémentaires en cas d'échec réseau.

Aucun déploiement Coolify n'est déclenché par ce workflow.
