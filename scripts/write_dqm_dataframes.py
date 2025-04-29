#!/usr/bin/env python3

import dqmtools.dataframe_creator as dfc
import hdf5libs
import os
import click


@click.command()
@click.argument('input_filenames', nargs=-1, type=click.Path(exists=True))
@click.argument('output_filename', nargs=1)
@click.option('--force', '-f', is_flag=True, help='Remove output file if it exists.')
@click.option('--append', '-a', is_flag=True, help='Append to file if it already exists.')
@click.option('--nrecords', '-n', default=1, help='How many Trigger Records to process (default: 1)')
@click.option('--nworkers', default=10, help='How many thread workers to launch (default: 10)')
@click.option('--wvfm_data_prescale', default=None, help='Prescale to apply to waveform data storage (default: None)')
@click.option('--complevel', default=0, help='Compression level to use (0-9, default: 0)')
@click.option('--complib', default=None, help='Compression library to use (zlib, lzo, bzip2, blosc, default: None)')
def main(input_filenames, output_filename, force, append, nrecords, wvfm_data_prescale, nworkers, complevel, complib):

    if force and append:
        print('Cannot use both --force (-f) and --append (-a) options. Use only one.')
    
    if os.path.isfile(output_filename):
        print(f'File {output_filename} exists.')
        if force:
            print('Deleting...')
            os.remove(output_filename)
        elif append:
            print('Append option enabled. Will append to existing file.')
        else:
            print("Remove file or use '-f' option to force removal, or use '-a' option to append new data to file.")
            return 1
    
    df_dict = {}
    n_processed_records = 0
    for filename in input_filenames:
        print(f'Processing file {filename}.')
        
        h5_file = hdf5libs.HDF5RawDataFile(filename)
        records = h5_file.get_all_record_ids()

        if nrecords == -1 or nrecords > (n_processed_records+len(records)):
            records_to_process = records
        else:
            records_to_process = records[:(nrecords-n_processed_records)]
        print(f'Will process {len(records_to_process)} of {len(records)} records.')

        for rid in records_to_process:
            print(f'Processing record {rid}')
            df_dict = dfc.process_record(h5_file, rid, df_dict, MAX_WORKERS=nworkers, wvfm_data_prescale=wvfm_data_prescale)
            n_processed_records += 1

        if n_processed_records == nrecords:
            break

    df_dict = dfc.concatenate_dataframes(df_dict)

    print(df_dict.keys())

    for key, df in df_dict.items():
        df.to_hdf(output_filename, key=key, complevel=complevel, complib=complib)
    

if __name__ == '__main__':
    main()
