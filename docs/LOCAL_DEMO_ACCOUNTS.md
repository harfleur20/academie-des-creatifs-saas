# Comptes de démonstration locaux

Après avoir appliqué les migrations, depuis le dossier `backend` :

```bash
source .venv/Scripts/activate
python scripts/seed_local_demo.py
```

Le script refuse de s'exécuter avec `APP_ENV=production`.

Comptes créés :

- Professeur : `prof.demo@academie.local`
- Étudiant : `etudiant.demo@academie.local`
- Mot de passe commun : `Demo2026!`

Le seed est idempotent. Il crée ou remet à jour une école de démonstration, une formation publiée, une session ouverte, l'affectation professeur, l'inscription étudiant, un cours, une leçon et un prochain créneau.
