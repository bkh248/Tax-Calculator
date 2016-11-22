"""
Tax-Calculator validation script that adds random amounts to most
variables in the puf.csv input file, which must be located in the
top-level directory of the Tax-Calculator source code tree.
The resulting input file is xYY.csv, where YY denotes the tax year.

When setting DEBUG = True, the aggregate weighted income and payroll tax
revenues generated by the xYY.csv input file are exactly the same as those
generated by the standard puf.csv input file.
"""
# CODING-STYLE CHECKS:
# pep8 --ignore=E402 csv_in.py
# pylint --disable=locally-disabled --extension-pkg-whitelist=numpy csv_in.py
# (when importing numpy, add "--extension-pkg-whitelist=numpy" pylint option)

import argparse
import sys
import os
import pandas as pd
import numpy as np
CUR_PATH = os.path.abspath(os.path.dirname(__file__))
sys.path.append(os.path.join(CUR_PATH, '..', '..'))
# pylint: disable=wrong-import-position,import-error
from taxcalc import Records

# specify maximum allowed values for command-line parameters
MAX_YEAR = 2023  # maximum tax year allowed for tax calculations
MAX_SEED = 999999999  # maximum allowed seed for random-number generator
MAX_SIZE = 100000  # maximum size of sample to draw from puf.csv

DEBUG = False  # True implies no variable randomization or record sampling

TRACE = False  # True implies tracing output written to stdout

# specify set of variables not included in xYY.csv file
if DEBUG:
    DROP_VARS = set(['filer'])
else:
    DROP_VARS = set(['filer', 's006', 'cmbtp',
                     'nu05', 'nu13', 'elderly_dependent',
                     'e09700', 'e09800', 'e09900', 'e11200'])

# specify set of variables whose values are not to be randomized
if DEBUG:
    SKIP_VARS = Records.USABLE_READ_VARS
else:
    SKIP_VARS = set(['RECID', 'MARS', 'DSI', 'MIDR', 'FLPDYR',
                     'age_head', 'age_spouse',
                     'XTOT', 'EIC', 'n24', 'f2441',
                     'f6251'])

ANNUAL_DRIFT = 0.03
NORM_STD_DEV = 0.25


def randomize_data(xdf, taxyear, rnseed):
    """
    Randomizes data variables.

    Parameters
    ----------
    xdf: Pandas DataFrame
        contains data to be randomized.

    taxyear: integer
        specifies year for which data is to be randomized.

    rnseed: integer
        specifies random-number seed to use in the randomization.
    """
    xdf['FLPDYR'] = taxyear
    num = xdf['FLPDYR'].size
    nmean = 1.0 + ANNUAL_DRIFT * (taxyear - 2009)
    nsdev = NORM_STD_DEV
    np.random.seed(rnseed)
    num_skips = 0
    for varname in list(xdf):
        if varname in SKIP_VARS:
            num_skips += 1
            continue
        # randomize nonzero variable amounts
        old = xdf[varname]
        oldint = old.round(decimals=0)
        oldint = oldint.astype(dtype=np.int64)
        rfactor = np.random.normal(loc=nmean, scale=nsdev, size=num)
        addon = oldint * rfactor  # addon is zero if oldint is zero
        raw = oldint + addon.round(decimals=0)
        raw = raw.astype(dtype=np.int64)
        if oldint.min() < 0:
            new = raw
        else:
            new = raw.clip(lower=0)
        if TRACE:
            info = '{} {} {} {} {}'.format(varname, old.dtype, old.min(),
                                           new.dtype, new.min())
            sys.stdout.write(info + '\n')
        xdf[varname] = new
    if TRACE:
        info = 'number_variable_randomization_skips={}'.format(num_skips)
        sys.stdout.write(info + '\n')


def constrain_data(xdf):
    """
    Constrains data variable values as required by Records class

    Parameters
    ----------
    xdf: Pandas DataFrame
        contains randomized data to be constrained.
    """
    if DEBUG:
        return
    # constraint: e00200 = e00200p + e00200s
    xdf['e00200'] = xdf['e00200p'] + xdf['e00200s']
    # constraint: e00900 = e00900p + e00900s
    xdf['e00900'] = xdf['e00900p'] + xdf['e00900s']
    # constraint: e02100 = e02100p + e02100s
    xdf['e02100'] = xdf['e02100p'] + xdf['e02100s']
    # constraint: e00600 >= e00650
    xdf['e00600'] = np.maximum(xdf['e00600'], xdf['e00650'])
    # constraint: e01500 >= e01700
    xdf['e01500'] = np.maximum(xdf['e01500'], xdf['e01700'])


def main(taxyear, rnseed, ssize):
    """
    Contains the high-level logic of the script.
    """
    # read puf.csv file into a Pandas DataFrame
    pufcsv_filename = os.path.join(CUR_PATH, '..', '..', 'puf.csv')
    if not os.path.isfile(pufcsv_filename):
        msg = 'ERROR: puf.csv file not found in top-level directory'
        sys.stderr.write(msg + '\n')
        return 1
    xdf = pd.read_csv(pufcsv_filename)
    # pylint: disable=no-member

    # remove xdf variables not needed in xYY.csv file
    if TRACE:
        info = 'df.shape before dropping = {}'.format(xdf.shape)
        sys.stdout.write(info + '\n')
    for var in DROP_VARS:
        if var not in Records.USABLE_READ_VARS:
            msg = 'ERROR: variable {} already dropped'.format(var)
            sys.stderr.write(msg + '\n')
            return 1
        xdf.drop(var, axis=1, inplace=True)
    if TRACE:
        info = 'df.shape  after dropping = {}'.format(xdf.shape)
        sys.stdout.write(info + '\n')

    # add random amounts to xdf variables
    randomize_data(xdf, taxyear, rnseed)

    # constrain values of certain variables as required by Records class
    constrain_data(xdf)

    # sample xdf without replacement to get ssize observations
    if DEBUG:
        (sample_size, _) = xdf.shape
        xxdf = xdf
    else:
        sample_size = ssize
        xxdf = xdf.sample(n=sample_size, random_state=rnseed)
    xxdf['RECID'] = [rid + 1 for rid in range(sample_size)]
    if TRACE:
        info = 'df.shape  after sampling = {}'.format(xxdf.shape)
        sys.stdout.write(info + '\n')

    # write randomized and sampled xxdf to xYY.csv file
    xxdf.to_csv('x{}.csv'.format(taxyear % 100), index=False)

    # normal return code
    return 0
# end of main function code


if __name__ == '__main__':
    # parse command-line arguments:
    PARSER = argparse.ArgumentParser(
        prog='python csv_in.py',
        description=('Adds random amounts to certain variables in '
                     'puf.csv input file and writes the randomized '
                     'CSV-formatted input file to xYY.csv file.'))
    PARSER.add_argument('YEAR', nargs='?', type=int, default=0,
                        help=('YEAR is tax year; '
                              'must be in [2013,{}] range.'.format(MAX_YEAR)))
    PARSER.add_argument('SEED', nargs='?', type=int, default=0,
                        help=('SEED is random-number seed; '
                              'must be in [1,{}] range.'.format(MAX_SEED)))
    PARSER.add_argument('SIZE', nargs='?', type=int, default=0,
                        help=('SIZE is sample size; '
                              'must be in [1,{}] range.'.format(MAX_SIZE)))
    ARGS = PARSER.parse_args()
    # check for invalid command-line parameter values
    ARGS_ERROR = False
    if ARGS.YEAR < 2013 or ARGS.YEAR > MAX_YEAR:
        RSTR = '[2013,{}] range'.format(MAX_YEAR)
        sys.stderr.write('ERROR: YEAR {} not in {}\n'.format(ARGS.YEAR, RSTR))
        ARGS_ERROR = True
    if ARGS.SEED < 1 or ARGS.SEED > MAX_SEED:
        RSTR = '[1,{}] range'.format(MAX_SEED)
        sys.stderr.write('ERROR: SEED {} not in {}\n'.format(ARGS.SEED, RSTR))
        ARGS_ERROR = True
    if ARGS.SIZE < 1 or ARGS.SIZE > MAX_SIZE:
        RSTR = '[1,{}] range'.format(MAX_SIZE)
        sys.stderr.write('ERROR: SIZE {} not in {}\n'.format(ARGS.SIZE, RSTR))
        ARGS_ERROR = True
    if ARGS_ERROR:
        sys.stderr.write('USAGE: python csv_in.py --help\n')
        RCODE = 1
    else:
        RCODE = main(ARGS.YEAR, ARGS.SEED, ARGS.SIZE)
    sys.exit(RCODE)
