# Architecture multi-tenant

## Règle fondamentale

Une donnée métier appartenant à une école doit implémenter `OrganizationOwnedMixin` ou, au minimum, posséder une clé étrangère `organization_id` non nulle vers `organizations.id`.

Un endpoint ne doit jamais récupérer une ressource tenant-scoped uniquement par son identifiant global.

Incorrect :

```python
db.get(FormationRecord, formation_id)
```

Correct :

```python
db.scalar(
    scoped_select(FormationRecord, tenant).where(
        FormationRecord.id == formation_id,
    )
)
```

## Tenant actif

Le lot 1 utilise `X-Organization-Id` pour sélectionner explicitement le tenant actif.

Le header n'accorde aucun droit à lui seul. Le backend vérifie :

1. que l'organisation existe et est active ;
2. que l'utilisateur est membre actif de cette organisation ;
3. que son rôle permet l'action demandée.

Pour éviter l'énumération d'organisations, un utilisateur qui tente d'accéder à une organisation à laquelle il n'appartient pas reçoit volontairement une réponse 404.

Le rôle plateforme `super_admin` peut traverser les tenants pour l'administration du SaaS.

## Rôles

- `owner`
- `admin`
- `manager`
- `teacher`
- `student`

Ces rôles appartiennent à `organization_members`. `platform_role` reste réservé aux droits de plateforme.

## Contraintes base

- une adhésion unique par utilisateur et organisation ;
- slug d'organisation globalement unique ;
- slug de formation unique seulement dans son organisation ;
- `organization_id` indexé ;
- `ON DELETE CASCADE` pour les données strictement rattachées.

## Portage des modules existants

Pour chaque module porté depuis l'Académie actuelle :

1. ajouter `organization_id` ;
2. remplacer les lectures globales par `scoped_select` ;
3. vérifier les mutations avec le tenant actif ;
4. écrire au moins un test avec deux organisations ;
5. ne merger que lorsque le test anti-fuite passe.

Le patron est d'abord validé sur les formations, puis sera appliqué aux sessions, professeurs, étudiants, cours, évaluations, lives et certificats.
