# Badges de progression

Chaque étudiant porte un badge par formation : **Aventurier**, **Débutant**, **Intermédiaire**, **Semi-pro**, puis **Professionnel**. Les seuils et les poids viennent du site mère. Le SaaS y ajoute une règle : le badge ne pèse que ce qu'il y a à peser. Une formation avec peu de quiz ou de TP ne bloque donc pas ses étudiants, et les lives prennent le relais.

Code : `backend/app/services/badge_rules.py` (décision), `backend/app/services/learning_progress.py` (collecte des chiffres), `backend/app/services/live_classes.py` (présence en live).

## Les quatre principes

1. **Juste.** Rien ne compte contre un étudiant avant son échéance, ni tant qu'un professeur n'a pas corrigé son travail. Ce que l'étudiant fait compte tout de suite.
2. **Proportionné.** Une catégorie qui a peu d'éléments échus (quiz, TP, séances) ne bloque aucun niveau et pèse en proportion. Les autres catégories portent le badge, les lives en premier.
3. **Prouvé.** Chaque niveau demande un minimum de preuves. Le niveau Professionnel demande de vraies évaluations.
4. **Expliqué.** L'étudiant voit sur quoi repose son badge et ce qui peut encore le faire monter. Le professeur voit quand l'évaluation manque et qui décroche.

## Ce qui compte, et à partir de quand

| Activité | Compte tout de suite si… | Sinon, compte (échue) quand… |
| --- | --- | --- |
| Quiz | l'étudiant le réussit | le professeur le clôt, ou 7 jours après son ouverture |
| TP | l'étudiant le rend | sa date limite passe |
| Séance | – | son rapport est déposé (séance tenue ou partielle) |
| Contenu (leçon) | toujours | – |

- Un nouveau quiz ou TP ne change rien au badge avant son échéance. Il apparaît dans « À faire pour progresser » sur la page Progression de l'étudiant (les 3 plus proches), avec sa date.
- Un TP rendu mais pas encore corrigé compte comme rendu. Il ne pèse pas sur la part « validée » tant que le professeur ne l'a pas corrigé.
- Une absence excusée sort du décompte des séances.
- Les séances annulées, non tenues ou interrompues ne comptent pas, ni les activités qui leur sont rattachées (parcours guidés).

## Le score

Le score combine quatre piliers. Leur poids dépend du format :

| Pilier | Formation classique | Formation live |
| --- | --- | --- |
| Contenus (leçons terminées) | 35 | ≈ 24,7 |
| Évaluation (quiz, notes) | 25 | ≈ 17,6 |
| Production (TP, projet final) | 25 | ≈ 17,6 |
| Présences | 15 | 40 |

Chaque pilier pèse selon le nombre d'éléments échus, rapporté à un seuil :

| Catégorie | Seuil de « preuve complète » |
| --- | --- |
| Quiz | 3 quiz échus |
| TP | 2 TP échus |
| Séances | 4 séances tenues |

Avec un seul quiz échu, le pilier évaluation pèse un tiers de son poids. À partir de 3, il pèse tout son poids. Un travail fait en avance (quiz réussi ou TP rendu avant l'échéance) vaut un élément échu, pour qu'il compte tout de suite. Quand le professeur a saisi des notes, le pilier évaluation pèse tout son poids.

## Les niveaux

Sur un parcours guidé (live ou présentiel), un niveau demande tous ses critères :

| Niveau | Score | Contenus | TP | Quiz réussis | Séances suivies | Moyenne | Preuves |
| --- | --- | --- | --- | --- | --- | --- | --- |
| Débutant | 25 % | 25 % | 25 % rendus | 25 % | 25 % | – | 1 |
| Intermédiaire | 50 % | 50 % | 50 % validés | 50 % | 50 % | 10/20 | 3 |
| Semi-pro | 75 % | 75 % | 75 % validés | 70 % | 70 % | 12/20 | 5 |
| Professionnel | 90 % | 100 % | 100 % validés | 80 % | 80 % | 16/20 | 5 |

- Les critères TP, quiz et séances ne s'appliquent qu'à partir du seuil de leur catégorie (2 TP, 3 quiz, 4 séances échus). En dessous, la catégorie ne fait que peser dans le score.
- « Validés » se calcule sur les TP corrigés. Un TP en attente de correction ne fait baisser personne.
- Les **preuves** sont les séances suivies, les quiz réussis, les TP rendus et les notes saisies par le professeur. Les leçons n'en sont pas : sinon, elles pourraient remplacer les séances.
- Le niveau **Professionnel** demande en plus :
  - la fin de la session et la validation des séances ;
  - le projet final validé à 80 % au moins, s'il existe ;
  - au moins 3 quiz ou 2 TP échus. Une formation sans évaluation plafonne à Semi-pro.

Sur un parcours classique (en ligne, non guidé), seul le score global compte jusqu'à Semi-pro. Le niveau Professionnel applique tous les critères.

### Exemples

| Situation (formation live) | Badge |
| --- | --- |
| 8 lives sur 8, leçons terminées, ni quiz ni TP | Semi-pro |
| La même, plus un seul quiz, raté | Semi-pro |
| La même, plus un TP rendu en attente de correction | Semi-pro |
| 3 lives sur 8 et un quiz réussi | Débutant |
| Un seul live suivi, rien d'autre | Débutant |
| 3 quiz échus, aucun réussi | Aventurier (le critère quiz s'applique) |

## La présence en live est vérifiée

Une présence ne s'obtient pas en ouvrant la page et en partant.

- **Un appareil par étudiant.** Un deuxième appareil est refusé tant que le premier envoie des signaux. La place se libère 90 secondes après le dernier signal.
- **Temps passé dans la salle.** La page envoie un signal toutes les 30 secondes. Chaque signal crédite au plus 60 secondes : un onglet endormi n'accumule pas de temps.
- **Appel.** Le professeur responsable peut faire l'appel une fois le cours commencé. Chaque étudiant a 2 minutes pour répondre « Je suis là » (avec 15 secondes de tolérance).
- **Pré-remplissage au rapport.** Quand le professeur dépose le rapport, les présences sont proposées ainsi :
  - **absent** si l'étudiant n'est jamais entré ;
  - **absent** s'il y a eu un appel et qu'il n'a répondu à aucun ;
  - **absent** s'il a passé moins de la moitié de la durée du cours dans la salle ;
  - sinon, **en retard** s'il est arrivé plus de 15 minutes après le début, et **présent** sinon.
- Le professeur garde la main : il peut corriger chaque présence pendant 24 h après le rapport. La page Présences affiche les minutes passées dans la salle et les appels répondus.

## Alertes d'assiduité

Après chaque rapport de séance, un étudiant qui a manqué **deux séances de suite**, ou qui vient de passer **sous 60 %** de présence après au moins 3 séances, reçoit une notification. Son professeur aussi. Chaque alerte n'est envoyée qu'une fois. Un rapport déposé en retard sur une séance plus ancienne n'en déclenche pas.

Sur la page Performance du professeur, chaque session indique :

- le nombre d'étudiants sous 60 % de présence (après 3 séances) ;
- un conseil quand il y a moins de 3 quiz et de 2 TP échus : l'évaluation pèse alors peu et le niveau Professionnel reste fermé.

## Garanties

Deux propriétés sont vérifiées par les tests, dont un tirage de 4 000 situations au hasard :

1. **Aucune action de l'étudiant ne fait baisser son score ni son niveau.** Ces actions sont : réussir ou tenter un quiz, rendre un TP, venir à une séance, terminer une leçon.
2. **Publier une activité ne change rien avant son échéance.**

Elles tiennent parce que le poids et le blocage d'une catégorie ne dépendent que de ses éléments échus, jamais de ce que l'étudiant a fait en avance.

De plus, sur un parcours guidé dont le programme est figé, un niveau atteint est enregistré : le badge affiché ne redescend plus, même quand du travail est ajouté ensuite.

Tests : `backend/tests/test_badge_fairness.py`, `test_badge_rules.py`, `test_live_presence.py`, `test_attendance_alerts.py`.

## Écart assumé avec le site mère

Sur le site mère, un quiz ou un TP compte dès qu'il est accessible, et une catégorie bloque un niveau dès son premier élément. Un seul quiz raté peut donc retenir un étudiant assidu, et publier une activité fait baisser tout le monde jusqu'à ce qu'elle soit faite. Le SaaS garde les seuils et les poids du site mère, mais compte à l'échéance et pèse en proportion des preuves.
