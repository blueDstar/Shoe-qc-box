STYLE = """
QWidget { background: #080B10; color: #CBD5E1; font-family: 'Segoe UI'; font-size: 12px; }
QMainWindow, QTabWidget::pane { background: #080B10; border: none; }
QLabel#Brand { color: #FFFFFF; font-size: 23px; font-weight: 700; }
QLabel#Sub { color: #64748B; font-size: 11px; }
QLabel#Banner { background: #172B36; color: #67E8F9; padding: 9px; border-left: 3px solid #00D9FF; }
QLabel#Fault { background: #351723; color: #FCA5A5; padding: 9px; border-left: 3px solid #EF4444; }
QGroupBox { background: #111827; border: 1px solid #233247; border-radius: 6px; margin-top: 15px; padding: 12px 8px 7px; font-weight: 600; color: #00D9FF; }
QGroupBox::title { subcontrol-origin: margin; left: 10px; padding: 0 4px; }
QGroupBox QWidget { background: transparent; }
QPushButton { background: #1A2B3E; border: 1px solid #30455F; border-radius: 4px; padding: 7px 9px; color: #E2E8F0; }
QPushButton:hover { background: #25435B; border-color: #00D9FF; }
QPushButton:pressed { background: #006779; }
QPushButton:disabled { color: #475569; background: #111827; border-color: #1E293B; }
QPushButton#Primary { background: #007D92; border-color: #00D9FF; color: white; font-weight: 700; }
QPushButton#Stop { background: #582737; border-color: #AF4556; color: #FEE2E2; }
QLineEdit, QDoubleSpinBox, QSpinBox, QComboBox { background: #0C1421; border: 1px solid #304158; border-radius: 3px; padding: 5px; color: white; }
QTabBar::tab { background: #111827; color: #94A3B8; padding: 11px 16px; border-bottom: 2px solid #111827; }
QTabBar::tab:selected { color: #00D9FF; border-bottom-color: #00D9FF; }
QScrollArea { border: none; }
QScrollBar:vertical { background: #0C1421; width: 9px; }
QScrollBar::handle:vertical { background: #33465E; min-height: 28px; border-radius: 4px; }
QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical { height: 0; }
QTreeWidget, QTableWidget, QPlainTextEdit { background: #0C1421; border: 1px solid #233247; alternate-background-color: #111D2D; selection-background-color: #175264; }
QHeaderView::section { background: #142337; color: #CBD5E1; border: 1px solid #26364C; padding: 7px; }
QProgressBar { border: 1px solid #25354C; border-radius: 3px; background: #0C1421; text-align: center; }
QProgressBar::chunk { background: #008AA3; }
QSlider::groove:horizontal { height: 5px; background: #25354C; border-radius: 2px; }
QSlider::handle:horizontal { background: #00D9FF; width: 12px; margin: -5px 0; border-radius: 6px; }
QCheckBox::indicator { width: 14px; height: 14px; border: 1px solid #475569; background: #0C1421; }
QCheckBox::indicator:checked { background: #00A8C4; border-color: #67E8F9; }
"""
