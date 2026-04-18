from __future__ import annotations


def build_stylesheet() -> str:
    return """
    QWidget {
        background: #07101d;
        color: #edf4ff;
        font-family: "Segoe UI";
        font-size: 13px;
    }
    QMainWindow {
        background: qradialgradient(cx:0.12, cy:0.08, radius:1.2, fx:0.12, fy:0.08, stop:0 #12213f, stop:0.45 #0a1223, stop:1 #07101d);
    }
    QStackedWidget#contentStack, QWidget#pageSurface {
        background: transparent;
    }
    QFrame#panel {
        background: rgba(15, 25, 44, 0.76);
        border: 1px solid rgba(157, 189, 255, 0.14);
        border-radius: 24px;
    }
    QFrame#glassCard {
        background: rgba(18, 29, 52, 0.72);
        border: 1px solid rgba(157, 189, 255, 0.12);
        border-radius: 16px;
    }
    QLabel#muted {
        color: #94a8ce;
    }
    QLabel#previewLabel {
        color: #c9d9fb;
        font-size: 12px;
        font-weight: 700;
    }
    QLabel#cardTitle {
        color: #eef5ff;
        font-size: 14px;
        font-weight: 700;
    }
    QPushButton {
        background: rgba(255, 255, 255, 0.08);
        color: #f0f6ff;
        border: 1px solid rgba(255, 255, 255, 0.12);
        border-radius: 14px;
        padding: 12px 18px;
        font-weight: 700;
    }
    QPushButton:hover {
        background: rgba(255, 255, 255, 0.12);
        border: 1px solid rgba(164, 205, 255, 0.28);
    }
    QPushButton#settingsButton {
        min-height: 48px;
    }
    QPushButton#ghostButton {
        background: rgba(255, 255, 255, 0.08);
        color: #eff5ff;
        border: 1px solid rgba(255, 255, 255, 0.12);
    }
    QPushButton#ghostButton:hover {
        background: rgba(255, 255, 255, 0.12);
        border: 1px solid rgba(164, 205, 255, 0.28);
    }
    QToolButton {
        background: rgba(255, 255, 255, 0.06);
        color: #eff5ff;
        border: 1px solid rgba(255, 255, 255, 0.10);
        border-radius: 10px;
        padding: 6px 10px;
    }
    QToolButton:hover {
        background: rgba(255, 255, 255, 0.12);
    }
    QDialog {
        background: #09111f;
    }
    QLabel#dialogTitle {
        font-size: 20px;
        font-weight: 700;
        color: #f3f8ff;
    }
    QLabel#dialogCopy {
        color: #95abcf;
    }
    QLineEdit, QComboBox {
        background: rgba(10, 18, 33, 0.92);
        border: 1px solid rgba(123, 156, 212, 0.34);
        border-radius: 12px;
        padding: 10px 12px;
        min-height: 18px;
    }
    QLineEdit:focus, QComboBox:focus {
        border: 1px solid rgba(119, 201, 255, 0.95);
    }
    QScrollArea {
        border: none;
        background: transparent;
    }
    """
