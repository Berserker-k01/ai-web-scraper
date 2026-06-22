import csv
import json
from pathlib import Path
from typing import List

from openpyxl import Workbook

from models.business import BusinessLead

EXPORT_COLUMNS = [
    "Company Name",
    "Industry",
    "Description",
    "Address",
    "City",
    "Country",
    "Phone",
    "Email",
    "Website",
    "Facebook",
    "LinkedIn",
    "Instagram",
    "WhatsApp",
    "Latitude",
    "Longitude",
    "Source URL",
]


def export_json(leads: List[BusinessLead], path: Path) -> None:
    data = [lead.model_dump() for lead in leads]
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")


def export_csv(leads: List[BusinessLead], path: Path) -> None:
    rows = [lead.to_export_row() for lead in leads]
    with path.open("w", newline="", encoding="utf-8-sig") as file:
        writer = csv.DictWriter(file, fieldnames=EXPORT_COLUMNS)
        writer.writeheader()
        writer.writerows(rows)


def export_xlsx(leads: List[BusinessLead], path: Path) -> None:
    workbook = Workbook()
    sheet = workbook.active
    sheet.title = "Leads"
    sheet.append(EXPORT_COLUMNS)

    for lead in leads:
        row = lead.to_export_row()
        sheet.append([row[col] for col in EXPORT_COLUMNS])

    workbook.save(path)


def export_all(leads: List[BusinessLead], output_dir: Path, basename: str = "leads") -> dict:
    output_dir.mkdir(parents=True, exist_ok=True)
    paths = {
        "json": output_dir / f"{basename}.json",
        "csv": output_dir / f"{basename}.csv",
        "xlsx": output_dir / f"{basename}.xlsx",
    }
    export_json(leads, paths["json"])
    export_csv(leads, paths["csv"])
    export_xlsx(leads, paths["xlsx"])
    return {key: str(path) for key, path in paths.items()}
