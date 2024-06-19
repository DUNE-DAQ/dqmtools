#!/usr/bin/env python3

import rawdatautils.unpack.utils
import dqmtools.dataframe_creator as dfc
from dqmtools.dqmtools import *
from dqmtools.dqmtests import *
from dqmtools.dqmplots import *

import hdf5libs
import os

import click
@click.command()
@click.argument('filenames', nargs=-1, type=click.Path(exists=True))
@click.option('--nrecords', '-n', default=-1, help='How many Trigger Records to process (default: all)')
@click.option('--maxfiles', default=1, help='Maximum number of files to consider (default: 1)')
@click.option('--nworkers', default=10, help='How many thread workers to launch (default: 10)')
@click.option('--hd/--vd', default=True, help='Whether we are running HD (or VD) (default: "HD")')
@click.option('--warm/--cold', default=True, help='Whether we are running warm or cold (default: "warm")')

def main(filenames, nrecords, maxfiles, nworkers, hd, warm):

    print(filenames)
    if(os.path.isdir(filenames[0])):
        files = os.listdir(filenames[0])
        paths = [os.path.join(filenames[0], basename) for basename in files]
        print(paths)
        paths.sort(key=lambda x: os.path.getctime(x))
        paths.reverse()
        print(paths)
        filenames = paths

        
    print(filenames)
    if(maxfiles>len(filenames)):
        maxfiles=len(filenames)
    filenames = filenames[0:maxfiles]
    print(filenames)
    
    #setup our tests
    dqm_test_suite_wibs = DQMTestSuite("WIBEth Tests")
    dqm_test_suite_wibs.register_test(CheckAllExpectedFragmentsTest())
    dqm_test_suite_wibs.register_test(CheckNFrames_WIBEth())
    
    if(hd):
        tpc_det_name = "HD_TPC"
        tpc_det_id = 3
        tpc_rms_high_threshold=100
        tpc_rms_low_threshold=[15.]
        if not warm:
            tpc_rms_high_threshold=50
            tpc_rms_low_threshold=[4.,3.]
            
    else:
        tpc_det_name = "VD_BottomTPC"
        tpc_det_id = 10
        tpc_rms_high_threshold=100
        tpc_rms_low_threshold=[12.,20.]        
        if not warm:
            tpc_rms_high_threshold=50
            tpc_rms_low_threshold=[2.,3.]

    dqm_test_suite_wibs.register_test(CheckTimestampDiffs_WIBEth(tpc_det_name))

    dqm_test_suite_wibs.register_test(CheckWIBEth_COLDDATA_Timestamp_0_Diff(tpc_det_name))
    dqm_test_suite_wibs.register_test(CheckWIBEth_COLDDATA_Timestamp_1_Diff(tpc_det_name))
    dqm_test_suite_wibs.register_test(CheckWIBEth_COLDDATA_Timestamps_Aligned(tpc_det_name))

    dqm_test_suite_wibs.register_test(CheckWIBEth_CRC_Err(tpc_det_name))
    dqm_test_suite_wibs.register_test(CheckWIBEth_Pulser(tpc_det_name))
    dqm_test_suite_wibs.register_test(CheckWIBEth_Calibration(tpc_det_name))
    dqm_test_suite_wibs.register_test(CheckWIBEth_Ready(tpc_det_name))
    dqm_test_suite_wibs.register_test(CheckWIBEth_Context(tpc_det_name))
    dqm_test_suite_wibs.register_test(CheckWIBEth_CD(tpc_det_name))
    dqm_test_suite_wibs.register_test(CheckWIBEth_LOL(tpc_det_name))        
    dqm_test_suite_wibs.register_test(CheckWIBEth_Link_Valid(tpc_det_name))
    dqm_test_suite_wibs.register_test(CheckWIBEth_WIB_Sync(tpc_det_name))
    dqm_test_suite_wibs.register_test(CheckWIBEth_FEMB_Sync(tpc_det_name))

    dqm_test_suite_wibs.register_test(CheckTimestampsAligned(tpc_det_id),f"CheckTimestampsAligned_{tpc_det_name}")
    dqm_test_suite_wibs.register_test(CheckRequestTimes_WIBEth(tpc_det_name))

    #dqm_test_suite_wibs.register_test(CheckRMS_WIBEth(det_name=tpc_det_name,threshold=tpc_rms_high_threshold,verbose=True),
    #                                  name=f"CheckRMS_{tpc_det_name}_High")
    #dqm_test_suite_wibs.register_test(CheckRMS_WIBEth(det_name=tpc_det_name,threshold=tpc_rms_low_threshold,operator=operator.lt,verbose=True),
    #                                  name=f"CheckRMS_{tpc_det_name}_Low")
    #dqm_test_suite_wibs.register_test(CheckPedestal_WIBEth(det_name=tpc_det_name,verbose=True),
    #                                  name=f"CheckPedestal_{tpc_det_name}")

    df_dict = {}
    n_processed_records = 0
    for filename in filenames:
        print(f'Processing file {filename}.')
        
        h5_file = hdf5libs.HDF5RawDataFile(filename)
        records = h5_file.get_all_record_ids()

        if nrecords==-1 or nrecords > (n_processed_records+len(records)):
            records_to_process = records
        else:
            records_to_process = records[:(nrecords-n_processed_records)]
        print(f'Will process {len(records_to_process)} of {len(records)} records.')

        for rid in records_to_process:
            print(f'Processing record {rid}')
            df_dict = dfc.process_record(h5_file,rid,df_dict,MAX_WORKERS=nworkers,ana_data_prescale=None,wvfm_data_prescale=None)
            n_processed_records += 1

    df_dict = dfc.concatenate_dataframes(df_dict)

    #print(df_dict.keys())

    res = dqm_test_suite_wibs.run_test(df_dict)
    print(dqm_test_suite_wibs.get_table(show_last_update=False))

    for test in dqm_test_suite_wibs.get_all_tests():
        if test.is_test_suite():
            print(f'Results for {test.get_name()}:')
            print(test.get_table(show_last_update=False))

    results = dqm_test_suite_wibs.get_latest_results()[["result","message","name","last_update"]]
    def apply_color(x):
        if(x==DQMResultEnum.OK): return "rgb(179, 226, 205)"
        if(x==DQMResultEnum.BAD): return "rgb(251,180,174)"
        if(x==DQMResultEnum.WARNING): return "rgb(253,244,152)"
        if(x==DQMResultEnum.INVALID): return "rgb(251,180,174)"

    results["color"] = results["result"].apply(apply_color)
    #results=results.astype(str)
    #print(results)
    
    fig = go.Figure(data=[go.Table(
        columnorder=[1,2,3],
        columnwidth=[360,360,720],
        header=dict(values=["Test Name","Update time","Result"],
                    fill_color='royalblue',
                    align='left',
                    font=dict(color='white',size=12),
                    height=50),
        cells=dict(values=[results.name, results.last_update, results.message],
                   line_color=['darkslategray'],
                   fill_color=[results.color],
                   font_size=12,
                   align='left',
                   height=30))
                          ]
                    )
    fig.update_layout(height=len(results)*50,width=1500)
    #fig.update_layout(autosize=True)
    fig.write_image(f"Tests_WIBS_results.png")
    
if __name__ == '__main__':
    main()
