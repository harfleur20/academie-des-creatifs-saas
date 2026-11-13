# La démo en lecture seule

Sur la page d'accueil, le bouton **« Voir la démo »** laisse un visiteur, sans compte, parcourir une école de démonstration : son site public, et ses espaces direction, professeur et étudiant. Il voit tout et ne peut rien modifier.

## Mise en route

- Créer l'école de démonstration sur la plateforme, avec des personnes et des données fictives. Il lui faut un propriétaire, au moins un professeur affecté à une session et un étudiant inscrit à une session en cours.
- Indiquer son adresse courte au backend : `DEMO_ORGANIZATION_SLUG=studio-kora`.
- Sans cette variable, la page d'accueil affiche « Voir les tarifs » à la place de « Voir la démo ».

## Ce que voit le visiteur

1. « Voir la démo » ouvre le choix entre quatre lieux : le site de l'école, l'espace direction, l'espace professeur et l'espace étudiant.
2. Pour un espace, le serveur (`POST /auth/demo`) donne un jeton de 2 heures pour un membre de l'école :
   - **direction** : le propriétaire ;
   - **professeur** : le professeur qui a le plus de sessions ;
   - **étudiant** : un étudiant inscrit à une session en cours.
3. Une barre « Démo » reste en bas de l'écran. Elle indique le lieu visité, permet de passer à un autre et propose « Créer mon école ». La croix quitte la démo et ramène à la page d'accueil.
4. Le site de l'école de démo affiche un bandeau « Site de démonstration » et ne prend ni commande ni favori.

## Ce qui garantit la lecture seule

- **Le jeton de démo porte la marque `demo_org`.** Avec lui, le serveur refuse toute requête qui modifie quelque chose (autre que GET, HEAD ou OPTIONS), sur n'importe quelle route, et n'ouvre aucune autre école (`app/api/dependencies.py`).
- **Le jeton reste dans l'onglet du visiteur** (stockage de session), sans cookie. Il ne devient jamais le cookie de connexion partagé, même en passant par `/auth/me` ou par le transfert vers un domaine personnalisé. Une personne déjà connectée à sa propre école dans un autre onglet le reste.
- **Côté interface, rien de ce qui modifie n'est envoyé** pendant la démo. Le visiteur voit le message « Mode démo : rien n'est enregistré. Créez votre école pour essayer pour de vrai. »
- **Sur le site de l'école de démo**, la commande et les favoris sont refusés côté serveur, même pour un vrai compte.

Le code est dans `backend/app/services/demo.py`, `frontend/src/lib/demo.ts` et `frontend/src/components/DemoBar.tsx`. Les tests sont dans `backend/tests/test_demo.py`.

## À faire

- **Rafraîchir les données chaque nuit** : recaler les dates des sessions, séances, devoirs et paiements sur le jour même, sinon la démo vieillit (sessions terminées, calendrier vide).
