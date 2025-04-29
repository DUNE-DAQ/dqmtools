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

class CheckTimestampDiffs_DAPHNE(DQMTest):
    def __init__(self):
        super().__init__()
        self.name = "CheckTimestampDiffs_DAPHNE"

    def run_test(self, df_dict, verbose=False):

        n_bad_stream, n_bad = 0, 0

        if "detd_kHD_PDS_kDAPHNEStream" not in df_dict.keys() and "detd_kHD_PDS_kDAPHNE" not in df_dict.keys():
            return DQMTestResult(DQMResultEnum.WARNING,f'WARNING: No data for DAPHNE found.')
        
        if "deth_kHD_PDS_kDAPHNEStream" in df_dict.keys():

            tmp_df_stream  = df_dict["deth_kHD_PDS_kDAPHNEStream"]
            tmp_df_stream["ts_check"] = tmp_df_stream.apply(lambda x: 1 if (len(x.ts_diffs_vals)!=1) else 0, axis=1)
            n_bad_stream = tmp_df_stream["ts_check"].sum()

        if "deth_kHD_PDS_kDAPHNE" in df_dict.keys():

            tmp_df  = df_dict["deth_kHD_PDS_kDAPHNEStream"]
            tmp_df["ts_check"] = tmp_df.apply(lambda x: 1 if (len(x.ts_diffs_vals)!=1) else 0, axis=1)
            n_bad = tmp_df["ts_check"].sum()

        if n_bad == 0 and n_bad_stream == 0:
            return DQMTestResult(DQMResultEnum.OK,f'OK')
        else:
            if verbose:
                if n_bad != 0:
                    print(tabulate(tmp_df.reset_index()[["trigger","sequence","ts_diffs_vals", "ts_diffs_counts", "ts_check"]],
                                   headers=["record","sequence","ts_diffs","ts_diffs_counts","Check"],
                                   showindex=False,tablefmt='pretty',floatfmt=".2f"))
                elif n_bad_stream != 0:
                    print(tabulate(tmp_df_stream.reset_index()[["trigger","sequence","ts_diffs_vals", "ts_diffs_counts", "ts_check"]],
                                   headers=["record","sequence","ts_diffs","ts_diffs_counts","Check"],
                                   showindex=False,tablefmt='pretty',floatfmt=".2f"))

            return DQMTestResult(DQMResultEnum.BAD, f'{n_bad+n_bad_stream} links fail TS difference check.')


class CheckADCData_DAPHNE(DQMTest):

    def __init__(self):
        super().__init__()
        self.name = "CheckADCData_DAPHNE"
    
    def run_test(self, df_dict):

        if "detd_kHD_PDS_kDAPHNEStream" not in df_dict.keys() and "detd_kHD_PDS_kDAPHNE" not in df_dict.keys():
            return DQMTestResult(DQMResultEnum.WARNING,f'WARNING: No data for DAPHNE found.')
        
        elif "detd_kHD_PDS_kDAPHNEStream" in df_dict.keys():

            tmp_df_stream  = df_dict["detd_kHD_PDS_kDAPHNEStream"]
            means = np.array(df_dict["detd_kHD_PDS_kDAPHNEStream"]["adc_mean"])
            rmss  = np.array(df_dict["detd_kHD_PDS_kDAPHNEStream"]["adc_rms"])

            if np.any(means) == 0 or np.any(rmss) == 0:

                n_bad_means_stream = len(means[np.where(means == 0)])
                n_bad_rmss_stream  = len(rmss[np.where(rmss == 0)])
                return DQMTestResult(DQMResultEnum.BAD, f'{np.max(n_bad_means_stream, n_bad_rmss_stream)} channels have problems')
            
            else:
                return DQMTestResult(DQMResultEnum.OK,f'OK')
            
        else:

            tmp_df_stream  = df_dict["detd_kHD_PDS_kDAPHNE"]
            means = np.array(df_dict["detd_kHD_PDS_kDAPHNE"]["adc_mean"])
            rmss  = np.array(df_dict["detd_kHD_PDS_kDAPHNE"]["adc_rms"])

            if np.any(means) == 0 or np.any(rmss) == 0:

                n_bad_means = len(means[np.where(means == 0)])
                n_bad_rmss  = len(rmss[np.where(rmss == 0)])
                return DQMTestResult(DQMResultEnum.BAD, f'{np.max(n_bad_means, n_bad_rmss)} channels have problems')
            
            else:
                return DQMTestResult(DQMResultEnum.OK,f'OK')


        

