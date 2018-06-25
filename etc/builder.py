import os
import sys
from iocbuilder import AutoSubstitution, Device
from iocbuilder.arginfo import makeArgInfo, Simple, Ident, Choice
from iocbuilder.iocinit import IocDataStream
from iocbuilder.modules.asyn import AsynPort
from iocbuilder.modules.ADCore import ADCore, ADBaseTemplate, makeTemplateInstance
from iocbuilder.modules.calc import Calc
from iocbuilder.modules.restClient import restClient
from dls_dependency_tree import dependency_tree
sys.path.append(os.path.dirname(os.path.abspath(__file__)))
#import excalibur
#imp.load_source('excalibur', os.path.join(os.path.dirname(os.path.abspath(__file__)), "excalibur.py"))
from excalibur import ExcaliburProcessPlugin, ExcaliburReceiverPlugin

ADODIN_ROOT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..")
tree = dependency_tree() 
tree.process_module(ADODIN_ROOT)
names, paths = tree.paths(globs=['/'], include_name=True)
for name, path in zip(names, paths):
  if name == 'odin-data':
    FILE_WRITER_ROOT = path
  if name == 'excalibur-detector':
    EXCALIBUR_ROOT = path

print("ADOdin root: {}".format(ADODIN_ROOT))
print("Odind Data root: {}".format(FILE_WRITER_ROOT))
print("Excalibur root: {}".format(EXCALIBUR_ROOT))

#from iocbuilder.modules.odin_data import FileWriterPlugin
#from iocbuilder.modules.excalibur_detector import ExcaliburProcessPlugin, ExcaliburReceiverPlugin

import os
from string import Template


DATA = os.path.join(os.path.dirname(__file__), "../data")

__all__ = ["ExcaliburDetector", "OdinDataServer"]


class FileWriterPlugin(Device):

    """Store configuration for FileWriterPlugin."""

    # Device attributes
    AutoInstantiate = True

    def __init__(self, MACRO):
        self.__super.__init__()
        # Update attributes with parameters
        self.__dict__.update(locals())

    ArgInfo = makeArgInfo(__init__, MACRO=Simple("Dependency MACRO as in configure/RELEASE", str))


    
class OdinDetectorTemplate(AutoSubstitution):
    TemplateFile = "odinDetector.template"


class OdinDetector(AsynPort):

    """Create an odin detector"""

    Dependencies = (ADCore, restClient)

    # This tells xmlbuilder to use PORT instead of name as the row ID
    UniqueName = "PORT"

    def __init__(self, PORT, SERVER, ODIN_SERVER_PORT, DETECTOR, BUFFERS = 0, MEMORY = 0, **args):
        # Init the superclass (AsynPort)
        self.__super.__init__(PORT)
        # Update the attributes of self from the commandline args
        self.__dict__.update(locals())

    # __init__ arguments
    ArgInfo = ADBaseTemplate.ArgInfo + makeArgInfo(__init__,
        PORT=Simple("Port name for the detector", str),
        SERVER=Simple("Server host name", str),
        ODIN_SERVER_PORT=Simple("Odin server port", int),
        DETECTOR=Simple("Name of detector", str),
        BUFFERS=Simple("Maximum number of NDArray buffers to be created for plugin callbacks", int),
        MEMORY=Simple("Max memory to allocate, should be maxw*maxh*nbuffer for driver and all "
                      "attached plugins", int))

    # Device attributes
    LibFileList = ['odinDetector']
    DbdFileList = ['odinDetectorSupport']

    def Initialise(self):
        print "# odinDetectorConfig(const char * portName, const char * serverPort, " \
              "int odinServerPort, const char * detectorName, " \
              "int maxBuffers, size_t maxMemory, int priority, int stackSize)"
        print "odinDetectorConfig(\"%(PORT)s\", \"%(SERVER)s\", " \
              "%(ODIN_SERVER_PORT)d, \"%(DETECTOR)s\", " \
              "%(BUFFERS)d, %(MEMORY)d)" % self.__dict__
              
    def daq_templates(self):
        return None


class ExcaliburDetectorTemplate(AutoSubstitution):
    TemplateFile = "excaliburDetector.template"


class ExcaliburFPTemplate(AutoSubstitution):
    TemplateFile = "excaliburFP.template"


def add_excalibur_fp_template(cls):
    """Convenience function to add excaliburFPTemplate attributes to a class that
    includes it via an msi include statement rather than verbatim"""
    cls.Arguments = ExcaliburFPTemplate.Arguments + \
        [x for x in cls.Arguments if x not in ExcaliburFPTemplate.Arguments]
    cls.ArgInfo = ExcaliburFPTemplate.ArgInfo + cls.ArgInfo.filtered(
        without=ExcaliburFPTemplate.ArgInfo.Names())
    cls.Defaults.update(ExcaliburFPTemplate.Defaults)
    return cls


@add_excalibur_fp_template
class Excalibur2NodeFPTemplate(AutoSubstitution):
    TemplateFile = "excalibur2NodeFP.template"


@add_excalibur_fp_template
class Excalibur4NodeFPTemplate(AutoSubstitution):
    TemplateFile = "excalibur4NodeFP.template"


@add_excalibur_fp_template
class Excalibur8NodeFPTemplate(AutoSubstitution):
    TemplateFile = "excalibur8NodeFP.template"


class ExcaliburFemHousekeepingTemplate(AutoSubstitution):
    TemplateFile = "excaliburFemHousekeeping.template"


class ExcaliburFemStatusTemplate(AutoSubstitution):
    WarnMacros = False
    TemplateFile = "excaliburFemStatus.template"


def add_excalibur_fem_status(cls):
    """Convenience function to add excaliburFemStatusTemplate attributes to a class that
    includes it via an msi include statement rather than verbatim"""
    cls.Arguments = ExcaliburFemStatusTemplate.Arguments + \
        [x for x in cls.Arguments if x not in ExcaliburFemStatusTemplate.Arguments]
    cls.ArgInfo = ExcaliburFemStatusTemplate.ArgInfo + cls.ArgInfo.filtered(
        without=ExcaliburFemStatusTemplate.ArgInfo.Names())
    cls.Defaults.update(ExcaliburFemStatusTemplate.Defaults)
    return cls


@add_excalibur_fem_status
class Excalibur2FemStatusTemplate(AutoSubstitution):
    TemplateFile = "excalibur2FemStatus.template"


@add_excalibur_fem_status
class Excalibur6FemStatusTemplate(AutoSubstitution):
    TemplateFile = "excalibur6FemStatus.template"


class ExcaliburDetector(OdinDetector):

    """Create an Excalibur detector"""

    DETECTOR = "excalibur"
    SENSOR_OPTIONS = {  # (AutoSubstitution Template, Number of FEMs)
        "1M": (Excalibur2FemStatusTemplate, 2),
        "3M": (Excalibur6FemStatusTemplate, 6)
    }

    CONFIG_TEMPLATES = {
        "1M": {
                "ProcessPlugin": "fp_excalibur_1m.json",
                "ReceiverPlugin": "fr_excalibur_1m.json"
              },
        "3M": {
                "ProcessPlugin": "fp_excalibur_3m.json",
                "ReceiverPlugin": "fr_excalibur_3m.json"
              }
    }

    # This tells xmlbuilder to use PORT instead of name as the row ID
    UniqueName = "PORT"

    _SpecificTemplate = ExcaliburDetectorTemplate

    def __init__(self, PORT, SERVER, ODIN_SERVER_PORT, SENSOR, BUFFERS = 0, MEMORY = 0, FEMS_REVERSED = 0, PWR_CARD_IDX = 1, SHARED_MEM_SIZE = 1048576000, NODE_1_NAME = None, NODE_1_CTRL_IP = None, NODE_1_MAC = None, NODE_1_IPADDR = None, NODE_1_PORT = None, NODE_2_NAME = None, NODE_2_CTRL_IP = None, NODE_2_MAC = None, NODE_2_IPADDR = None, NODE_2_PORT = None, NODE_3_NAME = None, NODE_3_CTRL_IP = None, NODE_3_MAC = None, NODE_3_IPADDR = None, NODE_3_PORT = None, NODE_4_NAME = None, NODE_4_CTRL_IP = None, NODE_4_MAC = None, NODE_4_IPADDR = None, NODE_4_PORT = None, NODE_5_NAME = None, NODE_5_CTRL_IP = None, NODE_5_MAC = None, NODE_5_IPADDR = None, NODE_5_PORT = None, NODE_6_NAME = None, NODE_6_CTRL_IP = None, NODE_6_MAC = None, NODE_6_IPADDR = None, NODE_6_PORT = None, NODE_7_NAME = None, NODE_7_CTRL_IP = None, NODE_7_MAC = None, NODE_7_IPADDR = None, NODE_7_PORT = None, NODE_8_NAME = None, NODE_8_CTRL_IP = None, NODE_8_MAC = None, NODE_8_IPADDR = None, NODE_8_PORT = None, **args):
        # Init the superclass (OdinDetector)
        self.__super.__init__(PORT, SERVER, ODIN_SERVER_PORT, self.DETECTOR,
                              BUFFERS, MEMORY, **args)
        # Update the attributes of self from the commandline args
        self.__dict__.update(locals())
        # Make an instance of our template
        makeTemplateInstance(self._SpecificTemplate, locals(), args)

        # Add the FEM housekeeping template
        fem_hk_template = ExcaliburFemHousekeepingTemplate
        fem_hk_args = {
            "P": args["P"],
            "R": args["R"],
            "PORT": PORT,
            "TIMEOUT": args["TIMEOUT"]
        }
        fem_hk_template(**fem_hk_args)
        
        assert SENSOR in self.SENSOR_OPTIONS.keys()
        # Instantiate template corresponding to SENSOR, passing through some of own args
        status_template = self.SENSOR_OPTIONS[SENSOR][0]
        gui_name = PORT[:PORT.find(".")] + ".Status"
        status_args = {
            "P": args["P"],
            "R": args["R"],
            "ADDRESS": "0",
            "PORT": PORT,
            "NAME": gui_name,
            "TIMEOUT": args["TIMEOUT"],
            "TOTAL": self.SENSOR_OPTIONS[SENSOR][1]
        }
        status_template(**status_args)
        
        self.create_udp_file()
        self.create_odin_server_config_file()
        self.create_fr_startup_scripts()
        self.create_fp_startup_scripts()

    def daq_templates(self):
        print str(self.CONFIG_TEMPLATES[self.SENSOR])
        return self.CONFIG_TEMPLATES[self.SENSOR]

    def create_udp_file(self):
        output_file = IocDataStream("udp_excalibur.json")
        names = [self.NODE_1_NAME, self.NODE_2_NAME, self.NODE_3_NAME, self.NODE_4_NAME, self.NODE_5_NAME, self.NODE_6_NAME, self.NODE_7_NAME, self.NODE_8_NAME]
        macs = [self.NODE_1_MAC, self.NODE_2_MAC, self.NODE_3_MAC, self.NODE_4_MAC, self.NODE_5_MAC, self.NODE_6_MAC, self.NODE_7_MAC, self.NODE_8_MAC]
        ips = [self.NODE_1_IPADDR, self.NODE_2_IPADDR, self.NODE_3_IPADDR, self.NODE_4_IPADDR, self.NODE_5_IPADDR, self.NODE_6_IPADDR, self.NODE_7_IPADDR, self.NODE_8_IPADDR]
        ports = [self.NODE_1_PORT, self.NODE_2_PORT, self.NODE_3_PORT, self.NODE_4_PORT, self.NODE_5_PORT, self.NODE_6_PORT, self.NODE_7_PORT, self.NODE_8_PORT]
        number_of_nodes = 0
        output_text = '{\n\
    "fems": [\n'
        for index in [1,2,3,4,5,6]:
            offset = index - 1
            output_text = output_text + '        {{\n\
            "name": "fem{}",\n\
            "mac": "62:00:00:00:00:0{}",\n\
            "ipaddr": "10.0.2.10{}",\n\
            "port": 6000{},\n\
            "dest_port_offset": {}\n\
        }}'.format(index, index, index, index, offset)
            if index < 6:
                output_text = output_text + ',\n'
            else:
                output_text = output_text + '\n'
        output_text = output_text + '    ],\n\
    "nodes": [\n'
        for NAME, MAC, IPADDR, PORT in zip(names, macs, ips, ports):
            if NAME is not None:
                output_text = output_text + '        {{\n\
            "name": "{}",\n\
            "mac" : "{}",\n\
            "ipaddr" : "{}",\n\
            "port": {}\n\
        }},\n'.format(NAME, MAC, IPADDR, PORT)
                number_of_nodes += 1
        output_text = output_text[:-2]
        output_text = output_text + '\n    ],\n\
    "farm_mode" : {{\n\
        "enable": 1,\n\
        "num_dests": {}\n\
    }}\n\
}}\n'.format(number_of_nodes)
        output_file.write(output_text)

    def create_odin_server_config_file(self):
        ips = [self.NODE_1_CTRL_IP, self.NODE_2_CTRL_IP, self.NODE_3_CTRL_IP, self.NODE_4_CTRL_IP, self.NODE_5_CTRL_IP, self.NODE_6_CTRL_IP, self.NODE_7_CTRL_IP, self.NODE_8_CTRL_IP]
        output_file = IocDataStream("excalibur_odin_{}.cfg".format(self.SENSOR))
        if self.SENSOR == '1M':
            if self.FEMS_REVERSED == 0:
                fem_list = '192.168.0.101:6969, 192.168.0.102:6969'
            else:
                fem_list = '192.168.0.102:6969, 192.168.0.101:6969'
        if self.SENSOR == '3M':
            if self.FEMS_REVERSED == 0:
                fem_list = '192.168.0.101:6969, 192.168.0.102:6969, 192.168.0.103:6969, 192.168.0.104:6969, 192.168.0.105:6969, 192.168.0.106:6969'
            else:
                fem_list = '192.168.0.106:6969, 192.168.0.105:6969, 192.168.0.104:6969, 192.168.0.103:6969, 192.168.0.102:6969, 192.168.0.101:6969'
        
        # Loop over the UDP destinations, for each one setup a FP and FR control address
        # FP ports will always start 5004 and increment by 10
        # FR ports will always start 5000 and increment by 10
        fp_server_count = {}
        fp_ctrl_addresses = {}
        fr_endpoints = ""
        fp_endpoints = ""
        for ip in ips:
            if ip is not None:
                if ip not in fp_server_count:
                    fp_server_count[ip] = 0
                fp_port_number = 5004 + (10 * fp_server_count[ip])
                fr_port_number = 5000 + (10 * fp_server_count[ip])
                fp_server_count[ip] += 1
                fr_endpoints = fr_endpoints + ", {}:{}".format(ip, fr_port_number)
                fp_endpoints = fp_endpoints + ", {}:{}".format(ip, fp_port_number)
        fr_endpoints = fr_endpoints[2:]
        fp_endpoints = fp_endpoints[2:]
        print(fr_endpoints)
        print(fp_endpoints)


        output_text = '[server]\n\
debug_mode  = 1\n\
http_port   = 8888\n\
http_addr   = 0.0.0.0\n\
adapters    = excalibur, fp, fr\n\
\n\
[tornado]\n\
logging = error\n\
\n\
[adapter.excalibur]\n\
module = excalibur.adapter.ExcaliburAdapter\n\
detector_fems = {}\n\
powercard_fem_idx = {}\n\
chip_enable_mask = 0xFF, 0xFF\n\
\n\
[adapter.fp]\n\
module = odin_data.frame_processor_adapter.FrameProcessorAdapter\n\
endpoints = {}\n\
update_interval = 0.5\n\
\n\
[adapter.fr]\n\
module = odin_data.odin_data_adapter.OdinDataAdapter\n\
endpoints = {}\n\
update_interval = 0.5\n\
\n'.format(fem_list, self.PWR_CARD_IDX, fp_endpoints, fr_endpoints)
        output_file.write(output_text)

    def create_fr_startup_scripts(self):
        ips = [self.NODE_1_CTRL_IP, self.NODE_2_CTRL_IP, self.NODE_3_CTRL_IP, self.NODE_4_CTRL_IP, self.NODE_5_CTRL_IP, self.NODE_6_CTRL_IP, self.NODE_7_CTRL_IP, self.NODE_8_CTRL_IP]
        fr_server_count = {}
        counter = 0
        for ip in ips:
            if ip is not None:
                counter += 1
                if ip not in fr_server_count:
                    fr_server_count[ip] = 0
                fr_port_number = 5000 + (10 * fr_server_count[ip])
                fr_server_count[ip] += 1
                output_file = IocDataStream("st_fr_{}.sh".format(counter))
                bin_path = os.path.join(FILE_WRITER_ROOT, "prefix")
                data_path = os.path.join(ADODIN_ROOT, "data")
                output_text = '#!/bin/bash\n\
cd {}\n\
./bin/frameReceiver --sharedbuf=exc_buf_{} -m {} --ctrl=tcp://0.0.0.0:{} --logconfig {}/fr_log4cxx.xml\n'.format(bin_path, counter, self.SHARED_MEM_SIZE, fr_port_number, data_path)
                output_file.write(output_text)
                print(output_text)

    def create_fp_startup_scripts(self):
        ips = [self.NODE_1_CTRL_IP, self.NODE_2_CTRL_IP, self.NODE_3_CTRL_IP, self.NODE_4_CTRL_IP, self.NODE_5_CTRL_IP, self.NODE_6_CTRL_IP, self.NODE_7_CTRL_IP, self.NODE_8_CTRL_IP]
        fp_server_count = {}
        counter = 0
        for ip in ips:
            if ip is not None:
                counter += 1
                if ip not in fp_server_count:
                    fp_server_count[ip] = 0
                fp_port_number = 5004 + (10 * fp_server_count[ip])
                fp_server_count[ip] += 1
                output_file = IocDataStream("st_fp_{}.sh".format(counter))
                bin_path = os.path.join(FILE_WRITER_ROOT, "prefix")
                data_path = os.path.join(ADODIN_ROOT, "data")
                output_text = '#!/bin/bash\n\
cd {}\n\
./bin/frameProcessor --ctrl=tcp://0.0.0.0:{} --logconfig {}/fp_log4cxx.xml\n'.format(bin_path, fp_port_number, data_path)
                output_file.write(output_text)
                print(output_text)

    # __init__ arguments
    ArgInfo = ADBaseTemplate.ArgInfo + _SpecificTemplate.ArgInfo + makeArgInfo(__init__,
        PORT=Simple("Port name for the detector", str),
        SERVER=Simple("Server host name", str),
        ODIN_SERVER_PORT=Simple("Odin server port", int),
        SENSOR=Choice("Sensor type", ["1M", "3M"]),
        BUFFERS=Simple("Maximum number of NDArray buffers to be created for plugin callbacks", int),
        MEMORY=Simple("Max memory to allocate, should be maxw*maxh*nbuffer for driver and all "
                      "attached plugins", int),
        FEMS_REVERSED=Simple("Are the FEM IP addresses reversed 106..101", int),
        PWR_CARD_IDX=Simple("Index of the power card", int),
        SHARED_MEM_SIZE=Simple("Size of shared memory buffers in bytes", int),
        NODE_1_NAME=Simple("Name of detector output node 1", str),
        NODE_1_CTRL_IP=Simple("IP address for control of FR and FP", str),
        NODE_1_MAC=Simple("Mac address of detector output node 1", str),
        NODE_1_IPADDR=Simple("IP address of detector output node 1", str),
        NODE_1_PORT=Simple("Port of detector output node 1", int),
        NODE_2_NAME=Simple("Name of detector output node 2", str),
        NODE_2_CTRL_IP=Simple("IP address for control of FR and FP", str),
        NODE_2_MAC=Simple("Mac address of detector output node 2", str),
        NODE_2_IPADDR=Simple("IP address of detector output node 2", str),
        NODE_2_PORT=Simple("Port of detector output node 2", int),
        NODE_3_NAME=Simple("Name of detector output node 3", str),
        NODE_3_CTRL_IP=Simple("IP address for control of FR and FP", str),
        NODE_3_MAC=Simple("Mac address of detector output node 3", str),
        NODE_3_IPADDR=Simple("IP address of detector output node 3", str),
        NODE_3_PORT=Simple("Port of detector output node 3", int),
        NODE_4_NAME=Simple("Name of detector output node 4", str),
        NODE_4_CTRL_IP=Simple("IP address for control of FR and FP", str),
        NODE_4_MAC=Simple("Mac address of detector output node 4", str),
        NODE_4_IPADDR=Simple("IP address of detector output node 4", str),
        NODE_4_PORT=Simple("Port of detector output node 4", int),
        NODE_5_NAME=Simple("Name of detector output node 5", str),
        NODE_5_CTRL_IP=Simple("IP address for control of FR and FP", str),
        NODE_5_MAC=Simple("Mac address of detector output node 5", str),
        NODE_5_IPADDR=Simple("IP address of detector output node 5", str),
        NODE_5_PORT=Simple("Port of detector output node 5", int),
        NODE_6_NAME=Simple("Name of detector output node 6", str),
        NODE_6_CTRL_IP=Simple("IP address for control of FR and FP", str),
        NODE_6_MAC=Simple("Mac address of detector output node 6", str),
        NODE_6_IPADDR=Simple("IP address of detector output node 6", str),
        NODE_6_PORT=Simple("Port of detector output node 6", int),
        NODE_7_NAME=Simple("Name of detector output node 7", str),
        NODE_7_CTRL_IP=Simple("IP address for control of FR and FP", str),
        NODE_7_MAC=Simple("Mac address of detector output node 7", str),
        NODE_7_IPADDR=Simple("IP address of detector output node 7", str),
        NODE_7_PORT=Simple("Port of detector output node 7", int),
        NODE_8_NAME=Simple("Name of detector output node 8", str),
        NODE_8_CTRL_IP=Simple("IP address for control of FR and FP", str),
        NODE_8_MAC=Simple("Mac address of detector output node 8", str),
        NODE_8_IPADDR=Simple("IP address of detector output node 8", str),
        NODE_8_PORT=Simple("Port of detector output node 8", int))


class OdinDataTemplate(AutoSubstitution):
    TemplateFile = "odinData.template"


class OdinData(Device):

    """Store configuration for an OdinData process"""
    INDEX = 1  # Unique index for each OdinData instance

    # Device attributes
    AutoInstantiate = True

    def __init__(self, IP, READY, RELEASE, META):
        self.__super.__init__()
        # Update attributes with parameters
        self.__dict__.update(locals())

        # Create unique R MACRO for template file - OD1, OD2 etc.
        self.R = ":OD{}:".format(self.INDEX)
        self.index = OdinData.INDEX
        OdinData.INDEX += 1

    def create_config_file(self, prefix, template, index, extra_macros=None):
        macros = dict(IP=self.IP, RD_PORT=self.READY, RL_PORT=self.RELEASE,
                      FW_ROOT=FILE_WRITER_ROOT, PP_ROOT=EXCALIBUR_ROOT)
        if extra_macros is not None:
            macros.update(extra_macros)
        with open(os.path.join(DATA, template)) as template_file:
            template_config = Template(template_file.read())

        output = template_config.substitute(macros)

        output_file = IocDataStream("{}{}.json".format(prefix, index))
        output_file.write(output)


class OdinDataServer(Device):

    """Store configuration for an OdinDataServer"""
    PORT_BASE = 5000

    # Device attributes
    AutoInstantiate = True

    def __init__(self, IP, PROCESSES):
        self.__super.__init__()
        # Update attributes with parameters
        self.__dict__.update(locals())

        self.processes = []
        for _ in range(PROCESSES):
            self.processes.append(
                OdinData(IP, self.PORT_BASE + 1, self.PORT_BASE + 2, self.PORT_BASE + 3)
            )
            self.PORT_BASE += 10

        self.instantiated = False  # Make sure instances are only used once

    ArgInfo = makeArgInfo(__init__,
                          IP=Simple("IP address of server hosting processes", str),
                          PROCESSES=Simple("Number of OdinData processes on this server", int))


class OdinDataDriverTemplate(AutoSubstitution):
    TemplateFile = "odinDataDriver.template"


class OdinDataDriver(AsynPort):

    """Create an OdinData driver"""
    Dependencies = (ADCore, Calc, restClient, FileWriterPlugin)

    # This tells xmlbuilder to use PORT instead of name as the row ID
    UniqueName = "PORT"

    _SpecificTemplate = OdinDataDriverTemplate

    def __init__(self, PORT, SERVER, ODIN_SERVER_PORT, PROCESS_PLUGIN, RECEIVER_PLUGIN, FILE_WRITER, DATASET="data",
                 DETECTOR=None,
                 ODIN_DATA_SERVER_1=None, ODIN_DATA_SERVER_2=None, ODIN_DATA_SERVER_3=None,
                 ODIN_DATA_SERVER_4=None, ODIN_DATA_SERVER_5=None, ODIN_DATA_SERVER_6=None,
                 ODIN_DATA_SERVER_7=None, ODIN_DATA_SERVER_8=None,
                 BUFFERS = 0, MEMORY = 0, **args):
        # Init the superclass (AsynPort)
        self.__super.__init__(PORT)
        # Update the attributes of self from the commandline args
        self.__dict__.update(locals())
        # Make an instance of our template
        makeTemplateInstance(self._SpecificTemplate, locals(), args)

        self.FILE_WRITER_MACRO = FILE_WRITER.MACRO
        self.DETECTOR = PROCESS_PLUGIN.NAME
        self.PROCESS_PLUGIN_MACRO = PROCESS_PLUGIN.MACRO

        self.ODIN_DATA_PROCESSES = []

        # Count the number of servers
        self.server_count = 0
        for idx in range(1, 9):
            server = eval("ODIN_DATA_SERVER_{}".format(idx))
            if server is not None:
                self.server_count += 1
        print("Server count: {}".format(self.server_count))

        for idx in range(1, 9):
            server = eval("ODIN_DATA_SERVER_{}".format(idx))
            if server is not None:
                if server.instantiated:
                    raise ValueError("Same OdinDataServer object given twice")
                else:
                    server.instantiated = True

                port_number=61649
                index_number = 0
                for odin_data in server.processes:
                    address = idx + index_number - 1
                    print("Odin data idx: {}  index_number: {}  address: {}".format(idx, index_number, address))
                    self.ODIN_DATA_PROCESSES.append(odin_data)
                    # Use some OdinDataDriver macros to instantiate an odinData.template
                    args["PORT"] = PORT
                    args["ADDR"] = odin_data.index-1
                    args["R"] = odin_data.R
                    OdinDataTemplate(**args)

                    detector = eval("DETECTOR")
                    daq_templates = detector.daq_templates()
                    if daq_templates is not None:
                        port_number_1 = port_number
                        port_number_2 = port_number+1
                        port_number_3 = port_number+2
                        port_number_4 = port_number+3
                        port_number_5 = port_number+4
                        port_number_6 = port_number+5
                        port_number += 6
                        macros = dict(RX_PORT_1=port_number_1,
                                      RX_PORT_2=port_number_2,
                                      RX_PORT_3=port_number_3,
                                      RX_PORT_4=port_number_4,
                                      RX_PORT_5=port_number_5,
                                      RX_PORT_6=port_number_6)
                        odin_data.create_config_file('fp', daq_templates["ProcessPlugin"], address+1)
                        odin_data.create_config_file('fr', daq_templates["ReceiverPlugin"], address+1, extra_macros=macros)
                    index_number += self.server_count

    # __init__ arguments
    ArgInfo = ADBaseTemplate.ArgInfo + _SpecificTemplate.ArgInfo + makeArgInfo(__init__,
        PORT=Simple("Port name for the detector", str),
        SERVER=Simple("Server host name", str),
        ODIN_SERVER_PORT=Simple("Odin server port", int),
        DETECTOR=Ident("Detector configuration", OdinDetector),
        PROCESS_PLUGIN=Ident("Odin detector configuration", ExcaliburProcessPlugin),
        RECEIVER_PLUGIN=Ident("Odin detector configuration", ExcaliburReceiverPlugin),
        FILE_WRITER=Ident("FileWriterPlugin configuration", FileWriterPlugin),
        DATASET=Simple("Name of Dataset", str),
        ODIN_DATA_SERVER_1=Ident("OdinDataServer 1 configuration", OdinDataServer),
        ODIN_DATA_SERVER_2=Ident("OdinDataServer 2 configuration", OdinDataServer),
        ODIN_DATA_SERVER_3=Ident("OdinDataServer 3 configuration", OdinDataServer),
        ODIN_DATA_SERVER_4=Ident("OdinDataServer 4 configuration", OdinDataServer),
        ODIN_DATA_SERVER_5=Ident("OdinDataServer 5 configuration", OdinDataServer),
        ODIN_DATA_SERVER_6=Ident("OdinDataServer 6 configuration", OdinDataServer),
        ODIN_DATA_SERVER_7=Ident("OdinDataServer 7 configuration", OdinDataServer),
        ODIN_DATA_SERVER_8=Ident("OdinDataServer 8 configuration", OdinDataServer),
        BUFFERS=Simple("Maximum number of NDArray buffers to be created for plugin callbacks", int),
        MEMORY=Simple("Max memory to allocate, should be maxw*maxh*nbuffer for driver and all "
                      "attached plugins", int))

    # Device attributes
    LibFileList = ['odinDetector']
    DbdFileList = ['odinDetectorSupport']

    def Initialise(self):
        # Configure up to 8 OdinData processes
        print "# odinDataProcessConfig(const char * ipAddress, int readyPort, " \
              "int releasePort, int metaPort)"
        for process in self.ODIN_DATA_PROCESSES:
            print "odinDataProcessConfig(\"%(IP)s\", %(READY)d, " \
                  "%(RELEASE)d, %(META)d)" % process.__dict__

        print "# odinDataDriverConfig(const char * portName, const char * serverPort, " \
              "int odinServerPort, " \
              "const char * datasetName, const char * detectorName, " \
              "int maxBuffers, size_t maxMemory)"
        print "odinDataDriverConfig(\"%(PORT)s\", \"%(SERVER)s\", " \
              "%(ODIN_SERVER_PORT)d, " \
              "\"%(DATASET)s\", \"%(DETECTOR)s\", " \
              "%(BUFFERS)d, %(MEMORY)d)" % self.__dict__

              
class FrameProcessor(Device):

    def __init__(self, IOC, LOG_CFG):
        self.__super.__init__()
        # Update attributes with parameters
        self.__dict__.update(locals())
        self.create_startup_file()

    def create_startup_file(self):
        macros = dict(LOG_CFG=self.LOG_CFG, FW_ROOT=FILE_WRITER_ROOT)
        template_config = Template('#!/bin/bash\n\
cd $FW_ROOT\n\
./bin/frameProcessor --logconfig $LOG_CFG\n')

        output = template_config.substitute(macros)

        output_file = IocDataStream("st{}.sh".format(self.IOC))
        output_file.write(output)

    # __init__ arguments
    ArgInfo = makeArgInfo(__init__,
        IOC=Simple("Name of the IOC", str),
        LOG_CFG=Simple("Full path to the Log configuration file", str))



