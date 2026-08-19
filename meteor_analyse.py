"""Interaktive Plotly-Auswertung der CSV-Dateien aus ``meteor_detect.py``.

Ohne Argument wird die zuletzt geaenderte ``meteor_events_*.csv`` aus ``out/``
geladen. Jede Visualisierung wird als eigene HTML-Datei gespeichert.
"""

from __future__ import annotations

import argparse
from pathlib import Path
from typing import Callable

import pandas as pd
import plotly.graph_objects as go

SCRIPT_DIR = Path(__file__).resolve().parent
DEFAULT_OUTPUT_DIR = SCRIPT_DIR / "out"
REQUIRED_COLUMNS = {
    "start_time", "stop_time", "start_seconds", "stop_seconds",
    "duration_seconds", "snr_mean_db", "snr_max_db", "status",
}
NUMERIC_COLUMNS = [
    "start_seconds", "stop_seconds", "duration_seconds",
    "snr_mean_db", "snr_max_db",
]
WEEKDAY_LABELS = [
    "Montag", "Dienstag", "Mittwoch", "Donnerstag",
    "Freitag", "Samstag", "Sonntag",
]
MONTH_LABELS = [
    "Jan", "Feb", "Mär", "Apr", "Mai", "Jun",
    "Jul", "Aug", "Sep", "Okt", "Nov", "Dez",
]


def newest_event_csv(output_dir: Path = DEFAULT_OUTPUT_DIR) -> Path:
    """Liefert die zuletzt geaenderte Event-CSV im Ausgabeordner."""
    candidates = list(output_dir.glob("meteor_events_*.csv"))
    if not candidates:
        raise FileNotFoundError(
            f"Keine meteor_events_*.csv in '{output_dir}' gefunden."
        )
    return max(candidates, key=lambda path: path.stat().st_mtime)


def load_events(csv_path: Path | str | None = None) -> pd.DataFrame:
    """Laedt und validiert eine Event-CSV als pandas DataFrame."""
    path = Path(csv_path).expanduser().resolve() if csv_path else newest_event_csv()
    if not path.is_file():
        raise FileNotFoundError(f"CSV-Datei nicht gefunden: {path}")

    dataframe = pd.read_csv(path)
    missing = REQUIRED_COLUMNS.difference(dataframe.columns)
    if missing:
        raise ValueError(
            "In der CSV fehlen folgende Spalten: " + ", ".join(sorted(missing))
        )

    dataframe["start_time"] = pd.to_datetime(
        dataframe["start_time"], utc=True, errors="raise"
    )
    dataframe["stop_time"] = pd.to_datetime(
        dataframe["stop_time"], utc=True, errors="raise"
    )
    dataframe[NUMERIC_COLUMNS] = dataframe[NUMERIC_COLUMNS].apply(
        pd.to_numeric, errors="raise"
    )
    dataframe = dataframe.sort_values("start_time").reset_index(drop=True)
    dataframe.attrs["source"] = path
    return dataframe


def _layout(figure: go.Figure, title: str, x_title: str, y_title: str) -> go.Figure:
    figure.update_layout(
        title=title, xaxis_title=x_title, yaxis_title=y_title,
        template="plotly_white", hovermode="x unified",
        width=1000, height=550,
    )
    return figure


def _empty_figure(title: str) -> go.Figure:
    figure = go.Figure()
    figure.add_annotation(
        text="Die CSV enthält noch keine Events.", x=0.5, y=0.5,
        xref="paper", yref="paper", showarrow=False, font={"size": 18},
    )
    return _layout(figure, title, "", "")


def plot_snr_timeline(dataframe: pd.DataFrame) -> go.Figure:
    figure = go.Figure()
    figure.add_trace(go.Scatter(
        x=dataframe["start_time"], y=dataframe["snr_mean_db"],
        mode="lines+markers", name="SNR Mittel",
    ))
    figure.add_trace(go.Scatter(
        x=dataframe["start_time"], y=dataframe["snr_max_db"],
        mode="lines+markers", name="SNR Maximum",
    ))
    return _layout(figure, "Signal-Rausch-Abstand", "Zeit (UTC)", "SNR [dB]")


def plot_event_duration(dataframe: pd.DataFrame) -> go.Figure:
    if dataframe.empty:
        return _empty_figure("Dauer je Event")

    colors = dataframe["status"].map(
        {"detected": "#1f77b4", "discarded_timeout": "#ff7f0e"}
    ).fillna("#7f7f7f")

    # Plotly interpretiert die Breite von Balken auf Datumsachsen in
    # Millisekunden. Ohne eine explizite Breite koennen einzelne Events so
    # schmal gezeichnet werden, dass der Report leer aussieht.
    if len(dataframe) == 1:
        bar_width_ms = 60_000.0
    else:
        time_span_ms = (
                               dataframe["start_time"].max() - dataframe["start_time"].min()
                       ).total_seconds() * 1_000
        bar_width_ms = max(1.0, time_span_ms * 0.7 / len(dataframe))

    figure = go.Figure(go.Bar(
        x=dataframe["start_time"], y=dataframe["duration_seconds"],
        width=bar_width_ms, marker_color=colors,
        customdata=dataframe[["status", "snr_max_db"]],
        hovertemplate=(
            "Zeit: %{x}<br>Dauer: %{y:.3f} s<br>Status: %{customdata[0]}"
            "<br>SNR max.: %{customdata[1]:.3f} dB<extra></extra>"
        ),
    ))
    return _layout(figure, "Dauer je Event", "Zeit (UTC)", "Dauer [s]")


def plot_duration_histogram(dataframe: pd.DataFrame) -> go.Figure:
    figure = go.Figure(go.Histogram(
        x=dataframe["duration_seconds"], nbinsx=400,
        name="Dauer", marker_color="#1f77b4",
    ))
    return _layout(figure, "Verteilung der Event-Dauer", "Dauer [s]", "Anzahl")


def plot_duration_snr(dataframe: pd.DataFrame) -> go.Figure:
    if dataframe.empty:
        return _empty_figure("SNR vs. Event-Dauer")

    figure = go.Figure()
    for status, group in dataframe.groupby("status", sort=False):
        hover_data = group[["start_time", "snr_mean_db", "snr_max_db"]]
        figure.add_trace(go.Scatter(
            x=group["duration_seconds"], y=group["snr_mean_db"],
            mode="markers", name=f"{status} – SNR Mittel",
            legendgroup=str(status), marker={"symbol": "circle"},
            customdata=hover_data,
            hovertemplate=(
                "Dauer: %{x:.3f} s<br>SNR mittel: %{customdata[1]:.3f} dB"
                "<br>SNR max.: %{customdata[2]:.3f} dB"
                "<br>Zeit: %{customdata[0]}<extra>%{fullData.name}</extra>"
            ),
        ))
        figure.add_trace(go.Scatter(
            x=group["duration_seconds"], y=group["snr_max_db"],
            mode="markers", name=f"{status} – SNR Maximum",
            legendgroup=str(status), marker={"symbol": "x"},
            customdata=hover_data,
            hovertemplate=(
                "Dauer: %{x:.3f} s<br>SNR mittel: %{customdata[1]:.3f} dB"
                "<br>SNR max.: %{customdata[2]:.3f} dB"
                "<br>Zeit: %{customdata[0]}<extra>%{fullData.name}</extra>"
            ),
        ))
    figure = _layout(
        figure, "SNR vs. Event-Dauer", "Dauer [s]", "SNR [dB]"
    )
    figure.update_layout(hovermode="closest")
    return figure


def plot_snr_histogram(dataframe: pd.DataFrame) -> go.Figure:
    detected = dataframe[dataframe["status"] == "detected"]
    if detected.empty:
        return _empty_figure("Verteilung der SNR (nicht verworfen)")

    figure = go.Figure()
    figure.add_trace(go.Histogram(
        x=detected["snr_mean_db"], name="SNR Mittel", opacity=0.7,
    ))
    figure.add_trace(go.Histogram(
        x=detected["snr_max_db"], name="SNR Maximum", opacity=0.7,
    ))
    figure.update_layout(barmode="overlay")
    return _layout(
        figure, "Verteilung der SNR (nicht verworfen)", "SNR [dB]", "Anzahl"
    )


def _count_series(
        dataframe: pd.DataFrame, attribute: str, index: pd.Index,
) -> tuple[pd.Series, pd.Series]:
    all_counts = dataframe.groupby(attribute).size().reindex(index, fill_value=0)
    discarded_counts = (
        dataframe[dataframe["status"] != "detected"]
        .groupby(attribute).size().reindex(index, fill_value=0)
    )
    return all_counts, discarded_counts


def _count_figure(
        x_values: pd.Index,
        all_counts: pd.Series,
        discarded_counts: pd.Series,
        title: str,
        x_title: str,
) -> go.Figure:
    figure = go.Figure()
    figure.add_trace(go.Bar(
        x=x_values, y=all_counts, name="Alle", marker_color="blue"
    ))
    figure.add_trace(go.Bar(
        x=x_values, y=discarded_counts, name="Verworfen", marker_color="red"
    ))
    figure.update_layout(barmode="overlay")
    return _layout(figure, title, x_title, "Anzahl")


def plot_counts_per_date_hour(dataframe: pd.DataFrame) -> go.Figure:
    """Zeigt Datum/Zeit gegen die Anzahl der Events innerhalb jeder Stunde."""
    if dataframe.empty:
        return _empty_figure("Detektionen pro Stunde")

    data = dataframe.assign(time_hour=dataframe["start_time"].dt.floor("h"))
    hours = pd.date_range(
        data["time_hour"].min(), data["time_hour"].max(), freq="h"
    )
    all_counts, discarded_counts = _count_series(data, "time_hour", hours)
    figure = _count_figure(
        hours, all_counts, discarded_counts,
        "Detektionen pro Stunde nach Datum", "Datum und Stunde (UTC)",
    )
    figure.update_xaxes(tickformat="%d.%m.%Y<br>%H:%M")
    return figure


def plot_counts_per_date_minute(dataframe: pd.DataFrame) -> go.Figure:
    """Zeigt Datum/Zeit gegen die Anzahl der Events innerhalb jeder Minute."""
    if dataframe.empty:
        return _empty_figure("Detektionen pro Minute")

    data = dataframe.assign(time_minute=dataframe["start_time"].dt.floor("min"))
    minutes = pd.date_range(
        data["time_minute"].min(), data["time_minute"].max(), freq="min"
    )
    all_counts, discarded_counts = _count_series(
        data, "time_minute", minutes
    )
    figure = _count_figure(
        minutes, all_counts, discarded_counts,
        "Detektionen pro Minute nach Datum", "Datum und Minute (UTC)",
    )
    figure.update_xaxes(tickformat="%d.%m.%Y<br>%H:%M")
    return figure


def plot_counts_by_hour(dataframe: pd.DataFrame) -> go.Figure:
    data = dataframe.assign(hour=dataframe["start_time"].dt.hour)
    index = pd.Index(range(24))
    counts = _count_series(data, "hour", index)
    return _count_figure(index, *counts, "Detektionen nach Stunde", "Stunde (UTC)")


def plot_counts_by_weekday(dataframe: pd.DataFrame) -> go.Figure:
    data = dataframe.assign(dayofweek=dataframe["start_time"].dt.dayofweek)
    index = pd.Index(range(7))
    counts = _count_series(data, "dayofweek", index)
    figure = _count_figure(
        index, *counts, "Detektionen nach Wochentag", "Wochentag"
    )
    figure.update_xaxes(
        tickmode="array", tickvals=list(index), ticktext=WEEKDAY_LABELS
    )
    return figure


def plot_counts_by_month(dataframe: pd.DataFrame) -> go.Figure:
    data = dataframe.assign(month=dataframe["start_time"].dt.month)
    index = pd.Index(range(1, 13))
    counts = _count_series(data, "month", index)
    figure = _count_figure(index, *counts, "Detektionen nach Monat", "Monat")
    figure.update_xaxes(
        tickmode="array", tickvals=list(index), ticktext=MONTH_LABELS
    )
    return figure


def _date_hour_matrix(
        dataframe: pd.DataFrame, discarded_only: bool = False,
) -> pd.DataFrame:
    data = dataframe.copy()
    if discarded_only:
        data = data[data["status"] != "detected"]

    all_dates = pd.DatetimeIndex(
        dataframe["start_time"].dt.floor("D").drop_duplicates().sort_values()
    )
    if data.empty:
        matrix = pd.DataFrame(0, index=all_dates, columns=range(24))
    else:
        data["date"] = data["start_time"].dt.floor("D")
        data["hour"] = data["start_time"].dt.hour
        matrix = pd.crosstab(data["date"], data["hour"])
        matrix = matrix.reindex(index=all_dates, columns=range(24), fill_value=0)
    matrix.index = matrix.index.strftime("%d.%m.%Y")
    return matrix


def _heatmap_figure(matrix: pd.DataFrame, title: str, y_title: str) -> go.Figure:
    # Funktioniert sowohl mit pandas-Versionen vor als auch nach Einfuehrung
    # von DataFrame.map.
    text = matrix.astype(str).mask(matrix == 0, "")
    figure = go.Figure(go.Heatmap(
        z=matrix.to_numpy(), x=list(matrix.columns), y=list(matrix.index),
        colorscale="Viridis", colorbar={"title": "Anzahl"},
        hovertemplate=(
                "Stunde: %{x}:00 UTC<br>" + y_title + ": %{y}"
                                                      "<br>Anzahl: %{z}<extra></extra>"
        ),
    ))
    # Heatmap.texttemplate ist erst in neueren Plotly-Versionen verfuegbar.
    # Annotationen zeigen die Werte auch mit aelteren Installationen an.
    for row_index, y_value in enumerate(matrix.index):
        for column_index, x_value in enumerate(matrix.columns):
            if text.iat[row_index, column_index]:
                figure.add_annotation(
                    x=x_value, y=y_value,
                    text=text.iat[row_index, column_index],
                    showarrow=False, font={"color": "white"},
                )
    return _layout(figure, title, "Stunde (UTC)", y_title)


def plot_weekday_hour_heatmap(dataframe: pd.DataFrame) -> go.Figure:
    data = dataframe.assign(
        hour=dataframe["start_time"].dt.hour,
        dayofweek=dataframe["start_time"].dt.dayofweek,
    )
    matrix = pd.crosstab(data["dayofweek"], data["hour"]).reindex(
        index=range(7), columns=range(24), fill_value=0
    )
    matrix.index = WEEKDAY_LABELS
    return _heatmap_figure(
        matrix, "Heatmap: Wochentag und Stunde", "Wochentag"
    )


def plot_date_hour_heatmap(dataframe: pd.DataFrame) -> go.Figure:
    figure = _heatmap_figure(
        _date_hour_matrix(dataframe),
        "Heatmap: Detektionen nach Datum und Stunde", "Datum",
    )
    figure.update_yaxes(autorange="reversed")
    return figure


def plot_discarded_date_hour_heatmap(dataframe: pd.DataFrame) -> go.Figure:
    figure = _heatmap_figure(
        _date_hour_matrix(dataframe, discarded_only=True),
        "Heatmap: Verworfene Detektionen nach Datum und Stunde", "Datum",
    )
    figure.update_yaxes(autorange="reversed")
    return figure


PLOTS: dict[str, Callable[[pd.DataFrame], go.Figure]] = {
    "report-snr-verlauf.html": plot_snr_timeline,
    "report-dauer-je-event.html": plot_event_duration,
    "report-dauer-histogramm.html": plot_duration_histogram,
    "report-dauer-snr.html": plot_duration_snr,
    "report-snr-histogramm.html": plot_snr_histogram,
    "report-anzahl-pro-stunde.html": plot_counts_per_date_hour,
    "report-anzahl-pro-minute.html": plot_counts_per_date_minute,
    "report-count-hour.html": plot_counts_by_hour,
    "report-count-dayofweek.html": plot_counts_by_weekday,
    "report-count-month.html": plot_counts_by_month,
    "report-heatmap-day-hour.html": plot_weekday_hour_heatmap,
    "report-heatmap-date-hour.html": plot_date_hour_heatmap,
    "report-heatmap-discarded-date-hour.html": plot_discarded_date_hour_heatmap,
}


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Meteor-Event-CSV mit Plotly visualisieren"
    )
    parser.add_argument(
        "csv", nargs="?", type=Path,
        help="CSV-Datei (Standard: neueste meteor_events_*.csv in out/)",
    )
    parser.add_argument(
        "--output-dir", type=Path, default=DEFAULT_OUTPUT_DIR,
        help="Zielordner fuer die einzelnen HTML-Dateien (Standard: out/)",
    )
    parser.add_argument(
        "--show", action="store_true",
        help="HTML-Visualisierungen nach dem Erzeugen im Browser anzeigen",
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    dataframe = load_events(args.csv)
    print(f"Geladen: {dataframe.attrs['source']}")
    print(f"Events:  {len(dataframe)}")

    args.output_dir.mkdir(parents=True, exist_ok=True)
    for filename, plot_function in PLOTS.items():
        figure = plot_function(dataframe)
        output_path = args.output_dir / filename
        figure.write_html(output_path, include_plotlyjs=True, full_html=True)
        print(f"Report gespeichert: {output_path.resolve()}")
        if args.show:
            figure.show()


if __name__ == "__main__":
    main()
