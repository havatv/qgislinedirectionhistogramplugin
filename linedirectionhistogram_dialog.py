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
import math
import tempfile
import random

from PyQt4 import uic
from PyQt4.QtCore import SIGNAL, QObject, QThread, QCoreApplication
from PyQt4.QtCore import QPointF, QLineF, QRectF, QPoint, QSettings
from PyQt4.QtCore import QSizeF, QSize, QRect
from PyQt4.QtCore import QVariant
from PyQt4.QtGui import QDialog, QDialogButtonBox, QFileDialog
from PyQt4.QtGui import QGraphicsLineItem, QGraphicsEllipseItem
from PyQt4.QtGui import QGraphicsScene, QBrush, QPen, QColor
from PyQt4.QtGui import QGraphicsView
from PyQt4.QtGui import QPrinter, QPainter
from PyQt4.QtGui import QApplication, QImage, QPixmap
from PyQt4.QtSvg import QSvgGenerator
from qgis.core import QgsMessageLog, QgsMapLayerRegistry, QgsMapLayer
from qgis.core import QGis
from qgis.core import QgsVectorLayer
from qgis.core import QgsField, QgsFeature
from qgis.core import QgsCategorizedSymbolRendererV2, QgsSymbolV2,
from qgis.core import QgsSvgMarkerSymbolLayerV2, QgsRendererCategoryV2
#from qgis.gui import QgsMessageBar
from qgis.utils import showPluginHelp

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
        self.HELP = self.tr('Help')
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
        helpButton = self.helpButton
        helpButton.setText(self.HELP)

        browseButtonCSV = self.browseButtonCSV
        browseButtonCSV.setText(self.BROWSE)
        browseButtonTile = self.browseButtonTile
        browseButtonTile.setText(self.BROWSE)
        closeButton = self.button_box.button(QDialogButtonBox.Close)
        closeButton.setText(self.CLOSE)

        # Connect signals
        okButton.clicked.connect(self.startWorker)
        cancelButton.clicked.connect(self.killWorker)
        helpButton.clicked.connect(self.giveHelp)
        closeButton.clicked.connect(self.reject)
        browseButtonCSV.clicked.connect(self.browse)
        browseButtonTile.clicked.connect(self.browseTile)
        dirNeutralCBCh = self.directionNeutralCheckBox.stateChanged
        dirNeutralCBCh.connect(self.updateBins)
        noWeightingCBCh = self.noWeightingCheckBox.stateChanged
        noWeightingCBCh.connect(self.noWeighting)
        noAreaProportionalCBCh = self.proportionalAreaCheckBox.stateChanged
        noAreaProportionalCBCh.connect(self.proportionalArea)
        binsSBCh = self.binsSpinBox.valueChanged[str]
        binsSBCh.connect(self.updateBins)
        offsetAngleSBCh = self.offsetAngleSpinBox.valueChanged[str]
        offsetAngleSBCh.connect(self.updateBins)
        self.saveAsPDFButton.clicked.connect(self.saveAsPDF)
        self.saveAsSVGButton.clicked.connect(self.saveAsSVG)
        self.copyToClipboardButton.clicked.connect(self.copyToClipboard)

        self.saveAsPDFButton.setEnabled(False)
        self.saveAsSVGButton.setEnabled(False)
        self.copyToClipboardButton.setEnabled(False)
        cancelButton.setEnabled(True)
        #self.tileDirectory.
        #self.iface.legendInterface().itemAdded.connect(
        #    self.layerlistchanged)
        #self.iface.legendInterface().itemRemoved.connect(
        #    self.layerlistchanged)
        QObject.disconnect(self.button_box, SIGNAL("rejected()"),
                           self.reject)

        # Set instance variables
        self.worker = None
        self.inputlayerid = None
        #self.layerlistchanging = False
        self.bins = 8
        self.binsSpinBox.setValue(self.bins)
        # Direction neutrality is the default
        self.directionneutral = True
        self.directionNeutralCheckBox.setChecked(self.directionneutral)
        # Weighting by line segment length is the default
        self.noWeightingCheckBox.setChecked(False)
        self.proportionalAreaCheckBox.setChecked(False)
        self.selectedFeaturesCheckBox.setChecked(True)
        self.setupScene = QGraphicsScene(self)
        self.setupGraphicsView.setScene(self.setupScene)
        self.histscene = QGraphicsScene(self)
        self.histogramGraphicsView.setScene(self.histscene)
        maxoffsetangle = int(360 / self.bins)
        if self.directionneutral:
            maxoffsetangle = int(maxoffsetangle / 2)
        self.offsetAngleSpinBox.setMaximum(maxoffsetangle)
        self.offsetAngleSpinBox.setMinimum(-maxoffsetangle)
        self.pointLayer = None
        self.idfieldname = 'ID'
        self.svgfiles = []
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
            self.histscene.clear()
            return
        self.bins = self.binsSpinBox.value()
        self.outputfilename = self.outputFile.text()
        self.directionneutral = False
        if self.directionNeutralCheckBox.isChecked():
            self.directionneutral = True
        self.offsetangle = self.offsetAngleSpinBox.value()
        tilelayer = None
        if self.useTilingCheckBox.isChecked():
            layerindex = self.TilingLayer.currentIndex()
            layerId = self.TilingLayer.itemData(layerindex)
            tilelayer = QgsMapLayerRegistry.instance().mapLayer(layerId)
            if tilelayer is None:
                self.showError(self.tr('No tile layer defined'))
                return
            if tilelayer.featureCount() == 0:
                self.showError(self.tr('No features in tile layer'))
                self.histscene.clear()
                return
            self.pointLayer = QgsVectorLayer('Point?crs=EPSG:4326',
                                       "SVGPoints", "memory")
            self.pointLayer.setCrs(tilelayer.crs())
            self.pointLayer.dataProvider().addAttributes(
                       [QgsField(self.idfieldname, QVariant.Int)])
            self.pointLayer.updateFields()
            id = 1
            for feature in tilelayer.getFeatures():
                newfeature = QgsFeature()
                #centroid = newfeature.geometry().centroid()
                centroid = feature.geometry().pointOnSurface()
                newfeature.setGeometry(centroid)
                newfeature.setAttributes([id])
                self.pointLayer.dataProvider().addFeatures([newfeature])
                id = id + 1
        # create a new worker instance
        worker = Worker(inputlayer, self.bins, self.directionneutral,
                        self.offsetangle,
                        self.selectedFeaturesCheckBox.isChecked(),
                        tilelayer)
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
        self.button_box.button(QDialogButtonBox.Cancel).setEnabled(True)
        self.saveAsPDFButton.setEnabled(False)
        self.saveAsSVGButton.setEnabled(False)
        self.copyToClipboardButton.setEnabled(False)

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
        # Three outcomes:
        # 1) No data returned
        # 2) A vector with only one element: Draw the rose diagram
        # 3) A vector with several elements: Create a layer
        #                                    with rose diagrams as symbols
        if ok and ret is not None:
            self.result = ret[0]
            if len(ret) > 1:  # Several elements - create SVG files for layer
                self.showInfo("Several elements in the result: " +
                              str(len(ret)))
                self.svgfiles = [None] * (len(ret))
                for i in range(len(ret) - 1):
                    self.showInfo("Tile " + str(i + 1) + ": " +
                                  str(len(ret[i + 1])))
                    self.showInfo("Elements: " + str(ret[i + 1]))
                    self.result = ret[i + 1]
                    self.drawHistogram()
                    tmpdir = tempfile.gettempdir()
                    if self.tileDirectory.text():
                        tmpdir = self.tileDirectory.text()
                    tempfilepathprefix = tmpdir + '/qgisLDH_'
                    filename = (tempfilepathprefix + 'rose' +
                                str(i + 1) + '.svg')
                    self.saveAsSVG(filename)
                    #self.svgfiles.append(filename)
                    self.svgfiles[i + 1] = filename
                #self.result = ret[2]

                # Create the SVG symbol renderer
                # Get the unique values for the ID field
                fni = self.pointLayer.fieldNameIndex(self.idfieldname)
                uniq_vals = self.pointLayer.dataProvider().uniqueValues(fni)
                categories = []  # For renderer categories
                # Create the symbols for each unique ID value
                for val in uniq_vals:
                    # initialize with the default symbol for this geom type
                    symbol = QgsSymbolV2.defaultSymbol(
                                self.pointLayer.geometryType())
                    # configure a symbol layer
                    layer_style = {}
                    layer_style['fill'] = '#ffffff'
                    layer_style['name'] = self.svgfiles[int(val)]
                    layer_style['outline'] = '#000000'
                    layer_style['outline-width'] = '6.8'
                    layer_style['size'] = '50'
                    #layer_style['color'] = '%d, %d, %d' % (
                    #                          random.randrange(0,256),
                    #                          random.randrange(0,256),
                    #                          random.randrange(0,256))
                    sym_layer = QgsSvgMarkerSymbolLayerV2.create(layer_style)
                    # replace default symbol layer with the configured one
                    if sym_layer is not None:
                        symbol.changeSymbolLayer(0, sym_layer)
                    # create renderer object
                    category = QgsRendererCategoryV2(val, symbol, str(val))
                    # entry for the list of category items
                    categories.append(category)
                # create renderer object
                renderer = QgsCategorizedSymbolRendererV2(self.idfieldname,
                                                          categories)
                if renderer is not None:
                    self.pointLayer.setRendererV2(renderer)

                #renderer = self.pointLayer.rendererV2()
                #newrenderer = QgsCategorizedSymbolRendererV2(self.idfieldname)
                #self.showInfo("renderer type: " + renderer.type())
                #self.showInfo("newrenderer type: " + newrenderer.type())

                QgsMapLayerRegistry.instance().addMapLayer(self.pointLayer)
                self.result = ret[0]
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
        else:  # No data returned
            # notify the user that something went wrong
            if not ok:
                self.showError(self.tr('Aborted') + '!')
            else:
                self.showError(self.tr('No histogram created') + '!')
        # Update the user interface
        self.progressBar.setValue(0.0)
        self.button_box.button(QDialogButtonBox.Ok).setEnabled(True)
        self.button_box.button(QDialogButtonBox.Close).setEnabled(True)
        self.button_box.button(QDialogButtonBox.Cancel).setEnabled(False)
        self.saveAsPDFButton.setEnabled(True)
        self.saveAsSVGButton.setEnabled(True)
        self.copyToClipboardButton.setEnabled(True)
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

    def giveHelp(self):
        self.showInfo('Giving help')
        #QDesktopServices.openUrl(QUrl.fromLocalFile(
        #                 self.plugin_dir + "/help/html/index.html"))
        showPluginHelp(None, "help/html/index")
    # end of giveHelp

    # Implement the reject method to have the possibility to avoid
    # exiting the dialog when cancelling
    def reject(self):
        """Reject override."""
        # exit the dialog
        QDialog.reject(self)

    def browse(self):
        outpath = saveCSVDialog(self)
        self.outputFile.setText(outpath)

    def browseTile(self):
        outpath = findTileDialog(self)
        self.tileDirectory.setText(outpath)

    def noWeighting(self):
        if self.result is not None:
            self.drawHistogram()

    def proportionalArea(self):
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
        self.histscene.clear()
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
            self.histscene.addItem(circle)
        for i in range(self.bins):
            linelength = maxlength * self.result[i][element] / maxvalue
            if self.proportionalAreaCheckBox.isChecked():
                linelength = (maxlength * math.sqrt(self.result[i][element]) /
                              math.sqrt(maxvalue))
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
                self.histscene.addItem(QGraphicsLineItem(QLineF(otherend,
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
                self.histscene.addItem(sector)
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
                self.histscene.addItem(sector)
            else:
                self.histscene.addItem(QGraphicsLineItem(QLineF(start, end)))
                sector = QGraphicsEllipseItem(start.x() - linelength,
                                              start.y() - linelength,
                                              linelength * 2.0,
                                              linelength * 2.0)
                sector.setStartAngle(int(16 * (90.0 - i * 360.0 /
                                               self.bins -
                                               self.offsetangle)))
                sector.setSpanAngle(int(16 * (-360.0 / self.bins)))
                sector.setBrush(QBrush(QColor(240, 240, 240)))
                self.histscene.addItem(sector)

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
        if self.result is not None:
            self.drawHistogram()

    # Overriding
    def showEvent(self, event):
        #self.showInfo("showEvent")
        self.updateBins()

    # Save to PDF
    def saveAsPDF(self):
        savename = unicode(QFileDialog.getSaveFileName(self, "Save File",
                                                       "", "*.pdf"))
        printer = QPrinter(QPrinter.HighResolution)
        printer.setPaperSize(QSizeF(100, 100), QPrinter.Millimeter)
        printer.setPageMargins(0, 0, 0, 0, QPrinter.Millimeter)
        printer.setOutputFormat(QPrinter.PdfFormat)
        printer.setOutputFileName(savename)
        p = QPainter(printer)
        self.histscene.render(p)
        p.end()

    # Save to SVG
    def saveAsSVG(self, location=None):
        savename = location
        if location is None:
            savename = unicode(QFileDialog.getSaveFileName(self, "Save File",
"*.svg"))
        svgGen = QSvgGenerator()
        svgGen.setFileName(savename)
        svgGen.setSize(QSize(200, 200))
        svgGen.setViewBox(QRect(0, 0, 201, 201))
        painter = QPainter(svgGen)
        self.histscene.render(painter)
        painter.end()

    def copyToClipboard(self):
        QApplication.clipboard().setImage(QImage(
                        QPixmap.grabWidget(QGraphicsView(self.histscene))))


def saveCSVDialog(parent):
        """Shows a file dialog and return the selected file path."""
        settings = QSettings()
        key = '/UI/lastShapefileDir'
        tryDir = settings.value(key)
        filter = 'Comma Separated Value (*.csv)'
        outFilePath = QFileDialog.getSaveFileName(parent,
                       parent.tr('Output CSV file'), tryDir, filter)
        outFilePath = unicode(outFilePath)
        if outFilePath:
            root, ext = os.path.splitext(outFilePath)
            if ext.upper() != '.CSV':
                outFilePath = '%s.csv' % outFilePath
            tryDir = os.path.dirname(outFilePath)
            settings.setValue(key, tryDir)
        return outFilePath


def findTileDialog(parent):
        """Shows a file dialog and return the selected file path."""
        settings = QSettings()
        key = '/UI/lastShapefileDir'
        outDir = settings.value(key)
        #filter = 'Comma Separated Value (*.csv)'
        outFilePath = QFileDialog.getExistingDirectory(parent,
                       parent.tr('Directory for SVGs'), outDir)
        outFilePath = unicode(outFilePath)
        if outFilePath:
            #root, ext = os.path.splitext(outFilePath)
            #if ext.upper() != '.CSV':
            #    outFilePath = '%s.csv' % outFilePath
            outDir = os.path.dirname(outFilePath)
            settings.setValue(key, outDir)
        return outFilePath
