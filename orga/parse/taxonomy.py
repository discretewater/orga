"""
Default Weighted Taxonomy for ORGA.
Used when no external taxonomy is provided.
Tuned for M7.1: Stricter weights and more negative keywords to prevent false positives.
"""

DEFAULT_TAXONOMY = {
    "Hospital": {
        "keywords": {
            "hospital": 5.0,
            "medical center": 4.0,
            "medical centre": 4.0,
            "health sciences centre": 4.0,
            "clinic": 2.5, # Lowered from 3.0 (could be vet/legal)
            "health care": 2.0, # Very generic
            "patient": 1.5,
            "emergency": 2.0,
            "surgery": 2.0,
            "pediatric": 3.0,
            "doctors": 1.5,
            "nursing": 1.5,
            "physicians": 1.5
        },
        "negative_keywords": [
            "veterinary", "pet hospital", "animal hospital", "pet care", 
            "news about hospitals", "hospital foundation", # Foundation is a separate entity
            "toy hospital", "doll hospital"
        ]
    },
    "University": {
        "keywords": {
            "university": 5.0,
            "college": 3.0, # Can be professional college
            "campus": 2.5,
            "academic": 2.5,
            "research university": 4.0,
            "students": 1.5,
            "faculty": 1.5,
            "admissions": 2.0,
            "degree": 2.0,
            "undergraduate": 2.0,
            "graduate studies": 3.0
        },
        "negative_keywords": [
            "preschool", "daycare", "kindergarten", "driving school", 
            "training center", "career college" # Distinction vs Uni
        ]
    },
    "NonProfit": {
        "keywords": {
            "non-profit": 5.0,
            "not-for-profit": 5.0,
            "charity": 4.0,
            "charitable organization": 5.0,
            "foundation": 3.0, # Can be hospital foundation
            "donate": 2.0, # Many orgs have donate, doesn't define them
            "volunteer": 2.0,
            "mission": 1.0, # Too generic
            "community": 1.0, # Too generic
            "advocacy": 2.0,
            "support": 0.5  # Very generic
        },
        "negative_keywords": [
            "profit", "commercial", "inc.", "ltd.", "llc", "corporation"
        ]
    },
    "Government": {
        "keywords": {
            "government": 5.0,
            "ministry": 4.0,
            "department of": 3.0, # Ambiguous (Dept of Medicine vs Dept of State)
            "federal": 3.0,
            "provincial": 3.0,
            "municipal": 3.0,
            "city of": 4.0,
            "public service": 2.0,
            "official site": 1.0
        },
        "negative_keywords": [
            "student government", "student council"
        ]
    },
    "InternationalOrg": {
        "keywords": {
            "united nations": 5.0,
            "international organization": 4.0,
            "intergovernmental": 4.0,
            "global": 1.5, # Too generic
            "humanitarian": 3.0,
            "world health": 5.0,
            "unicef": 5.0,
            "unesco": 5.0,
            "wfp": 5.0,
            "who": 2.0 # Ambiguous stop word if case insensitive
        },
        "negative_keywords": [
            "international students", "international shipping", "international cuisine"
        ]
    },
    "Association": {
        "keywords": {
            "association": 5.0,
            "society": 3.5,
            "institute": 3.0,
            "members": 2.0,
            "membership": 2.0,
            "conference": 1.5,
            "professional": 1.5
        },
        "negative_keywords": [
            "homeowners association", "condo association"
        ]
    }
}
