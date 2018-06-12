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
import tempfile  # rose diagram SVG files for rose layer rendering
import uuid   # for generating unique file names (QGIS bug #13565)

from PyQt4 import uic
from PyQt4.QtCore import SIGNAL, QObject, QThread, QCoreApplication
from PyQt4.QtCore import QPointF, QLineF, QRectF, QPoint, QSettings
from PyQt4.QtCore import QSizeF, QSize, QRect, Qt
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
from qgis.core import QgsCategorizedSymbolRendererV2, QgsSymbolV2
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
        #self.iface = iface
        #self.plugin_dir = os.path.dirname(__file__)

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
        logaritmicCBCh = self.logaritmicCheckBox.stateChanged
        logaritmicCBCh.connect(self.logaritmic)
        noAreaProportionalCBCh = self.proportionalAreaCheckBox.stateChanged
        noAreaProportionalCBCh.connect(self.proportionalArea)
        binsSBCh = self.binsSpinBox.valueChanged[str]
        binsSBCh.connect(self.updateBins)
        offsetAngleSBCh = self.offsetAngleSpinBox.valueChanged[str]
        offsetAngleSBCh.connect(self.updateBins)
        self.saveAsPDFButton.clicked.connect(self.saveAsPDF)
        self.saveAsSVGButton.clicked.connect(self.saveAsSVG)
        self.copyToClipboardButton.clicked.connect(self.copyToClipboard)
        self.InputLayer.currentIndexChanged.connect(self.inputLayerChanged)
        self.useTilingCheckBox.toggled.connect(self.tilingToggled)

        self.saveAsPDFButton.setEnabled(False)
        self.saveAsSVGButton.setEnabled(False)
        self.copyToClipboardButton.setEnabled(False)
        cancelButton.setEnabled(True)

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
        # Layer for the rose diagrams based on the input polygon tiles
        self.roseLayer = None
        # ID field name - constant
        self.idfieldname = 'ID'
        self.svgfiles = []  # Array of SVG files - first element is None
        self.result = None
        self.ringcolour = QColor(153, 153, 255)
        self.sectorcolour = QColor(240, 240, 240)
        self.sectorcolourtrans = QColor(240, 240, 240, 0)
        self.meanvectorcolour = QColor(153, 0, 0)

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
        # If a tiling layer is used, create rose diagram layer
        if self.useTilingCheckBox.isChecked():
            layerindex = self.TilingLayer.currentIndex()
            layerId = self.TilingLayer.itemData(layerindex)
            tilelayer = QgsMapLayerRegistry.instance().mapLayer(layerId)
            if tilelayer is None:
                self.showError(self.tr('No tile layer defined'))
                self.histscene.clear()
                return
            if tilelayer.featureCount() == 0:
                self.showError(self.tr('No features in tile layer'))
                self.histscene.clear()
                return
            self.roseLayer = QgsVectorLayer('Point?crs=EPSG:4326',
                                       "RoseDiagrams", "memory")
            self.roseLayer.setCrs(tilelayer.crs())
            # Add the ID field / attribute
            self.roseLayer.dataProvider().addAttributes(
                       [QgsField(self.idfieldname, QVariant.Int)])
            self.roseLayer.updateFields()
            # Add the IDs [1..number of "tiles"]
            id = 1
            # Assumes that getFeatures will always return the features in
            # the same sequence
            for feature in tilelayer.getFeatures():
                newfeature = QgsFeature()
                centroid = feature.geometry().pointOnSurface()
                newfeature.setGeometry(centroid)
                newfeature.setAttributes([id])
                self.roseLayer.dataProvider().addFeatures([newfeature])
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
           worker has finished.
           ok: indicates if the result is sensible
           ret: array of bin arrays.  The first bin array is for
                the over all data.  Each bin array contains the
                statistics for a sector.
                The first sector starts at (or close to) north (the
                y-axis), and extends clockwise.  If the user has
                specified an offset, the sector starts either east
                (negative offset) or west (positive offset) of
                north."""
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
            #self.showInfo("ret: " + str(ret))
            # The first element is always the over all histogram
            self.result = ret[0]
            if len(ret) > 1:  # Several elements - create SVG files for layer
                # Initialise the vector of SVG files
                self.svgfiles = [None] * len(ret)
                # Determine the directory for storing the SVG files
                tmpdir = tempfile.gettempdir()
                if self.tileDirectory.text():
                    tmpdir = self.tileDirectory.text()
                # Set the prefix for the SVG files
                #tempfilepathprefix = tmpdir + '/qgisLDH_'
                tempfilepathprefix = (tmpdir + '/qgisLDH_rose_' +
                                      str(uuid.uuid4()))
                categories = []  # Renderer categories
                self.meandirstats = [] # For later saving to a CSV file
                # Create the SVG files and symbols for the tiles
                for i in range(len(ret) - 1):
                    # Set the global result variable to be used for
                    # drawing the histogram
                    self.result = ret[i + 1]
                    # Draw the histogram, and 
                    self.drawHistogram()
                    # Set the file name (and directory) for the SVG file
                    filename = (tempfilepathprefix + str(i + 1) + '.svg')
                    self.saveAsSVG(filename)
                    self.svgfiles[i + 1] = filename
                    ## Create the symbol for this ID value
                    # initialize with the default symbol for this geom type
                    symbol = QgsSymbolV2.defaultSymbol(
                                self.roseLayer.geometryType())
                    # configure an (SVG) symbol layer
                    layer_style = {}
                    layer_style['fill'] = '#ffffff'
                    layer_style['name'] = filename
                    layer_style['outline'] = '#000000'
                    layer_style['outline-width'] = '6.8'
                    layer_style['size'] = '20'
                    sym_layer = QgsSvgMarkerSymbolLayerV2.create(layer_style)
                    # replace default symbol layer with the configured one
                    if sym_layer is not None:
                        symbol.changeSymbolLayer(0, sym_layer)
                    # create renderer category
                    category = QgsRendererCategoryV2(i + 1, symbol,
                                                     str(i + 1))
                    categories.append(category)

                    # Calculate the mean directions (angle and strength)
                    strength = None
                    meandir = None
                    if (self.dirTrendCheckBox.isChecked() and self.directionneutral):
                        (maxbin, strength) = self.semiCircMean()
                        meandir = maxbin
                        #meandir = maxbin * 180 / self.bins
                    if (self.dirTrendCheckBox.isChecked() and not self.directionneutral):
                        (circmeanx, circmeany) = self.circMean()
                        #self.showInfo("circmean x, y: " + str(circmeanx) + ' ,' + str(circmeany))
                        if circmeanx is not None:
                            strength = math.sqrt(circmeanx*circmeanx + circmeany*circmeany)
                            #if circmeanx != 0:
                            if circmeany != 0:
                                #meandir = math.degrees(math.atan(circmeany / circmeanx))
                                meandir = math.degrees(math.atan(circmeanx / circmeany))
                                if meandir < 0:
                                    meandir = 360 + meandir
                            else:
                                meandir = math.degrees(math.pi/2)
                        #else:
                        #    meandir = None
                        #    strength = None
                    #self.showInfo("meandir: " + str(meandir))
                    self.meandirstats.append([i+1, meandir, strength])
                # create categorized renderer object
                renderer = QgsCategorizedSymbolRendererV2(self.idfieldname,
                                                          categories)
                if renderer is not None:
                    self.roseLayer.setRendererV2(renderer)
                QgsMapLayerRegistry.instance().addMapLayer(self.roseLayer)
                # Set the result to the over all histogram
                self.result = ret[0]
            # Shall the result be reported (as a CSV file):
            if self.outputfilename != "":
                try:
                    with open(self.outputfilename, 'wb') as csvfile:
                        csvwriter = csv.writer(csvfile, delimiter=';',
                                    quotechar='"', quoting=csv.QUOTE_MINIMAL)
                        if self.useTilingCheckBox.isChecked() and self.meanDirectionRB.isChecked():
                            csvwriter.writerow(["Id", "Direction", "Strength"])
                            for i in range(len(self.meandirstats)):
                                if self.directionneutral and self.meandirstats[i][1] is not None:
                                    angle = ((self.meandirstats[i][1]+0.5) * 180.0 / self.bins +
                                                    self.offsetangle)
                                else:
                                    angle = (self.meandirstats[i][1])
                                csvwriter.writerow([self.meandirstats[i][0],
                                                    angle,
                                                    self.meandirstats[i][2]])

                            with open(self.outputfilename + 't', 'wb') as csvtfile:
                                csvtfile.write('"Integer","Real","Real"')
                        elif self.histogramRB.isChecked():
                            csvwriter.writerow(["StartAngle", "EndAngle",
                                                "Length", "Number"])
                            for i in range(len(ret[0])):
                                if self.directionneutral:
                                    angle = (i * 180.0 / self.bins +
                                                    self.offsetangle)
                                    csvwriter.writerow([angle,
                                                       angle + 180.0 / self.bins,
                                                       ret[0][i][0], ret[0][i][1]])
                                else:
                                    angle = (i * 360.0 / self.bins +
                                                             self.offsetangle)
                                    csvwriter.writerow([angle,
                                                   angle + 360.0 / self.bins,
                                                   ret[0][i][0], ret[0][i][1]])
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

    def logaritmic(self):
        if self.result is not None:
            self.drawHistogram()

    # Draws the histogram by adding elements to self.histscence
    # No other updates of global variables
    def drawHistogram(self):
        # self.result shall contain the bins.  The first bin
        # starts at north + offsetangle, continuing clockwise
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
        if self.logaritmicCheckBox.isChecked():
            maxvalue = math.log1p(maxvalue)
        if self.proportionalAreaCheckBox.isChecked():
            maxvalue = math.sqrt(maxvalue)
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
        # The scene geomatry of the center point
        start = QPointF(self.histogramGraphicsView.mapToScene(center))
        # Create some concentric rings as background:
        for i in range(self.NUMBEROFRINGS):
            step = maxlength / self.NUMBEROFRINGS
            radius = step * (i + 1)
            circle = QGraphicsEllipseItem(start.x() - radius,
                                          start.y() - radius,
                                          radius * 2.0,
                                          radius * 2.0)
            circle.setPen(QPen(self.ringcolour))
            self.histscene.addItem(circle)

        # Get circular statistics for the direction neutral case
        #maxbin = -1
        maxbin = None
        #strength = -1.0
        strength = None
        if (self.dirTrendCheckBox.isChecked() and self.directionneutral):
            (maxbin, strength) = self.semiCircMean()

        # Create the sectors of the Rose diagram
        sectorwidth = 360.0 / self.bins
        if self.directionneutral:
            sectorwidth = sectorwidth / 2.0
        for i in range(self.bins):
            # Find the length of the sector
            currentLength = self.result[i][element]
            if self.logaritmicCheckBox.isChecked():
                currentLength = math.log1p(currentLength)
            if self.proportionalAreaCheckBox.isChecked():
                currentLength = math.sqrt(currentLength)
            linelength = maxlength * currentLength / maxvalue
            # Start angle for sector i
            # Working on Qt angles (0 = east, counter-clockwise)
            angle = 90 - i * sectorwidth - self.offsetangle
            # Draw the sector
            if not self.directionneutral:
                sector = QGraphicsEllipseItem(start.x() - linelength,
                                              start.y() - linelength,
                                              linelength * 2.0,
                                              linelength * 2.0)
                sector.setStartAngle(int(16 * angle))
                sector.setSpanAngle(int(16 * (-sectorwidth)))
                sector.setBrush(QBrush(self.sectorcolour))
                self.histscene.addItem(sector)
            else:
                # Shall direction trend be indicated
                if (self.dirTrendCheckBox.isChecked() and
                                              i == maxbin):
                    # Show the direction trend for this bin using maxlength:
                    sector = QGraphicsEllipseItem(start.x() - maxlength,
                                                start.y() - maxlength,
                                                maxlength * 2.0,
                                                maxlength * 2.0)
                    sector.setStartAngle(int(16 * angle))
                    sector.setSpanAngle(int(16 * (-sectorwidth)))
                    # Use a red tone according to the strength
                    colourintensity = 255 - (strength * 255)
                    trendcolour = QColor(255, colourintensity, colourintensity)
                    sector.setBrush(QBrush(trendcolour))
                    myPen = QPen(QPen(trendcolour))
                    myPen.setWidth(1)
                    sector.setPen(myPen)
                    self.histscene.addItem(sector)
                    # The sector in the opposite direction
                    sector = QGraphicsEllipseItem(start.x() - maxlength,
                                                start.y() - maxlength,
                                                maxlength * 2.0,
                                                maxlength * 2.0)
                    sector.setStartAngle(int(16 * (270.0 - i * sectorwidth -
                                                 self.offsetangle)))
                    sector.setSpanAngle(int(16 * (-sectorwidth)))
                    sector.setBrush(QBrush(trendcolour))
                    myPen = QPen(QPen(trendcolour))
                    myPen.setWidth(1)
                    sector.setPen(myPen)
                    self.histscene.addItem(sector)
                # Draw the rose diagram sector according to the value
                sector = QGraphicsEllipseItem(start.x() - linelength,
                                              start.y() - linelength,
                                              linelength * 2.0,
                                              linelength * 2.0)
                sector.setStartAngle(int(16 * angle))
                sector.setSpanAngle(int(16 * (-sectorwidth)))
                if self.dirTrendCheckBox.isChecked():
                    sector.setBrush(QBrush(self.sectorcolourtrans))
                else:
                    sector.setBrush(QBrush(self.sectorcolour))
                self.histscene.addItem(sector)
                # The sector in the opposite direction
                sector = QGraphicsEllipseItem(start.x() - linelength,
                                              start.y() - linelength,
                                              linelength * 2.0,
                                              linelength * 2.0)
                sector.setStartAngle(int(16 * (270.0 - i * sectorwidth -
                                               self.offsetangle)))
                sector.setSpanAngle(int(16 * (-sectorwidth)))
                if self.dirTrendCheckBox.isChecked():
                    sector.setBrush(QBrush(self.sectorcolourtrans))
                else:
                    sector.setBrush(QBrush(self.sectorcolour))
                self.histscene.addItem(sector)
        if not self.directionneutral and self.dirTrendCheckBox.isChecked():
            # Get the mean
            (circmeanx, circmeany) = self.circMean()
            if circmeanx is None:
                return
            # Draw a point
            radius = 4
            ptcircle = QGraphicsEllipseItem(
                      start.x() + circmeanx * maxlength - radius,
                      start.y() - circmeany * maxlength - radius,
                      radius * 2.0, radius * 2.0)
            # Draw the line that connects the point to the centre
            dirLine = QGraphicsLineItem(start.x(), start.y(),
                                        start.x() + circmeanx *
                                        maxlength,
                                        start.y() - circmeany *
                                        maxlength)
            myPen = QPen(self.meanvectorcolour)
            myPen.setWidth(5)
            myPen.setCapStyle(Qt.FlatCap)
            dirLine.setPen(myPen)
            ptcircle.setPen(QPen(self.meanvectorcolour))
            ptcircle.setBrush(QBrush(self.meanvectorcolour))
            self.histscene.addItem(ptcircle)
            self.histscene.addItem(dirLine)

    # Calculate the circular mean for the current result.
    # Returns the normalised vector (x,y) - in QT graphics view
    # coordinates (east = 0, counter-clockwise).
    # Must not be applied in direction neutral mode.
    def circMean(self):
        sectorwidth = 360.0 / self.bins
        if self.directionneutral:  # Should not happen
            sectorwidth = sectorwidth / 2.0
        element = 0
        if self.noWeightingCheckBox.isChecked():
            element = 1
        sumx = 0  # sum of x values
        sumy = 0  # sum of y values
        sumlinelength = 0  # sum of line lengths
        for i in range(self.bins):
            # Get the accumulated line length for the sector
            linelength = self.result[i][element]
            # Accumulate line length
            sumlinelength = sumlinelength + linelength
            # Set the start angle for sector i
            # Angles are geographic (0 = north, clockwise)
            # Working on Qt angles (0 = east, counter-clockwise)
            angle = 90 - ((i + 0.5) * sectorwidth + self.offsetangle)
            addx = linelength * math.cos(math.radians(angle))
            addy = linelength * math.sin(math.radians(angle))
            sumx = sumx + addx
            sumy = sumy + addy
        # Directional statistics
        if sumlinelength == 0:
            return (None, None)  # ????
        else:
            normsumx = sumx / sumlinelength
            normsumy = sumy / sumlinelength
            return (normsumx, normsumy)

    # Approximate the direction neutral circular mean for the current
    # result by returning the bin / sector number (starting at 0)
    # that gives the maximum semi-circular mean together with the
    # strength ([0..1]) of the direction trend.
    # Must only be applied in direction neutral mode.
    def semiCircMean(self):
        #oddnumberofbins = self.bins % 2
        sectorwidth = 360.0 / self.bins
        if self.directionneutral:  # Should always be the case
            sectorwidth = sectorwidth / 2.0
        # Should line length of number of lines be used:
        element = 0
        if self.noWeightingCheckBox.isChecked():
            element = 1

        # Calculate the circle reference values for normalisation
        # The "border" sectors will have an angle of 90 deg to the
        # reference sector for even numbers of sectors, and will
        # therefore not contribute.
        refangle = (180.0 / self.bins) * (0.5 + self.bins // 2)
        totalsum = 0  # sum of all the bin values
        totalx = 0    # sum of the horizontal components (unit)
        for i in range(self.bins):
            angle = (180.0 / self.bins) * (0.5 + i)
            xvalue = math.cos(math.radians(angle - refangle))
            totalx = totalx + xvalue
            binvalue = self.result[i][element]
            totalsum = totalsum + binvalue
        refmagnitude = totalx / self.bins

        # For each bin direction, calculate the semi-circular statistics
        maxvalue = 0  # Maximum normalised value
        maxbin = 0    # Bin with maximum normalised value
        for j in range(self.bins):
            sumx = 0  # sum of x values
            # Set the mean compass angle for sector j
            binangle = (j + 0.5) * sectorwidth + self.offsetangle
            for i in range(self.bins):
                # Get the accumulated line length for the sector
                linelength = self.result[i][element]
                # Set the mean compass angle for sector i
                angle = (i + 0.5) * sectorwidth + self.offsetangle
                anglediff = angle - binangle
                # Wrap around?
                if (anglediff > 90):
                    anglediff = 180 - anglediff
                elif (anglediff < -90):
                    anglediff = 180 + anglediff
                addx = (linelength * math.cos(math.radians(anglediff)))
                sumx = sumx + addx
            if sumx > maxvalue:
                maxvalue = sumx
                maxbin = j
        # Normalise to [0..1]
        if totalsum == 0:
            return (None, None)    # ???
        else:
            normalmax = maxvalue / totalsum
        # Adjust the according to the lowest achievable value
        if refmagnitude == 1:
            adjustedmax = normalmax    # ???
        else:
            adjustedmax = (normalmax - refmagnitude) / (1 - refmagnitude)
        return (maxbin, adjustedmax)

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
            circle.setPen(QPen(self.ringcolour))
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
    #   self.layerlistchanging = False

    def inputLayerChanged(self):
        layerindex = self.InputLayer.currentIndex()
        layerId = self.InputLayer.itemData(layerindex)
        inputlayer = QgsMapLayerRegistry.instance().mapLayer(layerId)
        if inputlayer is None:
            self.showInfo(self.tr('No input layer defined'))
            return
        if inputlayer.featureCount() == 0:
            self.showInfo(self.tr('No features in input layer'))
            return
        # If there are no selected features, the "selected features
        # only" checkbox should be unchecked
        if inputlayer.selectedFeatureCount() == 0:
            self.selectedFeaturesCheckBox.setChecked(False)
        else:
            self.selectedFeaturesCheckBox.setChecked(True)

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

    def tilingToggled(self, checked):
        if checked:
            self.meanDirectionRB.setEnabled(True)
        else:
            self.meanDirectionRB.setEnabled(False)
            self.histogramRB.setChecked(True)


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

    # Save to SVG using self.histscene
    def saveAsSVG(self, location=None):
        savename = location
        #if location is None:
        if not isinstance(savename, basestring):
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
            outDir = os.path.dirname(outFilePath)
            settings.setValue(key, outDir)
        return outFilePath
