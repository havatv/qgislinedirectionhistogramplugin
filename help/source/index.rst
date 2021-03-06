.. linedirectionhistogram documentation master file, created by
   sphinx-quickstart on Sun Feb 12 17:11:03 2015.

*******************************************
The QGIS Line Direction Histogram Plugin
*******************************************

.. toctree::
   :maxdepth: 2


.. |rose| image:: illustrations/rosediagram.png
   :width: 200
   :align: middle

|rose|
   
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

  +---------------+----------------+
  | Fewer bins    | More bins      |
  +===============+================+
  | |rose|        | |rose90_1|     |
  +---------------+----------------+

.. |rose90_1| image:: illustrations/rose90_1.png
   :width: 200
   :align: middle

- All the direction bin sectors will have the same size (same number
  of degrees covered).  This type of angle histogram is also called
  a "rose diagram" or "rose plot".

- An angle offset (positive or negative - clockwise or counter
  clockwise) for the direction bins can be specified.

- The positions of the direction bins are shown graphically.

  +------------------------------------------+
  | Direction bins illustration and options  |
  +==========================================+
  | |specbins|                               |
  +------------------------------------------+

.. |specbins| image:: illustrations/specify_bins.png
   :align: middle

- The user can choose if the histograms shall be "orientation"
  neutral (0-180 degrees instead of 0-360 degrees).

  +----------------------+---------------------------------------------------------+
  | Orientation neutral  | Not orientation neutral (with twice the number of bins) |
  +======================+=========================================================+
  | |rose|               | |rose36_5_360|                                          |
  +----------------------+---------------------------------------------------------+

.. |rose36_5_360| image:: illustrations/rose36_5_360.png
   :width: 200
   :align: middle

- A direction histogram (or rose diagram) is displayed, showing the
  distribution of the directions according to the chosen bins.
  
- The histogram can be saved to a CSV file.

- The histogram can be saved as PDF (100 mm by 100 mm) and SVG
  (200 by 200). -- added in version 1.3.

- The histogram can be copied to the clipboard. -- added in version
  1.4.
  
- If the plugin window is resized, the direction histogram is also
  resized.

Tiling
------
Added in version 2.0.

There is an option available for producing at point layer styled
using rose diagrams (using SVG files) according to a tiling
specified using a polygon layer.

  .. |tiling| image:: illustrations/tiling.png
   :align: middle

|tiling|

- The polygon layer can be chosen.

- The location for storing the SVG files can be specified.

- The SVG files are not deleted - the default location is the
  system temporary file directory.

- CRS transformations are not performed, so the tiling layer
  should have the same CRS as the input layer.
  A warning is given if the CRSs are different.


All the other options are also respected when generating the
rose diagrams for the tiles.

Due to a QGIS issue with SVG file caching (#13565: "modifying a
svg already cached doesn't invalidate the cache, renders as
version initially loaded during a session"), the SVG files have
to be stored using unique file names.
This produces a lot of SVG files that are not deleted by the plugin.

Direction mean
--------------
Added in version 2.4.

An indication of the direction mean (direction and strength) can be
added to the rose diagrams.

The user can choose the base colour for the direction mean
indication (added in version 3.1).

  .. |dirmeannon| image:: illustrations/rosedirmeannonneutral.png
   :width: 200
   :align: middle

  .. |dirmeanlow| image:: illustrations/rosedirmeanneutrallow.png
   :width: 200
   :align: middle

  .. |dirmeanhigh| image:: illustrations/rosedirmeanneutralhigh.png
   :width: 200
   :align: middle

  .. |dirmean| image:: illustrations/rosedirmeanneutral.png
   :width: 200
   :align: middle

+-----------------+---------------+---------------+---------------+
| Direction mean                                                  |
+-----------------+---------------+---------------+---------------+
| Not or. neutral | Orientation neutral                           |
+-----------------+---------------+---------------+---------------+
|                 | medium        | low           | high          |
+=================+===============+===============+===============+
| |dirmeannon|    | |dirmean|     | |dirmeanlow|  | |dirmeanhigh| |
+-----------------+---------------+---------------+---------------+

Non-orientation neutral
  The direction mean is visualised by a "vector" in the rose diagram,
  with length corresponding to the strength of the trend.

Direction neutral
  The direction mean is visualised by filling the bin with colour
  according to the strength of the trend (white for direction neutral,
  full colour for maximum strength).


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
  (but if no features are selected, all features will be used).
  This is the default if the layer has selected features.

- The user can specify the number of direction bins (the default
  is 8).

- The user can specify an angle offset (clockwise from north)
  for the direction bins (the default i 0).

- The user can choose to ignore the "orientation" of the lines.
  In that case, two lines with opposite  directions will end up in
  the same direction bin (this is the default).

- The user can specify an output CSV file for the (over all)
  histogram.

- The user can specify if line segment length shall be used for
  weighting the bins (this is the default).

- The user can choose to use the logarithm to define the radius of
  the sectors.
  The default is not to use the logarithm.

- The user can choose to have the area of a sector of the
  histogram be proportional to the accumulated amount for
  that sector.
  The default is that the length / radius of a sector is
  proportional to the accumulated amount (histogram like
  behaviour).

- The user can choose to produce a point layer styled with rose
  diagrams according to a tiling by a selected polygon layer.
  For this option, it is also possible to specify the location
  for storing the generated SVGs (that are used for styling the
  rose diagram layer.

- The user can specify that the direction mean shall be included in
  the rose diagram(s).

  For the orientated option, a line that shows the average direction
  vector is added.

  For the non-orientated option, the sector that has the highest
  mean direction value is given a background colour, with the amount
  of colour indicating the strength of direction trend (white for
  neutral, 100% colour if all line segments have a direction that
  belongs to this sector).
  For the non-oriented option, the sector bins are transparent.

- The user can specify the base colour for the direction mean.


Implementation
================

The calculations of the histogram is performed in a separate thread.
Each line geometry is traversed from start to end.
For each segment of the line, the angle and length are calculated.
The angle is used to determine which bin the segment belongs to, and
the length is added to the accumulated length for the bin.

Polygons are split into its rings (the outer ring and zero or more
inner rings), and the line geometries of the rings are used for the
calculations.


Mean direction
-----------------

.. |distancemean| image:: illustrations/dist_mean_calc.png
   :align: middle

.. |normalised| image:: illustrations/normalised_value_calc.png
   :align: middle

Non-orientation neutral
  The normalised mean direction vector
  (**dist_mean**) is calculated using vector summation from the bins
  (sectors), not from the original lines.
  Each sector is represented by a vector
  (**sector**) with length equal to the total length
  of the line segments in the sector.
  The middle of the bin's sector is used as the angle for the sector
  vector.
  The result vector is normalised by dividing by the sum of the bin /
  sector line lengths.

  |distancemean|

  This means that the mean direction is very sensitive to the number
  of bins - the more bins, the more precise will the mean direction
  be.

Orientation neutral
  The mean direction is found by calculating the magnitude of the
  "direction trend" for each of the bins.

  The "direction trend" for a bin, B, is calculated using the values
  for all the bins within 90 degrees offset from the angle of B.
  For each bin (including B), the angle between that bin and B is
  calculated (using the angles of the middle of the bin sectors), and
  the cosine of that angle is multiplied by the bin value.

  The "direction trend" of B is the sum of these values.
  The bin with the largest value is taken to represent the direction
  mean.

  The value is then normalised to a [0..1] scale using the the sum
  of the bin values (*total_sum*) as the maximum value, and the value
  that had been obtained (*even_dist_value*) if the distribution of
  line segment lengths among the bins had been even, as the minimum
  value.

  |normalised|


Versions
===============
The current version is 3.1

- 3.1
    - Fixed issue with geometry conversion for tiling (#27)
    - Added possibility to specify the colour for the direction trend
      (#28)
- 3.0.1
    - Fixed issue with plugin icon not showing in the QGIS user
      interface (#25)
    - Fixed issue with help not showing (#26)
- 3.0.0
    - Support for QGIS 3
- 2.5.1
    - SVG export fixed (#21)
- 2.5
    - User interface modified to allow use on smaller screens (#20)
- 2.4
    - Added directional mean indicators to the rose diagrams (#14)
    - User interface change from toolbox to tab for options
- 2.3
    - Added the logarithm option (#17)
    - Fixed CSV output (#16)
- 2.2
    - Fixed angle offset issue (#15) and added some circular
      statistics output (#14)
- 2.1
    - Fixed issue #13 (problems with multipart geometries)
- 2.0
    - Added option to generate a point layer with rose diagrams based
      on tiles provided through a polygon layer (#10, #11)
    - Set the default state for "selected features only" based on the
      presence of a selection (#12)
- 1.6
    - Fixed progress bar issue (#9)
- 1.5
    - Added help button
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

Citation
==========

Would you like to cite / reference this plugin?

Tveite, H. (2015). The QGIS Line Direction Histogram Plugin.
http://plugins.qgis.org/plugins/LineDirectionHistogram/.

Bibtex:

.. code-block:: latex

  @misc{tveitesde,
    author =   {Håvard Tveite},
    title =    {The {QGIS} Line Direction Histogram Plugin},
    howpublished = {\url{http://plugins.qgis.org/plugins/LineDirectionHistogram/}},
    year = {2015--2018}
  }


.. _LineDirectionHistogram code repository: https://github.com/havatv/qgislinedirectionhistogramplugin.git
.. _LineDirectionHistogram Plugin: https://plugins.qgis.org/plugins/LineDirectionHistogram/
.. _LineDirectionHistogram issues: https://github.com/havatv/qgislinedirectionhistogramplugin/issues
.. |N2| replace:: N\ :sup:`2`
