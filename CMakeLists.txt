cmake_minimum_required(VERSION 3.12 FATAL_ERROR)
project(dqmtools VERSION 0.3.0)

find_package(daq-cmake REQUIRED)
find_package(fmt REQUIRED)
find_package(Boost COMPONENTS unit_test_framework REQUIRED)
find_package(rawdatautils REQUIRED)
find_package(detdataformats REQUIRED)
find_package(hdf5libs REQUIRED)

daq_setup_environment()

##############################################################################
# Main library
#daq_add_library (WIBFragmentDecoder.cpp LINK_LIBRARIES)

##############################################################################
#daq_add_python_bindings(*.cpp LINK_LIBRARIES ${PROJECT_NAME} daqdataformats::daqdataformats detdataformats::detdataformats fddetdataformats::fddetdataformats fmt::fmt)

#daq_add_unit_test(WIBtoWIB2_test LINK_LIBRARIES detdataformats::detdataformats fddetdataformats::fddetdataformats)

##############################################################################
# Applications
# daq_add_application(hdf5_demo_tpc_decoder demo_tpc_decoder.cpp LINK_LIBRARIES ${PROJECT_NAME})
# daq_add_application(hdf5_demo_pd_decoder demo_pd_decoder.cpp LINK_LIBRARIES ${PROJECT_NAME})

daq_install()
