# Forfaits, commission et options

Ce document décrit le modèle économique des écoles et où il vit dans le code. La grille est posée par la migration `20261112_0062_free_plan_annual_discount`, revue le 2026-11-14 par `20261114_0066_live_for_every_plan`, mise à jour par `20261115_0070_adjust_live_plan_limits` et complétée par le quota multi-écoles dans `20261116_0074_organization_creation_quotas`. Elle reste modifiable dans l'administration (Forfaits).

## Le principe

- **Étudiants illimités dans tous les forfaits.** Un étudiant de plus ne coûte presque rien à la plateforme, qui gagne déjà sur chacun par sa commission.
- **On limite ce qui consomme des serveurs** : la taille des classes live, le nombre de lives en même temps, les heures enregistrées et transcrites.
- **Trois revenus** : l'abonnement, la commission sur les ventes des écoles, les options à l'unité.

## La grille

| | Découverte | Starter | Pro | Business |
| --- | --- | --- | --- | --- |
| Mensuel | 0 | 15 000 FCFA | 30 000 FCFA | 65 000 FCFA |
| Annuel (−20 %) | – | 144 000 FCFA | 288 000 FCFA | 624 000 FCFA |
| Écoles gérées par le propriétaire | 1 | 1 | 2 | 5 |
| Commission sur les ventes, frais compris | 10 % | 8 % | 6 % | 4 % |
| Étudiants | illimités | illimités | illimités | illimités |
| Formations publiées | 1 | illimitées | illimitées | illimitées |
| Professeurs | 1 | 2 | 10 | illimités |
| Étudiants par classe live (`live`) | 10 | 15 | 25 | 30 |
| Lives en même temps (`live_rooms`) | 1 | 2 | 5 | 10 |
| Heures de live par mois (`live_hours`) | 6 h | illimitées | illimitées | illimitées |
| Durée d'un cours en live (`live_class_hours`) | 2 h au plus | 3 h au plus | 4 h au plus | 4 h au plus |
| Replays par mois (`replays`, bientôt) | – | 2 h | 15 h | 25 h |
| Conservation après la session (`replay_retention_days`, bientôt) | – | 0 jour | 30 jours | 180 jours |
| Transcription par mois (`transcription`, bientôt) | – | – | 5 h | 25 h |
| Statistiques avancées et exports (`advanced_stats`, bientôt) | – | – | oui | oui |
| Domaine personnalisé (`custom_domain`) | – | – | oui | oui |
| Sans « Powered by » (`white_label`) | – | – | – | oui |
| Support | – | – | WhatsApp | prioritaire, aide à la mise en place |

Les fonctionnalités marquées « bientôt » font déjà partie des forfaits : elles s'affichent avec une étiquette « Bientôt » sur la page d'accueil et la page Abonnement tant qu'elles ne fonctionnent pas.

Sur ces deux pages, chaque carte ne montre que 4 ou 5 points clés (`planHighlights` dans `frontend/src/lib/planFeatures.ts`). Le détail complet est dans le tableau « Comparer les forfaits en détail », replié sous les cartes (`frontend/src/components/PlanComparison.tsx`).

## Le forfait gratuit

- Une école crée son compte avec 14 jours d'essai du forfait Pro, lives compris, sans moyen de paiement.
- **Sans forfait payé en cours, l'école est en Découverte** : essai terminé, forfait résilié, ou délai de paiement dépassé. Elle n'est jamais coupée ; elle garde des lives plus petits (10 étudiants, un à la fois, 6 h par mois), perd les quotas plus larges, et la commission passe à 10 %. Ce qui existe déjà (formations publiées, professeurs) reste en place ; seul l'ajout au-delà du quota est refusé.
- Pendant le délai de grâce d'un paiement en retard (`past_due`), l'école garde son forfait.
- Le nombre d'écoles est un quota du compte propriétaire : le forfait le plus élevé de ses écoles détermine la limite. Une baisse de forfait ne supprime aucune école existante, mais bloque les nouvelles créations au-delà de la nouvelle limite.
- Code : `get_effective_plan` dans `backend/app/services/subscriptions.py`. Quand la grille n'a pas de forfait gratuit actif, une école sans forfait n'est pas limitée (comportement d'avant).

## Le parcours après un clic sur un forfait

1. Chaque bouton de la page d'accueil mène à l'inscription avec le forfait et la période choisis (`/login?mode=register&plan=starter&interval=annual`). L'inscription les rappelle au-dessus du formulaire et les garde dans l'onglet (`frontend/src/lib/planChoice.ts`).
2. À la création de l'école, l'essai Pro de 14 jours démarre dans tous les cas. Le forfait choisi est gardé sur l'abonnement d'essai (`chosen_plan_code`, `chosen_billing_interval`).
3. Ensuite :
   - **Découverte ou Pro** : la mise en route s'ouvre avec l'annonce de l'essai ;
   - **Starter ou Business** : la page Abonnement s'ouvre sur la carte choisie (« Votre choix ») et sa période, avec le choix de payer tout de suite ou après l'essai.
4. Une personne déjà connectée qui a une école arrive directement sur la page Abonnement, le forfait présélectionné.
5. Trois jours puis un jour avant la fin de l'essai, la direction reçoit un rappel qui mène au forfait choisi (`notify_trial_endings`, lancé par la tâche horaire des abonnements).

## L'annuel

Douze mois moins 20 %, pour le forfait comme pour les options à l'unité (`period_amount` dans `backend/app/services/plan_limits.py`). Un professeur supplémentaire coûte 2 500 FCFA par mois, ou 24 000 FCFA sur une facture annuelle.

## La commission et la passerelle de paiement

- Les étudiants paient sur le compte de la plateforme. Chaque échéance payée est créditée à l'école, moins la commission de son forfait à ce moment (`record_sale` dans `backend/app/services/school_revenue.py`). L'école demande ses retraits ; un super administrateur fait le virement puis le marque versé.
- **La commission inclut les frais de paiement.** Elle n'est donc rentable qu'avec une passerelle autour de 3 %. Tara Money prend 10 % (6 à 8 % avec son offre à 20 000 FCFA par mois), ce qui ferait perdre de l'argent sur chaque vente.
- **Décision du 2026-11-12 : passer à une passerelle autour de 3 % avant le lancement**, par exemple Fapshi (3 %, versements gratuits) ou CinetPay (environ 2 %), ou Tara si elle s'aligne. Vérifier avec elle qu'on peut encaisser pour le compte des écoles puis leur reverser. Tara est isolé dans `tara_money.py` et `tara_webhook.py`, et chaque commande garde sa passerelle (`payment_provider`).

## Les options à l'unité

| Option | Prix | Forfaits |
| --- | --- | --- |
| Professeur supplémentaire | 2 500 FCFA par mois | Starter, Pro |
| 10 h de replay en plus (bientôt) | 3 000 FCFA | Starter, Pro, Business |
| 10 h de transcription en plus (bientôt) | 3 000 FCFA | Pro, Business |

L'école accepte l'option avant d'ajouter un professeur au-delà de son quota ; l'option est ajoutée à sa prochaine facture. Découverte n'a pas d'option : il faut passer à un forfait payé. Les options « étudiant supplémentaire » et « formation supplémentaire » sont arrêtées : les formations sont illimitées dans tous les forfaits payants depuis 0066.

## Les lives

- **Par classe** : au-delà de la taille du forfait, un étudiant de plus ne peut pas entrer (`join_live_class`).
- **En même temps** : un professeur ne démarre un cours que si l'école a encore une salle libre. Un cours compte jusqu'à son compte rendu, ou jusqu'à 15 minutes après son heure de fin (`_require_live_room` dans `backend/app/services/live_classes.py`).
- **25 étudiants au plus par classe en Pro et 30 en Business** : au-delà de la taille du forfait, un étudiant de plus ne peut pas entrer. Une école qui a plus d'inscrits ouvre une autre session.
- **Durée selon le forfait** (`live_class_hours`) : 2 h en Découverte, 3 h en Starter et 4 h en Pro et Business. La programmation refuse un cours en live plus long (`_require_live_class_length` dans `planning.py`) ; le présentiel reste libre. Pendant le cours, la salle prévient 10 minutes avant sa limite et se ferme à la durée maximale du forfait.
- **6 h par mois en Découverte** (`live_hours`) : le compteur tourne seulement quand le live est actif, c'est-à-dire quand au moins une personne (professeur ou étudiant) est dans la salle d'un cours démarré. Il se met en pause quand la salle est vide et reprend quand quelqu'un revient : 10 minutes, une heure de salle vide, puis 20 minutes consomment 30 minutes. Chaque signal de présence (toutes les 30 secondes) ajoute le temps écoulé depuis le précédent, sauf après plus de 90 secondes de silence (`live_active_seconds`, `_credit_room_activity` dans `live_classes.py`). Quand les heures du mois sont épuisées, la salle ouverte se ferme et plus aucun cours ne démarre jusqu'au 1er du mois suivant. Le professeur voit les heures restantes à l'accueil de la classe. Les heures de l'essai Pro comptent dans le mois.
- **Capacité de la plateforme** (`LIVE_PLATFORM_MAX_PARTICIPANTS`) : toutes les écoles partagent les serveurs du live. Un cours ne démarre que si les étudiants qu'il peut amener (inscrits, dans la limite de la classe) tiennent avec ceux des cours en cours sous ce plafond. Sinon, le professeur lit seulement « Impossible d'ouvrir la salle pour le moment. Réessayez dans quelques minutes. », et `SUPPORT_EMAIL` reçoit une alerte, au plus une par heure. Plafond : environ 100 sur le serveur partagé, 300 de plus par relais vidéo (`infra/live/README.md`). 0 : pas de plafond.

## Ce qui reste à construire

1. **Replays** : Jibri sur une machine séparée (une instance par enregistrement simultané, environ 8 Go de mémoire), stockage Cloudflare R2 (lecture gratuite), quota d'heures et date de suppression. Chaque replay reste disponible jusqu'à la fin de sa session plus les jours du forfait ; l'école est prévenue 7 jours avant et peut télécharger la vidéo. La transcription, elle, est gardée. La partie école (publication, lecture protégée, téléchargement) existe déjà dans `live_recordings.py`.
2. **Transcription** des replays, à la minute chez un prestataire externe (à indiquer dans les conditions).
3. **Statistiques avancées** : élèves à risque, parcours d'achat du site, comparaison des sessions et des professeurs, exports Excel, rapport mensuel au directeur.
4. **Passerelle de paiement** autour de 3 %, avant le lancement.
