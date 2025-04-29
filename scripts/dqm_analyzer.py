#!/usr/bin/env python3

import rawdatautils.unpack.utils
import dqmtools.dataframe_creator as dfc
from dqmtools.dqmtools import *
from dqmtools.dqmtests import *
from dqmtools.dqmplots import *

import hdf5libs

import click
@click.command()
@click.argument('filenames', nargs=-1, type=click.Path(exists=True))
@click.option('--nrecords', '-n', default=1, help='How many Trigger Records to process (default: 1)')
@click.option('--nworkers', default=10, help='How many thread workers to launch (default: 10)')
@click.option('--hd/--vd', default=True, help='Whether we are running HD (or VD) (default: "HD")')
@click.option('--warm/--cold', default=True, help='Whether we are running warm or cold (default: "warm")')
@click.option('--pds',is_flag=True, help='If PDS was included and should be processed')
@click.option('--wibpulser', is_flag=True, help='WIBs in pulser mode')
@click.option('--make-plots',is_flag=True, help='Option to make plots')

def main(filenames, nrecords, nworkers, hd, warm, pds, wibpulser, make_plots):

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

    if(not wibpulser):
        dqm_test_suite_wibs.register_test(CheckRMS_WIBEth(det_name=tpc_det_name,threshold=tpc_rms_high_threshold,verbose=True),
                                         name=f"CheckRMS_{tpc_det_name}_High")
        dqm_test_suite_wibs.register_test(CheckRMS_WIBEth(det_name=tpc_det_name,threshold=tpc_rms_low_threshold,operator=operator.lt,verbose=True),
                                         name=f"CheckRMS_{tpc_det_name}_Low")
        dqm_test_suite_wibs.register_test(CheckPedestal_WIBEth(det_name=tpc_det_name,verbose=True),
                                         name=f"CheckPedestal_{tpc_det_name}")

    dqm_test_suite = DQMTestSuite("All Tests")
    dqm_test_suite.register_test(dqm_test_suite_wibs)
        
    if pds:
        """
        Create separate test suite for DAPHNE and register all related tests
        """
        dqm_test_suite_daphne = DQMTestSuite("DAPHNETests")
        dqm_test_suite_daphne.register_test(CheckTimestampsAligned(2),"CheckTimestampsAligned_PDS")
        dqm_test_suite_daphne.register_test(CheckEmptyFragments_DAPHNE(), "CheckEmptyFragments_DAPHNE")
        dqm_test_suite_daphne.register_test(CheckTimestampDiffs_DAPHNE())
        dqm_test_suite_daphne.register_test(CheckADCData_DAPHNE())

        dqm_test_suite.register_test(dqm_test_suite_daphne)


        
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
            df_dict = dfc.process_record(h5_file,rid,df_dict,MAX_WORKERS=nworkers)
            n_processed_records += 1

    df_dict = dfc.concatenate_dataframes(df_dict)

    #print(df_dict.keys())

    res = dqm_test_suite.run_test(df_dict)
    print(dqm_test_suite.get_table(show_last_update=False))

    for test in dqm_test_suite.get_all_tests():
        if test.is_test_suite():
            print(f'Results for {test.get_name()}:')
            print(test.get_table(show_last_update=False))

    if(make_plots):
        if(not wibpulser):
            plot_WIBEth_by_channel(df_dict,var="adc_rms",det_name=tpc_det_name,jpeg_base=f"pdune2_{tpc_det_name}_rms")
            plot_WIBEth_by_channel(df_dict,var="adc_rms",det_name=tpc_det_name,yrange=[-1,60],jpeg_base=f"pdune2_{tpc_det_name}_rms_fixrange")
            plot_WIBEth_by_channel(df_dict,var="adc_mean",det_name=tpc_det_name,jpeg_base=f"pdune2_{tpc_det_name}_mean")
        if(wibpulser):
            plot_WIBEth_pulser_by_channel(df_dict,det_name=tpc_det_name,jpeg_base=f'pdune2_{tpc_det_name}_pulser')

        if (pds):
            plot_DAPHNE_stats(df_dict,jpeg_base="pdune2_DAPHNE")
            plot_DAPHNE_baseline(df_dict,jpeg_base="pdune2_DAPHNE")


if __name__ == '__main__':
    main()
