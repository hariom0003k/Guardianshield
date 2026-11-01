"""
Guardian Shield Threat History & Security Dashboard.
Allows reviewing audit logs, inspecting detection metrics, and configuring sensitivity.
"""

from datetime import datetime
from typing import Optional
from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QDialog,
    QFrame,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QPushButton,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

try:
    from ..core.events import ToastAlertTriggeredEvent, event_bus
    from ..core.logger import AuditLogger
except ImportError:
    from core.events import ToastAlertTriggeredEvent, event_bus
    from core.logger import AuditLogger


class DashboardDialog(QDialog):
    """Security management dashboard and threat history audit viewer."""

    def __init__(self, logger: AuditLogger, parent: Optional[QWidget] = None):
        super().__init__(parent)
        self.logger = logger

        self.setWindowTitle("Guardian Shield — Security & Threat Dashboard")
        self.resize(750, 520)
        self.setStyleSheet("""
            QDialog {
                background-color: #0F172A;
                color: #F8FAFC;
                font-family: 'Segoe UI', Arial, sans-serif;
            }
            QLabel {
                color: #E2E8F0;
            }
            QFrame.card {
                background-color: #1E293B;
                border-radius: 8px;
                border: 1px solid #334155;
                padding: 12px;
            }
            QTableWidget {
                background-color: #1E293B;
                gridline-color: #334155;
                border: 1px solid #334155;
                border-radius: 6px;
                color: #F8FAFC;
                selection-background-color: #0284C7;
            }
            QHeaderView::section {
                background-color: #0F172A;
                color: #94A3B8;
                padding: 6px;
                font-weight: bold;
                border: 1px solid #334155;
            }
        """)

        self._init_ui()
        self.refresh_data()

    def _init_ui(self) -> None:
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(20, 20, 20, 20)
        main_layout.setSpacing(16)

        # Title Row
        title_row = QHBoxLayout()
        title_label = QLabel("🛡️ Guardian Shield Security Center")
        title_label.setStyleSheet("font-size: 18px; font-weight: bold; color: #38BDF8;")
        title_row.addWidget(title_label)
        title_row.addStretch()

        btn_test_alert = QPushButton("⚡ Test Peeper Alert")
        btn_test_alert.setStyleSheet("""
            QPushButton {
                background-color: #D97706;
                color: white;
                font-weight: bold;
                padding: 6px 12px;
                border-radius: 6px;
                border: none;
            }
            QPushButton:hover { background-color: #F59E0B; }
        """)
        btn_test_alert.clicked.connect(self._trigger_test_alert)
        title_row.addWidget(btn_test_alert)

        btn_refresh = QPushButton("🔄 Refresh")
        btn_refresh.setStyleSheet("""
            QPushButton {
                background-color: #334155;
                color: white;
                padding: 6px 12px;
                border-radius: 6px;
                border: none;
            }
            QPushButton:hover { background-color: #475569; }
        """)
        btn_refresh.clicked.connect(self.refresh_data)
        title_row.addWidget(btn_refresh)
        main_layout.addLayout(title_row)

        # KPI Summary Cards
        kpi_layout = QHBoxLayout()
        kpi_layout.setSpacing(12)

        self.card_alerts = self._create_kpi_card("Total Peeper Alerts", "0", "#EF4444")
        self.card_shields = self._create_kpi_card("Shields Deployed", "0", "#38BDF8")
        self.card_peak = self._create_kpi_card("Peak Threat Score", "0%", "#F59E0B")

        kpi_layout.addWidget(self.card_alerts)
        kpi_layout.addWidget(self.card_shields)
        kpi_layout.addWidget(self.card_peak)
        main_layout.addLayout(kpi_layout)

        # Audit Log Table
        table_label = QLabel("Audit Trail & Threat History")
        table_label.setStyleSheet("font-size: 14px; font-weight: bold; color: #94A3B8;")
        main_layout.addWidget(table_label)

        self.table = QTableWidget()
        self.table.setColumnCount(5)
        self.table.setHorizontalHeaderLabels(["Timestamp", "Event Type", "Threat Level", "Score", "Action Taken"])
        self.table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
        self.table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        self.table.setAlternatingRowColors(True)
        main_layout.addWidget(self.table)

    def _create_kpi_card(self, title: str, value: str, color: str) -> QFrame:
        card = QFrame()
        card.setProperty("class", "card")
        layout = QVBoxLayout(card)
        layout.setContentsMargins(12, 10, 12, 10)
        layout.setSpacing(4)

        t_lbl = QLabel(title)
        t_lbl.setStyleSheet("font-size: 11px; color: #94A3B8; text-transform: uppercase;")
        layout.addWidget(t_lbl)

        v_lbl = QLabel(value)
        v_lbl.setObjectName("value_label")
        v_lbl.setStyleSheet(f"font-size: 24px; font-weight: bold; color: {color};")
        layout.addWidget(v_lbl)
        return card

    def refresh_data(self) -> None:
        """Fetches latest metrics and rows from SQLite."""
        stats = self.logger.get_summary_stats()
        self.card_alerts.findChild(QLabel, "value_label").setText(str(stats["total_alerts"]))
        self.card_shields.findChild(QLabel, "value_label").setText(str(stats["total_shields"]))
        self.card_peak.findChild(QLabel, "value_label").setText(f"{int(stats['peak_threat_score'] * 100)}%")

        events = self.logger.get_recent_events(limit=40)
        self.table.setRowCount(len(events))

        for row, evt in enumerate(events):
            t_str = datetime.fromtimestamp(evt["timestamp"]).strftime("%H:%M:%S")
            self.table.setItem(row, 0, QTableWidgetItem(t_str))
            self.table.setItem(row, 1, QTableWidgetItem(evt.get("event_type", "")))
            self.table.setItem(row, 2, QTableWidgetItem(evt.get("threat_level", "NONE")))

            score = evt.get("threat_score", 0.0)
            score_item = QTableWidgetItem(f"{int(score * 100)}%" if score else "-")
            score_item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
            self.table.setItem(row, 3, score_item)

            action = evt.get("action_taken") or evt.get("details") or "-"
            self.table.setItem(row, 4, QTableWidgetItem(action))

    def _trigger_test_alert(self) -> None:
        """Simulates a test alert event."""
        event_bus.publish(ToastAlertTriggeredEvent(
            threat_score=0.88,
            peeper_count=1,
            urgency="high"
        ))
