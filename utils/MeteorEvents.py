from dataclasses import dataclass
from datetime import datetime

import pandas as pd

class MeteorEvents:
    @dataclass
    class DateRange:
        start: datetime
        maximum: datetime
        end: datetime
        label: str

    # Date format: YYYY-MM-DD

    # Pls set previous year to 1999 in every entry (year will be overwritten in app)
    # Pls set current year to 2000 in every entry (year will be overwritten in app)
    # Pls set next year to 2001 in every entry (year will be overwritten in app)

    data_items = [
        DateRange(start=pd.to_datetime("1999-12-28"),
                  maximum=pd.to_datetime("2000-01-03"),
                  end=pd.to_datetime("2000-01-12"),
                  label="Quadrantiden (80)"),

        DateRange(start=pd.to_datetime("2000-01-10"),
                  maximum=pd.to_datetime("2000-01-18"),
                  end=pd.to_datetime("2000-01-22"),
                  label="γ-Ursae Minoriden (3)"),

        DateRange(start=pd.to_datetime("2000-01-31"),
                  maximum=pd.to_datetime("2000-02-08"),
                  end=pd.to_datetime("2000-02-20"),
                  label="α-Centauriden (6)"),

        DateRange(start=pd.to_datetime("2000-04-14"),
                  maximum=pd.to_datetime("2000-04-22"),
                  end=pd.to_datetime("2000-04-30"),
                  label="April Lyriden (18)"),

        DateRange(start=pd.to_datetime("2000-04-15"),
                  maximum=pd.to_datetime("2000-04-23"),
                  end=pd.to_datetime("2000-04-28"),
                  label="π-Puppiden (Var)"),

        DateRange(start=pd.to_datetime("2000-04-19"),
                  maximum=pd.to_datetime("2000-05-06"),
                  end=pd.to_datetime("2000-05-28"),
                  label="η-Aquariiden (50)"),

        DateRange(start=pd.to_datetime("2000-05-03"),
                  maximum=pd.to_datetime("2000-05-10"),
                  end=pd.to_datetime("2000-05-14"),
                  label="η-Lyriden (3)"),

        DateRange(start=pd.to_datetime("2000-05-14"),
                  maximum=pd.to_datetime("2000-06-07"),
                  end=pd.to_datetime("2000-06-24"),
                  label="Tages-Arietiden (30)"),

        DateRange(start=pd.to_datetime("2000-06-22"),
                  maximum=pd.to_datetime("2000-06-27"),
                  end=pd.to_datetime("2000-07-02"),
                  label="Juni Bootiden (Var)"),

        DateRange(start=pd.to_datetime("2000-07-04"),
                  maximum=pd.to_datetime("2000-07-10"),
                  end=pd.to_datetime("2000-07-14"),
                  label="Juli Pegasiden (3)"),

        DateRange(start=pd.to_datetime("2000-07-25"),
                  maximum=pd.to_datetime("2000-07-28"),
                  end=pd.to_datetime("2000-07-31"),
                  label="Juli γ-Draconiden (5)"),

        DateRange(start=pd.to_datetime("2000-07-12"),
                  maximum=pd.to_datetime("2000-07-31"),
                  end=pd.to_datetime("2000-08-23"),
                  label="S. δ-Aquariiden (25)"),

        DateRange(start=pd.to_datetime("2000-07-03"),
                  maximum=pd.to_datetime("2000-07-31"),
                  end=pd.to_datetime("2000-08-15"),
                  label="α-Capricorniden (5)"),

        DateRange(start=pd.to_datetime("2000-07-31"),
                  maximum=pd.to_datetime("2000-08-07"),
                  end=pd.to_datetime("2000-08-19"),
                  label="η-Eridaniden (3)"),

        DateRange(start=pd.to_datetime("2000-07-17"),
                  maximum=pd.to_datetime("2000-08-12"),
                  end=pd.to_datetime("2000-08-24"),
                  label="Perseiden (100)"),

        DateRange(start=pd.to_datetime("2000-08-03"),
                  maximum=pd.to_datetime("2000-08-16"),
                  end=pd.to_datetime("2000-08-28"),
                  label="κ-Cygniden (3)"),

        DateRange(start=pd.to_datetime("2000-08-28"),
                  maximum=pd.to_datetime("2000-09-01"),
                  end=pd.to_datetime("2000-09-05"),
                  label="Aurigiden (6)"),

        DateRange(start=pd.to_datetime("2000-09-05"),
                  maximum=pd.to_datetime("2000-09-09"),
                  end=pd.to_datetime("2000-09-21"),
                  label="Sep. ε-Perseiden (8)"),

        DateRange(start=pd.to_datetime("2000-09-09"),
                  maximum=pd.to_datetime("2000-09-27"),
                  end=pd.to_datetime("2000-10-09"),
                  label="Tages-Sextantiden (5)"),

        DateRange(start=pd.to_datetime("2000-10-05"),
                  maximum=pd.to_datetime("2000-10-05"),
                  end=pd.to_datetime("2000-10-06"),
                  label="Okt. Camelopard. (5)"),

        DateRange(start=pd.to_datetime("2000-10-06"),
                  maximum=pd.to_datetime("2000-10-08"),
                  end=pd.to_datetime("2000-10-10"),
                  label="Okt. Draconiden (5)"),

        DateRange(start=pd.to_datetime("2000-10-10"),
                  maximum=pd.to_datetime("2000-10-11"),
                  end=pd.to_datetime("2000-10-18"),
                  label="δ-Aurigiden (2)"),

        DateRange(start=pd.to_datetime("2000-10-14"),
                  maximum=pd.to_datetime("2000-10-18"),
                  end=pd.to_datetime("2000-10-27"),
                  label="ε-Geminiden (3)"),

        DateRange(start=pd.to_datetime("2000-10-02"),
                  maximum=pd.to_datetime("2000-10-21"),
                  end=pd.to_datetime("2000-11-07"),
                  label="Orioniden (20)"),

        DateRange(start=pd.to_datetime("2000-10-19"),
                  maximum=pd.to_datetime("2000-10-24"),
                  end=pd.to_datetime("2000-10-27"),
                  label="Leonis Minoriden (2)"),

        DateRange(start=pd.to_datetime("2000-09-20"),
                  maximum=pd.to_datetime("2000-11-05"),
                  end=pd.to_datetime("2000-11-20"),
                  label="S. Tauriden (7)"),

        DateRange(start=pd.to_datetime("2000-10-20"),
                  maximum=pd.to_datetime("2000-11-12"),
                  end=pd.to_datetime("2000-12-10"),
                  label="N. Tauriden (5)"),

        DateRange(start=pd.to_datetime("2000-11-06"),
                  maximum=pd.to_datetime("2000-11-17"),
                  end=pd.to_datetime("2000-11-30"),
                  label="Leoniden (10)"),

        DateRange(start=pd.to_datetime("2000-11-15"),
                  maximum=pd.to_datetime("2000-11-21"),
                  end=pd.to_datetime("2000-11-25"),
                  label="α-Monocerotiden (Var)"),

        DateRange(start=pd.to_datetime("2000-11-13"),
                  maximum=pd.to_datetime("2000-11-28"),
                  end=pd.to_datetime("2000-12-06"),
                  label="Nov. Orioniden (3)"),

        DateRange(start=pd.to_datetime("2000-12-01"),
                  maximum=pd.to_datetime("2000-12-01"),
                  end=pd.to_datetime("2000-12-05"),
                  label="Phoeniciden (Var)"),

        DateRange(start=pd.to_datetime("2000-12-01"),
                  maximum=pd.to_datetime("2000-12-07"),
                  end=pd.to_datetime("2000-12-15"),
                  label="Puppid-Veliden (10)"),

        DateRange(start=pd.to_datetime("2000-12-05"),
                  maximum=pd.to_datetime("2000-12-09"),
                  end=pd.to_datetime("2000-12-20"),
                  label="Monocerotiden (3)"),

        DateRange(start=pd.to_datetime("2000-12-03"),
                  maximum=pd.to_datetime("2000-12-09"),
                  end=pd.to_datetime("2000-12-20"),
                  label="σ-Hydriden (7)"),

        DateRange(start=pd.to_datetime("2000-12-04"),
                  maximum=pd.to_datetime("2000-12-14"),
                  end=pd.to_datetime("2000-12-20"),
                  label="Geminiden (150)"),

        DateRange(start=pd.to_datetime("2000-12-05"),
                  maximum=pd.to_datetime("2000-12-16"),
                  end=pd.to_datetime("2001-02-04"),
                  label="Comae Bereniciden (3)"),

        DateRange(start=pd.to_datetime("2000-12-17"),
                  maximum=pd.to_datetime("2000-12-22"),
                  end=pd.to_datetime("2000-12-26"),
                  label="Ursiden (10)"),
    ]

    @staticmethod
    def overwrite_years(data_items):
        current_year = datetime.now().year
        previous_year = current_year - 1
        next_year = current_year + 1

        for item in data_items:
            if item.start.year == 2000:
                item.start = item.start.replace(year=current_year)
            elif item.start.year == 1999:
                item.start = item.start.replace(year=previous_year)
            elif item.start.year == 2001:
                item.start = item.start.replace(year=next_year)

            if item.maximum.year == 2000:
                item.maximum = item.maximum.replace(year=current_year)
            elif item.maximum.year == 1999:
                item.maximum = item.maximum.replace(year=previous_year)
            elif item.maximum.year == 2001:
                item.maximum = item.maximum.replace(year=next_year)

            if item.end.year == 2000:
                item.end = item.end.replace(year=current_year)
            elif item.end.year == 1999:
                item.end = item.end.replace(year=previous_year)
            elif item.end.year == 2001:
                item.end = item.end.replace(year=next_year)

        return data_items


## Test Section
if __name__ == "__main__":
    Local = MeteorEvents()
    print(Local.data_items[2].label)
    print(Local.data_items[2].start)
