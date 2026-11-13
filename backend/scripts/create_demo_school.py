"""Create the demonstration school, Studio Kora (docs/DEMO.md).

From `backend`, on a migrated database:

    python scripts/create_demo_school.py            # create it
    python scripts/create_demo_school.py --reset    # delete it and create it again, dates from today
    python scripts/create_demo_school.py --password 'Demo2026!'   # local tests only: a known password

Then give its address to the backend: DEMO_ORGANIZATION_SLUG=studio-kora.
Without --password, nobody knows the passwords of its fictional people: the demo
opens its spaces with read-only tokens.
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.db.session import SessionLocal  # noqa: E402
from app.services.demo_school import DEMO_SLUG, build_demo_school, remove_demo_school  # noqa: E402


def main() -> int:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    parser = argparse.ArgumentParser(description="Crée l'école de démonstration.")
    parser.add_argument("--slug", default=DEMO_SLUG, help="adresse courte de l'école (défaut : studio-kora)")
    parser.add_argument("--reset", action="store_true", help="supprime l'école de démo existante avant de la recréer")
    parser.add_argument("--password", help="mot de passe commun aux comptes fictifs, pour les tests en local seulement")
    parser.add_argument("--site-url", help="adresse du site qui sert les images de frontend/public/demo (défaut : FRONTEND_URL)")
    args = parser.parse_args()

    db = SessionLocal()
    try:
        if args.reset and remove_demo_school(db, args.slug):
            print(f"Ancienne école « {args.slug} » supprimée.")
        try:
            summary = build_demo_school(db, slug=args.slug, password=args.password, site_url=args.site_url)
        except ValueError as error:
            print(f"{error} Relancez avec --reset pour la recréer.")
            return 1
    finally:
        db.close()
    print(f"École de démo prête : {summary['formations']} formations, {summary['students']} étudiants.")
    print(f"Direction : {summary['owner']} | Professeur : {summary['teacher']} | Étudiante : {summary['student']}")
    print(f"À mettre dans backend/.env : DEMO_ORGANIZATION_SLUG={summary['slug']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
