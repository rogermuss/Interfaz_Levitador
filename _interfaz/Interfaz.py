import sys
import time
from collections import deque

import serial
import serial.tools.list_ports

from PyQt5.QtCore import QTimer, Qt
from PyQt5.QtWidgets import (
    QApplication, QMainWindow, QWidget, QLabel, QLineEdit,
    QPushButton, QVBoxLayout, QHBoxLayout, QGridLayout, QGroupBox,
    QDoubleSpinBox, QComboBox
)
import pyqtgraph as pg


def listar_puertos():
    return [p.device for p in serial.tools.list_ports.comports()]


class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()

        self.ser = None
        self.serial_buffer = ""
        self.t0 = None

        self.max_points = 600
        self.time_data = deque(maxlen=self.max_points)
        self.dist_data = deque(maxlen=self.max_points)

        self.current_setpoint = 0.0

        self._build_ui()

        self.timer = QTimer(self)
        self.timer.setInterval(20)  # ms
        self.timer.timeout.connect(self.update_from_serial)
        self.timer.start()


    def _build_ui(self):
        self.setWindowTitle("PID")
        self.resize(1050, 650)

        self.setStyleSheet("""
        QWidget {
            background-color: #F0F8FF; /* Alice Blue - Fondo muy claro */
            color: #000000; /* Texto negro por defecto para alto contraste */
            font-family: 'Segoe UI';
        }
        QGroupBox {
            border: 2px solid #A0B9D5; /* Borde azul suave */
            border-radius: 12px;
            margin-top: 20px;
            background-color: #FFFFFF; /* Fondo de grupo blanco */
        }
        QGroupBox::title {
            subcontrol-origin: margin;
            subcontrol-position: top left;
            padding: 0 10px;
            color: #4682B4; /* Azul acero - Título de grupo */
            font-size: 13pt;
            font-weight: bold;
        }
        QLabel {
            font-size: 11pt;
            color: #1E90FF; /* Azul oscuro para texto general */
        }
        QPushButton {
            background-color: #6495ED; /* Cornflower Blue - Botón principal */
            color: #FFFFFF; /* Texto blanco en botón */
            border-radius: 8px;
            padding: 8px 16px;
            font-weight: bold;
        }
        QPushButton:hover {
            background-color: #778899; /* Light Slate Gray en hover */
        }
        QPushButton:disabled {
            background-color: #A0B9D5;
        }
        QLineEdit, QDoubleSpinBox, QComboBox {
            background-color: #E0FFFF; /* Azure - Campos de entrada */
            border: 1px solid #4682B4;
            border-radius: 6px;
            padding: 4px 6px;
            font-size: 10pt;
            color: #000000;
        }
        """)

        central = QWidget()
        main_layout = QVBoxLayout(central)
        main_layout.setContentsMargins(16, 12, 16, 12)
        main_layout.setSpacing(12)

        header_layout = QHBoxLayout()
        lbl_title = QLabel("Levitador")
        lbl_title.setStyleSheet("font-size: 26pt; font-weight: 700; color: #4682B4;")

        lbl_credits = QLabel("Materia - Sistemas de Control")
        lbl_credits.setAlignment(Qt.AlignRight | Qt.AlignVCenter)
        lbl_credits.setStyleSheet("font-size: 11pt; color: #6A5ACD;")

        header_layout.addWidget(lbl_title, 1)
        header_layout.addWidget(lbl_credits, 0)
        main_layout.addLayout(header_layout)

        center_layout = QHBoxLayout()
        center_layout.setSpacing(20)

        left_panel = QVBoxLayout()
        left_panel.setSpacing(15)


        grp_config = QGroupBox("Configuración y Referencia")
        config_layout = QVBoxLayout()
        config_layout.setSpacing(15)


        conn_grid = QGridLayout()
        conn_grid.setColumnStretch(1, 1)

        lbl_port = QLabel("Puerto:")
        self.cmb_port = QComboBox()
        self.refresh_ports()

        btn_refresh = QPushButton("Actualizar")
        btn_refresh.clicked.connect(self.refresh_ports)

        lbl_baud = QLabel("Baudrate:")
        self.txt_baud = QLineEdit("115200")

        self.btn_connect = QPushButton("Conectar")
        self.btn_connect.clicked.connect(self.toggle_connection)
        self.lbl_status = QLabel("Estado: Desconectado")
        self.lbl_status.setStyleSheet("color: #FF6347; font-size: 10pt; font-weight: 500;")

        conn_grid.addWidget(lbl_port, 0, 0)
        conn_grid.addWidget(self.cmb_port, 0, 1)
        conn_grid.addWidget(btn_refresh, 0, 2)
        conn_grid.addWidget(lbl_baud, 1, 0)
        conn_grid.addWidget(self.txt_baud, 1, 1)

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

        config_layout.addLayout(conn_grid)
        config_layout.addWidget(self.btn_connect)
        config_layout.addWidget(self.lbl_status)
        config_layout.addStretch(1)
        config_layout.addLayout(setpoint_h)
        grp_config.setLayout(config_layout)
        left_panel.addWidget(grp_config)


        grp_state = QGroupBox("Variables de Proceso")
        state_layout = QVBoxLayout()

        lbl_ref_style = "font-size: 13pt; color: #4682B4; font-weight: 600;"
        lbl_pos_style = "font-size: 16pt; font-weight: 700; color: #1E90FF;"
        lbl_error_style = "font-size: 14pt; font-weight: 600; color: #3CB371;"

        self.lbl_ref = QLabel("Referencia (Set): 0.00 cm")
        self.lbl_ref.setStyleSheet(lbl_ref_style)

        self.lbl_pos = QLabel("Posición (PV): --- cm")
        self.lbl_pos.setStyleSheet(lbl_pos_style)

        self.lbl_error = QLabel("Error (E): ---")
        self.lbl_error.setStyleSheet(lbl_error_style)

        self.lbl_in_range = QLabel("Estado: ---")
        self.lbl_in_range.setStyleSheet("font-size: 11pt; color: #778899;")

        state_layout.addWidget(self.lbl_ref)
        state_layout.addWidget(self.lbl_pos)
        state_layout.addWidget(self.lbl_error)
        state_layout.addWidget(self.lbl_in_range)
        grp_state.setLayout(state_layout)
        left_panel.addWidget(grp_state)


        grp_pid = QGroupBox("Ganancias Kp, Ki, Kd")
        pid_layout = QGridLayout()

        lbl_kp = QLabel("Kp (Proporcional):")
        lbl_ki = QLabel("Ki (Integral):")
        lbl_kd = QLabel("Kd (Derivativo):")

        self.spn_kp = QDoubleSpinBox()
        self.spn_kp.setDecimals(3)
        self.spn_kp.setRange(0.0, 1000.0)
        self.spn_kp.setSingleStep(0.1)
        self.spn_kp.setValue(1.0)

        self.spn_ki = QDoubleSpinBox()
        self.spn_ki.setDecimals(4)
        self.spn_ki.setRange(0.0, 1000.0)
        self.spn_ki.setSingleStep(0.01)
        self.spn_ki.setValue(10.0)

        self.spn_kd = QDoubleSpinBox()
        self.spn_kd.setDecimals(3)
        self.spn_kd.setRange(0.0, 1000.0)
        self.spn_kd.setSingleStep(1.0)
        self.spn_kd.setValue(9.0)

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

        right_panel = QVBoxLayout()
        grp_plot = QGroupBox("Respuesta en tiempo real (Posición vs. Referencia)")
        plot_layout = QVBoxLayout()
        pg.setConfigOption("background", "#FFFFFF")
        pg.setConfigOption("foreground", "#000000")
        self.plot_widget = pg.PlotWidget()
        self.plot_widget.setLabel("bottom", "Tiempo", units="s")
        self.plot_widget.setLabel("left", "Posición", units="cm")
        self.plot_widget.showGrid(x=True, y=True, alpha=0.3)
        self.plot_widget.setTitle(
            "<span style='color:#4682B4; font-size:14pt;'>Posición (Azul) y Referencia (Rojo)</span>")

        # CURVAS
        self.curve_pos = self.plot_widget.plot([], [],
                                               pen=pg.mkPen(color='#1E90FF', width=2, name="Posición"))
        self.curve_ref = self.plot_widget.plot([], [], pen=pg.mkPen(color='#FF6347', style=Qt.DashLine, width=2,
                                                                    name="Referencia"))
        self.ref_data = deque(maxlen=self.max_points)

        self.plot_widget.addLegend()

        plot_layout.addWidget(self.plot_widget)
        grp_plot.setLayout(plot_layout)
        right_panel.addWidget(grp_plot)
        center_layout.addLayout(left_panel, 1)
        center_layout.addLayout(right_panel, 2)

        main_layout.addLayout(center_layout)
        self.setCentralWidget(central)


    def refresh_ports(self):
        current = self.cmb_port.currentText() if hasattr(self, "cmb_port") else ""
        self.cmb_port.clear()
        ports = listar_puertos()
        if not ports:
            self.cmb_port.addItem("Sin puertos")
        else:
            self.cmb_port.addItems(ports)
            if current in ports:
                self.cmb_port.setCurrentText(current)

    def toggle_connection(self):
        if self.ser and self.ser.is_open:
            self.close_serial()
        else:
            self.open_serial()

    def open_serial(self):
        port = self.cmb_port.currentText()
        if not port or port == "Sin puertos":
            self.lbl_status.setText("Estado: No hay puerto seleccionado")
            return
        try:
            baud = int(self.txt_baud.text())
        except ValueError:
            self.lbl_status.setText("Estado: Baudrate inválido")
            return

        try:
            self.ser = serial.Serial(port, baudrate=baud, timeout=0.01)
            self.serial_buffer = ""
            self.t0 = time.time()
            self.btn_connect.setText("Desconectar")
            self.lbl_status.setText(f"Estado: Conectado a {port} @ {baud}")
        except Exception as e:
            self.ser = None
            self.lbl_status.setText(f"Estado: Error al conectar ({e})")

    def close_serial(self):
        try:
            if self.ser and self.ser.is_open:
                self.ser.close()
        except Exception:
            pass
        self.ser = None
        self.btn_connect.setText("Conectar")
        self.lbl_status.setText("Estado: Desconectado")

    def send_setpoint(self):
        if not (self.ser and self.ser.is_open):
            self.lbl_status.setText("Estado: No conectado (no se envió Setpoint)")
            return

        setpoint = self.spn_setpoint.value()
        self.current_setpoint = setpoint

        msg = f"S{setpoint:.1f}\n"

        try:
            self.ser.write(msg.encode("ascii"))
            self.lbl_status.setText(f"Estado: Setpoint enviado = {setpoint:.1f} cm")
            self.lbl_ref.setText(f"Referencia (Set): {setpoint:.2f} cm")
        except Exception as e:
            self.lbl_status.setText(f"Estado: Error enviando Setpoint ({e})")

    def send_pid(self):
        if not (self.ser and self.ser.is_open):
            self.lbl_status.setText("Estado: No conectado")
            return

        kp = self.spn_kp.value()
        ki = self.spn_ki.value()
        kd = self.spn_kd.value()

        msg = f"K{kp:.4f},{ki:.4f},{kd:.4f}\n"

        try:
            self.ser.write(msg.encode("ascii"))
            self.lbl_status.setText(
                f"Estado: PID actualizado -> Kp={kp:.3f}, Ki={ki:.4f}, Kd={kd:.3f}"
            )
        except Exception as e:
            self.lbl_status.setText(f"Estado: Error enviando PID ({e})")


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

        error_color = "#3CB371"  # Verde Mar (Mínimo error)
        if abs(error_val) > 0.2:
            error_color = "#FFA500"  # Naranja (Error medio)
        if abs(error_val) > 5.0:
            error_color = "#FF6347"  # Rojo Coral (Error grande)
        self.lbl_error.setStyleSheet(f"font-size: 14pt; font-weight: 600; color: {error_color};")

        # Estado de centrado (AJUSTE DE RANGOS)
        Rint = 10  # Aumentado de 8 a 10 para menos sensibilidad
        Rext = 50  # Aumentado de 40 a 50 para menos sensibilidad

        if abs(dist_cm) < Rint:
            txt = "Estado: CENTRADA (Dentro del objetivo)"
            color = "#3CB371"  # Verde Mar
        elif abs(dist_cm) < Rext:
            txt = "Estado: Controlando"
            color = "#FFA500"  # Naranja
        else:
            txt = "Estado: FUERA DE RANGO"
            color = "#FF6347"  # Rojo Coral
        self.lbl_in_range.setText(txt)
        self.lbl_in_range.setStyleSheet(f"font-size: 11pt; font-weight: 600; color: {color};")

        # Actualizar curvas
        self.curve_pos.setData(list(self.time_data), list(self.dist_data))
        self.curve_ref.setData(list(self.time_data), list(self.ref_data))


if __name__ == "__main__":
    app = QApplication(sys.argv)
    window = MainWindow()
    window.show()
    sys.exit(app.exec_())