from dqmtools.dqmtools import *
from rawdatautils.unpack.dataclasses import *

import numpy as np
import operator

class CheckAllExpectedFragmentsTest(DQMTest):

    def __init__(self):
        super().__init__()
        self.name = 'CheckAllExpectedFragmentsTest'

    def run_test(self,df_dict):
        df_tmp = (df_dict["trh"]["n_fragments"]!=df_dict["trh"]["n_requested_components"])
        n_not_matched = df_tmp.sum()
        if n_not_matched==0:
            return DQMTestResult(DQMResultEnum.OK,f'OK')
        else:
            return DQMTestResult(DQMResultEnum.BAD,f'{n_not_matched} / {len(df_tmp)} records missing fragments.')

class CheckTimestampsAligned(DQMTest):

    def __init__(self,det_id,verbose=True):
        super().__init__()
        self.det_id = det_id
        self.name = f'CheckTimestampsAligned_{det_id}'
        self.verbose = verbose
        
    def any_different(arr):
        return (arr.values!=arr.values[0]).sum()

    def unique(arr):
        return np.unique(arr.values,return_counts=True)
    
    def run_test(self,df_dict):
        df_tmp = df_dict["daqh"].loc[df_dict["daqh"]["det_id"]==self.det_id]
        
        if len(df_tmp)==0:
            return DQMTestResult(DQMResultEnum.WARNING,f'WARNING: No components found with detector id {self.det_id}.')
        
        df_tmp_gb = df_tmp.groupby(by=["run","trigger","sequence"])["timestamp_first_dts"].agg(CheckTimestampsAligned.unique)
        df_tmp_gb_n = df_tmp_gb.apply(lambda x: len(x[1]))
        n_different = (df_tmp_gb_n!=1).sum()

        if n_different==0:
            return DQMTestResult(DQMResultEnum.OK,f'OK')
        else:
            if self.verbose:
                df_tmp_fr = df_dict["frh"].loc[df_dict["frh"]["det_id"]==self.det_id][["trigger_timestamp_dts","window_begin_dts","window_end_dts"]]
                
                df_tmp_gb_mode = df_tmp_gb.apply(lambda x: x[0][np.argmax(x[1])])
                df_tmp = df_tmp.join(df_tmp_gb_mode,rsuffix='_majority')
                df_tmp = df_tmp.join(df_tmp_fr)
                df_tmp = df_tmp.loc[(df_tmp["timestamp_first_dts"]!=df_tmp["timestamp_first_dts_majority"])]

                df_tmp["timestamp_diff"] = df_tmp["timestamp_first_dts"]-df_tmp["timestamp_first_dts_majority"]
                n_different = len(np.unique(df_tmp.reset_index()["src_id"].apply(lambda x: int(x))))
                print(f"\nFRAGMENTS FAILING TIMESTAMP ALIGNMENT for Detector ID {self.det_id}")
                print(tabulate(df_tmp.reset_index()[["trigger","sequence","crate_id","slot_id","stream_id","timestamp_first_dts","timestamp_first_dts_majority","timestamp_diff",
                                                     "window_begin_dts","window_end_dts"]],
                                headers=["Record","Seq.","Crate","Slot","Stream","Timestamp (first)","Majority timestamp","Difference","Window begin","Window end"],
                                showindex=False,tablefmt='pretty'))

            return DQMTestResult(DQMResultEnum.BAD,
                                 f'{n_different} sources have some timestamp misalignment for det_id {self.det_id}.')

