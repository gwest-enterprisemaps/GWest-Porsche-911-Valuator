"""Porsche 911 domain knowledge used by the MCP server.

Baseline values are ILLUSTRATIVE seed figures (USD, mid-2026, good-condition
private-sale). The agent is instructed to cross-check them against live
market comps via web search before producing a final estimate.
"""

GENERATIONS = [
    {
        "code": "964",
        "years": (1989, 1994),
        "notes": "First 911 with ABS, power steering, coil springs. Air-cooled collectible.",
        "known_issues": ["Cylinder head oil leaks", "Dual-mass flywheel (early cars)"],
    },
    {
        "code": "993",
        "years": (1995, 1998),
        "notes": "Last air-cooled 911. Strong collector demand across all trims.",
        "known_issues": ["Valve guide wear", "Secondary air injection (SAI) clogging"],
    },
    {
        "code": "996",
        "years": (1999, 2004),
        "notes": "First water-cooled 911. Most affordable entry point; GT/Turbo trims exempt from stigma.",
        "known_issues": ["IMS bearing failure (non-Turbo/GT)", "Rear main seal leaks", "Cracked cylinder heads (rare)"],
    },
    {
        "code": "997.1",
        "years": (2005, 2008),
        "notes": "Return to classic styling. M96/M97 engines retain IMS/bore-score risk.",
        "known_issues": ["IMS bearing (2005 only, smaller bearing)", "Bore scoring (3.8L especially)"],
    },
    {
        "code": "997.2",
        "years": (2009, 2012),
        "notes": "New 9A1 DFI engine (no IMS), PDK introduced. Sweet spot for usability + value.",
        "known_issues": ["Coolant pipe fittings (Turbo)", "PDK early software"],
    },
    {
        "code": "991.1",
        "years": (2012, 2016),
        "notes": "Larger platform, electric steering. Last naturally-aspirated Carreras.",
        "known_issues": ["GT3 (2014) engine recall — verify replacement done"],
    },
    {
        "code": "991.2",
        "years": (2017, 2019),
        "notes": "Turbocharged Carreras. GT3 returned with manual option — strong demand.",
        "known_issues": ["Few systemic issues; check overrev reports on GT cars"],
    },
    {
        "code": "992.1",
        "years": (2020, 2023),
        "notes": "Wider body standard. 8-speed PDK. Digital-heavy interior.",
        "known_issues": ["Early infotainment glitches"],
    },
    {
        "code": "992.2",
        "years": (2024, 2026),
        "notes": "Facelift; hybrid GTS (T-Hybrid). Newest generation, values near MSRP or above for GT cars.",
        "known_issues": ["Too new for systemic issues"],
    },
]

# Baseline good-condition private-sale values (USD) by generation and trim family.
# (low, high) — ILLUSTRATIVE. Agent must validate with live comps.
BASELINE_VALUES = {
    "964": {"carrera": (65000, 110000), "targa": (70000, 115000), "cabriolet": (55000, 90000),
            "turbo": (180000, 320000), "rs": (300000, 550000)},
    "993": {"carrera": (75000, 130000), "targa": (85000, 140000), "cabriolet": (65000, 105000),
            "carrera_s": (140000, 200000), "turbo": (250000, 450000), "gt2": (900000, 1600000)},
    "996": {"carrera": (22000, 40000), "carrera_4s": (35000, 60000), "targa": (25000, 42000),
            "cabriolet": (18000, 32000), "turbo": (55000, 95000), "gt3": (90000, 140000),
            "gt2": (180000, 300000)},
    "997.1": {"carrera": (35000, 55000), "carrera_s": (42000, 65000), "carrera_4s": (45000, 70000),
              "targa": (45000, 68000), "cabriolet": (32000, 50000), "turbo": (75000, 115000),
              "gt3": (120000, 170000), "gt3_rs": (170000, 260000), "gt2": (200000, 320000)},
    "997.2": {"carrera": (50000, 72000), "carrera_s": (60000, 88000), "carrera_4s": (65000, 95000),
              "targa": (65000, 92000), "cabriolet": (48000, 70000), "turbo": (95000, 140000),
              "turbo_s": (115000, 160000), "gt3": (140000, 200000), "gt3_rs": (250000, 400000),
              "gt2_rs": (600000, 950000)},
    "991.1": {"carrera": (60000, 85000), "carrera_s": (72000, 100000), "carrera_4s": (78000, 108000),
              "targa": (85000, 115000), "cabriolet": (58000, 82000), "turbo": (105000, 140000),
              "turbo_s": (125000, 165000), "gt3": (135000, 175000), "gt3_rs": (185000, 240000)},
    "991.2": {"carrera": (75000, 100000), "carrera_s": (88000, 118000), "carrera_4s": (95000, 125000),
              "targa": (100000, 135000), "cabriolet": (72000, 98000), "gts": (105000, 140000),
              "turbo": (130000, 165000), "turbo_s": (155000, 200000), "gt3": (165000, 215000),
              "gt3_rs": (230000, 300000), "gt2_rs": (330000, 450000)},
    "992.1": {"carrera": (95000, 125000), "carrera_s": (110000, 145000), "carrera_4s": (118000, 152000),
              "targa": (125000, 160000), "cabriolet": (92000, 122000), "gts": (135000, 175000),
              "turbo": (165000, 200000), "turbo_s": (185000, 240000), "gt3": (215000, 270000),
              "gt3_rs": (300000, 420000), "sport_classic": (400000, 550000)},
    "992.2": {"carrera": (115000, 140000), "carrera_s": (135000, 165000), "gts": (165000, 210000),
              "targa": (150000, 185000), "cabriolet": (112000, 138000), "gt3": (250000, 330000),
              "gt3_rs": (380000, 500000), "turbo_s": (240000, 300000)},
}

# Options / attributes that move 911 values, by generation bucket.
VALUE_DRIVERS = {
    "air_cooled": [  # 964, 993
        {"factor": "Documented service history / engine rebuild records", "impact": "high", "direction": "up"},
        {"factor": "Matching numbers engine & gearbox", "impact": "high", "direction": "up"},
        {"factor": "Original paint / low respray count", "impact": "high", "direction": "up"},
        {"factor": "Rare factory colors (PTS-equivalent)", "impact": "medium", "direction": "up"},
        {"factor": "Sunroof-delete coupe", "impact": "medium", "direction": "up"},
        {"factor": "Accident history or rust", "impact": "high", "direction": "down"},
        {"factor": "Non-original engine or Tiptronic", "impact": "high", "direction": "down"},
    ],
    "water_cooled_early": [  # 996, 997.1
        {"factor": "IMS bearing retrofit with documentation", "impact": "high", "direction": "up"},
        {"factor": "Bore scope inspection results (997.1 3.8L)", "impact": "high", "direction": "up"},
        {"factor": "Manual transmission", "impact": "medium", "direction": "up"},
        {"factor": "Recent clutch / RMS service", "impact": "medium", "direction": "up"},
        {"factor": "Tiptronic on non-Turbo cars", "impact": "medium", "direction": "down"},
        {"factor": "Deferred maintenance / no records", "impact": "high", "direction": "down"},
    ],
    "modern": [  # 997.2+
        {"factor": "Manual transmission (Carrera/GT models)", "impact": "high", "direction": "up"},
        {"factor": "Sport Chrono package", "impact": "medium", "direction": "up"},
        {"factor": "Paint-to-Sample (PTS) or rare launch colors", "impact": "high", "direction": "up"},
        {"factor": "PCCB ceramic brakes (check rotor wear)", "impact": "medium", "direction": "up"},
        {"factor": "Front-axle lift (GT cars)", "impact": "medium", "direction": "up"},
        {"factor": "Full PPF from new", "impact": "medium", "direction": "up"},
        {"factor": "Buckets/LWB seats (GT cars)", "impact": "medium", "direction": "up"},
        {"factor": "Aftermarket tune / exhaust (non-reversible)", "impact": "medium", "direction": "down"},
        {"factor": "Paintwork or accident on CARFAX", "impact": "high", "direction": "down"},
        {"factor": "Overrev events in DME report (GT cars)", "impact": "high", "direction": "down"},
    ],
}


def generation_for_year(model_year: int):
    for g in GENERATIONS:
        if g["years"][0] <= model_year <= g["years"][1]:
            return g
    return None


def driver_bucket(gen_code: str) -> str:
    if gen_code in ("964", "993"):
        return "air_cooled"
    if gen_code in ("996", "997.1"):
        return "water_cooled_early"
    return "modern"


def normalize_trim(trim: str) -> str:
    t = trim.lower().strip().replace(" ", "_").replace("-", "_")
    aliases = {
        "c2": "carrera", "c4": "carrera", "carrera_4": "carrera", "base": "carrera",
        "c2s": "carrera_s", "c4s": "carrera_4s", "carrera_4_s": "carrera_4s",
        "carrera_gts": "gts", "targa_4s": "targa", "targa_4": "targa",
        "cab": "cabriolet", "convertible": "cabriolet",
        "gt3_touring": "gt3", "gt3rs": "gt3_rs", "gt2rs": "gt2_rs",
        "turbo_cabriolet": "turbo",
    }
    return aliases.get(t, t)
