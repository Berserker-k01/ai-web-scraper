import argparse
import asyncio
import sys

from dotenv import load_dotenv

load_dotenv()


def main() -> None:
    parser = argparse.ArgumentParser(
        description="B2B Lead Scraper — génération de leads depuis des annuaires professionnels."
    )
    parser.add_argument(
        "--url",
        required=True,
        help="URL de la page de recherche ou catégorie à scraper.",
    )
    parser.add_argument(
        "--web",
        action="store_true",
        help="Lancer l'interface web (équivalent à python app.py).",
    )
    args = parser.parse_args()

    if args.web:
        import uvicorn
        uvicorn.run("app:app", host="0.0.0.0", port=8000, reload=False)
        return

    from config import API_TOKEN
    if not API_TOKEN:
        print("Erreur : DEEPSEEK_API_KEY manquante dans .env")
        sys.exit(1)

    from src.lead_scraper import LeadScraper
    from src.progress import ProgressTracker

    tracker = ProgressTracker()

    async def run():
        scraper = LeadScraper(progress=tracker)
        leads = await scraper.run(args.url)
        snap = tracker.snapshot()
        print(f"\n✓ {len(leads)} entreprises extraites.")
        if snap.get("export_files"):
            for fmt, path in snap["export_files"].items():
                print(f"  {fmt.upper()} : {path}")
        print("\nPour l'interface web : python app.py  ou  docker compose up")

    asyncio.run(run())


if __name__ == "__main__":
    main()
