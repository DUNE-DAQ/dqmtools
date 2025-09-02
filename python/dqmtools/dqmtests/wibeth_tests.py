from dqmtools.dqmtools import *
from rawdatautils.unpack.dataclasses import *

import numpy as np
import operator

class CheckTimestampDiffs_WIBEth(DQMTest):
    
    def __init__(self,det_name):
        super().__init__()
        self.name = f'CheckTimestampDiffs_WIBEth_{det_name}'
        self.det_head_key=f'deth_k{det_name}_kWIBEth'
        
    def run_test(self,df_dict):

        if self.det_head_key not in df_dict.keys():
            return DQMTestResult(DQMResultEnum.WARNING,f'Could not find {self.det_head_key} in DataFrame dict.')
        
        df_tmp = df_dict[self.det_head_key]
        df_tmp["ts_diff_wrong"] = df_tmp.apply(lambda x: (x.timestamp_dts_diff_vals!=x.sampling_period).sum(), axis=1)
        n_ts_diff_wrong = df_tmp["ts_diff_wrong"].sum()
        if n_ts_diff_wrong==0:
            return DQMTestResult(DQMResultEnum.OK,f'OK')
        else:
            return DQMTestResult(DQMResultEnum.BAD,
                                 f'{n_ts_diff_wrong} / {len(df_tmp)} fragments have bad timestamp differences.')

class CheckWIBEth_COLDDATA_Timestamps_Aligned(DQMTest):

    def __init__(self,det_name):
        super().__init__()
        self.name = f'CheckWIBEth_COLDDATA_Timestamps_Aligned_{det_name}'
        self.det_head_key=f'deth_k{det_name}_kWIBEth'

    def run_test(self,df_dict):

        if self.det_head_key not in df_dict.keys():
            return DQMTestResult(DQMResultEnum.WARNING,f'Could not find {self.det_head_key} in DataFrame dict.')

        df_tmp = df_dict[self.det_head_key]
        df_tmp["timestamp_dts_first_15bit"] = df_tmp["timestamp_dts_first"] & 0x7fff
        df_tmp["ts_diff_cd0_dts"] = df_tmp["timestamp_dts_first_15bit"]-df_tmp["colddata_timestamp_0_first"]
        df_tmp["ts_diff_cd1_dts"] = df_tmp["timestamp_dts_first_15bit"]-df_tmp["colddata_timestamp_1_first"]
        
        df_tmp = df_tmp[ (df_tmp["ts_diff_cd0_dts"]!=0) | (df_tmp["ts_diff_cd1_dts"]!=0) ]

        if len(df_tmp)==0:
            return DQMTestResult(DQMResultEnum.OK,f'OK')
        else:
            return DQMTestResult(DQMResultEnum.BAD,
                                 f'{len(df_tmp)} COLDDATA timestamps across {len(df_tmp)} fragments have bad timestamp differences relative to DTS.')

        
class CheckWIBEth_Header_Value(DQMTest):
    
    def __init__(self,det_name,field,good_value):
        super().__init__()
        self.name = f'CheckWIBEth_Header_Value_{det_name}'
        self.det_head_key=f'deth_k{det_name}_kWIBEth'
        self.header_field = field
        self.good_value = good_value

    def run_test(self,df_dict):

        if self.det_head_key not in df_dict.keys():
            return DQMTestResult(DQMResultEnum.WARNING,f'Could not find {self.det_head_key} in DataFrame dict.')
        
        df_tmp = df_dict[self.det_head_key].rename(columns={f"{self.header_field}_vals":"vals",f"{self.header_field}_idx":"idx"})
        df_tmp["n_empty"] = df_tmp.apply(lambda x: (1 if x.vals == [] else 0), axis=1)
        n_empty_err = df_tmp["n_empty"].sum()
        if n_empty_err != 0:
            print(df_tmp[["vals","idx"]])
            return DQMTestResult(DQMResultEnum.BAD,
                                 f'{n_empty_err} {self.header_field}!={self.good_value} errors across {len(df_tmp)} fragments.')
        
        df_tmp["n_err"] = df_tmp.apply(lambda x: (x.vals!=self.good_value).sum(), axis=1)
        n_total_err = df_tmp["n_err"].sum()
        if n_total_err==0:
            return DQMTestResult(DQMResultEnum.OK,f'OK')
        else:
            print(df_tmp[["vals","idx"]])
            return DQMTestResult(DQMResultEnum.BAD,
                                 f'{n_total_err} {self.header_field}!={self.good_value} errors across {len(df_tmp)} fragments.')

        
class CheckWIBEth_COLDDATA_Timestamp_0_Diff(CheckWIBEth_Header_Value):
    
    def __init__(self,det_name):
        super().__init__(det_name,"colddata_timestamp_0_diff",512/16*64)
        self.name = f'CheckWIBEth_COLDDATA_Timestamp_0_Diff_{det_name}'
        
class CheckWIBEth_COLDDATA_Timestamp_1_Diff(CheckWIBEth_Header_Value):
    
    def __init__(self,det_name):
        super().__init__(det_name,"colddata_timestamp_1_diff",512/16*64)
        self.name = f'CheckWIBEth_COLDDATA_Timestamp_1_Diff_{det_name}'
        
class CheckWIBEth_CRC_Err(CheckWIBEth_Header_Value):
    
    def __init__(self,det_name):
        super().__init__(det_name,"crc_err",0)
        self.name = f'CheckWIBEth_CRC_Err_{det_name}'
        
class CheckWIBEth_Pulser(CheckWIBEth_Header_Value):
    
    def __init__(self,det_name):
        super().__init__(det_name,"pulser",0)
        self.name = f'CheckWIBEth_Pulser_{det_name}'

class CheckWIBEth_Calibration(CheckWIBEth_Header_Value):
    
    def __init__(self,det_name):
        super().__init__(det_name,"calibration",0)
        self.name = f'CheckWIBEth_Calibration_{det_name}'

class CheckWIBEth_Ready(CheckWIBEth_Header_Value):
    
    def __init__(self,det_name):
        super().__init__(det_name,"ready",0)
        self.name = f'CheckWIBEth_Ready_{det_name}'

class CheckWIBEth_Context(CheckWIBEth_Header_Value):
    
    def __init__(self,det_name):
        super().__init__(det_name,"context",0)
        self.name = f'CheckWIBEth_Context_{det_name}'
        
class CheckWIBEth_CD(CheckWIBEth_Header_Value):
    
    def __init__(self,det_name):
        super().__init__(det_name,"cd",0)
        self.name = f'CheckWIBEth_CD_{det_name}'

class CheckWIBEth_Link_Valid(CheckWIBEth_Header_Value):
    
    def __init__(self,det_name):
        super().__init__(det_name,"link_valid",3)
        self.name = f'CheckWIBEth_Link_Valid_{det_name}'

class CheckWIBEth_LOL(CheckWIBEth_Header_Value):
    
    def __init__(self,det_name):
        super().__init__(det_name,"lol",0)
        self.name = f'CheckWIBEth_LOL_{det_name}'

class CheckWIBEth_WIB_Sync(CheckWIBEth_Header_Value):
    
    def __init__(self,det_name):
        super().__init__(det_name,"wib_sync",0)
        self.name = f'CheckWIBEth_WIB_Sync_{det_name}'

class CheckWIBEth_FEMB_Sync(CheckWIBEth_Header_Value):
    
    def __init__(self,det_name):
        super().__init__(det_name,"femb_sync",3)
        self.name = f'CheckWIBEth_FEMB_Sync_{det_name}'

class CheckRequestTimes_WIBEth(DQMTest):

    def __init__(self,det_name,verbose=True):
        super().__init__()
        self.name = f'CheckRequestTimes_WIBEth'
        self.deth_name=f'deth_k{det_name}_kWIBEth'
        self.verbose = verbose

    def run_test(self,df_dict):
        df_tmp = df_dict["frh"].loc[df_dict["frh"]["fragment_type"]==12][["window_begin_dts","window_end_dts"]]
        if len(df_tmp)==0:
            return DQMTestResult(DQMResultEnum.WARNING,f'WARNING: No components with detid {self.det_id} found.')
        df_tmp = df_tmp.join(df_dict[self.deth_name][["timestamp_dts_diff_vals","timestamp_dts_diff_idx","timestamp_dts_first","n_frames"]])
        print(df_tmp.iloc[0]["timestamp_dts_first"],df_tmp.iloc[0]["timestamp_dts_diff_vals"],df_tmp.iloc[0]["timestamp_dts_diff_idx"])
        df_tmp["timestamp_dts_last"] = df_tmp.apply(lambda x: desparsify_array_diff_of_diff_locs_and_vals(x.timestamp_dts_first,x.timestamp_dts_diff_idx,x.timestamp_dts_diff_vals,x.n_frames*64)[-1],axis=1)

        df_bad = df_tmp.loc[(df_tmp["timestamp_dts_first"]>(df_tmp["window_begin_dts"]+32))|(df_tmp["timestamp_dts_last"]<(df_tmp["window_end_dts"]-32))]
        n_bad = len(df_bad)
        
        if n_bad==0:
            return DQMTestResult(DQMResultEnum.OK,f'OK')
        else:
            if self.verbose:
                df_bad = df_bad.join(df_dict["daqh"])
                print(f"\nFRAGMENTS FAILING WIBETH WINDOW ALIGNMENT CHECK")
                print(tabulate(df_bad.reset_index()[["trigger","sequence","crate_id","slot_id","stream_id",
                                                     "timestamp_dts_first","timestamp_dts_last",
                                                     "window_begin_dts","window_end_dts"]].astype('int64'),
                                headers=["Record","Seq.","Crate","Slot","Stream",
                                         "Timestamp (first)","Timestamp (last)",
                                         "Window begin","Window end"],
                                showindex=False,tablefmt='pretty'))

            return DQMTestResult(DQMResultEnum.BAD,
                                 f'{n_bad} / {len(df_tmp)} WIBEth fragments have misaligned request windows.')
