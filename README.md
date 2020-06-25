# gribdownload

Python script to download QPE, QPF, and HRRR GRIB files from NOAA websites.

gribdownload was written in Python 2.7 to allow integration into CWMS/RTS CAVI.

## USACE Branch

usace/cavi

The included shebang (#!) is set to a USACE installed ArcGIS version.
The user should review their available Python installation(s) to determine the
best way for them to run this script.  For USACE users, the shebang (#!) can point
to jython.exe in the CWMS CAVI installation using the FQPN.

## Help Output

```usage: GribDownload.py [-h] [-w /path/to/working/directory] -o
                       /path/to/output/directory [--force]
                       [-l /path/to/log/file.log] [-n {0,1,2,3,4,5}]
                       {qpe,qpf,hrrr} ...

Download Quantitative Precipitation Estimates (QPE), Quantitative
Precipitation Forecasts (QPF), or High-Resolution Rapid Refresh (HRRR)
precipitation Gridded Binary (GRIB2) files.  These products are provided by
NOAA on public websites.  QPE and QPF sources only provide a select number
of observed (QPE) and forecasted (QPF) products.  HRRR files are downloaded
from nomads.ncep.noaa.gov Grib Filter application extracting surface level
and the variable PRATE (precip rate).

optional arguments:
  -h, --help            show this help message and exit
  -w /path/to/working/directory, --working-dir /path/to/working/directory
                        Set the script's working directory.
  -o /path/to/output/directory, --output-dir /path/to/output/directory
                        Path to the ouptut directory. User expansion and
                        environment variables acceptable.
  --force               Force the downloading of files even if on the local
                        system
  -l /path/to/log/file.log, --log-file /path/to/log/file.log
                        Path to the log file. User expansion and environment
                        variables acceptable.
  -n {0,1,2,3,4,5}, --log-level {0,1,2,3,4,5}
                        Set numeric logger level. Levels 0-5 (NOTSET -
                        CRITICAL) [default = 2]

Quantitative Precipitation Estimates and Forecasts:
  Defining the product type and related parameters

  {qpe,qpf,hrrr}        GribDownload.py [qpe]|[qpf]|[hrrr] --help to get help
                        for these commands

qpe, qpf, and hrrr are options that should be listed last.  Each
product has additional options that can be defined.

qpe [-p, --product {GaugeCorr*, GaugeOnly, RadarOnly}] [-i, --interval {1*, 3, 6, 12, 24, 48, 72}]
qpf [-i, --interval {6*,24,48,120}] [-c, --cycle hour (default=current UTC hour)]
hrrr [-c, --cycle hour (default=current UTC hour)] [-f, --fct-hour range(s)(default=0-18)]
    [--left-lon 0] [--right-lon 360] [--top-lat 90] [--bottom-lat -90], where range is 
    the list of values for the HRRR forecast hours.  The range can include comma delimated
    numbers and ranges.  Example 1,2,3,9-20 produces a list of forecast hours
    1,2,3,9,10,11,12,13,14,15,16,17,18,19,20.

    *indicates the default value.```
