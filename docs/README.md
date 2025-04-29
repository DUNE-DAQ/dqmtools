# dqmtools
Tools for on the spot Data Quality Monitoring. With dqmtools package it is possible to perform a number of basic checks for a given data file. 

### Quickstart
To run dqm_analyzer some external python libraries are needed, so one will need to create DBT working area with local python environment.
```bash
# Create a  DBT work area witl local python environment
dbt-create <release> <workarea>
cd <workarea>
source env.sh

# Clone dqmtools here
cd dqmtools
pip install -r requirements.txt
```
After these steps everything should be ready and one can run
```bash
dqm_analyzer.py --help
```
to list available options.
By default script will look for HD TPC data and analyze only first record in a given file. When finished script will print out in a table with possible check results -- INVALID,OK,WARNING,BAD. 

### Usage examples
The most basic usage requires only one argument -- data file and works for the HD TPC data:
```bash
dqm_analyzer.py /data1/np04_hd_run022752_0000_dataflow0_datawriter_0_20230925T084543.hdf5.copied
```
In case of VD TPC additional argument `--vd` is required:
```bash
dqm_analyzer.py --vd /data1/np02_vd_run022748_0000_dataflow0_datawriter_0_20230925T074747.hdf5
```
Adding `--pds` will initialize checks related to the DAPHNE data and print results in a separate table:
```bash
dqm_analyzer.py --pds /data1/np04_hd_run022752_0000_dataflow0_datawriter_0_20230925T084543.hdf5.copied
```
And to add plotting of some stats for the collected data:
```bash
dqm_analyzer.py --make-plots --pds /data1/np04_hd_run022752_0000_dataflow0_datawriter_0_20230925T084543.hdf5.copied
```

### How to get PDS waveforms from hdf5 file 
dqmtools package provides a script for dumping pds waveforms for further analysis (initially used to speed up the calibration process). `dump_dps_ana_info.py` takes two arguments -- input directory and run number, and has several options. For the list of available options try: `dump_pds_ana_info.py --help`. For each input file and each channel script will produce separate file containing 2-dimensional numpy array with waveforms.

Most general usage example:
```bash
dump_pds_ana_info.py  /data3/ 24100
``` 
which will process all files/all records/all channels in the run.
In case there is need for a quick look on the waveform quality and only part of channels are of interest
```bash
dump_pds_ana_info.py  /data3/ 24100 -nr 2 -nf 1 --cathode
``` 
this will process only 2 records in 1 file and only channles in the cathode PDS modules.
