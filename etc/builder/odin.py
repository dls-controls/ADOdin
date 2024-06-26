from iocbuilder import AutoSubstitution, Device
from iocbuilder.arginfo import makeArgInfo, Simple, Ident, Choice
from iocbuilder.iocinit import IocDataStream
from iocbuilder.modules.asyn import AsynPort
from iocbuilder.modules.ADCore import ADCore, ADBaseTemplate, makeTemplateInstance
from iocbuilder.modules.restClient import restClient
from iocbuilder.modules.calc import Calc

from util import (
    debug_print,
    OdinPaths,
    data_file_path,
    expand_template_file,
    create_config_entry,
    write_batch_file,
    ADODIN_ROOT,
)


# ~~~~~~~~ #
# OdinData #
# ~~~~~~~~ #

debug_print(
    "OdinData: \n{}\n{}".format(OdinPaths.ODIN_DATA_TOOL, OdinPaths.ODIN_DATA_PYTHON),
    1
)

DETECTOR_CHOICES = Choice(
    "Detector type",
    [
        "Excalibur1M",
        "Excalibur3M",
        "Eiger500K",
        "Eiger4M",
        "Eiger9M",
        "Eiger16M",
        "Tristan1M",
        "Tristan10M",
        "Arc",
        "Xspress4",
        "Xspress3",
    ]
)


class _OdinDataTemplate(AutoSubstitution):
    TemplateFile = "OdinData.template"


class _OdinData(Device):

    """Store configuration for an OdinData process"""
    INDEX = 1  # Unique index for each OdinData instance
    RANK = None
    FP_ENDPOINT = ""
    FR_ENDPOINT = ""

    # Device attributes
    AutoInstantiate = True

    def __init__(self, server, READY, RELEASE, META, SHARED_MEM_SIZE, BUFFER_IDX, PLUGINS):
        self.__super.__init__()
        # Update attributes with parameters
        self.__dict__.update(locals())

        self.IP = server.IP
        self.plugins = PLUGINS

        # Create unique R MACRO for template file - OD1, OD2 etc.
        self.R = ":OD{}:".format(self.INDEX)
        self.index = _OdinData.INDEX
        _OdinData.INDEX += 1

    def create_config_file(self, prefix, template, extra_macros=None):
        macros = dict(
            IP=self.server.IP, ODIN_DATA=OdinPaths.ODIN_DATA_TOOL,
            RD_PORT=self.READY, RL_PORT=self.RELEASE, META_PORT=self.META,
            SHARED_MEM_SIZE=self.SHARED_MEM_SIZE,
            BUFFER_IDX=self.BUFFER_IDX
        )
        if extra_macros is not None:
            macros.update(extra_macros)
        if self.plugins is not None:
            load_entries = []
            connect_entries = []
            config_entries = []
            for plugin in self.plugins:
                load_entries.append(plugin.create_config_load_entry())
                connect_entries.append(create_config_entry(plugin.create_config_connect_entry()))
                config_entries += plugin.create_extra_config_entries(self.RANK, self.TOTAL)
            for mode in self.plugins.modes:
                valid_entries = False
                mode_config_dict = {'store': {'index': mode, 'value': [{'plugin': {'disconnect': 'all'}}]}}
                for plugin in self.plugins:
                    entry = plugin.create_config_connect_entry(mode)
                    if entry is not None:
                        valid_entries = True
                        mode_config_dict['store']['value'].append(entry)
                if valid_entries:
                    connect_entries.append(create_config_entry(mode_config_dict))

            custom_plugin_config_macros = dict(
                LOAD_ENTRIES=",\n  ".join(load_entries),
                CONNECT_ENTRIES=",\n  ".join(connect_entries),
                CONFIG_ENTRIES=",\n  ".join(config_entries)
            )
            macros.update(custom_plugin_config_macros)

        expand_template_file(template, macros, "{}{}.json".format(prefix, self.RANK + 1))

    def create_config_files(self, index, total):
        raise NotImplementedError("Method must be implemented by child classes")


class _FrameProcessorPlugin(Device):

    NAME = None
    CLASS_NAME = None
    LIBRARY_NAME = None
    LIBRARY_PATH = OdinPaths.ODIN_DATA_TOOL

    TEMPLATE = None
    TEMPLATE_INSTANTIATED = False

    def __init__(self, source=None):
        self.connections = {}

        if source is not None:
            self.source = source.NAME
        else:
            self.source = "frame_receiver"

    def add_mode(self, mode, source=None):
        if source is not None:
            self.connections[mode] = source.NAME
        else:
            self.connections[mode] = "frame_receiver"

    def create_config_load_entry(self):
        library_name = self.LIBRARY_NAME if self.LIBRARY_NAME is not None else self.CLASS_NAME
        entry = {
            "plugin": {
                "load": {
                    "index": self.NAME,
                    "name": self.CLASS_NAME,
                    "library": "{}/lib/lib{}.so".format(self.LIBRARY_PATH, library_name)
                }
            }
        }
        return create_config_entry(entry)

    def create_config_connect_entry(self, mode=None):
        cnxn = None
        if mode is None:
            cnxn = self.source
        elif mode in self.connections:
            cnxn = self.connections[mode]

        entry = None
        if cnxn is not None:
            entry = {
                "plugin": {
                    "connect": {
                        "index": self.NAME,
                        "connection": cnxn,
                    }
                }
            }
        return entry

    def create_extra_config_entries(self, rank, total):
        return []

    def create_template(self, template_args):
        if self.TEMPLATE is not None and not self.TEMPLATE_INSTANTIATED:
            makeTemplateInstance(self.TEMPLATE, locals(), template_args)
        self.TEMPLATE_INSTANTIATED = True


_FrameProcessorPlugin.ArgInfo = makeArgInfo(_FrameProcessorPlugin.__init__,
    source=Ident("Plugin to connect to", _FrameProcessorPlugin)
)


class _PluginConfig(Device):

    def __init__(self, PLUGIN_1=None, PLUGIN_2=None, PLUGIN_3=None, PLUGIN_4=None, PLUGIN_5=None,
                 PLUGIN_6=None, PLUGIN_7=None, PLUGIN_8=None):
        self.plugins = [plugin for plugin in
                        [PLUGIN_1, PLUGIN_2, PLUGIN_3, PLUGIN_4,
                         PLUGIN_5, PLUGIN_6, PLUGIN_7, PLUGIN_8]
                        if plugin is not None]
        self.modes = []

    ArgInfo = makeArgInfo(__init__,
        PLUGIN_1=Ident("Plugin 1", _FrameProcessorPlugin),
        PLUGIN_2=Ident("Plugin 2", _FrameProcessorPlugin),
        PLUGIN_3=Ident("Plugin 3", _FrameProcessorPlugin),
        PLUGIN_4=Ident("Plugin 4", _FrameProcessorPlugin),
        PLUGIN_5=Ident("Plugin 5", _FrameProcessorPlugin),
        PLUGIN_6=Ident("Plugin 6", _FrameProcessorPlugin),
        PLUGIN_7=Ident("Plugin 7", _FrameProcessorPlugin),
        PLUGIN_8=Ident("Plugin 8", _FrameProcessorPlugin)
    )

    def detector_setup(self, od_args):
        # No op, should be overridden by specific detector
        pass

    def __iter__(self):
        for plugin in self.plugins:
            yield plugin


class _OdinDataServer(Device):

    """Store configuration for an OdinDataServer"""
    PORT_BASE = 10000
    PROCESS_COUNT = 0

    # Device attributes
    AutoInstantiate = True

    def __init__(self, IP, PROCESSES, SHARED_MEM_SIZE, PLUGIN_CONFIG=None,
                 IO_THREADS=1, TOTAL_NUMA_NODES=0):
        self.__super.__init__()
        # Update attributes with parameters
        self.__dict__.update(locals())

        self.plugins = PLUGIN_CONFIG

        self.processes = []
        for idx in range(PROCESSES):
            self.processes.append(
                self.create_odin_data_process(
                    self, self.PORT_BASE + 1, self.PORT_BASE + 2, self.PORT_BASE + 8, 
                    SHARED_MEM_SIZE, idx + 1, PLUGIN_CONFIG)
            )
            self.PORT_BASE += 10

        self.instantiated = False  # Make sure instances are only used once

    ArgInfo = makeArgInfo(__init__,
        IP=Simple("IP address of server hosting OdinData processes", str),
        PROCESSES=Simple("Number of OdinData processes on this server", int),
        SHARED_MEM_SIZE=Simple("Size of shared memory buffers in bytes", int),
        PLUGIN_CONFIG=Ident("Define a custom set of plugins", _PluginConfig),
        IO_THREADS=Simple("Number of FR Ipc Channel IO threads to use", int),
        TOTAL_NUMA_NODES=Simple("Total number of numa nodes available to distribute processes over"
                                " - Optional for performance tuning", int)
    )

    def create_odin_data_process(self, server, ready, release, meta, buffer_size, buffer_idx, plugin_config):
        raise NotImplementedError("Method must be implemented by child classes")

    def configure_processes(self, server_rank, total_servers, total_processes):
        rank = server_rank
        for idx, process in enumerate(self.processes):
            process.RANK = rank
            process.TOTAL = total_processes
            rank += total_servers

    def create_od_startup_scripts(self):
        for idx, process in enumerate(self.processes):
            fp_port_number = 10004 + (10 * idx)
            fr_port_number = 10000 + (10 * idx)
            ready_port_number = 10001 + (10 * idx)
            release_port_number = 10002 + (10 * idx)

            # If TOTAL_NUMA_NODES was set, we enable the NUMA call macro instantitation
            if self.TOTAL_NUMA_NODES > 0:
                numa_node = idx % int(self.TOTAL_NUMA_NODES)
                numa_call = "numactl --membind={node} --cpunodebind={node} ".format(node=numa_node)
            else:
                numa_call = ""

            # Store server designation on OdinData object
            process.FP_ENDPOINT = "{}:{}".format(self.IP, fp_port_number)
            process.FR_ENDPOINT = "{}:{}".format(self.IP, fr_port_number)

            output_file = "stFrameReceiver{}.sh".format(process.RANK + 1)
            macros = dict(
                NUMBER=process.RANK + 1,
                ODIN_DATA=OdinPaths.ODIN_DATA_TOOL,
                CTRL_PORT=fr_port_number, IO_THREADS=self.IO_THREADS,
                LOG_CONFIG=data_file_path("log4cxx.xml"),
                NUMA=numa_call)
            expand_template_file("fr_startup", macros, output_file, executable=True)

            output_file = "stFrameProcessor{}.sh".format(process.RANK + 1)
            macros = dict(
                NUMBER=process.RANK + 1,
                ODIN_DATA=OdinPaths.ODIN_DATA_TOOL,
                HDF5_FILTERS=OdinPaths.HDF5_FILTERS,
                CTRL_PORT=fp_port_number,
                LOG_CONFIG=data_file_path("log4cxx.xml"),
                NUMA=numa_call)
            expand_template_file("fp_startup", macros, output_file, executable=True)


class OdinLogConfig(Device):

    """Create logging configuration file"""

    # Device attributes
    AutoInstantiate = True

    def __init__(self, BEAMLINE, DETECTOR):
        self.__super.__init__()
        # Update attributes with parameters
        self.__dict__.update(locals())

        self.create_config_file(BEAMLINE, DETECTOR)

    def create_config_file(self, BEAMLINE, DETECTOR):
        macros = dict(BEAMLINE=BEAMLINE, DETECTOR=DETECTOR)

        expand_template_file("log4cxx_template.xml", macros, "log4cxx.xml")

    # __init__ arguments
    ArgInfo = makeArgInfo(
        __init__,
        BEAMLINE=Simple("Beamline name, e.g. b21, i02-2", str),
        DETECTOR=DETECTOR_CHOICES
    )


# ~~~~~~~~~~~ #
# OdinControl #
# ~~~~~~~~~~~ #

class _OdinControlServer(Device):

    """Store configuration for an OdinControlServer"""

    ODIN_SERVER = None
    ADAPTERS = ["fp", "fr", "meta_listener"]

    # Device attributes
    AutoInstantiate = True

    def __init__(self, IP, DETECTOR, PORT=8888, META_WRITER_IP=None,
                 ODIN_DATA_SERVER_1=None, ODIN_DATA_SERVER_2=None,
                 ODIN_DATA_SERVER_3=None, ODIN_DATA_SERVER_4=None,
                 ODIN_DATA_SERVER_5=None, ODIN_DATA_SERVER_6=None,
                 ODIN_DATA_SERVER_7=None, ODIN_DATA_SERVER_8=None,
                 ODIN_DATA_SERVER_9=None, ODIN_DATA_SERVER_10=None):
        self.__super.__init__()
        # Update attributes with parameters
        self.__dict__.update(locals())

        self.detector_model = DETECTOR

        self.meta_writer_ip = META_WRITER_IP or ODIN_DATA_SERVER_1.IP

        self.odin_data_servers = [
            server for server in [
                ODIN_DATA_SERVER_1,
                ODIN_DATA_SERVER_2,
                ODIN_DATA_SERVER_3,
                ODIN_DATA_SERVER_4,
                ODIN_DATA_SERVER_5,
                ODIN_DATA_SERVER_6,
                ODIN_DATA_SERVER_7,
                ODIN_DATA_SERVER_8,
                ODIN_DATA_SERVER_9,
                ODIN_DATA_SERVER_10
            ] if server is not None
        ]

        if not self.odin_data_servers:
            raise ValueError("Received no control endpoints for Odin Server")

        self.odin_data_processes = []
        for server in self.odin_data_servers:
            if server is not None:
                self.odin_data_processes += server.processes

        self.create_startup_script()

    ArgInfo = makeArgInfo(__init__,
        IP=Simple("IP address of control server", str),
        DETECTOR=DETECTOR_CHOICES,
        PORT=Simple("Port of control server", int),
        META_WRITER_IP=Simple("IP address of MetaWriter (None -> first OdinDataServer)", str),
        ODIN_DATA_SERVER_1=Ident("OdinDataServer 1 configuration", _OdinDataServer),
        ODIN_DATA_SERVER_2=Ident("OdinDataServer 2 configuration", _OdinDataServer),
        ODIN_DATA_SERVER_3=Ident("OdinDataServer 3 configuration", _OdinDataServer),
        ODIN_DATA_SERVER_4=Ident("OdinDataServer 4 configuration", _OdinDataServer),
        ODIN_DATA_SERVER_5=Ident("OdinDataServer 5 configuration", _OdinDataServer),
        ODIN_DATA_SERVER_6=Ident("OdinDataServer 6 configuration", _OdinDataServer),
        ODIN_DATA_SERVER_7=Ident("OdinDataServer 7 configuration", _OdinDataServer),
        ODIN_DATA_SERVER_8=Ident("OdinDataServer 8 configuration", _OdinDataServer),
        ODIN_DATA_SERVER_9=Ident("OdinDataServer 9 configuration", _OdinDataServer),
        ODIN_DATA_SERVER_10=Ident("OdinDataServer 10 configuration", _OdinDataServer),
    )

    def create_startup_script(self):
        static_fields = [
            "beamline=${BEAMLINE}",
            "application_name={}".format(self.ODIN_SERVER.split("/")[-1])
        ] + [
            "=".join((k, v)) for k, v in self.create_extra_static_fields().items()
        ]
        extra_params = " ".join([
            "--graylog_static_fields " + ",".join(static_fields),
        ])

        macros = dict(
            ODIN_SERVER=self.ODIN_SERVER,
            CONFIG="odin_server.cfg",
            EXTRA_PARAMS=extra_params
        )
        expand_template_file("odin_server_startup", macros, "stOdinServer.sh", executable=True)

    def create_extra_static_fields(self):
        return dict(detector=self.detector_model)

    def create_config_file(self):
        macros = dict(PORT=self.PORT,
                      ADAPTERS=", ".join(self.ADAPTERS),
                      ADAPTER_CONFIG="\n\n".join(self.create_odin_server_config_entries()),
                      STATIC_PATH=self.create_odin_server_static_path())
        expand_template_file("odin_server.ini", macros, "odin_server.cfg")

    def create_odin_server_static_path(self):
        return "./static"

    def create_odin_server_config_entries(self):
        config_entries = [
            self._create_odin_data_config_entry(),
            self._create_meta_writer_config_entry()
        ]
        config_entries.extend(self.create_extra_config_entries())

        return config_entries

    def _create_meta_writer_config_entry(self):
        return (
            "[adapter.meta_listener]\n"
            "module = odin_data.control.meta_listener_adapter.MetaListenerAdapter\n"
            "endpoints = {}:5659\n"
            "update_interval = 0.5"
        ).format(self.meta_writer_ip)

    def _create_odin_data_config_entry(self):
        fp_endpoints = []
        fr_endpoints = []
        for process in sorted(self.odin_data_processes, key=lambda x: x.RANK):
            fp_endpoints.append(process.FP_ENDPOINT)
            fr_endpoints.append(process.FR_ENDPOINT)

        return (
            "[adapter.fp]\n"
            "module = odin_data.control.frame_processor_adapter.FrameProcessorAdapter\n"
            "endpoints = {}\n"
            "update_interval = 0.2\n\n"
            "[adapter.fr]\n"
            "module = odin_data.control.frame_receiver_adapter.FrameReceiverAdapter\n"
            "endpoints = {}\n"
            "update_interval = 0.2".format(
                ", ".join(fp_endpoints), ", ".join(fr_endpoints)
            )
        )


class _MetaWriterTemplate(AutoSubstitution):
    TemplateFile = "MetaListener.template"


class _MetaWriter(object):
    APP_PATH = OdinPaths.ODIN_DATA_PYTHON
    APP_NAME = "meta_writer"
    WRITER_CLASS = None
    DETECTOR = ""
    SENSOR_SHAPE = None
    TEMPLATE = _MetaWriterTemplate

    def __init__(self, detector_model, odin_data_servers):
        self.detector_model = detector_model

        self.data_endpoints = []
        for server in odin_data_servers:
            if server is not None:
                base_port = 10000
                for odin_data in server.processes:
                    port = base_port + 8
                    self.data_endpoints.append("tcp://{}:{}".format(odin_data.IP, port))
                    base_port += 10

        self.create_startup_script()

    def create_startup_script(self):
        if self.WRITER_CLASS is not None:
            writer = "-w {}".format(self.WRITER_CLASS)
        else:
            writer = ""

        if self.SENSOR_SHAPE is not None:
            sensor_shape = "--sensor-shape {} {}".format(*self.SENSOR_SHAPE)
        else:
            sensor_shape = ""

        macros = dict(
            APP_PATH=self.APP_PATH,
            APP_NAME=self.APP_NAME,
            WRITER=writer,
            SENSOR_SHAPE=sensor_shape,
            DATA_ENDPOINTS=",".join(self.data_endpoints),
            DETECTOR_MODEL=self.detector_model,
        )

        expand_template_file("meta_startup", macros, "stMetaWriter.sh", executable=True)


# ~~~~~~~~~~~~ #
# AreaDetector #
# ~~~~~~~~~~~~ #


class _OdinDetectorTemplate(AutoSubstitution):
    TemplateFile = "OdinDetector.template"


class _OdinDetector(AsynPort):

    """Create an odin detector"""

    Dependencies = (ADCore, restClient)

    # This tells xmlbuilder to use PORT instead of name as the row ID
    UniqueName = "PORT"

    def __init__(self, PORT, ODIN_CONTROL_SERVER, DETECTOR, BUFFERS = 0, MEMORY = 0, **args):
        # Init the superclass (AsynPort)
        self.__super.__init__(PORT)
        # Update the attributes of self from the commandline args
        self.__dict__.update(locals())

        # Define Macros for Initialise substitutions
        self.CONTROL_SERVER_IP = ODIN_CONTROL_SERVER.IP
        self.CONTROL_SERVER_PORT = ODIN_CONTROL_SERVER.PORT

    # __init__ arguments
    ArgInfo = ADBaseTemplate.ArgInfo + makeArgInfo(__init__,
        PORT=Simple("Port name for the detector", str),
        ODIN_CONTROL_SERVER=Ident("Odin control server", _OdinControlServer),
        DETECTOR=Simple("Name of detector", str),
        BUFFERS=Simple("Maximum number of NDArray buffers to be created for plugin callbacks", int),
        MEMORY=Simple("Max memory to allocate, should be maxw*maxh*nbuffer for driver and all "
                      "attached plugins", int)
    )

    # Device attributes
    LibFileList = ["OdinDetector"]
    DbdFileList = ["OdinDetectorSupport"]

    def Initialise(self):
        print "# odinDetectorConfig(const char * portName, const char * serverPort, " \
              "int odinServerPort, const char * detectorName, " \
              "int maxBuffers, size_t maxMemory, int priority, int stackSize)"
        print "odinDetectorConfig(\"%(PORT)s\", \"%(CONTROL_SERVER_IP)s\", " \
              "%(CONTROL_SERVER_PORT)d, \"%(DETECTOR)s\", " \
              "%(BUFFERS)d, %(MEMORY)d)" % self.__dict__


class _OdinDataDriverTemplate(AutoSubstitution):
    TemplateFile = "OdinDataDriver.template"


class _OdinDataDriver(AsynPort):

    """Create an OdinData driver"""

    Dependencies = (ADCore, Calc, restClient)

    # This tells xmlbuilder to use PORT instead of name as the row ID
    UniqueName = "PORT"

    META_WRITER_CLASS = _MetaWriter

    def __init__(self, PORT, ODIN_CONTROL_SERVER, DETECTOR=None, DATASET="data",
                 BUFFERS=0, MEMORY=0, **args):
        # Init the superclass (AsynPort)
        self.__super.__init__(PORT)
        # Update the attributes of self from the commandline args
        self.__dict__.update(locals())

        self.control_server = ODIN_CONTROL_SERVER
        self.server_count = len(self.control_server.odin_data_servers)

        # Make an instance of our template
        self.odin_data_processes = len(self.control_server.odin_data_processes)
        args["TOTAL"] = self.odin_data_processes
        makeTemplateInstance(_OdinDataDriverTemplate, locals(), args)

        # Define Macros for Initialise substitutions
        self.CONTROL_SERVER_IP = ODIN_CONTROL_SERVER.IP
        self.CONTROL_SERVER_PORT = ODIN_CONTROL_SERVER.PORT
        self.DETECTOR_PLUGIN = DETECTOR.lower()
        self.ODIN_DATA_PROCESSES = []

        plugin_config = None
        for server_idx, server in enumerate(self.control_server.odin_data_servers):
            if server.instantiated:
                raise ValueError("Same OdinDataServer object given twice")
            else:
                server.instantiated = True

            server.configure_processes(server_idx, self.server_count, self.odin_data_processes)

            process_idx = server_idx
            for odin_data in server.processes:
                self.ODIN_DATA_PROCESSES.append(odin_data)
                # Use some OdinDataDriver macros to instantiate an OdinData.template
                od_args = dict((key, args[key]) for key in ["P", "TIMEOUT"])
                od_args["PORT"] = PORT
                od_args["ADDR"] = odin_data.index - 1
                od_args["R"] = odin_data.R
                od_args["TOTAL"] = self.odin_data_processes
                _OdinDataTemplate(**od_args)

                odin_data.create_config_files(process_idx + 1, self.odin_data_processes)
                process_idx += self.server_count

            if server.plugins is not None:
                plugin_config = server.plugins
                for plugin in server.plugins:
                    if not plugin.TEMPLATE_INSTANTIATED:
                        plugin_args = dict((key, args[key]) for key in ["P", "R"])
                        plugin_args["PORT"] = PORT
                        plugin_args["TOTAL"] = self.odin_data_processes
                        plugin_args["GUI"] = \
                            self.gui_macro(PORT, "OdinData." + plugin.NAME.capitalize())
                        plugin.create_template(plugin_args)

            server.create_od_startup_scripts()

        if plugin_config is not None:
            od_args = dict((key, args[key]) for key in ["P", "TIMEOUT"])
            od_args["PORT"] = PORT
            od_args["ADDRESS"] = 0
            od_args["R"] = ":OD:"
            plugin_config.detector_setup(od_args)

        self.meta_writer = self.META_WRITER_CLASS(
            self.control_server.detector_model, self.control_server.odin_data_servers
        )
        template_args = {
            "P": args["P"],
            "R": ":OD:",
            "PORT": PORT
        }
        self.meta_writer.TEMPLATE(**template_args)

        # Now OdinData instances are configured, OdinControlServer can generate its config from them
        self.control_server.create_config_file()

    # __init__ arguments
    ArgInfo = (
        ADBaseTemplate.ArgInfo
        + _OdinDataDriverTemplate.ArgInfo.filtered(without=["TOTAL"])
        + makeArgInfo(
            __init__,
            PORT=Simple("Port name for the detector", str),
            BUFFERS=Simple("Maximum number of NDArray buffers", int,),
            MEMORY=Simple("Max memory to allocate", int),
            ODIN_CONTROL_SERVER=Ident("Odin control server", _OdinControlServer),
            DATASET=Simple("Name of Dataset", str),
            DETECTOR=Simple("Detector type", str),
        )
    )

    # Device attributes
    LibFileList = ["OdinDetector"]
    DbdFileList = ["OdinDetectorSupport"]

    def Initialise(self):
        print "# odinDataDriverConfig(const char * portName, const char * serverPort, " \
              "int odinServerPort, int odinDataCount, " \
              "const char * datasetName, const char * detectorName, " \
              "int maxBuffers, size_t maxMemory)"
        print "odinDataDriverConfig(\"%(PORT)s\", \"%(CONTROL_SERVER_IP)s\", " \
              "%(CONTROL_SERVER_PORT)d, %(odin_data_processes)d, " \
              "\"%(DATASET)s\", \"%(DETECTOR_PLUGIN)s\", " \
              "%(BUFFERS)d, %(MEMORY)d)" % self.__dict__

    def gui_macro(self, port, name):
        top = port[:port.find(".")]
        return "{}.{}".format(top, name)

    def create_gui_macros(self, port):
        return dict(
            OD_HDF_STATUS_GUI=self.gui_macro(port, "HDFStatus")
        )


class OdinStartAllScript(Device):

    """Create a start-up script for this IOC"""

    def __init__(self, driver):
        self.create_start_all_script(driver.DETECTOR.upper(), driver.odin_data_processes)

    ArgInfo = makeArgInfo(__init__, driver=Ident("OdinDataDriver", _OdinDataDriver))

    def create_start_all_script(self, detector_name, odin_data_processes):
        scripts, kdl = self.create_scripts(odin_data_processes)
        macros = dict(DETECTOR=getattr(OdinPaths, "{}_TOOL".format(detector_name)),
                      ODIN_DATA=OdinPaths.ODIN_DATA_TOOL,
                      SCRIPTS="\n".join([script for script in scripts]),
                      COMMANDS="\n".join([self.create_command_entry(script.split("=")[0])
                                          for script in scripts]))
        expand_template_file("odin_startup", macros, "startAll.sh", executable=True)
        expand_template_file(
            "layout.kdl",
            dict(NAME=detector_name, PANES="\n".join([k for k in kdl])),
            "startAll.kdl"
        )
        expand_template_file("startIOC.sh", None, "startIOC.sh", executable=True)

    def create_scripts(self, odin_data_processes):
        scripts = []
        kdl = []
        for process_number in range(1, odin_data_processes + 1):
            scripts.append(self.create_script_entry(
                "FR{}".format(process_number),
                "stFrameReceiver{}.sh".format(process_number),
            ))
            scripts.append(self.create_script_entry(
                "FP{}".format(process_number),
                "stFrameProcessor{}.sh".format(process_number),
            ))
            kdl.append(self.create_kdl_entry(
                "stFrameReceiver{}.sh".format(process_number),
            ))
            kdl.append(self.create_kdl_entry(
                "stFrameProcessor{}.sh".format(process_number),
            ))

        scripts.append(self.create_script_entry(
            "MetaWriter", "stMetaWriter.sh",
        ))
        kdl.append(self.create_kdl_entry("stMetaWriter.sh"))

        return scripts, kdl

    def create_script_entry(self, name, script_name):
        return "{name}=\"${{SCRIPT_DIR}}/{script_name}\"".format(
            name=name, script_name=script_name
        )

    def create_command_entry(self, script):
        return "gnome-terminal --tab --title=\"{script}\" -- bash -c \"${{{script}}}\"".format(
            script=script
        )

    def create_kdl_entry(self, command):
        return '            pane command="./{}"'.format(command)

class _OdinProcServ(AutoSubstitution):
    TemplateFile = "OdinProcServ.template"

class _OdinProcServProcess(AutoSubstitution):
    TemplateFile = "OdinProcServProcess.template"

class OdinProcServ(Device):

    def __init__(
        self,
        ODIN_DATA_DRIVER,
        IOC_NAME,
        PREFIX,
        PROCESS_PREFIX,
        ADODIN_IOC_NAME,
        SERVER_DELAY=2,
        IOC_DELAY=5,
    ):
        self.odin_data_driver = ODIN_DATA_DRIVER

        application_names = self.create_application_list()
        process_names = [
            self._format_odin_process(PROCESS_PREFIX, i)
            for i in range(1, len(application_names) + 1)
        ]

        # Create Templates
        detector_name = PROCESS_PREFIX.split("-")[-1]
        for application_name, process_name in zip(application_names, process_names):
            _OdinProcServProcess(
                name=detector_name,
                APPLICATION_NAME=application_name,
                PROCESS_NAME=process_name,
            )
        # Add ADOdin IOC
        _OdinProcServProcess(
            name=detector_name,
            APPLICATION_NAME=ADODIN_IOC_NAME,
            PROCESS_NAME=ADODIN_IOC_NAME,
        )
        # Add root screen with start/stop/restart all buttons
        _OdinProcServ(name=detector_name, PREFIX=PREFIX)

        config = dict(
            ODIN_PROC_SERV_CONTROL=OdinPaths.ODIN_PROC_SERV_CONTROL,
            IOC_NAME=IOC_NAME,
            PREFIX=PREFIX,
            PROCESS_PREFIX=PROCESS_PREFIX,
            PROCESS_COUNT=len(process_names),
            SERVER_PROCESS_NAME=process_names[0],  # The server is the first process
            SERVER_DELAY=SERVER_DELAY,
            ADODIN_IOC_NAME=ADODIN_IOC_NAME,
            IOC_DELAY=IOC_DELAY,
        )
        self.write_ioc_boot_script(config)

        batch_entries = [
            "{} st{}.sh".format(process, application)
            for process, application in zip(process_names, application_names)
        ]
        # Insert ourselves into the batch file
        batch_entries.append("{0} {0}.yaml".format(config["IOC_NAME"]))
        write_batch_file(batch_entries)

    def create_application_list(self):
        application_names = ["OdinServer"]

        number = 1
        for odin_data_server in self.odin_data_driver.control_server.odin_data_servers:
            for _ in odin_data_server.processes:
                application_names.append("FrameReceiver{}".format(number))
                application_names.append("FrameProcessor{}".format(number))
                number += 1

        application_names.append("MetaWriter")
        application_names.extend(self.extra_applications)

        return application_names

    @property
    def extra_applications(self):
        return []

    # __init__ arguments
    ArgInfo = makeArgInfo(
        __init__,
        ODIN_DATA_DRIVER=Ident("OdinDataDriver", _OdinDataDriver),
        IOC_NAME=Simple("OdinProcServ IOC name - e.g. BLXXY-CS-IOC-01", str),
        PREFIX=Simple("Prefix of OdinProcServ PVs - e.g. BLXXY-CS-EIG1-01", str),
        PROCESS_PREFIX=Simple("Prefix of odin processes - e.g. BLXXY-EA-EIG1", str),
        SERVER_DELAY=Simple("Delay before starting odin server", int),
        ADODIN_IOC_NAME=Simple("Name of ADOdin IOC", str),
        IOC_DELAY=Simple("Delay before starting IOC", int),
    )

    def _format_odin_process(self, prefix, process_number):
        if not prefix.endswith("-"):
            prefix += "-"
        return "{}{:02d}".format(prefix, process_number)

    def write_ioc_boot_script(self, config):
        expand_template_file(
            "odinprocservcontrol.yaml",
            config,
            "{}.yaml".format(config["IOC_NAME"]),
            executable=True
        )

