# Mode paiement démo

Le SaaS possède un mode de paiement de test inspiré de la Coupe des Créatifs.

## Activation

Le mode démo exige simultanément :

```env
APP_ENV=development
PAYMENT_MODE=demo
ALLOW_DEMO_PAYMENTS=true
```

Si `APP_ENV=production`, les confirmations démo sont toujours refusées, même si les deux autres variables ont été activées par erreur.

## Parcours

1. Le propriétaire ou un administrateur choisit un forfait.
2. Le backend crée une tentative `billing_payment_attempts` avec `provider=demo`.
3. Aucun appel TaraMoney n'est réalisé.
4. L'utilisateur confirme explicitement le paiement de test.
5. La tentative passe de `pending` à `paid`.
6. L'ancien abonnement actif ou en essai est clôturé.
7. Un nouvel abonnement est créé avec `provider=demo`.

La confirmation est idempotente : confirmer deux fois la même tentative ne crée pas deux abonnements.

## Montant

Si le forfait possède déjà un prix configuré, ce prix est utilisé.

Si le prix n'est pas encore configuré, `DEMO_PAYMENT_AMOUNT_CENTS` fournit uniquement un montant fictif de test. Il n'est jamais utilisé pour un paiement réel.

## Production

Le futur provider Tara utilisera la même table de tentatives mais avec `provider=taramoney`.

Le mode démo n'est donc pas une logique parallèle : il teste le même cycle métier d'abonnement, seule la preuve de paiement est simulée.
