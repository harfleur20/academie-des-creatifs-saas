# Cycle de vie des abonnements

## États

Le moteur SaaS gère maintenant :

- `trialing` : période d'essai ;
- `active` : accès payé ou essai actif ;
- `past_due` : période payée terminée, paiement attendu pendant la grâce ;
- `suspended` : grâce terminée sans paiement ;
- `cancelled` : abonnement clôturé.

## Expiration

À la fin d'une période payée :

- si `cancel_at_period_end=true`, l'abonnement passe en `cancelled` ;
- sinon il passe en `past_due` ;
- la période de grâce est définie par `BILLING_GRACE_PERIOD_DAYS` (7 jours par défaut) ;
- à la fin de la grâce, l'abonnement passe en `suspended`.

Les droits SaaS restent accordés uniquement à `trialing` et `active`.

## Renouvellement

Un paiement du même forfait et du même intervalle prolonge l'abonnement existant.

Si l'abonnement est déjà `past_due` ou `suspended`, le paiement le réactive avec une nouvelle période à partir du paiement.

## Changement de forfait

Un paiement vérifié pour un autre forfait ou un autre intervalle :

1. clôture l'ancien abonnement ;
2. crée le nouvel abonnement ;
3. applique immédiatement les nouveaux droits.

Il n'y a pas encore de prorata : un changement est donc déclenché uniquement après un paiement complet du nouveau forfait.

## Factures

Chaque paiement confirmé est lié à une facture `paid`.

Quand une période arrive à échéance sans paiement, une facture `open` est créée lorsque le tarif du forfait est configuré. Le paiement ultérieur règle cette facture au lieu d'en créer une deuxième.

## Cron

L'endpoint interne :

```
POST /api/v1/billing/internal/lifecycle
X-Billing-Cron-Secret: <secret>
```

applique les transitions d'expiration.

Il doit être appelé régulièrement par le scheduler de production. Il n'est pas exposé dans la documentation OpenAPI publique.
