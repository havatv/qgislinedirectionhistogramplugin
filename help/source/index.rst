.. linedirectionhistogram documentation master file, created by
   sphinx-quickstart on Sun Feb 12 17:11:03 2015.
   You can adapt this file completely to your liking, but it should at least
   contain the root `toctree` directive.

*******************************************
The QGIS Line Direction Histogram Plugin
*******************************************

.. toctree::
   :maxdepth: 2

   
Functionality
=================

- The QGIS Line Direction Histogram Plugin creates a rose diagram
  that can be used to investigate the distribution of the directions
  of line segments of a line or polygon vector dataset.

- The accumulated lengths of the line segments for each direction bin
  determines the shape of the histogram.
  Alternatively, the number of segments can be used (no weighting on
  line segment length).

- Line and Polygon vector layers are supported, including
  multigeometries.

- Feature selections are supported.

- The number of direction bins for the histogram can be specified.

- All the direction bin sectors will have the same size (same number
  of degrees covered).  This type of angle histogram is also called
  a "rose diagram" or "rose plot".

- An angle offset (positive or negative - clockwise or counter
  clockwise) for the direction bins can be specified.

- The positions of the direction bins are shown graphically.

- A direction histogram (or rose diagram) is displayed, showing the
  distribution of the directions according to the chosen bins.
  
- The histogram can be saved to a CSV file.

- The histogram can be saved as PDF (100 mm by 100 mm) and SVG
  (200 by 200). -- added in version 1.3

- The histogram can be copied to the clipboard. -- added in version
  1.4
  
- If the plugin window is resized, the direction histogram is also
  resized.

The displayed histogram
========================

The displayed histogram is normalised, so that the maximum value of
the direction bins will result in a sector with a maximum length, and
the lengths of the sectors of the rest of the bins are scaled
proportionally.


The saved histogram (CSV)
=========================

The saved histogram is a CSV file with four columns:

- The first column ("StartAngle") contains the start angle of the
  direction bin.
- The second column ("EndAngle") contains the end angle of the
  direction bin.
- The third column ("Length") contains the accumulated lengths of
  the line segments that fall within the bin.
- The fourth column ("Number") contains the number of line segments
  that fall within the bin.

"." is used as the decimal separator in the CSV file.

The CSV file is accompanied by a CSVT file that describes the
data types of the CSV file columns.


Options
=============

- The user can specify if only selected features are to be used
  (but if no features are selected, all features will be used)

- The user can specify the number of direction bins.

- The user can specify an angle offset for the direction bins.

- The user can choose to ignore the "orientation" of the lines.  In
  that case, two lines with opposite  directions will end up in the
  same direction bin.

- The user can specify an output CSV file for the histogram.

- The user can specify if line segment length shall be used for
  weighting the bins (this is the default).

- The user can choose to have the area of a sector of the
  histogram be proportional to the accumulated amount for
  that sector.
  The default is that the length / radius of a sector is
  proportional to the accumulated amount (histogram like
  behaviour).

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
The current version is 1.4.

- 1.4
    - Copy to clipboard button added (#8)

- 1.3
    - PDF and SVG export added
    - Area-proportional sectors option introduced
- 1.2
    - Fixed issue #1 (on update of min/max for angle offset)
    - Fixed issue #2 (divide by zero when no features in layer)
    - Fixed issue #3 (effect of "no weighting" checkbox)
- 1.1:
    - Selected features option introduced
    - Unweighted option introduced
    - Multigeometry support
    - CSV file header row added
    - CSV angle offset bug fixed
    - User interface fixes and updates

- 1.0: First official version.


Links
=======

`LineDirectionHistogram Plugin`_

`LineDirectionHistogram code repository`_

`LineDirectionHistogram issues`_


.. _LineDirectionHistogram code repository: https://github.com/havatv/qgislinedirectionhistogramplugin.git
.. _LineDirectionHistogram Plugin: https://plugins.qgis.org/plugins/LineDirectionHistogram/
.. _LineDirectionHistogram issues: https://github.com/havatv/qgislinedirectionhistogramplugin/issues
.. |N2| replace:: N\ :sup:`2`
