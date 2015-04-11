.. linedirectionhistogram documentation master file, created by
   sphinx-quickstart on Sun Feb 12 17:11:03 2015.
   You can adapt this file completely to your liking, but it should at least
   contain the root `toctree` directive.

*******************************************
The QGIS Line Direction Histogram Plugin
*******************************************

Contents:

.. toctree::
   :maxdepth: 2

   
Functionality
=================

- The QGIS Line Direction Histogram Plugin can be used to investigate
  the distribution of the directions of line segments of a line or
  polygon vector dataset. 

- The accumulated lengths of the line segments for each direction bin
  determines the shape of the histogram.

- Line and Polygon vector layers are supported.

- The number of direction bins for the histogram can be specified.

- All the direction bin sectors will have the same size (same number
  of degrees covered).

- An angle offset (positive or negative - clockwise or counter
  clockwise) for the direction bins can be specified.

- The positions of the direction bins are shown graphically.

- A direction histogram is displayed, showing the distribution of the
  directions according to the chosen bins.
  
- The histogram can be saved to a CSV file.


The displayed histogram
========================

The diplayed histogram is normalised, so that the maximum value of
the direction bins will result in a sector with a maximum length, and
the lengths of the sectors of the rest of the bins are scaled
proportionally.

The saved histogram
====================

The saved histogram is a CSV file with two columns.
The first column contains the start angle of the direction bin, while
the second column contains the accumulated lengths of the line
segments that fall within that bin.
"." is used as decimal separator in the CSV file.


Options
=============

- The user can specify the number of direction bins.

- The user can specify an angle offset for the direction bins.

- The user can choose to ignore the "orientation" of the lines.  In
  that case, two lines with opposite  directions will end up in the
  same direction bin.

- The user can specify an output CSV file for the histogram.


Implementation
================

The calculations of the histogram is performed in a separate thread.
Each line geometry is traversed from start to end.
For each segment of the line, the angle and length are calculated.
The angle is used to determine which bin the segment falls into, and
the length is added to the accumulated length for the bin.

Polygons are split into its rings, and the line geometry of each ring
is used for the calculations.


Versions
===============
The current version is 1.0.0

- 1.0.0: First official version.


Links
=======

`linedirectionhistogram Plugin`_

`linedirectionhistogram code repository`_

`linedirectionhistogram issues`_


.. _linedirectionhistogram code repository: https://github.com/havatv/qgislinedirectionhistogramplugin.git
.. _linedirectionhistogram Plugin: https://plugins.qgis.org/plugins/LineDirectionHistogram/
.. _linedirectionhistogram issues: https://github.com/havatv/qgislinedirectionhistogramplugin/issues
.. |N2| replace:: N\ :sup:`2`
