# TaraMoney — stratégie SaaS

## Source des bonnes pratiques

Le provider SaaS combine les deux intégrations déjà utilisées :

- **Coupe des Créatifs** pour la sécurité et la vérification serveur ;
- **Académie des Créatifs** pour la gestion des tentatives de paiement et des retours tardifs.

## Principe de confiance

Le webhook n'est jamais une preuve suffisante de paiement.

Même si Tara envoie `SUCCESS`, le SaaS appelle ensuite l'API de statut TaraMoney et vérifie :

- le `productId` ;
- le `businessId` quand il est retourné ;
- le montant ;
- l'horodatage quand il est disponible ;
- l'identifiant de transaction.

Le montant vérifié doit être exactement celui stocké dans `billing_payment_attempts`.

Une transaction TaraMoney déjà utilisée pour une autre tentative est refusée.

## Webhook

Le corps est limité à 16 Ko.

L'authentification accepte :

- une signature HMAC-SHA256 ;
- ou un secret partagé dans un header explicitement configuré.

Si aucun mécanisme d'authentification documenté n'est disponible côté Tara, le webhook est traité uniquement comme un **indice** : le `businessId` et le `productId` servent à retrouver la tentative, puis la preuve vient exclusivement d'une requête serveur-to-server vers TaraMoney.

## Devise

L'intégration TaraMoney actuelle impose `XAF`.

Le backend refuse donc un checkout Tara sur un plan qui n'est pas configuré en XAF. Aucune conversion de devise implicite n'est faite.

Pour les plans XAF, les champs de prix actuels contiennent l'entier envoyé à TaraMoney (par exemple `25000` pour 25 000 FCFA).

## Retour navigateur

Le retour vers `/app/billing?tara_order=...` ne confirme jamais le paiement.

Le frontend appelle l'endpoint de réconciliation, qui effectue à nouveau la vérification serveur Tara avant toute activation.

## Idempotence

Une tentative possède `activated_subscription_id`.

Une seconde confirmation du même paiement retourne le même abonnement et ne crée pas de doublon.
