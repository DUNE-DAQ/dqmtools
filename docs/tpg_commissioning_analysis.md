# TPG Comissioning analysis

## DUNEDAQ environment Installation

1. Setup a DUNEDAQ software environment:

```
source /cvmfs/dunedaq.opensciencegrid.org/setup_dunedaq.sh
setup_dbt fddaq-v5.3.1
dbt-create -b candidate fddaq-v5.3.2-a9
cd fddaq-v5.3.2-a9
```

If you are running on a DUNEDAQ server, set the web proxy:
```
source ~np04daq/bin/web_proxy.sh
```

2. get the relavent repos and branches

```
# change directory to the "sourcecode" subdir, if possible and needed
if [[ -d "sourcecode" ]]; then
    cd sourcecode
fi
# double-check that we're in the correct subdir
current_subdir=`echo ${PWD} | xargs basename`
if [[ "$current_subdir" != "sourcecode" ]]; then
    echo ""
    echo "*** Current working directory is not \"sourcecode\", skipping repo clones"
else
    # finally, do the repo clone(s)
    git clone https://github.com/DUNE-DAQ/rawdatautils.git -b sbhuller/v5+
    git clone https://github.com/DUNE-DAQ/dqmtools.git -b sbhuller/v5+
    pip install -r dqmtools/requirements.txt
    cd ..
fi
```
If you are running on a DUNEDAQ server, unset the web proxy:
```
source ~np04daq/bin/web_proxy.sh -u
```

3. initialise work area and build
```
source env.sh
dbt-build -j 20
dbt-workarea-env
```

**NOTE:** when opening a fresh terminal, run
```
source /cvmfs/dunedaq.opensciencegrid.org/setup_dunedaq.sh
source env.sh
```

Also, when developing in the repos, even if just python ensure you run `dbt-build` to update the copies of the python scripts in the install path.

## Run raw data analysis

To run a check on the raw ADC data to get noisy channels and event displays (and initial TPG thresholds eventually), run

```
tpc_data_analyzer.py <path-to-trigger-record> --vd
```

and a pdf document called `run<run-numer>_raw_adc_data_analysis.pdf` should be generated. The document will contain:

- plots of channel rms for each detector element
- table of channels to mask (ones that exceed an rms of 100) **can make configurable**
- event displays for each detector element and plane
- per plane, calculate the 3 sigma deviation in the mean ADC value, set this a the initial thresholds to use for the TPG. **can make configurable**

Items missing:

- FT of the waveforms to get a noise profile (get high/low frequency components).
