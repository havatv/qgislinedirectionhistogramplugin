# -*- coding: utf-8 -*-
"""
/***************************************************************************
 linedirectionhistogramDialog
                                 A QGIS plugin
 Create histogram of line directions
                             -------------------
        begin                : 2015-01-10
        git sha              : $Format:%H$
        copyright            : (C) 2015 by Håvard Tveite, NMBU
        email                : havard.tveite@nmbu.no
 ***************************************************************************/

/***************************************************************************
 *                                                                         *
 *   This program is free software; you can redistribute it and/or modify  *
 *   it under the terms of the GNU General Public License as published by  *
 *   the Free Software Foundation; either version 2 of the License, or     *
 *   (at your option) any later version.                                   *
 *                                                                         *
 ***************************************************************************/
"""

# User interface input components:
#   histogramGraphicsView: The GraphicsView that contains the histogram
#   setupGraphicsView: The GraphicsView that shows the setup (bins and angles)
#   binsSpinBox
#   offsetAngleSpinBox
#   directionNeutralCheckBox
#   selectedFeaturesCheckBox
#   noWeightingCheckBox
#   inputLayer

import os
import csv

from PyQt4 import uic
from PyQt4.QtCore import SIGNAL, QObject, QThread, QCoreApplication
from PyQt4.QtCore import QPointF, QLineF, QRectF, QPoint, QSettings
from PyQt4.QtGui import QDialog, QDialogButtonBox, QFileDialog
from PyQt4.QtGui import QGraphicsLineItem, QGraphicsEllipseItem
from PyQt4.QtGui import QGraphicsScene, QBrush, QPen, QColor
from PyQt4.QtGui import QGraphicsView
from qgis.core import QgsMessageLog, QgsMapLayerRegistry, QgsMapLayer
from qgis.core import QGis
#from qgis.gui import QgsMessageBar

from linedirectionhistogram_engine import Worker

FORM_CLASS, _ = uic.loadUiType(os.path.join(
    os.path.dirname(__file__), 'linedirectionhistogram_dialog_base.ui'))


# Angles:
# Real world angles (and QGIS azimuth) are measured clockwise from
# the 12 o'clock position (north).
# QT angles are measured counter clockwise from the 3 o'clock
# position.
class linedirectionhistogramDialog(QDialog, FORM_CLASS):

    def __init__(self, iface, parent=None):
        self.iface = iface
        self.plugin_dir = os.path.dirname(__file__)

        # Some constants
        self.LINEDIRECTIONHISTOGRAM = self.tr('LineDirectionHistogram')
        self.BROWSE = self.tr('Browse')
        self.CANCEL = self.tr('Cancel')
        self.CLOSE = self.tr('Close')
        self.OK = self.tr('OK')
        self.NUMBEROFRINGS = 10  # Number of concentric rings in the histogram

        """Constructor."""
        super(linedirectionhistogramDialog, self).__init__(parent)
        # Set up the user interface from Designer.
        # After setupUI you can access any designer object by doing
        # self.<objectname>, and you can use autoconnect slots - see
        # http://qt-project.org/doc/qt-4.8/designer-using-a-ui-file.html
        # #widgets-and-dialogs-with-auto-connect
        self.setupUi(self)

        okButton = self.button_box.button(QDialogButtonBox.Ok)
        okButton.setText(self.OK)
        cancelButton = self.button_box.button(QDialogButtonBox.Cancel)
        cancelButton.setText(self.CANCEL)

        browseButton = self.BrowseButton
        browseButton.setText(self.BROWSE)
        closeButton = self.button_box.button(QDialogButtonBox.Close)
        closeButton.setText(self.CLOSE)

        # Connect signals
        okButton.clicked.connect(self.startWorker)
        cancelButton.clicked.connect(self.killWorker)
        closeButton.clicked.connect(self.reject)
        browseButton.clicked.connect(self.browse)
        dirNeutralCBCh = self.directionNeutralCheckBox.stateChanged
        dirNeutralCBCh.connect(self.updateBins)
        noWeightingCBCh = self.noWeightingCheckBox.stateChanged
        noWeightingCBCh.connect(self.noWeighting)
        binsSBCh = self.binsSpinBox.valueChanged[str]
        binsSBCh.connect(self.updateBins)
        offsetAngleSBCh = self.offsetAngleSpinBox.valueChanged[str]
        offsetAngleSBCh.connect(self.updateBins)

        #self.iface.legendInterface().itemAdded.connect(
        #    self.layerlistchanged)
        #self.iface.legendInterface().itemRemoved.connect(
        #    self.layerlistchanged)
        QObject.disconnect(self.button_box, SIGNAL("rejected()"),
                           self.reject)

        # Set instance variables
        self.worker = None
        self.inputlayerid = None
        self.layerlistchanging = False
        self.bins = 8
        self.binsSpinBox.setValue(self.bins)
        # Direction neutrality is the default
        self.directionneutral = True
        self.directionNeutralCheckBox.setChecked(self.directionneutral)
        # Weighting by line segment length is the default
        self.noweighting = False
        self.noWeightingCheckBox.setChecked(self.noweighting)
        self.noWeightingCheckBox.setEnabled(False)
        self.selectedFeaturesCheckBox.setChecked(True)
        self.setupScene = QGraphicsScene(self)
        self.setupGraphicsView.setScene(self.setupScene)
        self.scene = QGraphicsScene(self)
        self.histogramGraphicsView.setScene(self.scene)
        maxoffsetangle = int(360 / self.bins)
        if self.directionneutral:
            maxoffsetangle = int(maxoffsetangle / 2)
        self.offsetAngleSpinBox.setMaximum(maxoffsetangle)
        self.offsetAngleSpinBox.setMinimum(-maxoffsetangle)
        self.result = None

    def startWorker(self):
        #self.showInfo('Ready to start worker')
        # Get the input layer
        layerindex = self.InputLayer.currentIndex()
        layerId = self.InputLayer.itemData(layerindex)
        inputlayer = QgsMapLayerRegistry.instance().mapLayer(layerId)
        if inputlayer is None:
            self.showError(self.tr('No input layer defined'))
            return
        if inputlayer.featureCount() == 0:
            self.showError(self.tr('No features in input layer'))
            self.scene.clear()
            return
        self.bins = self.binsSpinBox.value()
        self.outputfilename = self.outputFile.text()
        self.directionneutral = False
        if self.directionNeutralCheckBox.isChecked():
            self.directionneutral = True
        self.offsetangle = self.offsetAngleSpinBox.value()
        # create a new worker instance
        worker = Worker(inputlayer, self.bins, self.directionneutral,
                        self.offsetangle,
                        self.selectedFeaturesCheckBox.isChecked())
        ## configure the QgsMessageBar
        #msgBar = self.iface.messageBar().createMessage(self.tr('Joining'), '')
        #self.aprogressBar = QProgressBar()
        #self.aprogressBar.setAlignment(Qt.AlignLeft | Qt.AlignVCenter)
        #acancelButton = QPushButton()
        #acancelButton.setText(self.CANCEL)
        #acancelButton.clicked.connect(self.killWorker)
        #msgBar.layout().addWidget(self.aprogressBar)
        #msgBar.layout().addWidget(acancelButton)
        ## Has to be popped after the thread has finished (in
        ## workerFinished).
        #self.iface.messageBar().pushWidget(msgBar,
        #                                   self.iface.messageBar().INFO)
        #self.messageBar = msgBar
        # start the worker in a new thread
        thread = QThread(self)
        worker.moveToThread(thread)
        worker.finished.connect(self.workerFinished)
        worker.error.connect(self.workerError)
        worker.status.connect(self.workerInfo)
        worker.progress.connect(self.progressBar.setValue)
        #worker.progress.connect(self.aprogressBar.setValue)
        thread.started.connect(worker.run)
        thread.start()
        self.thread = thread
        self.worker = worker
        self.button_box.button(QDialogButtonBox.Ok).setEnabled(False)
        self.button_box.button(QDialogButtonBox.Close).setEnabled(False)

    def workerFinished(self, ok, ret):
        """Handles the output from the worker and cleans up after the
           worker has finished."""
        # clean up the worker and thread
        self.worker.deleteLater()
        self.thread.quit()
        self.thread.wait()
        self.thread.deleteLater()
        # remove widget from the message bar (pop)
        #self.iface.messageBar().popWidget(self.messageBar)
        if ok and ret is not None:
            self.result = ret
            # report the result
            # As a CSV file:
            if self.outputfilename != "":
                try:
                    with open(self.outputfilename, 'wb') as csvfile:
                        csvwriter = csv.writer(csvfile, delimiter=';',
                                    quotechar='"', quoting=csv.QUOTE_MINIMAL)
                        csvwriter.writerow(["StartAngle", "EndAngle",
                                            "Length", "Number"])
                        for i in range(len(ret)):
                            if self.directionneutral:
                                angle = (i * 180.0 / self.bins +
                                                self.offsetangle)
                                csvwriter.writerow([angle,
                                                   angle + 180.0 / self.bins,
                                                   ret[i][0], ret[i][1]])
                            else:
                                angle = (i * 360.0 / self.bins +
                                                         self.offsetangle)
                                csvwriter.writerow([angle,
                                               angle + 360.0 / self.bins,
                                               ret[i][0], ret[i][1]])
                    with open(self.outputfilename + 't', 'wb') as csvtfile:
                        csvtfile.write('"Real","Real","Real","Integer"')
                except IOError, e:
                    self.showInfo("Trouble writing the CSV file: " + str(e))
            # Draw the histogram
            self.drawHistogram()
            self.noWeightingCheckBox.setEnabled(True)
        else:
            # notify the user that something went wrong
            if not ok:
                self.showError(self.tr('Aborted') + '!')
            else:
                self.showError(self.tr('No histogram created') + '!')
        # Update the user interface
        self.progressBar.setValue(0.0)
        self.button_box.button(QDialogButtonBox.Ok).setEnabled(True)
        self.button_box.button(QDialogButtonBox.Close).setEnabled(True)
        # end of workerFinished(self, ok, ret)

    def workerError(self, exception_string):
        """Report an error from the worker."""
        #QgsMessageLog.logMessage(self.tr('Worker failed - exception') +
        #                         ': ' + str(exception_string),
        #                         self.LINEDIRECTIONHISTOGRAM,
        #                         QgsMessageLog.CRITICAL)
        self.showError(exception_string)

    def workerInfo(self, message_string):
        """Report an info message from the worker."""
        QgsMessageLog.logMessage(self.tr('Worker') + ': ' +
                                 message_string,
                                 self.LINEDIRECTIONHISTOGRAM,
                                 QgsMessageLog.INFO)

    def killWorker(self):
        """Kill the worker thread."""
        if self.worker is not None:
            QgsMessageLog.logMessage(self.tr('Killing worker'),
                                     self.LINEDIRECTIONHISTOGRAM,
                                     QgsMessageLog.INFO)
            self.worker.kill()

    # Implement the reject method to have the possibility to avoid
    # exiting the dialog when cancelling
    def reject(self):
        """Reject override."""
        # exit the dialog
        QDialog.reject(self)

    def browse(self):
        outpath = saveDialog(self)
        self.outputFile.setText(outpath)

    def noWeighting(self):
        if self.result is not None:
            self.drawHistogram()

    def drawHistogram(self):
        if self.result is None:
            return
        #self.showInfo(str(self.result))
        # Check which element should be used for the histogram
        element = 0
        if self.noWeightingCheckBox.isChecked():
            element = 1
        # Find the maximum direction value for scaling
        maxvalue = 0.0
        for i in range(len(self.result)):
            if self.result[i][element] > maxvalue:
                maxvalue = self.result[i][element]
        self.scene.clear()
        if maxvalue == 0:
            return
        viewprect = QRectF(self.histogramGraphicsView.viewport().rect())
        self.histogramGraphicsView.setSceneRect(viewprect)
        bottom = self.histogramGraphicsView.sceneRect().bottom()
        top = self.histogramGraphicsView.sceneRect().top()
        left = self.histogramGraphicsView.sceneRect().left()
        right = self.histogramGraphicsView.sceneRect().right()
        height = bottom - top
        width = right - left
        size = width
        if width > height:
            size = height
        padding = 3
        maxlength = size / 2.0 - padding * 2
        center = QPoint(left + width / 2.0, top + height / 2.0)
        start = QPointF(self.histogramGraphicsView.mapToScene(center))
        # Create some concentric rings as background:
        for i in range(self.NUMBEROFRINGS):
                step = maxlength / self.NUMBEROFRINGS
                radius = step * (i + 1)
                circle = QGraphicsEllipseItem(start.x() - radius,
                                              start.y() - radius,
                                              radius * 2.0,
                                              radius * 2.0)
                circle.setPen(QPen(QColor(153, 153, 255)))
                self.scene.addItem(circle)
        for i in range(self.bins):
                linelength = maxlength * self.result[i][element] / maxvalue
                angle = 90 - i * 360.0 / self.bins - self.offsetangle
                if self.directionneutral:
                    angle = 90.0 - i * 180.0 / self.bins - self.offsetangle
                directedline = QLineF.fromPolar(linelength, angle)
                topt = center + QPoint(directedline.x2(), directedline.y2())
                end = QPointF(self.histogramGraphicsView.mapToScene(topt))
                if self.directionneutral:
                    otherendpt = center - QPoint(directedline.x2(),
                                               directedline.y2())
                    scotendpt = self.histogramGraphicsView.mapToScene(otherendpt)
                    otherend = QPointF(scotendpt)
                    self.scene.addItem(QGraphicsLineItem(QLineF(otherend,
                                                                end)))
                    sector = QGraphicsEllipseItem(start.x() - linelength,
                                                  start.y() - linelength,
                                                  linelength * 2.0,
                                                  linelength * 2.0)
                    sector.setStartAngle(int(16 * (90.0 - i * 180.0 /
                                                   self.bins -
                                                   self.offsetangle)))
                    sector.setSpanAngle(int(16 * (-180.0 / self.bins)))
                    sector.setBrush(QBrush(QColor(240, 240, 240)))
                    self.scene.addItem(sector)
                    # The sector in the oposite direction
                    sector = QGraphicsEllipseItem(start.x() - linelength,
                                                  start.y() - linelength,
                                                  linelength * 2.0,
                                                  linelength * 2.0)
                    sector.setStartAngle(int(16 * (270.0 - i * 180.0
                                                   / self.bins -
                                                   self.offsetangle)))
                    sector.setSpanAngle(int(16 * (-180.0 / self.bins)))
                    sector.setBrush(QBrush(QColor(240, 240, 240)))
                    self.scene.addItem(sector)
                else:
                    self.scene.addItem(QGraphicsLineItem(QLineF(start, end)))
                    sector = QGraphicsEllipseItem(start.x() - linelength,
                                                  start.y() - linelength,
                                                  linelength * 2.0,
                                                  linelength * 2.0)
                    sector.setStartAngle(int(16 * (90.0 - i * 360.0 /
                                                   self.bins -
                                                   self.offsetangle)))
                    sector.setSpanAngle(int(16 * (-360.0 / self.bins)))
                    sector.setBrush(QBrush(QColor(240, 240, 240)))
                    self.scene.addItem(sector)

    # Update the visualisation of the bin structure
    def updateBins(self):
        self.directionneutral = False
        if self.directionNeutralCheckBox.isChecked():
            self.directionneutral = True
        self.bins = self.binsSpinBox.value()
        if self.bins < 2:
            self.bins = 2
            self.binsSpinBox.setValue(bins)
        maxoffsetangle = int(360 / self.bins)
        if self.directionneutral:
            maxoffsetangle = int(maxoffsetangle / 2)
        self.offsetAngleSpinBox.setMaximum(maxoffsetangle)
        self.offsetAngleSpinBox.setMinimum(-maxoffsetangle)
        self.offsetangle = self.offsetAngleSpinBox.value()
        if self.offsetangle > maxoffsetangle:
            self.offsetAngleSpinBox.setValue(maxoffsetangle)
            self.offsetangle = maxoffsetangle
        elif self.offsetangle < -maxoffsetangle:
            self.offsetAngleSpinBox.setValue(-maxoffsetangle)
            self.offsetangle = -maxoffsetangle
        self.setupScene.clear()
        self.setupScene.update()
        viewprect = QRectF(self.setupGraphicsView.viewport().rect())
        self.setupGraphicsView.setSceneRect(viewprect)
        bottom = self.setupGraphicsView.sceneRect().bottom()
        top = self.setupGraphicsView.sceneRect().top()
        left = self.setupGraphicsView.sceneRect().left()
        right = self.setupGraphicsView.sceneRect().right()
        height = bottom - top
        width = right - left
        size = width
        if width > height:
            size = height
        padding = 3.0
        maxlength = size / 2.0 - padding
        center = QPoint(left + width / 2.0, top + height / 2.0)
        start = QPointF(self.setupGraphicsView.mapToScene(center))
        # Create some concentric rings:
        setuprings = self.NUMBEROFRINGS // 2
        for i in range(setuprings):
            step = maxlength / setuprings
            radius = step * (i + 1)
            circle = QGraphicsEllipseItem(start.x() - radius,
                                          start.y() - radius,
                                          radius * 2.0,
                                          radius * 2.0)
            circle.setPen(QPen(QColor(153, 153, 255)))
            self.setupScene.addItem(circle)
        for i in range(self.bins):
            linelength = maxlength
            angle = 90 - i * 360.0 / self.bins - self.offsetangle
            if self.directionneutral:
                angle = 90.0 - i * 180.0 / self.bins - self.offsetangle
            directedline = QLineF.fromPolar(linelength, angle)
            topt = center + QPoint(directedline.x2(),
                                   directedline.y2())
            end = QPointF(self.setupGraphicsView.mapToScene(topt))
            if self.directionneutral:
                otherpt = center - QPoint(directedline.x2(),
                                          directedline.y2())
                mirrorpt = QPointF(self.setupGraphicsView.mapToScene(otherpt))
                self.setupScene.addItem(QGraphicsLineItem(
                                         QLineF(mirrorpt, end)))
            else:
                self.setupScene.addItem(QGraphicsLineItem(QLineF(start, end)))
        self.noWeightingCheckBox.setEnabled(False)
        # end of updatebins


    #def layerlistchanged(self):
    #    self.layerlistchanging = True
    #    # Repopulate the input and join layer combo boxes
    #    # Save the currently selected input layer
    #    inputlayerid = self.inputlayerid
    #    self.InputLayer.clear()
    #    # We are only interested in line and polygon layers
    #    for alayer in self.iface.legendInterface().layers():
    #        if alayer.type() == QgsMapLayer.VectorLayer:
    #            if (alayer.geometryType() == QGis.Line or
    #                alayer.geometryType() == QGis.Polygon):
    #                self.InputLayer.addItem(alayer.name(), alayer.id())
    #    # Set the previous selection
    #    for i in range(self.InputLayer.count()):
    #        if self.InputLayer.itemData(i) == inputlayerid:
    #            self.InputLayer.setCurrentIndex(i)
    #    self.layerlistchanging = False

    def showError(self, text):
        """Show an error."""
        #self.iface.messageBar().pushMessage(self.tr('Error'), text,
        #                                    level=QgsMessageBar.CRITICAL,
        #                                    duration=3)
        QgsMessageLog.logMessage('Error: ' + text,
                                 self.LINEDIRECTIONHISTOGRAM,
                                 QgsMessageLog.CRITICAL)

    def showWarning(self, text):
        """Show a warning."""
        #self.iface.messageBar().pushMessage(self.tr('Warning'), text,
        #                                    level=QgsMessageBar.WARNING,
        #                                    duration=2)
        QgsMessageLog.logMessage('Warning: ' + text,
                                 self.LINEDIRECTIONHISTOGRAM,
                                 QgsMessageLog.WARNING)

    def showInfo(self, text):
        """Show info."""
        #self.iface.messageBar().pushMessage(self.tr('Info'), text,
        #                                    level=QgsMessageBar.INFO,
        #                                    duration=2)
        QgsMessageLog.logMessage('Info: ' + text,
                                 self.LINEDIRECTIONHISTOGRAM,
                                 QgsMessageLog.INFO)

    # Implement the accept method to avoid exiting the dialog when
    # starting the work
    def accept(self):
        """Accept override."""
        pass

    # Implement the reject method to have the possibility to avoid
    # exiting the dialog when cancelling
    def reject(self):
        """Reject override."""
        # exit the dialog
        QDialog.reject(self)

    # Translation
    def tr(self, message):
        """Get the translation for a string using Qt translation API.

        :param message: String for translation.
        :type message: str, QString

        :returns: Translated version of message.
        :rtype: QString
        """
        return QCoreApplication.translate('LineDirectionDialog', message)

    # Overriding
    def resizeEvent(self, event):
        #self.showInfo("resizeEvent")
        self.drawHistogram()

    # Overriding
    def showEvent(self, event):
        #self.showInfo("showEvent")
        self.updateBins()


def saveDialog(parent):
        """Shows a file dialog and return the selected file path."""
        settings = QSettings()
        key = '/UI/lastShapefileDir'
        outDir = settings.value(key)
        filter = 'Comma Separated Value (*.csv)'
        outFilePath = QFileDialog.getSaveFileName(parent,
                       parent.tr('Output CSV file'), outDir, filter)
        outFilePath = unicode(outFilePath)
        if outFilePath:
            root, ext = os.path.splitext(outFilePath)
            if ext.upper() != '.CSV':
                outFilePath = '%s.csv' % outFilePath
            outDir = os.path.dirname(outFilePath)
            settings.setValue(key, outDir)
        return outFilePath
