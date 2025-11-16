import sys
from PyQt6.QtWidgets import QApplication, QMainWindow
from _interfaz.interfaz_levitador import Ui_MainWindow
from pyqtgraph import PlotWidget
from Estado import *



#arduino = serial.Serial('COM3', 9600)  # COM3 es el puerto de tu Arduino
#time.sleep(2)

class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.ui = Ui_MainWindow()
        self.ui.setupUi(self)

        estado = Estado.NO_BALL

        # Crear un widget de gráfica
        self.graph = PlotWidget()

        # Insertarlo en el layout
        self.ui.plotLayout.addWidget(self.graph)

        # Ejemplo de datos
        self.graph.plot([0, 1, 2, 3, 4, 5], [10, 20, 30, 25, 15, 5])


        self.ui.valueBox.setMinimum(0)
        self.ui.valueBox.setMaximum(50)
        self.ui.valueBox.setValue(25)


if __name__ == "__main__":
    app = QApplication(sys.argv)
    window = MainWindow()
    window.show()
    sys.exit(app.exec())


