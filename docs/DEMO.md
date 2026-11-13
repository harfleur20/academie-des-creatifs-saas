# La démo en lecture seule

Sur la page d'accueil, le bouton **« Voir la démo »** laisse un visiteur, sans compte, parcourir une école de démonstration : son site public, et ses espaces direction, professeur et étudiant. Il voit tout et ne peut rien modifier.

## Mise en route

1. Créer l'école de démonstration, **Studio Kora**, depuis `backend`, sur une base migrée :

   ```bash
   python scripts/create_demo_school.py
   ```

2. Indiquer son adresse courte au backend : `DEMO_ORGANIZATION_SLUG=studio-kora`, puis le redémarrer.

Sans cette variable, la page d'accueil affiche « Voir les tarifs » à la place de « Voir la démo ».

### Ce que contient Studio Kora

Tout est fictif (`app/services/demo_school.py`) : une directrice, 3 professeurs, 26 étudiants, 6 formations (live, en ligne, présentiel), les commandes payées en une fois ou en 3 fois avec deux retards, les ventes nettes de commission, les cours, les séances avec présences et rapports, des quiz et des devoirs corrigés. Chaque formation live accepte aussi l'acompte, et les prochaines cohortes ouvrent dans environ deux mois.

- **Les dates partent du jour où le script tourne.** Les cohortes sont en cours, les séances passées ont leur rapport, les suivantes sont planifiées. Les données ne bougent plus ensuite. Si la démo paraît datée (séances passées sans rapport, cohorte terminée), on la recrée : `python scripts/create_demo_school.py --reset`.
- **Personne ne connaît les mots de passe** des comptes fictifs (tous en `@studiokora.example`). La démo ouvre les espaces avec un jeton. En local seulement, `--password '...'` donne un mot de passe commun pour se connecter comme eux.
- **Rien ne part** : l'école de démo n'envoie ni e-mail ni WhatsApp (`queue_school_event`).
- **Les images** sont dans `frontend/public/demo/`, servies par le site à l'adresse `FRONTEND_URL` (ou `--site-url`). Le site public exige des adresses complètes pour les couvertures.

### Crédits des photos (licence Unsplash, usage commercial gratuit)

| Fichier | Photo |
|---|---|
| `hero.jpg` | [Vitaly Gariev](https://unsplash.com/photos/8gAbl776pc0) |
| `covers/design-graphique.jpg` | [Kelly Sikkema](https://unsplash.com/photos/person-drawing-on-tablet-at-workspace-Dx1b5ucschA) |
| `covers/motion-design.jpg` | [Shubham Dhage](https://unsplash.com/photos/a-3d-image-of-a-purple-and-black-object-J-YFM4xlQrc) |
| `covers/ui-ux-design.jpg` | [Dharmik Moradiya](https://unsplash.com/photos/I_8_KJBWAV4) |
| `covers/photographie.jpg` | [Sofia Lasheva](https://unsplash.com/photos/a-photography-studio-setup-with-lighting-equipment-vhKyOG9LjqI) |
| `covers/marketing-digital.jpg` | [Swello](https://unsplash.com/photos/hands-holding-smartphone-displaying-social-media-feed--UtJxTRAndY) |
| `covers/montage-video.jpg` | [Peter Stumpf](https://unsplash.com/photos/video-editing-timeline-on-dark-screen-yk9VXp4W5-Q) |

### Les portraits

Les 25 portraits de `frontend/public/demo/people/` sont des photos Unsplash gratuites, recadrées sur le visage : la directrice, les 3 professeurs et environ 80 % des étudiants. Les étudiants qui ont un paiement en retard ou une assiduité faible gardent leurs initiales : aucun visage réel ne porte les alertes de la démo. Sources : [f01](https://unsplash.com/photos/h1lA3N5wb8M) · [f02](https://unsplash.com/photos/I49bIyEHaIs) · [f03](https://unsplash.com/photos/UzSPiVmnkAA) · [f05](https://unsplash.com/photos/HIPIOPYz0tQ) · [f06](https://unsplash.com/photos/V6iX4MiOCyY) · [f12](https://unsplash.com/photos/lG8E7KT7Elk) · [f13](https://unsplash.com/photos/J1jYLLlRpA4) · [f14](https://unsplash.com/photos/Me-MSv_dUNU) · [f15](https://unsplash.com/photos/4VN2WWVWqDs) · [f16](https://unsplash.com/photos/eXclz2FOr0M) · [f17](https://unsplash.com/photos/OmxCTe8rusY) · [f18](https://unsplash.com/photos/BJ9hkwB1tBE) · [f22](https://unsplash.com/photos/04Rd4wrSI1M) · [m02](https://unsplash.com/photos/10fvuGtnoEM) · [m03](https://unsplash.com/photos/P_jBxTIYGKg) · [m06](https://unsplash.com/photos/9KmzY22Tz-4) · [m11](https://unsplash.com/photos/ucXB9wyzXtw) · [m12](https://unsplash.com/photos/F_1ww3Y6F_c) · [m13](https://unsplash.com/photos/80oPuH_jogY) · [m14](https://unsplash.com/photos/2EGNqazbAMk) · [m15](https://unsplash.com/photos/_ObjhzjnMmc) · [m16](https://unsplash.com/photos/Ve7xjKImd28) · [m20](https://unsplash.com/photos/5xBTYnYzdU8) · [m21](https://unsplash.com/photos/IJrIeCs3D4g) · [m23](https://unsplash.com/photos/aPwQ8YF_IG0).

## Ce que voit le visiteur

1. « Voir la démo » ouvre le choix entre quatre lieux : le site de l'école, l'espace direction, l'espace professeur et l'espace étudiant.
2. Pour un espace, le serveur (`POST /auth/demo`) donne un jeton de 2 heures pour un membre de l'école :
   - **direction** : le propriétaire ;
   - **professeur** : le professeur qui a le plus de sessions ;
   - **étudiant** : un étudiant inscrit à une session en cours.
3. Une barre « Démo » reste en bas de l'écran. Elle indique le lieu visité, permet de passer à un autre et propose « Créer mon école ». La croix quitte la démo et ramène à la page d'accueil.
4. Le site de l'école de démo affiche un bandeau « Site de démonstration » et ne prend ni commande ni favori.
5. Dans les espaces, seuls les écrans du **parcours de démo** s'ouvrent. Les autres restent dans les menus, grisés avec un cadenas (« Disponible quand vous créez votre école ») ; ouverts par leur adresse, ils affichent un écran qui le dit.
   - **Direction** : tableau de bord, formations (liste et fiche), suivi pédagogique, statistiques, ventes.
   - **Professeur** : tableau de bord, sessions et leur planning, étudiants, notes.
   - **Étudiant** : vue d'ensemble, parcours, cours, planning, mes résultats.
   - Le site public reste entièrement visitable.

## Ce qui garantit la lecture seule

- **Le jeton de démo porte la marque `demo_org`.** Avec lui, le serveur refuse toute requête qui modifie quelque chose (autre que GET, HEAD ou OPTIONS), sur n'importe quelle route, et n'ouvre aucune autre école (`app/api/dependencies.py`).
- **Le serveur n'ouvre que le parcours.** Un jeton de démo ne lit que les routes dont ces écrans ont besoin (`DEMO_ALLOWED_READS` dans `app/services/demo.py`, la même liste que `DEMO_OPEN_SCREENS` dans `frontend/src/lib/demoState.ts`). Toute autre lecture est refusée (`demo_locked`). Un nouvel écran ouvert à la démo s'ajoute aux deux listes.
- **Rien de ce que fait une requête de démo n'est gardé.** Certaines lectures enregistrent quelque chose au passage (un niveau de badge atteint) : pendant une requête de démo, ces écritures restent dans une transaction jamais validée, annulée à la fin de la requête.
- **Le rythme est limité par visiteur** (adresse IP) : 40 jetons de démo par heure et 20 PDF (relevés, factures) par 10 minutes, sinon une erreur 429 « Trop de demandes pour la démo ».
- **Le jeton reste dans l'onglet du visiteur** (stockage de session), sans cookie. Il ne devient jamais le cookie de connexion partagé, même en passant par `/auth/me` ou par le transfert vers un domaine personnalisé. Une personne déjà connectée à sa propre école dans un autre onglet le reste.
- **Côté interface, rien de ce qui modifie n'est envoyé** pendant la démo. Le visiteur voit le message « Mode démo : rien n'est enregistré. Créez votre école pour essayer pour de vrai. »
- **Sur le site de l'école de démo**, la commande et les favoris sont refusés côté serveur, même pour un vrai compte.

Le code est dans `backend/app/services/demo.py`, `demo_school.py`, `frontend/src/lib/demo.ts` et `frontend/src/components/DemoBar.tsx`. Les tests sont dans `backend/tests/test_demo.py`.
