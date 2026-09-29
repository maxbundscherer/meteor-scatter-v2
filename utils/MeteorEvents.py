from dataclasses import dataclass
from datetime import datetime, timedelta

import pandas as pd

LOCAL_DELTA = 2  # Delta of 2 days, so only the maximum is needed


class MeteorEvents:
    @dataclass
    class DateRange:
        start: datetime
        end: datetime
        label: str

    # YEAR-MOTH-DAY: pls 2025.02.01 not for e.g. 2025.2.1

    # Pls set previous year to 1999 in every entry (year will be overwritten in app)
    # Pls set current year to 2000 in every entry (year will be overwritten in app)
    # Pls set next year to 2001 in every entry (year will be overwritten in app)

    @staticmethod
    def get_data_items(day: str, split: str = "start") -> str:
        """
        Shift a given date string by LOCAL_DELTA days depending on split.
        - split == "start": subtract LOCAL_DELTA days
        - split == "end":   add LOCAL_DELTA days
        Returns the shifted date as 'YYYY-MM-DD'.
        """
        base = datetime.strptime(day, "%Y-%m-%d")
        if split == "start":
            shifted = base - timedelta(days=LOCAL_DELTA)
        elif split == "end":
            shifted = base + timedelta(days=LOCAL_DELTA)
        else:
            raise ValueError("split must be 'start' or 'end'")
        return shifted.strftime("%Y-%m-%d")

    # During class creation, call the undecorated function while building the ranges.
    get_data_items = get_data_items.__func__

    data_items = [
        DateRange(start=pd.to_datetime(get_data_items("2000-01-03", "start")),
                  end=pd.to_datetime(get_data_items("2000-01-03", "end")),
                  label="Quadrantiden (80)"),

        DateRange(start=pd.to_datetime(get_data_items("2000-01-18", "start")),
                  end=pd.to_datetime(get_data_items("2000-01-18", "end")),
                  label="γ-Ursae Minoriden (3)"),

        DateRange(start=pd.to_datetime(get_data_items("2000-02-08", "start")),
                  end=pd.to_datetime(get_data_items("2000-02-08", "end")),
                  label="α-Centauriden (6)"),

        DateRange(start=pd.to_datetime(get_data_items("2000-04-22", "start")),
                  end=pd.to_datetime(get_data_items("2000-04-22", "end")),
                  label="April Lyriden (18)"),

        DateRange(start=pd.to_datetime(get_data_items("2000-04-23", "start")),
                  end=pd.to_datetime(get_data_items("2000-04-23", "end")),
                  label="π-Puppiden (Var)"),

        DateRange(start=pd.to_datetime(get_data_items("2000-05-06", "start")),
                  end=pd.to_datetime(get_data_items("2000-05-06", "end")),
                  label="η-Aquariiden (50)"),

        DateRange(start=pd.to_datetime(get_data_items("2000-05-10", "start")),
                  end=pd.to_datetime(get_data_items("2000-05-10", "end")),
                  label="η-Lyriden (3)"),

        DateRange(start=pd.to_datetime(get_data_items("2000-06-07", "start")),
                  end=pd.to_datetime(get_data_items("2000-06-07", "end")),
                  label="Tages-Arietiden (30)"),

        DateRange(start=pd.to_datetime(get_data_items("2000-06-27", "start")),
                  end=pd.to_datetime(get_data_items("2000-06-27", "end")),
                  label="Juni Bootiden (Var)"),

        DateRange(start=pd.to_datetime(get_data_items("2000-07-10", "start")),
                  end=pd.to_datetime(get_data_items("2000-07-10", "end")),
                  label="Juli Pegasiden (3)"),

        DateRange(start=pd.to_datetime(get_data_items("2000-07-28", "start")),
                  end=pd.to_datetime(get_data_items("2000-07-28", "end")),
                  label="Juli γ-Draconiden (5)"),

        DateRange(start=pd.to_datetime(get_data_items("2000-07-31", "start")),
                  end=pd.to_datetime(get_data_items("2000-07-31", "end")),
                  label="S. δ-Aquariiden (25)"),

        DateRange(start=pd.to_datetime(get_data_items("2000-07-31", "start")),
                  end=pd.to_datetime(get_data_items("2000-07-31", "end")),
                  label="α-Capricorniden (5)"),

        DateRange(start=pd.to_datetime(get_data_items("2000-08-07", "start")),
                  end=pd.to_datetime(get_data_items("2000-08-07", "end")),
                  label="η-Eridaniden (3)"),

        DateRange(start=pd.to_datetime(get_data_items("2000-08-12", "start")),
                  end=pd.to_datetime(get_data_items("2000-08-12", "end")),
                  label="Perseiden (100)"),

        DateRange(start=pd.to_datetime(get_data_items("2000-08-16", "start")),
                  end=pd.to_datetime(get_data_items("2000-08-16", "end")),
                  label="κ-Cygniden (3)"),

        DateRange(start=pd.to_datetime(get_data_items("2000-09-01", "start")),
                  end=pd.to_datetime(get_data_items("2000-09-01", "end")),
                  label="Aurigiden (6)"),

        DateRange(start=pd.to_datetime(get_data_items("2000-09-09", "start")),
                  end=pd.to_datetime(get_data_items("2000-09-09", "end")),
                  label="Sep. ε-Perseiden (8)"),

        DateRange(start=pd.to_datetime(get_data_items("2000-09-27", "start")),
                  end=pd.to_datetime(get_data_items("2000-09-27", "end")),
                  label="Tages-Sextantiden (5)"),

        DateRange(start=pd.to_datetime(get_data_items("2000-10-05", "start")),
                  end=pd.to_datetime(get_data_items("2000-10-05", "end")),
                  label="Okt. Camelopard. (5)"),

        DateRange(start=pd.to_datetime(get_data_items("2000-10-08", "start")),
                  end=pd.to_datetime(get_data_items("2000-10-08", "end")),
                  label="Okt. Draconiden (5)"),

        DateRange(start=pd.to_datetime(get_data_items("2000-10-11", "start")),
                  end=pd.to_datetime(get_data_items("2000-10-11", "end")),
                  label="δ-Aurigiden (2)"),

        DateRange(start=pd.to_datetime(get_data_items("2000-10-18", "start")),
                  end=pd.to_datetime(get_data_items("2000-10-18", "end")),
                  label="ε-Geminiden (3)"),

        DateRange(start=pd.to_datetime(get_data_items("2000-10-21", "start")),
                  end=pd.to_datetime(get_data_items("2000-10-21", "end")),
                  label="Orioniden (20)"),

        DateRange(start=pd.to_datetime(get_data_items("2000-10-24", "start")),
                  end=pd.to_datetime(get_data_items("2000-10-24", "end")),
                  label="Leonis Minoriden (2)"),

        DateRange(start=pd.to_datetime(get_data_items("2000-11-05", "start")),
                  end=pd.to_datetime(get_data_items("2000-11-05", "end")),
                  label="S. Tauriden (7)"),

        DateRange(start=pd.to_datetime(get_data_items("2000-11-12", "start")),
                  end=pd.to_datetime(get_data_items("2000-11-12", "end")),
                  label="N. Tauriden (5)"),

        DateRange(start=pd.to_datetime(get_data_items("2000-11-17", "start")),
                  end=pd.to_datetime(get_data_items("2000-11-17", "end")),
                  label="Leoniden (10)"),

        DateRange(start=pd.to_datetime(get_data_items("2000-11-21", "start")),
                  end=pd.to_datetime(get_data_items("2000-11-21", "end")),
                  label="α-Monocerotiden (Var)"),

        DateRange(start=pd.to_datetime(get_data_items("2000-11-28", "start")),
                  end=pd.to_datetime(get_data_items("2000-11-28", "end")),
                  label="Nov. Orioniden (3)"),

        DateRange(start=pd.to_datetime(get_data_items("2000-12-01", "start")),
                  end=pd.to_datetime(get_data_items("2000-12-01", "end")),
                  label="Phoeniciden (Var)"),

        DateRange(start=pd.to_datetime(get_data_items("2000-12-07", "start")),
                  end=pd.to_datetime(get_data_items("2000-12-07", "end")),
                  label="Puppid-Veliden (10)"),
        DateRange(start=pd.to_datetime(get_data_items("2000-12-09", "start")),
                  end=pd.to_datetime(get_data_items("2000-12-09", "end")),
                  label="Monocerotiden (3)"),

        DateRange(start=pd.to_datetime(get_data_items("2000-12-09", "start")),
                  end=pd.to_datetime(get_data_items("2000-12-09", "end")),
                  label="σ-Hydriden (7)"),

        DateRange(start=pd.to_datetime(get_data_items("2000-12-14", "start")),
                  end=pd.to_datetime(get_data_items("2000-12-14", "end")),
                  label="Geminiden (150)"),

        DateRange(start=pd.to_datetime(get_data_items("2000-12-16", "start")),
                  end=pd.to_datetime(get_data_items("2000-12-16", "end")),
                  label="Comae Bereniciden (3)"),

        DateRange(start=pd.to_datetime(get_data_items("2000-12-22", "start")),
                  end=pd.to_datetime(get_data_items("2000-12-22", "end")),
                  label="Ursiden (10)"),
    ]

    # Preserve the public API as a static method after initializing data_items.
    get_data_items = staticmethod(get_data_items)

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
