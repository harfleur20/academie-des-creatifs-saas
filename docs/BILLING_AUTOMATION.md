# Automatisation du cycle de facturation

Le workflow `.github/workflows/billing-lifecycle.yml` s'exécute toutes les heures, à la minute 17.

Il ne fait rien tant que les secrets GitHub suivants ne sont pas configurés :

- `BILLING_CRON_URL` : URL publique du backend SaaS, sans slash final ;
- `BILLING_CRON_SECRET` : même valeur que la variable backend `BILLING_CRON_SECRET`.

Le workflow appelle, dans cet ordre :

```
POST /api/v1/billing/internal/lifecycle      # abonnements des écoles
POST /api/v1/assignments/internal/reminders  # rappels 24 h et 1 h avant la date limite d'un devoir
```

Chaque appel a un timeout de 30 secondes et deux tentatives supplémentaires en cas d'échec réseau. Une étape en échec n'empêche pas les suivantes.

Le premier passage envoie aussi les emails restés dans la file. Avant d'activer le workflow sur une base existante, vérifiez les messages `pending` ou `failed` de `communication_outbox` ; passez ceux qui ne doivent plus partir en `needs_review`, d'où un gestionnaire peut encore les relancer.

Aucun déploiement Coolify n'est déclenché par ce workflow.
