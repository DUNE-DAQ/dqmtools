#!/usr/bin/env python3

import rawdatautils.unpack.utils
import dqmtools.dataframe_creator as dfc
from dqmtools.dqmtools import *
from dqmtools.dqmtests import *
from dqmtools.dqmplots import *

import h5py
import hdf5libs

import concurrent.futures
import os
import timeit

import pytz

from rich import print

import click


def make_adc_map_fig(element, plane, df_dict, det_keys, offset, index, imgtype,
                     trigger_types_str, trigger_timestamp_cern, output_dir):
    title = (f"Run {int(index[0])}, Trigger {int(index[1])}, {element} Plane {plane}\n"
             f"Trigger Type {trigger_types_str}, {trigger_timestamp_cern} (CERN)")
    fig = plot_TPC_adc_map_mpl(df_dict=df_dict, det_keys=det_keys,
                               plane=plane, ele=element,
                               make_static=True,
                               offset=offset,
                               make_tp_overlay=False,
                               orientation='vertical',
                               colorscale='plasma',
                               color_range=(-256, 256),
                               run=index[0],
                               trigger=index[1],
                               seq=index[2],
                               figsize=(12, 8),
                               title=title)
    print(f"Figure for Element {element} plane {plane} processed...")
    img_file_name = (f"EventDisplay_run{int(index[0])}_trigger{int(index[1])}"
                     f"_seq{int(index[2])}_{element}_plane{plane}.{imgtype}")
    fig.tight_layout()
    fig.savefig(os.path.join(output_dir, img_file_name))
    return img_file_name


@click.command()
@click.argument('input_data', type=click.Path(exists=True))
@click.argument('output_dir', type=click.Path(exists=True))
@click.option('--nworkers', default=10, help='How many thread workers to launch (default: 10)')
@click.option('--nskip', default=0, help='How many trigger records to skip at start of file')
@click.option('--nrecords', default=1, help='How many trigger records to plot')
@click.option('--imgtype', default='png', help='Type of image to write')
@click.option('--component', default=None, help='Specific component to plot')
@click.option('--plane', default=None, help='Specific plane to plot')
def main(input_data, output_dir, nworkers, nskip, nrecords, imgtype, component, plane):

    filename = input_data
    if os.path.isdir(input_data):
        print(f"Scanning directory {input_data}")
        files = os.listdir(input_data)
        paths = [os.path.join(input_data, basename) for basename in files if not basename.endswith(".writing")]
        filename = max(paths, key=os.path.getctime)

    print(f'Opening file {filename}')

    with h5py.File(filename, 'r') as f:
        op_env = f.attrs.get("operational_environment", "")

    print(f"Operational environment: {op_env}")

    h5_file = hdf5libs.HDF5RawDataFile(filename)
    records = h5_file.get_all_record_ids()

    if len(records) == 0:
        print(f'No records found in file {filename}.')
        return

    if len(records) < nskip:
        print(f'Requested to skip {nskip} records, but there are only {len(records)} in the file.')
        return

    record_count = 0

    if nrecords == -1:
        nrecords = len(records)

    while record_count < nrecords and (record_count + nskip) < len(records):

        rid = records[nskip + record_count]

        print(f"Processing record {rid} in file {filename}.")
        t_start = timeit.default_timer()

        df_dict = dfc.process_record(h5_file, rid, {}, MAX_WORKERS=nworkers, ana_data_prescale=1, wvfm_data_prescale=1)
        df_dict = dfc.concatenate_dataframes(df_dict)

        print(f"Dataframes loaded in {timeit.default_timer() - t_start:.1f}s")

        index = df_dict["trh"].index[0]
        det_keys = [key for key in df_dict if key.startswith('detw') and 'TPC' in key]

        match op_env:
            case 'np02vd' | 'np02cb':
                hd = False
            case 'np04hd' | 'np04cb':
                hd = True
            case _:
                print(f"Unknown op_env '{op_env}', falling back to det_keys heuristic")
                hd = any("kHD" in k for k in det_keys)

        offset = True

        planes = [int(plane)] if plane is not None else [0, 1, 2]

        if component is not None:
            element_ids = [int(component)]
        elif hd:
            element_ids = [1, 2, 3, 4]
        else:
            element_ids = [2, 3, 4, 5]

        element_type = "APA" if hd else "CRP"
        elements = [f'{element_type}{i}' for i in element_ids]

        myplanes = [(el, pl) for el in elements for pl in planes]

        df_dict["trh"]['trigger_time_cern'] = pd.to_datetime(df_dict["trh"]['trigger_time'])
        df_dict['trh']['trigger_time_cern'] = df_dict['trh']['trigger_time_cern'].dt.tz_convert('Europe/Zurich')
        trigger_timestamp_cern = df_dict["trh"]["trigger_time_cern"].iloc[0]

        trigger_types_str = "("
        for trigtype in df_dict["trh"]["trigger_type_bits"].iloc[0]:
            trigger_types_str += trigtype.name[1:] + ","
        trigger_types_str = trigger_types_str[:-1] + ")"

        with concurrent.futures.ThreadPoolExecutor(max_workers=nworkers) as executor:
            future_p = {
                executor.submit(make_adc_map_fig, p[0], p[1], df_dict, det_keys, offset,
                                index, imgtype, trigger_types_str, trigger_timestamp_cern, output_dir): p
                for p in myplanes
            }
            for future in concurrent.futures.as_completed(future_p):
                res = future.result()
                print(f"Completed image {res} ({timeit.default_timer() - t_start:.1f}s elapsed)")

        record_count += 1
        print(f"Done with {record_count} records ({timeit.default_timer() - t_start:.1f}s total).")


if __name__ == '__main__':
    main()
