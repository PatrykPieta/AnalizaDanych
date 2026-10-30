"""
IT-Salary-Predictor: Data Cleaning & Preprocessing Module.

Zawiera funkcje czyszczące i transformujące surowe oferty JSON z tabeli 'raw_offers'
do ustrukturyzowanej tabeli 'cleaned_offers' przygotowanej dla Inżyniera ML.
"""

from typing import Any, Dict, List, Optional, Tuple
import numpy as np
import pandas as pd


# Słownik normalizacji technologii (częste warianty pisowni w ogłoszeniach)
TECH_NORMALIZATION_MAP: Dict[str, str] = {
    "react.js": "React",
    "reactjs": "React",
    "react": "React",
    "vue.js": "Vue",
    "vuejs": "Vue",
    "vue": "Vue",
    "node.js": "Node.js",
    "nodejs": "Node.js",
    "node": "Node.js",
    "angular.js": "Angular",
    "angularjs": "Angular",
    "angular": "Angular",
    "python3": "Python",
    "python": "Python",
    "javascript": "JavaScript",
    "js": "JavaScript",
    "typescript": "TypeScript",
    "ts": "TypeScript",
    "c#": "C#",
    ".net": ".NET",
    "dotnet": ".NET",
    ".net core": ".NET Core",
    "c++": "C++",
    "golang": "Go",
    "go": "Go",
    "postgresql": "PostgreSQL",
    "postgres": "PostgreSQL",
    "sql server": "MS SQL Server",
    "mssql": "MS SQL Server",
    "amazon web services": "AWS",
    "aws": "AWS",
    "google cloud platform": "GCP",
    "gcp": "GCP",
    "microsoft azure": "Azure",
    "azure": "Azure",
    "k8s": "Kubernetes",
    "kubernetes": "Kubernetes",
    "docker": "Docker",
}


def normalize_skill(skill_name: Optional[str]) -> Optional[str]:
    """Ujednolica nazwę technologii wg słownika synonimów."""
    if not skill_name or not isinstance(skill_name, str):
        return None
    cleaned = skill_name.strip()
    return TECH_NORMALIZATION_MAP.get(cleaned.lower(), cleaned)


def parse_salary_bands(employment_types: List[Dict[str, Any]]) -> Dict[str, Any]:
    """
    Ekstraktuje i normalizuje widełki płacowe dla różnych rodzajów umów.
    W API JustJoin.it pola 'from' i 'to' są już fabrycznie znormalizowane
    do stawek miesięcznych w PLN (niezależnie od tego, czy jednostką była godzina, dzień czy rok).
    """
    res: Dict[str, Any] = {
        "salary_b2b_from": np.nan,
        "salary_b2b_to": np.nan,
        "salary_b2b_avg": np.nan,
        "salary_uop_from": np.nan,
        "salary_uop_to": np.nan,
        "salary_uop_avg": np.nan,
        "target_salary_avg": np.nan,
        "primary_contract_type": None
    }

    if not isinstance(employment_types, list):
        return res

    for emp in employment_types:
        emp_type = emp.get("type")
        s_from = emp.get("from")
        s_to = emp.get("to")
        currency = emp.get("currency", "PLN")

        # Rozważamy kwoty w PLN
        if currency != "PLN":
            continue

        if s_from is None and s_to is None:
            continue

        val_from = float(s_from) if s_from is not None else np.nan
        val_to = float(s_to) if s_to is not None else np.nan
        val_avg = np.nanmean([val_from, val_to])

        if emp_type == "b2b":
            res["salary_b2b_from"] = val_from
            res["salary_b2b_to"] = val_to
            res["salary_b2b_avg"] = val_avg
        elif emp_type == "permanent":
            res["salary_uop_from"] = val_from
            res["salary_uop_to"] = val_to
            res["salary_uop_avg"] = val_avg

    # Wybór stawki wiodącej dla modelu ML (priorytet B2B, w drugiej kolejności UoP)
    if not np.isnan(res["salary_b2b_avg"]):
        res["target_salary_avg"] = res["salary_b2b_avg"]
        res["primary_contract_type"] = "b2b"
    elif not np.isnan(res["salary_uop_avg"]):
        res["target_salary_avg"] = res["salary_uop_avg"]
        res["primary_contract_type"] = "uop"

    return res


def transform_raw_offers_dataframe(df_raw: pd.DataFrame) -> pd.DataFrame:
    """
    Główna funkcja czyszcząca surowe zrzuty z tabeli 'raw_offers'.
    Zwraca ustrukturyzowany DataFrame gotowy do zasilenia tabeli 'cleaned_offers'.
    """
    rows = []

    for _, record in df_raw.iterrows():
        payload = record["payload"]
        if not isinstance(payload, dict):
            continue

        ext_id = str(payload.get("slug") or payload.get("guid") or record.get("external_id"))
        title = payload.get("title", "").strip()
        company = payload.get("companyName", "").strip()
        category = payload.get("category", {}).get("key", "other")
        seniority = payload.get("experienceLevel", "mid")
        workplace_type = payload.get("workplaceType", "office")
        city = payload.get("city", "").strip()
        is_remote = workplace_type == "remote"
        published_at = payload.get("publishedAt")

        # Rozbicie widełek
        salary_info = parse_salary_bands(payload.get("employmentTypes", []))

        # Ekstrakcja i normalizacja technologii
        raw_skills = payload.get("requiredSkills", [])
        skills = []
        if isinstance(raw_skills, list):
            for sk in raw_skills:
                name = sk.get("name") if isinstance(sk, dict) else str(sk)
                norm_name = normalize_skill(name)
                if norm_name and norm_name not in skills:
                    skills.append(norm_name)

        rows.append({
            "external_id": ext_id,
            "title": title,
            "company_name": company,
            "category": category,
            "seniority": seniority,
            "workplace_type": workplace_type,
            "city": city,
            "is_remote": is_remote,
            "published_at": published_at,
            "salary_b2b_from": salary_info["salary_b2b_from"],
            "salary_b2b_to": salary_info["salary_b2b_to"],
            "salary_b2b_avg": salary_info["salary_b2b_avg"],
            "salary_uop_from": salary_info["salary_uop_from"],
            "salary_uop_to": salary_info["salary_uop_to"],
            "salary_uop_avg": salary_info["salary_uop_avg"],
            "target_salary_avg": salary_info["target_salary_avg"],
            "primary_contract_type": salary_info["primary_contract_type"],
            "skills": skills,
            "skills_count": len(skills)
        })

    return pd.DataFrame(rows)
