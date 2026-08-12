from dqmtools.dqmtools import *
from rawdatautils.unpack.dataclasses import *

import numpy as np
import operator

class CheckEmptyFragments_DAPHNE(DQMTest):

    def __init__(self):
        super().__init__()
        self.name = "CheckEmptyFragments_DAPHNE"

    def run_test(self,df_dict):
        df_tmp1 = df_dict["frh"].loc[df_dict["frh"]["fragment_type"]==3]

        if len(df_tmp1)==0:
            return DQMTestResult(DQMResultEnum.WARNING,f"WARNING: No Self-triggered DAPHNE data found.")
        
        n_emptyFrames          = len(df_tmp1.loc[df_tmp1["data_size_bytes"] == 0])
        n_filledFrames         = len(df_tmp1.loc[df_tmp1["data_size_bytes"] != 0])

        if n_emptyFrames != 0:
            return DQMTestResult(DQMResultEnum.BAD, f'{n_emptyFrames} fragments are empty ({n_filledFrames} are fine).')
        else:
            return DQMTestResult(DQMResultEnum.OK,f'OK')

class CheckFramesInTimeWindow_DAPHNE(DQMTest):

    def __init__(self):
        super().__init__()
        self.name = "CheckFramesInTimeWindow_DAPHNE"

    def run_test(self,df_dict):
        ...

class CheckTimestampDiffs_DAPHNEStream(DQMTest):
    def __init__(self,det_name):
        super().__init__()
        self.name = f"CheckTimestampDiffs_DAPHNEStream_{det_name}"
        self.det_head_key = f'deth_k{det_name}_kDAPHNEStream'

    def run_test(self, df_dict, verbose=False):

        n_bad_stream = 0

        if self.det_head_key not in df_dict.keys():
            return DQMTestResult(DQMResultEnum.WARNING,f'WARNING: No data for {self.det_head_key} found.')
        
        tmp_df_stream  = df_dict[self.det_head_key]
        tmp_df_stream["ts_check"] = tmp_df_stream.apply(lambda x: 1 if (len(x.ts_diffs_vals)!=1) else 0, axis=1)
        n_bad_stream = tmp_df_stream["ts_check"].sum()

        if n_bad_stream == 0:
            return DQMTestResult(DQMResultEnum.OK,f'OK')
        else:
            if verbose:
                print(tabulate(tmp_df_stream.reset_index()[["trigger","sequence","ts_diffs_vals", "ts_diffs_counts", "ts_check"]],
                                headers=["record","sequence","ts_diffs","ts_diffs_counts","Check"],
                                showindex=False,tablefmt='pretty',floatfmt=".2f"))

            return DQMTestResult(DQMResultEnum.BAD, f'{n_bad_stream} links fail TS difference check.')


class CheckADCData_DAPHNE(DQMTest):

    def __init__(self,det_name,data_type):
        super().__init__()
        self.name = f"CheckADCData_{det_name}_{data_type}"
        self.det_name = det_name
        self.data_type = data_type
        self.det_data_key = f'detd_k{det_name}_k{data_type}'
    
    def run_test(self, df_dict):

        if self.det_data_key not in df_dict.keys():
            return DQMTestResult(DQMResultEnum.WARNING,f'WARNING: No data for {self.det_data_key} found.')
        
        tmp_df_stream  = df_dict[self.det_data_key]
        means = np.array(df_dict[self.det_data_key]["adc_mean"])
        rmss  = np.array(df_dict[self.det_data_key]["adc_rms"])

        if np.any(means == 0) or np.any(rmss == 0):

            n_bad_means = len(means[np.where(means == 0)])
            n_bad_rmss  = len(rmss[np.where(rmss == 0)])
            return DQMTestResult(DQMResultEnum.BAD, f'{max(n_bad_means, n_bad_rmss)} channels have problems')
            
        else:
            return DQMTestResult(DQMResultEnum.OK,f'OK')


        

