#! python

"""Download NOAA Grib2 files to the user's PC
"""

# metadata
__author__="Jeff Gregory"
__credits__ = ["Jeff Gregory"]
#__version__ = '{mayor}.{minor}.{rel}'
__maintainer__ = "Jeff Gregory"
__email__ = "jeffrey.s.gregory@usace.army.mil"
__status__ = "Dev"

# Jython Imports
import os
import re
import sys
import urllib
import urlparse
import datetime
import logging
import logging.handlers
import argparse
import Queue
import threading


# Set Constants
_path = os.path.abspath(os.path.dirname(__file__))
_name = os.path.basename(__file__).split('.')[0]
max_thread = 4      # low thread count seems to keep out SSL errors

mrms_base = 'https://mrms.ncep.noaa.gov/data/2D/{PRODUCT}_QPE_{HOUR}H/'

qpf_base = 'https://ftp.wpc.ncep.noaa.gov/2p5km_qpf/'

hrrr_file = 'hrrr.t{CYCLE:02}z.wrfsfcf{HOUR:02}.grib2'
hrrr_base = 'https://nomads.ncep.noaa.gov/cgi-bin/filter_hrrr_2d.pl?file={FILE}&lev_surface=on&var_PRATE=on&leftlon={LLON}&rightlon={RLON}&toplat={TLAT}&bottomlat={BLAT}&dir=%2Fhrrr.{DATE}%2Fconus'

def local_logger(log_file=None, log_level=2):
    ''' Define a local logger for the main (global) space can get and use it
    CRITICAL    50
    ERROR       40
    WARNING     30
    INFO        20
    DEBUG       10
    NOTSET      0
    '''
    log_level *= 10
    # Start logging
    logger = logging.getLogger(_name)
    logger.setLevel(log_level)

    formatter = logging.Formatter('%(asctime)s.%(msecs)03d - ' +
        '%(name)s:%(funcName)15s - %(levelname)-5s - %(message)s',
        '%Y-%m-%dT%H:%M:%S')
    # Console logger
    ch = logging.StreamHandler()
    #ch.setLevel(logging.NOTSET)
    ch.setFormatter(formatter)
    logger.addHandler(ch)
    logger.debug('Logging set to a StreamHandler (Console)')

    # File logger
    if log_file:
        # try to get the log file's directory as described by the user
        try:
            log_dir = os.path.dirname(log_file)
        except TypeError, ex:
            logger.error(ex)
        except AttributeError, ex:
            logger.error(ex)
        if log_dir:
            # try to get a logging handler
            try:
                fh = logging.handlers.RotatingFileHandler(log_file, maxBytes=5000000,
                    backupCount=1)
                fh.setFormatter(formatter)
                #fh.setLevel(logging.NOTSET)
                logger.addHandler(fh)
                logger.info('Logging file set to: {}'.format(log_file))
            except IOError, ex:
                logger.warning(ex)
                logger.warning('Rotating File Handler not created.')
    
    return logger

class PathExpandAction(argparse.Action):
    ''' Argument parser action used to "expanduser" and "expandvars"
    
    Inheritance of argparse.Action using super() method to extend the base class
    '''
    def __init__(self, option_strings, dest, nargs=None, **kwargs):
        if nargs is not None:
            raise Exception('"nargs" not allowed')
        super(PathExpandAction, self).__init__(option_strings, dest, **kwargs)
    def __call__(self, parser, namespace, values, option_string=None):
        if values == '-':
            setattr(namespace, self.dest, None)
        else:
            values = os.path.realpath(
                os.path.expandvars(
                    os.path.expanduser(values)))
            setattr(namespace, self.dest, values)

def check_cycle(qpf, cycle):
    ''' Take the input value and check against the available forecast cycles
    as an hour.  The return will be a tuple of QPF6 and QPFx
    '''
    if qpf == 6:
        cycles = [18,12,6,0]
    else:
        cycles = [12,0]
    for x in cycles:
        if cycle >= x:
            logger.info('Returning {} as the forcast cycle hour'.format(x))
            return x

def set_working(s):
    ''' Change the working directory using user input option
    '''
    try:
        os.chdir(s)
        return os.getcwd()
    except OSError, ex:
        raise Exception(ex)
        sys.exit(1)

def set_forecast_hours(r):
    ''' Parse the range (r) returning a list of hours for the HRRR forecast hours
    '''
    _list = list()
    vals = r.split(',')
    for v in vals:
        if '-' in v:
            start, stop = v.split('-')
            rng = range(int(start),int(stop) + 1)
            _list.extend(rng)
        else:
            _list.extend(v)
    # get everything as an integer
    _list = [int(x) for x in _list]
    return _list

def local_argparse():
    ''' Define configuration parser for the main (global)
    '''
    desc = '''Download Quantitative Precipitation Estimates (QPE), Quantitative
Precipitation Forecasts (QPF), or High-Resolution Rapid Refresh (HRRR)
precipitation Gridded Binary (GRIB2) files.  These products are provided by
NOAA on public websites.  QPE and QPF sources only provide a select number
of observed (QPE) and forecasted (QPF) products.  HRRR files are downloaded
from nomads.ncep.noaa.gov Grib Filter application extracting surface level
and the variable PRATE (precip rate).'''
    epi = '''qpe, qpf, and hrrr are options that should be listed last.  Each
product has additional options that can be defined.

qpe [-p, --product {GaugeCorr*, GaugeOnly, RadarOnly}] [-i, --interval {1*, 3, 6, 12, 24, 48, 72}]
qpf [-i, --interval {6*,24,48,120}] [-c, --cycle hour (default=current UTC hour)]
hrrr [-c, --cycle hour (default=current UTC hour)] [-f, --fct-hour range(s)(default=0-18)]
    [--left-lon 0] [--right-lon 360] [--top-lat 90] [--bottom-lat -90], where range is 
    the list of values for the HRRR forecast hours.  The range can include comma delimated
    numbers and ranges.  Example 1,2,3,9-20 produces a list of forecast hours
    1,2,3,9,10,11,12,13,14,15,16,17,18,19,20.
    
    *indicates the default value.
'''
    
    parser = argparse.ArgumentParser(
        formatter_class=argparse.RawDescriptionHelpFormatter,
        description=desc,
        epilog=epi)
    subparser = parser.add_subparsers(
        title='Quantitative Precipitation Estimates and Forecasts',
        description="Defining the product type and related parameters",
        help='GribDownload.py [qpe]|[qpf]|[hrrr] --help to get help for these commands',
        dest='subparser_name')

    # Quantitative Precipitation Estimates subparser
    parser_qpe = subparser.add_parser('qpe')
    parser_qpe.add_argument('-p', '--product', action='store', type=str,
        choices=['GaugeCorr', 'GaugeOnly', 'RadarOnly'], default='GaugeCorr',
        help="GaugeCorr, GaugeOnly, or RadarOnly; Default=%(default)s")
    parser_qpe.add_argument('-i', '--interval', action='store', type=int,
        choices=[1, 3, 6, 12, 24, 48, 72], default=1,
        help="Hour Interval; Default=%(default)s")

    # Quantitative Precipitation Forecast subparser
    parser_qpf = subparser.add_parser('qpf')
    parser_qpf.add_argument('-i', '--interval', action='store', type=int,
        choices=[6,24,48,120], default=6,
        help="Hour Interval; Default=%(default)s")
    parser_qpf.add_argument('-c', '--cycle', action='store', type=int,
        default=datetime.datetime.utcnow().strftime('%H'), metavar='h',
        help="Define the forecast cycle, where H is hour; Default to current UTC hour (e.g., %(default)s)")

    # Quantitative Precipitation Forecast subparser for HRRR
    parser_hrrr = subparser.add_parser('hrrr')
    parser_hrrr.add_argument('-c','--cycle', action='store', type=int,
        default=datetime.datetime.utcnow().strftime('%H'), metavar='H',
        help="Define the forecast cycle, where H is hour; Default to current UTC hour (e.g., %(default)s)",
        dest='cycle')
    parser_hrrr.add_argument('-f','--fct-hour', action='store',
        default='0-18', type=set_forecast_hours, metavar='1,2,5-9',
        help="List of hours (0-18); Default List = %(default)s",
        dest='fct_hour')
    parser_hrrr.add_argument('--left-lon', action='store', type=float,
        default=0, metavar='0',
        help="Define the left longitude; Use negative numbers for south and west; Default=%(default)s", dest='llon')
    parser_hrrr.add_argument('--right-lon', action='store', type=float,
        default=360, metavar='360',
        help="Define the right longitude; Use negative numbers for south and west; Default=%(default)s", dest='rlon')
    parser_hrrr.add_argument('--top-lat', action='store', type=float,
        default=90, metavar='90',
        help="Define the top latitude; Use negative numbers for south and west; Default=%(default)s", dest='tlat')
    parser_hrrr.add_argument('--bottom-lat', action='store', type=float,
        default=-90, metavar='-90',
        help="Define the bottom latitude; Use negative numbers for south and west; Default=%(default)s", dest='blat')

    # Set the working directory
    parser.add_argument('-w', '--working-dir', action='store', type=set_working,
        metavar='/path/to/working/directory',
        help="Set the script's working directory.")

    # Define output file
    parser.add_argument('-o', '--output-dir', required=True,
        action=PathExpandAction,metavar='/path/to/output/directory',
        help="Path to the ouptut directory.  User expansion and environment " +
        "variables acceptable.", dest='output_dir')

    # Force the download of files no matter if already on local
    parser.add_argument('--force', action='store_true',
        help="Force the downloading of files even if on the local system")

    # Define log file for logger
    parser.add_argument('-l', '--log-file',action=PathExpandAction,
        metavar='/path/to/log/file.log',
        help="Path to the log file.  User expansion and environment " +
        "variables acceptable.",dest='log_file')

    # Logger level
    parser.add_argument('-n', '--log-level',type=int, choices=range(6),
        default=2,
        help="Set numeric logger level.  Levels 0-5 (NOTSET - CRITICAL) " +
        "[default = %(default)s]",dest='log_level')
    
    return parser

def check_url(url):
    ''' Check the url and return the code if good else false.
        Looking for a 200 to be good.
    '''
    try:
        logger.info('Checking URL: {}'.format(url))
        if urllib.urlopen(url).getcode() == 200:
            return True
    except IOError, ex:
        logger.warning(ex)
        logger.warning('Returning "False"')
        return False

def match_files(localfiles, url, regex, force):
    ''' Compare files from QPE or QPF 6 hour website to those locally and return
    a list of files and the full URL for each file
    '''
    if not check_url(url):
        logger.warning('"{}" failed URL check.')
        logger.warning('Script Exiting!')
        sys.exit(1)
    try:
        open_html = urllib.urlopen(url)
        html = open_html.read()
        open_html.close()
    except IOError, ex:
        logger.error(ex)
        logger.error('Failed to open {}'.format(url))
        logger.error('Script Exiting!')
        sys.exit(1)
    matches = re.findall(regex, html, re.MULTILINE)
    if force:
        logger.info('Forcing download of files even if we have them.')
        files = matches
    else:
        files = list(set(matches) - set(localfiles))
    logger.info('Captured {} files from website'.format(len(matches)))
    logger.info('Need to get {} files for local'.format(len(files)))
    files.sort()
    urls = [urlparse.urljoin(baseurl, file) for file in files]
    return files, urls


def download(q, outdir, index):
    ''' Method that runs as seperate threads
    
    While the queue has something, the thread will work on that item and then
    clear it when that item is done (queue.task_done).  The thread will try to
    open the url, read the file, and then write to the output directory.
    '''
    while not q.empty():
        qval = q.get()
        url, fname = qval
#        url = urlparse.urljoin(baseurl, file)
        outputfile = os.path.join(outdir, fname)
        try:
            logger.debug('Thread {} - try retrieve: {}'.format(index, url))
            logger.debug('Thread {} - try save to: {}'.format(index, outputfile))
            fn, h = urllib.urlretrieve(url, outputfile)
            # Files that are not available will raise the KeyError exception
            # when trying to log the 'Content-Disposition'
            if fname.startswith('hrrr'):
                logger.info(h['Content-Disposition'])
            logger.info('Thread {} - Download saved to: {}'.format(index, fn))
        except IOError, ex:
            logger.warning(ex)
        except KeyError:
            logger.warning('Forecast cycle not avaliable for {}.'.format(fname))
            logger.debug('Removing downloaded file attempt.')
            os.remove(fn)
        finally:
            q.task_done()


''' **************** The main part of the script **************** '''
''' Get the arguments parsed, set the logger, and show the logging level
'''
arg_parser = local_argparse()
args = arg_parser.parse_args()

if not os.path.isdir(args.working_dir):
    logger.warning('No ouput directory assigned!')
    logger.warning('Script Exiting!')
    sys.exit(1)

logger = local_logger(log_file=args.log_file, log_level=args.log_level)
args_dict = vars(args)

''' Adjust the observed UTC time to the appropriate cycle hour '''
if args.subparser_name == 'qpf':
    args.cycle = check_cycle(args.interval, args.cycle)
    logger.debug('Setting QPF cycle based on input cycle: {}'.format(args.cycle))

for arg, val in args_dict.iteritems():
    logger.debug('ArgParser: {}={}'.format(arg, val))

''' Check the output directory exists and get the list of files within that
directory to match later what is online
'''
if not os.path.isdir(args.output_dir):
    logger.warning('"{}" not a directory'.format(
        args.output_dir))
    logger.warning('Script Exiting!')
    sys.exit(1)

local_files = os.listdir(args.output_dir)
logger.debug('Local Files:')
[logger.debug('\t{}'.format(file)) for file in local_files]

''' Build the URL based on user's options and check that it is good.  If it
is good, then read the URL parsing the available files to download and
compare that to the list of files on the user's system
'''

if args.subparser_name == 'qpe':
    baseurl = mrms_base.format(PRODUCT=args.product,
        HOUR='{:02}'.format(args.interval))
    regex = ur'>(MRMS\w*\.\d*_\d*-\d*\.grib2\.gz)<'
    files, urls = match_files(local_files, baseurl, regex, args.force)
    logger.debug('QPE files and URLs:')
    [logger.debug('\t{}'.format(f)) for f in files]
    [logger.debug('\t{}'.format(u)) for u in urls]
elif args.subparser_name == 'qpf':
    dy = datetime.datetime.utcnow().strftime('%d')
    baseurl = qpf_base
    regex = ur'>(p{:02}m_......{}{}f\d\d\d\.grb)<'.format(args.interval, dy,
        args.cycle)
    files, urls = match_files(local_files, baseurl, regex, args.force)
    logger.debug('QPF files and URLs:')
    [logger.debug(f) for f in files]
    [logger.debug(u) for u in urls]
elif args.subparser_name == 'hrrr':
    urls = list()
    matches = list()
    # Create possible files to compare with what is already local
    # Also, trim based on forcing or not
    logger.debug('Files to get')
    for h in args.fct_hour:
        file = hrrr_file.format(CYCLE=args.cycle, HOUR=h)
        matches.append(file)
        logger.debug('\t{}'.format(file))
    if args.force:
        logger.info('Forcing download of files even if we have them')
        files = matches
    else:
        files = list(set(matches) - set(local_files))
    # Create all the URLs based on the list of files
    for file in files:
        urls.append(hrrr_base.format(FILE=file, LLON=args.llon, RLON=args.rlon,
        TLAT=args.tlat, BLAT=args.blat,
        DATE=datetime.datetime.utcnow().strftime('%Y%m%d')))
    logger.debug('HRRR files and URLs:')
    [logger.debug('\t{}'.format(f)) for f in files]
    [logger.debug('\t{}'.format(u)) for u in urls]
    logger.info('Captured {} files from website'.format(len(matches)))
    logger.info('Need to get {} files for local'.format(len(files)))

''' Load a queue with the base url, filenames, and the output directory.
After loading the queue, initialize multiple threads with "download" method
to process all in the queue.
'''
que = Queue.Queue()
for i, url in enumerate(urls):
    que.put((url, files[i]))
    logger.debug('Load Queue:')
    logger.debug('\t{}'.format(url))
    logger.debug('\t{}'.format(files[i]))

for i in range(min(que.qsize(), max_thread)):
    t = threading.Thread(target=download, args=(que, args.output_dir, i))
    t.daemon = True
    t.start()

logger.debug('Queue Join and wait')
que.join()

logger.info('Script Done!')