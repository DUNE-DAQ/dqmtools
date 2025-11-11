#!/usr/bin/env python3
import sys
import os

import rawdatautils.unpack.utils
import detdataformats
import daqdataformats

from rawdatautils.unpack.dataclasses import *
import dqmtools.dataframe_creator as dfc
from hdf5libs import HDF5RawDataFile
import h5py

import numpy as np
try:
    import pandas as pd
except ModuleNotFoundError as err:
    print(err)
    print("\n\n")
    print("Missing module is likely not part of standard dunedaq releases.")
    print("\n")
    print("Please install the missing module and try again.")
    sys.exit(1)
except:
    raise


import click
@click.command()
@click.argument('input_dir',        type=click.Path(exists=True))
@click.argument('run')
@click.option('--nrecords', '-nr',          default=-1,     help='Number of records to process in each file (default: all).')
@click.option('--nfiles',   '-nf',          default=-1,     help='Number of files to process in the run (default: all).')
@click.option('--cathode', is_flag=True,     default=False,  help='Use only cathode channels')
@click.option('--membrane',is_flag=True,    default=False,  help='Use only membrane channels')

def main(input_dir, run, nrecords, nfiles, cathode, membrane):
    """
        For the specified RUN script will iterate over datafiles, unpack the DAPHNE streaming data,
        create numpy arrays of the waveforms and save them to the files in current directory.
        Each channel will be saved in a separate file.
    """

    allFiles    = os.listdir(input_dir)
    goodFiles   = [file for file in allFiles if (f"run0{run}" in file and ".hdf5.copied" in file)]
    goodFiles = sorted(list(goodFiles))
    print(f"Total files in the run {run} -- {len(goodFiles)}")

    if nfiles == -1 or nfiles > len(goodFiles):
        files_to_process = goodFiles
    else:
        files_to_process = goodFiles[:nfiles]

    print(f"Will process {len(files_to_process)} files out of -- {len(goodFiles)} \n")

    if (not cathode or membrane) and (cathode or not membrane):
        active_chan     = [0,   1,  6,  7,
                           10, 11, 16, 17,
                           20, 21, 26, 27,
                           30, 31, 36, 37]
    elif cathode:
        active_chan     = [0, 7, 10, 17, 20, 27, 30, 37]
    else:
        active_chan     = [21, 36]

    
    for file in files_to_process:

        file_id   = file.split("_")[3]
        h5_file   = HDF5RawDataFile(input_dir+file)
        records   = h5_file.get_all_record_ids()
        n_records = len(records)
        print(f"Processing file -- {file}")

        if nrecords==-1 or nrecords > n_records:
            records_to_process = records
        else:
            records_to_process = records[:nrecords]
        
        print(f'Will process {len(records_to_process)} of {len(records)} records.')
    
        df_dict = {}

        for r in records_to_process:

            with h5py.File(h5_file.get_file_name(), 'r') as f:
                record_index = dfc.RecordDataBase(run=f.attrs["run_number"],trigger=r[0],sequence=r[1])
            sids = h5_file.get_source_ids(r)

            for sid in sids:

                sid_unpacker = rawdatautils.unpack.utils.SourceIDUnpacker(record_index)
                return_dict = sid_unpacker.get_all_data(sid)

                if sid.subsystem != daqdataformats.SourceID.Subsystem.kDetectorReadout:
                    continue
                
                frag        = h5_file.get_frag((record_index.trigger,record_index.sequence),sid)
                frag_type   = frag.get_fragment_type() #print(frag_type)
                
                if frag_type != daqdataformats.FragmentType.kDAPHNEStream:
                    continue

                det_id      = frag.get_detector_id()
                type_string = f'{detdataformats.DetID.Subdetector(det_id).name}_{frag_type.name}'

                fragment_unpacker = dfc.get_fragment_unpacker(frag_type,det_id)
                fragment_unpacker.wvfm_data_prescale = 1

                if fragment_unpacker is None:
                    print(f'Unknown fragment {type_string}. Source ID {sid}')
                    return return_dict
                
                return_dict = (return_dict | fragment_unpacker.get_all_data(frag) )
                
                for key, df in return_dict.items():
                    if key not in df_dict.keys():
                        df_dict[key] = []
                    df_dict[key].extend(df)

        df_dict = dfc.concatenate_dataframes(df_dict)


        try:
            daphne_data     = df_dict['detw_kHD_PDS_kDAPHNEStream']
        except KeyError:
            print('No waveform data in the file.')
            continue

        trigger_ts      = df_dict['frh'].trigger_timestamp_dts

        if len(np.unique(trigger_ts)) != len(records_to_process):
            print(f"Unique trigger timestamps for {len(records_to_process)} records \t - \t {len(np.unique(trigger_ts))}")
            print("Problems with trigger timestaps")
    
        trigger_ts      = np.array(np.unique(df_dict['frh'].trigger_timestamp_dts), dtype=np.int64)

        print(f"Width of the readout window -- {np.unique(np.array(df_dict['frh'].window_end_dts) - np.array(df_dict['frh'].window_begin_dts))}")
        #print(f"Unique trigger timestamps for {records_to_process} records \t - \t {len(np.unique(trigger_ts))}")

        req_wave_len = np.unique(np.array(df_dict['frh'].window_end_dts) - np.array(df_dict['frh'].window_begin_dts))[0]
        window_begin = np.unique(np.array(df_dict['frh'].window_begin_dts))
        window_end   = np.unique(np.array(df_dict['frh'].window_end_dts))

        window_begin = np.array(window_begin, dtype=np.int64)
        window_end   = np.array(window_end, dtype=np.int64)
    
        for ch in active_chan:

            dat     = daphne_data.query(f"daphne_chan == {ch}")
            if len(dat) == 0:
                continue
            run     = dat.index[0][0]
            record  = dat.index[0][1]
            src_id  = dat.index[0][3]

            adcs    = np.array(dat.adcs)
            for i in range(len(adcs)):
                if np.any(adcs[i]) > 2**14:
                    print(f"ADC values above physical limit -- {len(adcs[i][np.where(adcs[i] > 2**14)])}")
            tss     = np.array(dat.timestamps)
        
            waveforms = np.zeros((len(records_to_process), req_wave_len), dtype=np.uint16)

            print(waveforms.shape)

            for i in range(len(tss)):
                
                try:
                    index_begin = np.where( tss[i] == window_begin[i])[0][0]
                except:
                    print("Problems with window begin ts")
                    print(f"First ts -- {tss[i][0]}, Window begin -- {window_begin[i]}, difference -- {tss[i][0] - window_begin[i]}")
                    continue
                
                try:
                    index_end   = np.where( tss[i] == window_end[i] )[0][0]
                except:
                    if ( tss[i][-1] - window_end[i] == 0):
                        waveforms[i, :] = np.array(adcs[i])[index_begin-1:-1]
                        continue
                    else:
                        print("Problems with window end ts")
                        print(np.where( tss[i] == window_end[i] ))
                        print(f"Last ts -- {tss[i][-1]}, Window end -- {window_end[i]}, difference -- {tss[i][-1] - window_end[i]}")
                        continue

                waveforms[i, :] = np.array(adcs[i])[index_begin:index_end]

            filename_adc = f"adc_data_run_{run}_srcid_{src_id}_ch_{ch}_{file_id}.npy"
            np.save(filename_adc, waveforms)
                
    return


if __name__ == '__main__':
    main()
