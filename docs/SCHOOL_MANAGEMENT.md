# Gestion des écoles — Lot 2

## Objectif

Le Lot 2 transforme le tenant technique du Lot 1 en véritable espace administrable par le client.

## Paramètres d'école

Chaque organisation possède maintenant des paramètres opérationnels :

- nom ;
- email de contact ;
- fuseau horaire ;
- locale.

Le branding visuel (logo, couleurs, domaine personnalisé) reste volontairement réservé au lot white-label.

## Rôles

Hiérarchie de gestion :

- `owner` : contrôle complet de l'école ;
- `admin` : administration opérationnelle, sans contrôle des propriétaires ;
- `manager` : gestion des professeurs et étudiants ;
- `teacher` : accès pédagogique ;
- `student` : accès apprenant.

Un administrateur ne peut pas se promouvoir ou promouvoir un autre membre en `owner`.

## Protection des propriétaires

Une organisation doit toujours conserver au moins un `owner` actif.

Le backend refuse donc :

- la rétrogradation du dernier propriétaire ;
- la suspension du dernier propriétaire.

On conserve les adhésions suspendues au lieu de les supprimer afin de préserver l'historique.

## Invitations

Les invitations :

- sont rattachées à une seule organisation ;
- expirent après 7 jours ;
- utilisent un token aléatoire dont seul le hash SHA-256 est stocké ;
- ne peuvent être acceptées que par un compte utilisant l'adresse email invitée ;
- deviennent invalides après acceptation ou annulation.

Le token brut n'est renvoyé qu'au moment de la création. L'intégration email utilisera ensuite ce token pour construire le lien envoyé au futur membre.

## Isolation

Toutes les opérations de gestion d'un membre ou d'une invitation filtrent aussi par `organization_id`.

Même avec l'identifiant d'un membre appartenant à une autre école, l'API répond comme si cette ressource n'existait pas dans le tenant actif.
