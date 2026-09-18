"""Interaktive Plotly-Auswertung der CSV-Dateien aus ``meteor_detect.py``.

Alle CSV-Dateien aus einem Eingabeordner werden zu einem DataFrame
zusammengefuehrt. Jede Visualisierung wird als eigene HTML-Datei gespeichert.
"""

from __future__ import annotations

import argparse
from pathlib import Path
from typing import Callable

import pandas as pd
import plotly.graph_objects as go

SCRIPT_DIR = Path(__file__).resolve().parent
DEFAULT_INPUT_DIR = SCRIPT_DIR / "out_first_meas_stdfac4"  # TODO
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


def find_csv_files(input_dir: Path | str = DEFAULT_INPUT_DIR) -> list[Path]:
    """Liefert alle CSV-Dateien direkt im Eingabeordner."""
    directory = Path(input_dir).expanduser().resolve()
    if not directory.is_dir():
        raise NotADirectoryError(f"Eingabeordner nicht gefunden: {directory}")

    csv_files = sorted(
        path for path in directory.iterdir()
        if path.is_file() and path.suffix.lower() == ".csv"
    )
    if not csv_files:
        raise FileNotFoundError(
            f"Keine CSV-Dateien im Eingabeordner gefunden: {directory}"
        )
    return csv_files


def load_events(input_dir: Path | str = DEFAULT_INPUT_DIR) -> pd.DataFrame:
    """Laedt, validiert und verbindet alle CSV-Dateien eines Ordners."""
    csv_files = find_csv_files(input_dir)
    dataframes: list[pd.DataFrame] = []

    for csv_file in csv_files:
        dataframe = pd.read_csv(csv_file)
        missing = REQUIRED_COLUMNS.difference(dataframe.columns)
        if missing:
            raise ValueError(
                f"In '{csv_file}' fehlen folgende Spalten: "
                + ", ".join(sorted(missing))
            )
        dataframes.append(dataframe)

    dataframe = pd.concat(dataframes, ignore_index=True)

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
    dataframe.attrs["source"] = Path(input_dir).expanduser().resolve()
    dataframe.attrs["source_files"] = csv_files
    return dataframe


def _layout(
        figure: go.Figure, title: str, x_title: str, y_title: str,
        height: int = 550,
) -> go.Figure:
    figure.update_layout(
        title=title, xaxis_title=x_title, yaxis_title=y_title,
        template="plotly_white", hovermode="x unified",
        width=1000, height=height,
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
    detected = dataframe[dataframe["status"] == "detected"]
    if detected.empty:
        return _empty_figure("SNR vs. Event-Dauer (nicht verworfen)")

    figure = go.Figure()
    hover_data = detected[["start_time", "snr_mean_db", "snr_max_db"]]
    figure.add_trace(go.Scatter(
        x=detected["duration_seconds"], y=detected["snr_mean_db"],
        mode="markers", name="SNR Mittel", marker={"symbol": "circle"},
        customdata=hover_data,
        hovertemplate=(
            "Dauer: %{x:.3f} s<br>SNR mittel: %{customdata[1]:.3f} dB"
            "<br>SNR max.: %{customdata[2]:.3f} dB"
            "<br>Zeit: %{customdata[0]}<extra>%{fullData.name}</extra>"
        ),
    ))
    figure.add_trace(go.Scatter(
        x=detected["duration_seconds"], y=detected["snr_max_db"],
        mode="markers", name="SNR Maximum", marker={"symbol": "x"},
        customdata=hover_data,
        hovertemplate=(
            "Dauer: %{x:.3f} s<br>SNR mittel: %{customdata[1]:.3f} dB"
            "<br>SNR max.: %{customdata[2]:.3f} dB"
            "<br>Zeit: %{customdata[0]}<extra>%{fullData.name}</extra>"
        ),
    ))
    figure = _layout(
        figure, "SNR vs. Event-Dauer (nicht verworfen)",
        "Dauer [s]", "SNR [dB]",
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


def _heatmap_figure(
        matrix: pd.DataFrame, title: str, y_title: str, height: int = 550,
        v_max: float | None = None,
) -> go.Figure:
    # Funktioniert sowohl mit pandas-Versionen vor als auch nach Einfuehrung
    # von DataFrame.map.
    text = matrix.astype(str).mask(matrix == 0, "")
    figure = go.Figure(go.Heatmap(
        z=matrix.to_numpy(), x=list(matrix.columns), y=list(matrix.index),
        colorscale="Viridis", zmin=0, zmax=v_max,
        colorbar={"title": "Anzahl"},
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
    return _layout(figure, title, "Stunde (UTC)", y_title, height=height)


def plot_weekday_hour_heatmap(
        dataframe: pd.DataFrame, v_max: float | None = None,
) -> go.Figure:
    data = dataframe.assign(
        hour=dataframe["start_time"].dt.hour,
        dayofweek=dataframe["start_time"].dt.dayofweek,
    )
    matrix = pd.crosstab(data["dayofweek"], data["hour"]).reindex(
        index=range(7), columns=range(24), fill_value=0
    )
    matrix.index = WEEKDAY_LABELS
    return _heatmap_figure(
        matrix, "Heatmap: Wochentag und Stunde", "Wochentag", v_max=v_max,
    )


def plot_date_hour_heatmap(
        dataframe: pd.DataFrame, v_max: float | None = None,
) -> go.Figure:
    matrix = _date_hour_matrix(dataframe)
    figure = _heatmap_figure(
        matrix,
        "Heatmap: Detektionen nach Datum und Stunde", "Datum",
        height=max(550, 180 + len(matrix) * 32),
        v_max=v_max,
    )
    figure.update_yaxes(autorange="reversed")
    return figure


def plot_discarded_date_hour_heatmap(
        dataframe: pd.DataFrame, v_max: float | None = None,
) -> go.Figure:
    matrix = _date_hour_matrix(dataframe, discarded_only=True)
    figure = _heatmap_figure(
        matrix,
        "Heatmap: Verworfene Detektionen nach Datum und Stunde", "Datum",
        height=max(550, 180 + len(matrix) * 32),
        v_max=v_max,
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

HEATMAP_PLOTS = {
    plot_weekday_hour_heatmap,
    plot_date_hour_heatmap,
    plot_discarded_date_hour_heatmap,
}


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Meteor-Event-CSV mit Plotly visualisieren"
    )
    parser.add_argument(
        "--input-dir", type=Path, default=DEFAULT_INPUT_DIR,
        help="Ordner mit den CSV-Dateien",
    )
    parser.add_argument(
        "--output-dir", type=Path, default=DEFAULT_OUTPUT_DIR,
        help="Zielordner fuer die einzelnen HTML-Dateien",
    )
    parser.add_argument(
        "--show", action="store_true",
        help="HTML-Visualisierungen nach dem Erzeugen im Browser anzeigen",
    )
    parser.add_argument(
        "--heatmap-vmax", type=float, metavar="V_MAX",
        help=(
            "Oberes Ende der Farbskala aller Heatmaps; ohne Angabe wird "
            "die Skala automatisch bestimmt"
        ),
        default=600  # TODO
    )
    args = parser.parse_args()

    if args.heatmap_vmax is not None and args.heatmap_vmax <= 0:
        parser.error("--heatmap-vmax muss größer als 0 sein")
    return args


def main() -> None:
    args = parse_args()
    dataframe = load_events(args.input_dir)
    print(f"Eingabeordner: {dataframe.attrs['source']}")
    print(f"CSV-Dateien:   {len(dataframe.attrs['source_files'])}")
    print(f"Events:        {len(dataframe)}")

    args.output_dir = args.output_dir.expanduser().resolve()
    args.output_dir.mkdir(parents=True, exist_ok=True)
    for filename, plot_function in PLOTS.items():
        if plot_function in HEATMAP_PLOTS:
            figure = plot_function(dataframe, v_max=args.heatmap_vmax)
        else:
            figure = plot_function(dataframe)
        output_path = args.output_dir / filename
        figure.write_html(output_path, include_plotlyjs=True, full_html=True)
        print(f"Report gespeichert: {output_path.resolve()}")
        if args.show:
            figure.show()


if __name__ == "__main__":
    main()
