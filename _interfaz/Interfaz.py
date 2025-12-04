import sys
import time
from collections import deque

import serial
import serial.tools.list_ports

from PyQt5.QtCore import QTimer, Qt
from PyQt5.QtWidgets import (
    QApplication, QMainWindow, QWidget, QLabel,
    QPushButton, QVBoxLayout, QHBoxLayout, QGridLayout, QGroupBox,
    QDoubleSpinBox
)
import pyqtgraph as pg


def listar_puertos():
    ports = [p.device for p in serial.tools.list_ports.comports()]
    if not ports and sys.platform.startswith('win'):
        return ["COM8"]
    return ports


class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()

        self.ser = None
        self.serial_buffer = ""
        self.t0 = None
        self.FIXED_BAUDRATE = 115200

        self.max_points = 600
        self.time_data = deque(maxlen=self.max_points)
        self.dist_data = deque(maxlen=self.max_points)

        self.current_setpoint = 0.0

        self._build_ui()

        self.timer = QTimer(self)
        self.timer.setInterval(20)
        self.timer.timeout.connect(self.update_from_serial)
        self.timer.start()

    def _build_ui(self):
        self.setWindowTitle("Levitador")
        self.resize(1050, 650)

        # Definimos el estilo de la fuente de datos
        self.data_font_style = "font-family: 'Consolas', 'Courier New', monospace; font-size: 10pt; font-weight: 500;"

        # --- PALETA DE COLORES PASTEL/NARANJA ---
        COLOR_BACKGROUND = "#FFF0E6"  # Blanco/Crema muy suave
        COLOR_GROUP_TITLE = "#E67E22"  # Naranja Suave
        COLOR_LABEL_DEFAULT = "#E74C3C"  # Rojo Pastel
        COLOR_BUTTON_NORMAL = "#F39C12"  # Naranja
        COLOR_BUTTON_HOVER = "#F7C469"  # Naranja Pastel
        COLOR_TEXT_NORMAL = "#000000"

        # Colores de las gráficas
        COLOR_POSICION = "#C0392B"  # Rojo Ladrillo/Oscuro
        COLOR_REFERENCIA = "#F39C12"  # Naranja

        # Colores de estado
        COLOR_SUCCESS = "#2ECC71"  # Verde (para conexión OK)
        COLOR_ERROR = "#E74C3C"  # Rojo Pastel
        COLOR_WARNING = "#F39C12"  # Naranja
        COLOR_INFO = "#3498DB"  # Azul (para envío de SP/PID)
        COLOR_DESCONECTADO = "#778899"  # Gris

        self.setStyleSheet(f"""
        QWidget {{
            background-color: {COLOR_BACKGROUND}; 
            color: {COLOR_TEXT_NORMAL};
            font-family: 'Verdana', 'Calibri', 'Helvetica', sans-serif; 
        }}

        /* Estilo de Grupo: Sombra suave y sin borde duro (Estilo Soft UI) */
        QGroupBox {{
            border: none;
            border-radius: 12px;
            margin-top: 20px;
            background-color: #FFFFFF;
            box-shadow: 0 4px 8px rgba(0, 0, 0, 0.1); 
        }}
        QGroupBox::title {{
            subcontrol-origin: margin;
            subcontrol-position: top left;
            padding: 0 10px;
            color: {COLOR_GROUP_TITLE};
            font-size: 13pt;
            font-weight: bold;
        }}

        QLabel {{
            font-size: 11pt;
            color: {COLOR_LABEL_DEFAULT};
        }}

        /* Estilo de Botón: Estilo plano (flat) */
        QPushButton {{
            background-color: {COLOR_BUTTON_NORMAL};
            color: #FFFFFF;
            border: none;
            border-radius: 8px;
            padding: 8px 16px;
            font-weight: bold;
        }}
        QPushButton:hover {{
            background-color: {COLOR_BUTTON_HOVER}; 
        }}
        QPushButton:disabled {{
            background-color: #A0B9D5;
        }}

        /* Estilo de Inputs: Borde sutil y foco */
        QLineEdit, QDoubleSpinBox {{
            font-family: 'Consolas', 'Courier New', monospace; 
            background-color: {COLOR_BACKGROUND};
            border: 1px solid #E0E0E0;
            border-radius: 6px;
            padding: 4px 6px;
            font-size: 10pt;
            color: {COLOR_TEXT_NORMAL};
        }}
        QLineEdit:focus, QDoubleSpinBox:focus {{
            border: 1px solid {COLOR_LABEL_DEFAULT};
            background-color: #FFFFFF;
        }}
        """)

        central = QWidget()
        main_layout = QVBoxLayout(central)
        main_layout.setContentsMargins(16, 12, 16, 12)
        main_layout.setSpacing(12)

        # 1. TÍTULO CENTRADO
        header_layout = QHBoxLayout()
        header_layout.addStretch(1)
        lbl_title = QLabel("Levitador")
        lbl_title.setStyleSheet(f"font-size: 26pt; font-weight: 700; color: {COLOR_GROUP_TITLE};")
        lbl_title.setAlignment(Qt.AlignCenter)
        header_layout.addWidget(lbl_title, 0)
        header_layout.addStretch(1)
        main_layout.addLayout(header_layout)

        # 2. GRÁFICA SUPERIOR (stretch 6)
        grp_plot = QGroupBox("Grafica de Respuesta")
        plot_layout = QVBoxLayout()
        pg.setConfigOption("background", "#FFFFFF")
        pg.setConfigOption("foreground", COLOR_TEXT_NORMAL)
        self.plot_widget = pg.PlotWidget()
        self.plot_widget.setLabel("bottom", "Tiempo", units="s")
        self.plot_widget.setLabel("left", "Posición", units="cm")
        self.plot_widget.showGrid(x=True, y=True, alpha=0.3)

        # Título con los nuevos colores y círculos
        self.plot_widget.setTitle(
            f"""
            <span style='color:{COLOR_GROUP_TITLE}; font-size:14pt;'>
                <span style='color:{COLOR_POSICION}; font-size: 20pt;'>●</span> Posición Actual &nbsp; - &nbsp; 
                <span style='color:{COLOR_REFERENCIA}; font-size: 20pt;'>●</span> Referencia
            </span>
            """
        )

        # CURVAS (Nuevos colores)
        self.curve_pos = self.plot_widget.plot([], [],
                                               pen=pg.mkPen(color=COLOR_POSICION, width=2, name="Posición"))
        self.curve_ref = self.plot_widget.plot([], [], pen=pg.mkPen(color=COLOR_REFERENCIA, style=Qt.DashLine, width=2,
                                                                    name="Referencia"))
        self.ref_data = deque(maxlen=self.max_points)

        self.plot_widget.addLegend()

        plot_layout.addWidget(self.plot_widget)
        grp_plot.setLayout(plot_layout)
        main_layout.addWidget(grp_plot, 6)

        # 3. INFORMACIÓN INFERIOR (stretch 1)
        bottom_layout = QHBoxLayout()
        bottom_layout.setSpacing(20)

        # Panel Izquierdo (Configuración y PID)
        left_panel = QVBoxLayout()
        left_panel.setSpacing(15)

        grp_config = QGroupBox()
        config_layout = QVBoxLayout()
        config_layout.setSpacing(15)

        # Conexión
        conn_layout = QVBoxLayout()
        self.auto_port = "COM8"
        self.btn_connect = QPushButton("Conectar")
        self.btn_connect.clicked.connect(self.toggle_connection)

        self.lbl_status = QLabel("DESCONECTADO.")
        self.lbl_status.setStyleSheet(f"color: {COLOR_ERROR}; {self.data_font_style}")

        conn_layout.addWidget(self.btn_connect)
        conn_layout.addWidget(self.lbl_status)

        setpoint_h = QHBoxLayout()
        lbl_setpoint = QLabel("Setpoint [cm]:")
        self.spn_setpoint = QDoubleSpinBox()
        self.spn_setpoint.setDecimals(1)
        self.spn_setpoint.setRange(0.0, 40.0)
        self.spn_setpoint.setSingleStep(0.5)
        self.spn_setpoint.setValue(0.0)
        self.btn_send_setpoint = QPushButton("Enviar Setpoint")
        self.btn_send_setpoint.clicked.connect(self.send_setpoint)

        setpoint_h.addWidget(lbl_setpoint)
        setpoint_h.addWidget(self.spn_setpoint)
        setpoint_h.addWidget(self.btn_send_setpoint)

        config_layout.addLayout(conn_layout)
        config_layout.addStretch(1)
        config_layout.addLayout(setpoint_h)
        grp_config.setLayout(config_layout)
        left_panel.addWidget(grp_config)

        grp_pid = QGroupBox("PID")
        pid_layout = QGridLayout()

        lbl_kp = QLabel("Kp (Proporcional):")
        lbl_ki = QLabel("Ki (Integral):")
        lbl_kd = QLabel("Kd (Derivativo):")

        self.spn_kp = QDoubleSpinBox()
        self.spn_kp.setDecimals(3)
        self.spn_kp.setRange(0.0, 1000.0)
        self.spn_kp.setSingleStep(0.1)
        self.spn_kp.setValue(13.0)

        self.spn_ki = QDoubleSpinBox()
        self.spn_ki.setDecimals(4)
        self.spn_ki.setRange(0.0, 1000.0)
        self.spn_ki.setSingleStep(0.01)
        self.spn_ki.setValue(0.11)

        self.spn_kd = QDoubleSpinBox()
        self.spn_kd.setDecimals(3)
        self.spn_kd.setRange(0.0, 1000.0)
        self.spn_kd.setSingleStep(1.0)
        self.spn_kd.setValue(37.0)

        self.btn_send_pid = QPushButton("Enviar Constantes K")
        self.btn_send_pid.clicked.connect(self.send_pid)

        pid_layout.addWidget(lbl_kp, 0, 0)
        pid_layout.addWidget(self.spn_kp, 0, 1)
        pid_layout.addWidget(lbl_ki, 1, 0)
        pid_layout.addWidget(self.spn_ki, 1, 1)
        pid_layout.addWidget(lbl_kd, 2, 0)
        pid_layout.addWidget(self.spn_kd, 2, 1)
        pid_layout.addWidget(self.btn_send_pid, 3, 0, 1, 2)
        grp_pid.setLayout(pid_layout)
        left_panel.addWidget(grp_pid)

        left_panel.addStretch(1)

        # Panel Derecho (Variables de Proceso)
        right_panel = QVBoxLayout()
        grp_state = QGroupBox()
        state_layout = QVBoxLayout()

        # Se usa el estilo de fuente de datos (monoespaciada)
        data_font_family = "font-family: 'Consolas', 'Courier New', monospace;"

        lbl_ref_style = f"{data_font_family} font-size: 13pt; color: {COLOR_GROUP_TITLE}; font-weight: 600;"
        lbl_pos_style = f"{data_font_family} font-size: 16pt; font-weight: 700; color: {COLOR_POSICION};"
        lbl_error_style = f"{data_font_family} font-size: 14pt; font-weight: 600; color: {COLOR_SUCCESS};"  # Color inicial

        self.lbl_ref = QLabel("Referencia (Set): 0.00 cm")
        self.lbl_ref.setStyleSheet(lbl_ref_style)

        self.lbl_pos = QLabel("Posición (PV): --- cm")
        self.lbl_pos.setStyleSheet(lbl_pos_style)

        self.lbl_error = QLabel("Error (E): ---")
        self.lbl_error.setStyleSheet(lbl_error_style)

        state_layout.addWidget(self.lbl_ref)
        state_layout.addWidget(self.lbl_pos)
        state_layout.addWidget(self.lbl_error)

        grp_state.setLayout(state_layout)
        right_panel.addWidget(grp_state)
        right_panel.addStretch(1)

        bottom_layout.addLayout(left_panel, 1)
        bottom_layout.addLayout(right_panel, 1)

        main_layout.addLayout(bottom_layout, 1)

        self.setCentralWidget(central)

    # --- Lógica de Conexión y PID ---

    def refresh_ports(self):
        pass

    def toggle_connection(self):
        if self.ser and self.ser.is_open:
            self.close_serial()
        else:
            self.open_serial()

    def open_serial(self):
        port = self.auto_port
        baud = self.FIXED_BAUDRATE
        COLOR_SUCCESS = "#2ECC71"
        COLOR_ERROR = "#E74C3C"

        try:
            self.ser = serial.Serial(port, baudrate=baud, timeout=0.01)
            self.serial_buffer = ""
            self.t0 = time.time()
            self.btn_connect.setText("Desconectar")
            self.lbl_status.setText(f"CONECTADO a {port}.")
            self.lbl_status.setStyleSheet(f"color: {COLOR_SUCCESS}; {self.data_font_style}")  # Verde Pastel
        except Exception:
            self.ser = None
            self.lbl_status.setText(f"ERROR: No se pudo conectar a {port}.")
            self.lbl_status.setStyleSheet(f"color: {COLOR_ERROR}; {self.data_font_style}")  # Rojo Pastel

    def close_serial(self):
        COLOR_DESCONECTADO = "#778899"
        try:
            if self.ser and self.ser.is_open:
                self.ser.close()
        except Exception:
            pass
        self.ser = None
        self.btn_connect.setText("Conectar")
        self.lbl_status.setText("DESCONECTADO.")
        self.lbl_status.setStyleSheet(f"color: {COLOR_DESCONECTADO}; {self.data_font_style}")  # Gris

    def send_setpoint(self):
        COLOR_WARNING = "#F39C12"
        COLOR_INFO = "#3498DB"
        COLOR_ERROR = "#E74C3C"

        if not (self.ser and self.ser.is_open):
            self.lbl_status.setText("DESCONECTADO. SP no enviado.")
            self.lbl_status.setStyleSheet(f"color: {COLOR_WARNING}; {self.data_font_style}")  # Naranja para advertencia
            return

        setpoint = self.spn_setpoint.value()
        self.current_setpoint = setpoint

        msg = f"S{setpoint:.1f}\n"

        try:
            self.ser.write(msg.encode("ascii"))
            self.lbl_status.setText(f"SP enviado = {setpoint:.1f} cm")
            self.lbl_ref.setText(f"Referencia (Set): {setpoint:.2f} cm")
            self.lbl_status.setStyleSheet(f"color: {COLOR_INFO}; {self.data_font_style}")  # Azul para acción completada
        except Exception:
            self.lbl_status.setText("ERROR al enviar SP.")
            self.lbl_status.setStyleSheet(f"color: {COLOR_ERROR}; {self.data_font_style}")  # Rojo Pastel para error

    def send_pid(self):
        COLOR_WARNING = "#F39C12"
        COLOR_INFO = "#3498DB"
        COLOR_ERROR = "#E74C3C"

        if not (self.ser and self.ser.is_open):
            self.lbl_status.setText("DESCONECTADO. PID no enviado.")
            self.lbl_status.setStyleSheet(f"color: {COLOR_WARNING}; {self.data_font_style}")  # Naranja para advertencia
            return

        kp = self.spn_kp.value()
        ki = self.spn_ki.value()
        kd = self.spn_kd.value()

        msg = f"K{kp:.4f},{ki:.4f},{kd:.4f}\n"

        try:
            self.ser.write(msg.encode("ascii"))
            self.lbl_status.setText(
                f"PID enviado -> Kp={kp:.3f}, Ki={ki:.4f}, Kd={kd:.3f}"
            )
            self.lbl_status.setStyleSheet(f"color: {COLOR_INFO}; {self.data_font_style}")  # Azul para acción completada
        except Exception:
            self.lbl_status.setText("ERROR al enviar PID.")
            self.lbl_status.setStyleSheet(f"color: {COLOR_ERROR}; {self.data_font_style}")  # Rojo Pastel para error

    def update_from_serial(self):
        if not (self.ser and self.ser.is_open):
            return

        try:
            data = self.ser.read(self.ser.in_waiting or 1).decode("ascii", errors="ignore")
            if not data:
                return
            self.serial_buffer += data

            while "$" in self.serial_buffer:
                frame, self.serial_buffer = self.serial_buffer.split("$", 1)
                self.process_frame(frame)

        except Exception:
            return

    def process_frame(self, frame: str):
        COLOR_SUCCESS = "#2ECC71"  # Verde Pastel
        COLOR_WARNING = "#F39C12"  # Naranja
        COLOR_ERROR = "#E74C3C"  # Rojo Pastel

        parts = frame.split(",")
        if len(parts) < 5:
            return

        try:
            raw_dist = float(parts[0])
            _ = float(parts[2])
            ref = float(parts[4])
        except ValueError:
            return

        dist_cm = raw_dist - 200.0
        t = time.time() - (self.t0 or time.time())

        self.current_setpoint = ref
        error_val = self.current_setpoint - dist_cm

        self.time_data.append(t)
        self.dist_data.append(dist_cm)
        self.ref_data.append(ref)

        self.lbl_ref.setText(f"Referencia (Set): {self.current_setpoint:6.2f} cm")
        self.lbl_pos.setText(f"Posición: {dist_cm:6.2f} cm")

        self.lbl_error.setText(f"Error (E): {error_val:6.2f} cm")

        # Lógica de color de error basada en el nuevo esquema
        error_color = COLOR_SUCCESS  # Verde para error pequeño
        if abs(error_val) > 0.2:
            error_color = COLOR_WARNING  # Naranja para error moderado
        if abs(error_val) > 5.0:
            error_color = COLOR_ERROR  # Rojo Pastel para error grande

        self.lbl_error.setStyleSheet(
            f"font-family: 'Consolas', 'Courier New', monospace; font-size: 14pt; font-weight: 600; color: {error_color};")

        self.curve_pos.setData(list(self.time_data), list(self.dist_data))
        self.curve_ref.setData(list(self.time_data), list(self.ref_data))


if __name__ == "__main__":
    app = QApplication(sys.argv)
    window = MainWindow()
    window.show()
    sys.exit(app.exec_())