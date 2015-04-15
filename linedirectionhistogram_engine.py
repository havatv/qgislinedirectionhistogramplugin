# -*- coding: utf-8 -*-
from math import sqrt
from PyQt4 import QtCore
from PyQt4.QtCore import QCoreApplication
from qgis.core import QGis
from qgis.core import QgsVectorLayer

# Angles:
# Real world angles are measured clockwise from the 12 o'clock
# position (north)
# QGIS azimuth angles: clockwise in degree, starting from north
# QT angles are measured counter clockwise from the 3 o'clock
# position


class Worker(QtCore.QObject):
    '''The worker that does the heavy lifting.
    The number and length of the line segments of the inputlayer
    line or polygon vector layer is calculated for each angle bin.
    A vector of bins is returned.  Each bin contains the total
    length and the number of line segments in the bin.
    '''
    # Define the signals used to communicate
    progress = QtCore.pyqtSignal(float)  # For reporting progress
    status = QtCore.pyqtSignal(str)
    error = QtCore.pyqtSignal(str)
    # Signal for sending over the result:
    finished = QtCore.pyqtSignal(bool, object)

    def __init__(self, inputvectorlayer, bins, directionneutral,
                                  offsetangle, selectedfeaturesonly):
        """Initialise.

        Arguments:
        inputvectorlayer --     (QgsVectorLayer) The base vector
                                 layer for the join
        bins --                 (int) bins for end point matching
        directionneutral --     (boolean) should lines in oposite
                                 directions be handled as having the
                                 same directionneutral
        offsetangle --          (float) Start the bins at a different
                                 angle
        selectedfeaturesonly -- (boolean) should only selected
                                 features be considered
        """

        QtCore.QObject.__init__(self)  # Essential!
        # Creating instance variables from parameters
        self.inputvectorlayer = inputvectorlayer
        self.bins = int(bins)
        self.directionneutral = directionneutral
        self.offsetangle = offsetangle
        self.selectedfeaturesonly = selectedfeaturesonly
        self.binsize = 360.0 / bins
        if self.directionneutral:
            self.binsize = 180.0 / bins

        # Creating instance variables for the progress bar ++
        # Number of elements that have been processed - updated by
        # calculate_progress
        self.processed = 0
        # Current percentage of progress - updated by
        # calculate_progress
        self.percentage = 0
        # Flag set by kill(), checked in the loop
        self.abort = False
        # Number of features in the input layer - used by
        # calculate_progress
        self.feature_count = self.inputvectorlayer.featureCount()
        # The number of elements that is needed to increment the
        # progressbar - set early in run()
        self.increment = self.feature_count // 1000

    def run(self):
        #self.status.emit('Started!')
        try:
            inputlayer = self.inputvectorlayer
            if inputlayer is None:
                self.error.emit(self.tr('No input layer defined'))
                self.finished.emit(False, None)
                return
            # Check the geometry type
            geometryType = self.inputvectorlayer.geometryType()
            if not (geometryType == QGis.Line or
                    geometryType == QGis.Polygon):
                self.error.emit('Only line and polygon layers are supported!')
                self.finished.emit(False, None)
                return
            self.processed = 0
            self.percentage = 0
            self.feature_count = inputlayer.featureCount()
            self.increment = self.feature_count // 1000
            # Initialise the bins
            statistics = []
            for i in range(self.bins):
                statistics.append([0.0, 0])
            # Get the features (iterator)
            if (inputlayer.selectedFeatureCount() > 0 and
                                          self.selectedfeaturesonly):
                features = inputlayer.selectedFeaturesIterator()
            else:
                features = inputlayer.getFeatures()
            for feat in features:
                # Allow user abort
                if self.abort is True:
                    break
                # We use a vector of polygon geometries to be able to
                # handle MultiPolygons
                inputpolygons = []
                # We use a vector of line geometries to be able to
                # handle MultiPolylines and Polygons
                inputlines = []
                if geometryType == QGis.Line:
                    if feat.geometry().isMultipart():
                        multiline = feat.geometry().asMultiPolyline()
                        for geomline in multiline:
                            inputlines.append(geomline)
                    else:
                        inputline = feat.geometry().asPolyline()
                        inputlines.append(inputline)
                elif geometryType == QGis.Polygon:
                    if feat.geometry().isMultipart():
                        multipoly = feat.geometry().asMultiPolygon()
                        for geompoly in multipoly:
                            inputpolygons.append(geompoly)
                    else:
                        inputpolygon = feat.geometry().asPolygon()
                        inputpolygons.append(inputpolygon)
                    # Add the polygon rings
                    for polygon in inputpolygons:
                        for ring in polygon:
                            inputlines.append(ring)
                for inputlinegeom in inputlines:
                    # Skip degenerate lines
                    if inputlinegeom is None or len(inputlinegeom) < 2:
                        continue
                    # Go through all the segments of this line
                    nextpoint = inputlinegeom[0]
                    for i in range(len(inputlinegeom) - 1):
                        thispoint = nextpoint
                        nextpoint = inputlinegeom[i + 1]
                        linelength = sqrt(thispoint.sqrDist(nextpoint))
                        # Find the angle, and adjust for angle offset
                        lineangle = (thispoint.azimuth(nextpoint)
                                     - self.offsetangle)
                        # Find the bin
                        fittingbin = (int(((lineangle + 180)) / self.binsize)
                                      % self.bins)
                        if self.directionneutral:
                            if lineangle < 0.0:
                                lineangle = 180.0 + lineangle
                            # Find the bin
                            fittingbin = (int((lineangle) / self.binsize)
                                          % self.bins)
                        # Have to handle special case to keep index in range
                        if fittingbin == self.bins:
                            fittingbin = 0
                        # Add to the length of the bin
                        statistics[fittingbin][0] = (statistics[fittingbin][0]
                                                  + linelength)
                        # Add to the number of line segments in the bin
                        statistics[fittingbin][1] = (statistics[fittingbin][1]
                                                  + 1)
                self.calculate_progress()
        except:
            import traceback
            self.error.emit(traceback.format_exc())
            self.finished.emit(False, None)
        else:
            if self.abort:
                self.finished.emit(False, None)
            else:
                self.finished.emit(True, statistics)

    def calculate_progress(self):
        '''Update progress and emit a signal with the percentage'''
        self.processed = self.processed + 1
        # update the progress bar at certain increments
        if self.increment == 0 or self.processed % self.increment == 0:
            percentage_new = (self.processed * 100) / self.feature_count
            if percentage_new > self.percentage:
                self.percentage = percentage_new
                self.progress.emit(self.percentage)

    def kill(self):
        '''Kill the thread by setting the abort flag'''
        self.abort = True

    def tr(self, message):
        """Get the translation for a string using Qt translation API.

        We implement this ourselves since we do not inherit QObject.

        :param message: String for translation.
        :type message: str, QString

        :returns: Translated version of message.
        :rtype: QString
        """
        # noinspection PyTypeChecker,PyArgumentList,PyCallByClass
        return QCoreApplication.translate('LineDirectionEngine', message)
