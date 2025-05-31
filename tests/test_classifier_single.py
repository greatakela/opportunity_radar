import asyncio
from src.agents.classifier import _fetch_home, _is_relevant
from src.vector import upsert_company
from src.db import Session, Company

async def test_single(domain):
    print(f"Fetching homepage for {domain}")
    home_txt = await _fetch_home(domain)
    if not home_txt:
        print("No homepage text found.")
        return
    if not _is_relevant(home_txt):
        print("No AI keywords found.")
        return
    print("Saving to DB...")
    with Session() as ses:
        # Check if the company already exists
        existing = ses.query(Company).filter_by(domain=domain).first()
        if existing:
            print(f"Company {domain} already exists in the database.")
            return
        c = Company(name=domain.split(".")[0].title(), domain=domain, description=home_txt)
        ses.add(c)
        ses.commit()
        ses.refresh(c)
        print("Calling upsert_company...")
        upsert_company(c.id, home_txt)
        print("upsert_company finished.")

if __name__ == "__main__":
    asyncio.run(test_single("orquest.com"))