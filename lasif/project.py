#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
Project management class.

It is important to not import necessary things at the method level to make
importing this file as fast as possible. Otherwise using the command line
interface feels sluggish and slow. Import things only the functions they are
needed.

:copyright:
    Lion Krischer (krischer@geophysik.uni-muenchen.de), 2013

:license:
    GNU General Public License, Version 3
    (http://www.gnu.org/copyleft/gpl.html)
"""
import colorama
import cPickle
import glob
import os
import warnings


class LASIFException(Exception):
    """
    Base LASIF specific exception.
    """
    pass


class Project(object):
    """
    A class representing and managing a single LASIF project.
    """
    def __init__(self, project_root_path, init_project=False):
        """
        Upon intialization, set the paths and read the config file.

        :type project_root_path: String
        :param project_root_path: The root path of the project.
        :type init_project: False or String
        :param init_project: Determines whether or not to initialize a new
            project, e.g. create the necessary folder structure. If a string is
            passed, the project will be given this name. Otherwise a default
            name will be chosen.
        """
        self._setup_paths(project_root_path)
        if init_project:
            self._init_new_project(init_project)
        if not os.path.exists(self.paths["config_file"]):
            msg = ("Could not find the project's config file. Wrong project "
                   "path or uninitialized project?")
            raise LASIFException(msg)
        self.update_folder_structure()
        self._read_config_file()

    def _setup_paths(self, root_path):
        """
        Central place to define all paths.
        """
        # Every key containing the string "file" denotes a file, all others
        # should denote directories.
        self.paths = {}
        self.paths["root"] = root_path
        self.paths["events"] = os.path.join(root_path, "EVENTS")
        self.paths["data"] = os.path.join(root_path, "DATA")
        self.paths["cache"] = os.path.join(root_path, "CACHE")
        self.paths["logs"] = os.path.join(root_path, "LOGS")
        self.paths["models"] = os.path.join(root_path, "MODELS")
        self.paths["iterations"] = os.path.join(root_path, "ITERATIONS")
        self.paths["synthetics"] = os.path.join(root_path, "SYNTHETICS")
        self.paths["kernels"] = os.path.join(root_path, "KERNELS")
        self.paths["stations"] = os.path.join(root_path, "STATIONS")
        self.paths["output"] = os.path.join(root_path, "OUTPUT")
        self.paths["windows"] = os.path.join(
            root_path, "ADJOINT_SOURCES_AND_WINDOWS", "WINDOWS")
        self.paths["adjoint_sources"] = os.path.join(
            root_path, "ADJOINT_SOURCES_AND_WINDOWS", "ADJOINT_SOURCES")

        # Station file subfolders.
        self.paths["dataless_seed"] = os.path.join(self.paths["stations"],
                                                   "SEED")
        self.paths["station_xml"] = os.path.join(self.paths["stations"],
                                                 "StationXML")
        self.paths["resp"] = os.path.join(self.paths["stations"],
                                          "RESP")

        # Paths for various files.
        self.paths["config_file"] = os.path.join(root_path,
                                                 "config.xml")
        self.paths["config_file_cache"] = \
            os.path.join(self.paths["cache"], "config.xml_cache.pickle")
        self.paths["inv_db_file"] = \
            os.path.join(self.paths["cache"], "inventory_db.sqlite")

    def update_folder_structure(self):
        """
        Updates the folder structure of the project.
        """
        for name, path in self.paths.iteritems():
            if "file" in name or os.path.exists(path):
                continue
            os.makedirs(path)
        events = self.get_event_dict().keys()
        folders = [self.paths["data"], self.paths["synthetics"]]
        for folder in folders:
            for event in events:
                event_folder = os.path.join(folder, event)
                if os.path.exists(event_folder):
                    continue
                os.makedirs(event_folder)

    def _init_new_project(self, project_name):
        """
        Initializes a new project. This currently just means that it creates a
        default config file. The folder structure is checked and rebuilt every
        time the project is initialized anyways.
        """
        from lxml import etree
        from lxml.builder import E

        if not project_name:
            project_name = "LASIFProject"

        doc = E.lasif_project(
            E.name(project_name),
            E.description(""),
            E.download_settings(
                E.arclink_username(""),
                E.seconds_before_event(str(300)),
                E.seconds_after_event(str(3600))),
            E.domain(
                E.domain_bounds(
                    E.minimum_longitude(str(-20)),
                    E.maximum_longitude(str(20)),
                    E.minimum_latitude(str(-20)),
                    E.maximum_latitude(str(20)),
                    E.minimum_depth_in_km(str(0.0)),
                    E.maximum_depth_in_km(str(200.0)),
                    E.boundary_width_in_degree(str(3.0))),
                E.domain_rotation(
                    E.rotation_axis_x(str(1.0)),
                    E.rotation_axis_y(str(1.0)),
                    E.rotation_axis_z(str(1.0)),
                    E.rotation_angle_in_degree(str(-45.0)))))

        string_doc = etree.tostring(doc, pretty_print=True,
                                    xml_declaration=True, encoding="UTF-8")

        with open(self.paths["config_file"], "wt") as open_file:
            open_file.write(string_doc)

    def __str__(self):
        """
        Pretty string representation.
        """
        from lasif.utils import sizeof_fmt
        # Count all files and sizes.

        raw_data_file_count = 0
        processed_data_file_count = 0
        synthetic_data_file_count = 0
        station_file_count = 0
        project_filesize = 0

        for dirpath, _, filenames in os.walk(self.paths["root"]):
            size = sum([os.path.getsize(os.path.join(dirpath, _i))
                        for _i in filenames])
            project_filesize += size
            if dirpath.startswith(self.paths["data"]):
                if dirpath.endswith("raw"):
                    raw_data_file_count += len(filenames)
                elif "processed" in dirpath:
                    processed_data_file_count += len(filenames)
            elif dirpath.startswith(self.paths["synthetics"]):
                synthetic_data_file_count += len(filenames)
            elif dirpath.startswith(self.paths["stations"]):
                station_file_count += len(filenames)

        ret_str = "LASIF project \"%s\"\n" % self.config["name"]
        ret_str += "\tDescription: %s\n" % self.config["description"]
        ret_str += "\tProject root: %s\n" % self.paths["root"]
        ret_str += "\tContent:\n"
        ret_str += "\t\t%i events\n" % len(self.get_event_dict())
        ret_str += "\t\t%i station files\n" % station_file_count
        ret_str += "\t\t%i raw waveform files\n" % raw_data_file_count
        ret_str += "\t\t%i processed waveform files \n" % \
            processed_data_file_count
        ret_str += "\t\t%i synthetic waveform files\n" % \
            synthetic_data_file_count

        ret_str += "\tTotal project size: %s" % sizeof_fmt(project_filesize)

        return ret_str

    def get_station_filename(self, network, station, location, channel,
                             file_format):
        """
        Function returning the filename a station file of a certain format
        should be written to. Only useful as a callback function.

        :type file_format: String
        :param file_format: 'datalessSEED', 'StationXML', or 'RESP'
        """
        if file_format not in ["datalessSEED", "StationXML", "RESP"]:
            msg = "Unknown format '%s'" % file_format
            raise ValueError(msg)
        if file_format == "datalessSEED":
            def seed_filename_generator():
                i = 0
                while True:
                    filename = os.path.join(
                        self.paths["dataless_seed"],
                        "dataless.{network}_{station}".format(
                            network=network, station=station))
                    if i:
                        filename += ".%i" % i
                    i += 1
                    yield filename
            for filename in seed_filename_generator():
                if not os.path.exists(filename):
                    break
            return filename
        if file_format == "RESP":
            def resp_filename_generator():
                i = 0
                while True:
                    filename = os.path.join(
                        self.paths["resp"],
                        "RESP.{network}.{station}.{location}.{channel}"
                        .format(network=network, station=station,
                                location=location, channel=channel))
                    if i:
                        filename += ".%i" % i
                    i += 1
                    yield filename
            for filename in resp_filename_generator():
                if not os.path.exists(filename):
                    break
            return filename
        else:
            raise NotImplementedError

    def _read_config_file(self):
        """
        Parse the config file.
        """
        # Attempt to read the cached config file. This might seem excessive but
        # since this file is read every single time a LASIF command is used it
        # makes difference at least in the perceived speed of LASIF.
        cfile = self.paths["config_file_cache"]
        if os.path.exists(cfile):
            with open(cfile, "rb") as fh:
                cf_cache = cPickle.load(fh)
            last_m_time = int(os.path.getmtime(self.paths["config_file"]))
            if last_m_time == cf_cache["last_m_time"]:
                self.config = cf_cache["config"]
                self.domain = cf_cache["domain"]
                return

        from lxml import etree
        root = etree.parse(self.paths["config_file"]).getroot()

        self.config = {}
        self.config["name"] = root.find("name").text
        self.config["description"] = root.find("description").text
        # The description field is the only field allowed to be empty.
        if self.config["description"] is None:
            self.config["description"] = ""

        self.config["download_settings"] = {}
        dl_settings = root.find("download_settings")
        self.config["download_settings"]["arclink_username"] = \
            dl_settings.find("arclink_username").text
        self.config["download_settings"]["seconds_before_event"] = \
            float(dl_settings.find("seconds_before_event").text)
        self.config["download_settings"]["seconds_after_event"] = \
            float(dl_settings.find("seconds_after_event").text)

        # Read the domain.
        domain = root.find("domain")
        self.domain = {}
        self.domain["bounds"] = {}

        bounds = domain.find("domain_bounds")
        self.domain["bounds"]["minimum_latitude"] = \
            float(bounds.find("minimum_latitude").text)
        self.domain["bounds"]["maximum_latitude"] = \
            float(bounds.find("maximum_latitude").text)
        self.domain["bounds"]["minimum_longitude"] = \
            float(bounds.find("minimum_longitude").text)
        self.domain["bounds"]["maximum_longitude"] = \
            float(bounds.find("maximum_longitude").text)
        self.domain["bounds"]["minimum_depth_in_km"] = \
            float(bounds.find("minimum_depth_in_km").text)
        self.domain["bounds"]["maximum_depth_in_km"] = \
            float(bounds.find("maximum_depth_in_km").text)
        self.domain["bounds"]["boundary_width_in_degree"] = \
            float(bounds.find("boundary_width_in_degree").text)

        rotation = domain.find("domain_rotation")
        self.domain["rotation_axis"] = [
            float(rotation.find("rotation_axis_x").text),
            float(rotation.find("rotation_axis_y").text),
            float(rotation.find("rotation_axis_z").text)]
        self.domain["rotation_angle"] = \
            float(rotation.find("rotation_angle_in_degree").text)

        # Write cache file.
        cf_cache = {}
        cf_cache["config"] = self.config
        cf_cache["domain"] = self.domain
        cf_cache["last_m_time"] = \
            int(os.path.getmtime(self.paths["config_file"]))
        with open(cfile, "wb") as fh:
            cPickle.dump(cf_cache, fh, protocol=2)

    def get_model_dict(self):
        """
        Returns a dictonary with all models in the project, the keys are the
        model names and the values the full paths to each model.
        """
        contents = [os.path.join(self.paths["models"], _i)
                    for _i in os.listdir(self.paths["models"])]
        models = [os.path.abspath(_i) for _i in contents if os.path.isdir(_i)]
        models = {os.path.basename(_i): _i for _i in models}
        return models

    def get_event_dict(self):
        """
        Returns a dictonary with all events in the project, the keys are the
        event names and the values the full paths to each event.
        """
        events = {}
        for event in glob.iglob(os.path.join(self.paths["events"],
                                             "*%sxml" % os.extsep)):
            event = os.path.abspath(event)
            event_name = os.path.splitext(os.path.basename(event))[0]
            events[event_name] = event
        return events

    def plot_domain(self, show_plot=True):
        """
        Plots the simulation domain and the actual physical domain.

        Wrapper around one of the visualization routines.
        """
        from lasif import visualization

        bounds = self.domain["bounds"]
        visualization.plot_domain(
            bounds["minimum_latitude"],
            bounds["maximum_latitude"], bounds["minimum_longitude"],
            bounds["maximum_longitude"], bounds["boundary_width_in_degree"],
            rotation_axis=self.domain["rotation_axis"],
            rotation_angle_in_degree=self.domain["rotation_angle"],
            plot_simulation_domain=True, show_plot=show_plot, zoom=True)

    def plot_Q_model(self, iteration_name, show_plot=True):
        """
        Plots the Q model for a given iteration. Will only work if the
        iteration uses SES3D as its solver.
        """
        from lasif.tools.Q_discrete import plot

        iteration = self._get_iteration(iteration_name)
        if iteration.solver_settings["solver"].lower() != "ses3d 4.0":
            msg = "Only works for SES3D 4.0"
            raise LASIFException(msg)

        proc_params = iteration.get_process_params()
        f_min = proc_params["highpass"]
        f_max = proc_params["lowpass"]

        relax = iteration.solver_settings["solver_settings"][
            "relaxation_parameter_list"]
        tau_p = relax["tau"]
        weights = relax["w"]

        plot(D_p=weights, tau_p=tau_p, f_min=f_min, f_max=f_max,
             show_plot=show_plot)

    def get_kernel_dir(self, iteration_name, event_name):
        return os.path.join(self.paths["kernels"], event_name, self.
                            _get_long_iteration_name(iteration_name))

    def get_event(self, event_name):
        """
        Helper function to avoid reading one event twice.
        """
        from obspy import readEvents

        if not hasattr(self, "_seismic_events"):
            self._seismic_events = {}
        # Read the file if it does not exist.
        if event_name not in self._seismic_events:
            filename = os.path.join(self.paths["events"], "%s%sxml" %
                                    (event_name, os.path.extsep))
            if not os.path.exists(filename):
                return None
            self._seismic_events[event_name] = readEvents(filename)[0]
            # Add the filename to the event object to later on be able to find
            # it.
            self._seismic_events[event_name].filename = filename
        return self._seismic_events[event_name]

    def create_new_iteration(self, iteration_name, solver_name, min_period=8.0,
                             max_period=100.0):
        """
        Creates a new iteration file.
        """
        from lasif import iteration_xml

        iteration_name = iteration_name.replace(" ", "_").upper()
        filename = self._get_long_iteration_name(iteration_name)
        filename = self._get_long_iteration_name(iteration_name) + \
            os.path.extsep + "xml"
        filename = os.path.join(self.paths["iterations"], filename)
        if os.path.exists(filename):
            msg = "Iteration already exists."
            raise LASIFException(msg)

        # Get a dictionary containing the event names as keys and a list of
        # stations per event as values.
        events_dict = {event: self.get_stations_for_event(event).keys()
                       for event in self.get_event_dict().keys()}

        xml_string = iteration_xml.create_iteration_xml_string(
            iteration_name, solver_name, events_dict, min_period=min_period,
            max_period=max_period)

        with open(filename, "wt") as fh:
            fh.write(xml_string)

        print "Created iteration %s" % iteration_name

    def get_iteration_dict(self):
        """
        Returns a dictonary with all iterations in the project, the keys are
        the iteration names and the values the full paths to each iteration.
        """
        iterations = {}
        for iteration in glob.iglob(os.path.join(self.paths["iterations"],
                                                 "*%sxml" % os.extsep)):
            iteration = os.path.abspath(iteration)
            iteration_name = os.path.splitext(os.path.basename(iteration))[0]
            if iteration_name.startswith("ITERATION_"):
                iteration_name = iteration_name[10:]
            iterations[iteration_name] = iteration
        return iterations

    def _get_iteration(self, iteration_name):
        """
        Helper method to read a certain iteration.
        """
        from lasif.iteration_xml import Iteration

        iterations = self.get_iteration_dict()
        if iteration_name not in iterations:
            msg = "Could not find iteration '%s'." % iteration_name
            raise LASIFException(msg)
        return Iteration(iterations[iteration_name])

    def preprocess_data(self, iteration_name, event_ids=None,
                        waiting_time=4.0):
        """
        Preprocesses all data for a given iteration.

        :param waiting_time: The time spent sleeping after the initial message
            has been printed. Useful if the user should be given the chance to
            cancel the processing.
        :param event_ids: event_ids is a list of events to process in this run.
            It will process all events if not given.
        """
        from lasif import preprocessing
        import obspy

        iteration = self._get_iteration(iteration_name)

        process_params = iteration.get_process_params()
        processing_tag = iteration.get_processing_tag()

        #======================================================================
        #- Waveform information generator for event information
        #======================================================================

        def processing_data_generator():
            """
            Generate a dictionary with information for processing for each
            waveform.
            """
            # Loop over the chosen events.
            for event_name, event in iteration.events.iteritems():
                # None means to process all events, otherwise it will be a list
                # of events.
                if (event_ids is None) or (event_name in event_ids):

                    event_info = self.get_event_info(event_name)

                    # The folder where all preprocessed data for this event
                    # will go.
                    event_data_path = os.path.join(self.paths["data"],
                                                   event_name, processing_tag)
                    if not os.path.exists(event_data_path):
                        os.makedirs(event_data_path)

                    #- Folder for processing logfiles. Logfile.
                    logfile_path = os.path.join(self.paths["logs"],
                                                "PROCESSING", event_name)
                    if not os.path.exists(logfile_path):
                        os.makedirs(logfile_path)

                    logfile_name = logfile_path + "/" + processing_tag + \
                        ".at." + str(obspy.UTCDateTime())

                    # All stations that will be processed for this iteration
                    # and event.
                    stations = event["stations"].keys()
                    waveforms = self._get_waveform_cache_file(event_name,
                                                              "raw")
                    if waveforms is False:
                        msg = ("Could not find any waveforms for event "
                               "{event}. Will be skipped.".format(
                                   event=event_name))
                        warnings.warn(msg)
                        continue

                    #- loop over waveforms in the event =======================
                    for waveform in waveforms.get_values():
                        station_id = "{network}.{station}".format(**waveform)

                        # Only process data from stations needed for the
                        # current iteration.
                        if station_id not in stations:
                            continue

                        # Generate the new filename for the waveform. If it
                        # already exists, continue.
                        processed_filename = os.path.join(
                            event_data_path,
                            os.path.basename(waveform["filename"]))
                        if os.path.exists(processed_filename):
                            continue

                        ret_dict = process_params.copy()
                        ret_dict["data_path"] = waveform["filename"]
                        ret_dict["processed_data_path"] = processed_filename
                        ret_dict.update(event_info)
                        ret_dict["station_filename"] = \
                            self.station_cache.get_station_filename(
                                waveform["channel_id"],
                                obspy.UTCDateTime(
                                    waveform["starttime_timestamp"]))
                        ret_dict["logfile_name"] = logfile_name

                        yield ret_dict

        count = preprocessing.launch_processing(processing_data_generator(),
                                                waiting_time=waiting_time)

        print colorama.Fore.GREEN + \
            ("\nDONE - Preprocessed %i files." % count) + \
            colorama.Style.RESET_ALL

    def get_all_events(self):
        """
        Parses all events and returns a list of Event objects.
        """
        events = self.get_event_dict()
        for event in events.keys():
            self.get_event(event)
        return self._seismic_events.values()

    def plot_event(self, event_name, show_plot=True):
        """
        Plots information about one event on the map.
        """
        from lasif import visualization
        import matplotlib.pyplot as plt

        # Plot the domain.
        bounds = self.domain["bounds"]
        map = visualization.plot_domain(
            bounds["minimum_latitude"], bounds["maximum_latitude"],
            bounds["minimum_longitude"], bounds["maximum_longitude"],
            bounds["boundary_width_in_degree"],
            rotation_axis=self.domain["rotation_axis"],
            rotation_angle_in_degree=self.domain["rotation_angle"],
            plot_simulation_domain=False, show_plot=False, zoom=True)

        all_events = self.get_event_dict()
        if event_name not in all_events:
            msg = "Event '%s' not found in project." % event_name
            raise ValueError(msg)

        event = self.get_event(event_name)
        event_info = self.get_event_info(event_name)

        stations = self.get_stations_for_event(event_name)
        visualization.plot_stations_for_event(
            map_object=map, station_dict=stations, event_info=event_info)
        # Plot the beachball for one event.
        visualization.plot_events([event], map_object=map)

        if show_plot:
            plt.show()

    def plot_events(self, plot_type="map", show_plot=True):
        """
        Plots the domain and beachballs for all events on the map.

        :param plot_type: Determines the type of plot created.
            * ``map`` (default) - a map view of the events
            * ``depth`` - a depth distribution histogram
            * ``time`` - a time distribution histogram
        """
        from lasif import visualization
        import matplotlib.pyplot as plt

        events = self.get_all_events()

        if plot_type == "map":
            bounds = self.domain["bounds"]
            map = visualization.plot_domain(
                bounds["minimum_latitude"], bounds["maximum_latitude"],
                bounds["minimum_longitude"], bounds["maximum_longitude"],
                bounds["boundary_width_in_degree"],
                rotation_axis=self.domain["rotation_axis"],
                rotation_angle_in_degree=self.domain["rotation_angle"],
                plot_simulation_domain=False, show_plot=False, zoom=True)
            visualization.plot_events(events, map_object=map)
        elif plot_type == "depth":
            visualization.plot_event_histogram(events, "depth")
        elif plot_type == "time":
            visualization.plot_event_histogram(events, "time")
        else:
            msg = "Unknown plot_type"
            raise LASIFException(msg)
        if show_plot:
            plt.show()

    def plot_raydensity(self, show_plot=False, save_plot=True):
        """
        Plots the raydensity.
        """
        from lasif import visualization
        import matplotlib.pyplot as plt

        plt.figure(figsize=(20, 21))

        bounds = self.domain["bounds"]
        map_object = visualization.plot_domain(
            bounds["minimum_latitude"], bounds["maximum_latitude"],
            bounds["minimum_longitude"], bounds["maximum_longitude"],
            bounds["boundary_width_in_degree"],
            rotation_axis=self.domain["rotation_axis"],
            rotation_angle_in_degree=self.domain["rotation_angle"],
            plot_simulation_domain=False, show_plot=False, zoom=True,
            resolution="l")

        event_stations = []
        for event_name in self.get_event_dict().keys():
            event = self.get_event(event_name)
            stations = self.get_stations_for_event(event_name)
            event_stations.append((event, stations))

        visualization.plot_raydensity(
            map_object, event_stations, bounds["minimum_latitude"],
            bounds["maximum_latitude"], bounds["minimum_longitude"],
            bounds["maximum_longitude"], self.domain["rotation_axis"],
            self.domain["rotation_angle"])

        events = self.get_all_events()
        visualization.plot_events(events, map_object=map_object)

        plt.tight_layout()

        if show_plot:
            plt.show()

        if save_plot:
            outfile = os.path.join(self.get_output_folder("raydensity_plot"),
                                   "raydensity.png")
            plt.savefig(outfile, dpi=200)
            print "Saved picture at %s" % outfile

    def get_event_info(self, event_name, get_filecount=False):
        """
        Returns a dictionary with information about one, specific event.

        :param name: The event name.
        :type get_filecount: bool, optional
        :param get_filecount: Whether or not to count the files for a given
            event. If True, it will also return the number of files associated
            with the event. Defaults to False.
            It will contain the additional keys:
                * raw_waveform_file_count
                * preprocessed_waveform_file_count
                * synthetic_data_file_count
        """
        from obspy.core.util import FlinnEngdahl

        all_events = self.get_event_dict()
        if event_name not in all_events:
            msg = "Event '%s' not found in project." % event_name
            raise ValueError(msg)
        event = self.get_event(event_name)
        mag = event.preferred_magnitude() or event.magnitudes[0]
        org = event.preferred_origin() or event.origins[0]

        if org.depth is None:
            warnings.warn("Origin contains no depth. Will be assumed to be 0")
            org.depth = 0.0

        if mag.magnitude_type is None:
            warnings.warn("Magnitude has no specified type. Will be assumed "
                          "to be Mw")
            mag.magnitude_type = "Mw"

        info = {
            "latitude": org.latitude,
            "longitude": org.longitude,
            "origin_time": org.time,
            "depth_in_km": org.depth / 1000.0,
            "magnitude": mag.mag,
            "region": FlinnEngdahl().get_region(org.longitude, org.latitude),
            "magnitude_type": mag.magnitude_type}

        if get_filecount is True:
            data_path = os.path.join(self.paths["data"], event_name)
            synth_path = os.path.join(self.paths["synthetics"], event_name)
            raw_data_count = 0
            processed_data_count = 0
            synthetic_data_count = 0
            for dirpath, _, filenames in os.walk(data_path):
                if dirpath.endswith("raw"):
                    raw_data_count += len(filenames)
                elif "preprocessed" in dirpath:
                    processed_data_count += len(filenames)
            for dirpath, _, filenames in os.walk(synth_path):
                synthetic_data_count += len(filenames)
            info["raw_waveform_file_count"] = raw_data_count
            info["synthetic_waveform_file_count"] = synthetic_data_count
            info["preprocessed_waveform_file_count"] = processed_data_count
        return info

    def generate_input_files(self, iteration_name, event_name,
                             simulation_type):
        """
        Generate the input files for one event.

        :param iteration_name: The name of the iteration.
        :param event_name: The name of the event for which to generate the
            input files.
        :param simulation_type: The type of simulation to perform. Possible
            values are: 'normal simulation', 'adjoint forward', 'adjoint
            reverse'
        """
        from wfs_input_generator import InputFileGenerator

        #======================================================================
        # read iteration xml file, get event and list of stations
        #======================================================================

        iteration = self._get_iteration(iteration_name)

        # Check that the event is part of the iterations.
        if event_name not in iteration.events:
            msg = "Event '%s' not part of iteration '%s'." % (
                event_name, iteration_name)
            raise ValueError(msg)
        event = self.get_event(event_name)
        stations_for_event = iteration.events[event_name]["stations"].keys()

        # Get all stations and create a dictionary for the input file
        # generator.
        stations = self.get_stations_for_event(event_name)
        stations = [{
            "id": key, "latitude": value["latitude"],
            "longitude": value["longitude"],
            "elevation_in_m": value["elevation"],
            "local_depth_in_m": value["local_depth"]} for key, value in
            stations.iteritems() if key in stations_for_event]

        #======================================================================
        # set solver options
        #======================================================================

        solver = iteration.solver_settings

        # Currently only SES3D 4.0 is supported
        if solver["solver"].lower() != "ses3d 4.0":
            msg = "Currently only SES3D 4.0 is supported."
            raise ValueError(msg)

        solver = solver["solver_settings"]

        #======================================================================
        # create the input file generator, add event and stations,
        # populate the configuration items
        #======================================================================

        # Add the event and the stations to the input file generator.
        gen = InputFileGenerator()
        gen.add_events(event)
        gen.add_stations(stations)

        # event tag
        gen.config.event_tag = event_name

        # Time configuration.
        npts = solver["simulation_parameters"]["number_of_time_steps"]
        delta = solver["simulation_parameters"]["time_increment"]
        gen.config.number_of_time_steps = npts
        gen.config.time_increment_in_s = delta

        # SES3D specific configuration
        gen.config.output_folder = solver["output_directory"].replace(
            "{{EVENT_NAME}}", event_name.replace(" ", "_"))
        gen.config.simulation_type = simulation_type

        gen.config.adjoint_forward_wavefield_output_folder = \
            solver["adjoint_output_parameters"][
                "forward_field_output_directory"].replace(
                "{{EVENT_NAME}}", event_name.replace(" ", "_"))
        gen.config.adjoint_forward_sampling_rate = \
            solver["adjoint_output_parameters"][
                "sampling_rate_of_forward_field"]

        # Visco-elastic dissipation
        diss = solver["simulation_parameters"]["is_dissipative"]
        if diss.lower() == "false":
            diss = False
        elif diss.lower() == "true":
            diss = True
        else:
            msg = ("is_dissipative value of '%s' unknown. "
                   "Choose true or false.") % diss
            raise ValueError(msg)
        gen.config.is_dissipative = diss

        gen.config.tau = solver["relaxation_parameter_list"]["tau"]
        gen.config.w = solver["relaxation_parameter_list"]["w"]

        # Discretization
        disc = solver["computational_setup"]
        gen.config.nx_global = disc["nx_global"]
        gen.config.ny_global = disc["ny_global"]
        gen.config.nz_global = disc["nz_global"]
        gen.config.px = disc["px_processors_in_theta_direction"]
        gen.config.py = disc["py_processors_in_phi_direction"]
        gen.config.pz = disc["pz_processors_in_r_direction"]
        gen.config.lagrange_polynomial_degree = \
            disc["lagrange_polynomial_degree"]

        # Configure the mesh.
        gen.config.mesh_min_latitude = \
            self.domain["bounds"]["minimum_latitude"]
        gen.config.mesh_max_latitude = \
            self.domain["bounds"]["maximum_latitude"]
        gen.config.mesh_min_longitude = \
            self.domain["bounds"]["minimum_longitude"]
        gen.config.mesh_max_longitude = \
            self.domain["bounds"]["maximum_longitude"]
        gen.config.mesh_min_depth_in_km = \
            self.domain["bounds"]["minimum_depth_in_km"]
        gen.config.mesh_max_depth_in_km = \
            self.domain["bounds"]["maximum_depth_in_km"]

        # Set the rotation parameters.
        gen.config.rotation_angle_in_degree = self.domain["rotation_angle"]
        gen.config.rotation_axis = self.domain["rotation_axis"]

        # Make source time function
        gen.config.source_time_function = \
            iteration.get_source_time_function()["data"]

        #======================================================================
        # output
        #======================================================================
        output_dir = self.get_output_folder(
            "input_files___ITERATION_%s__%s__EVENT_%s" % (
                iteration_name, simulation_type.replace(" ", "_"), event_name))

        gen.write(format="ses3d_4_0", output_dir=output_dir)
        print "Written files to '%s'." % output_dir

    def get_output_folder(self, tag):
        """
        Generates a output folder in a unified way.
        """
        from datetime import datetime
        output_dir = ("%s___%s" % (str(datetime.now()), tag)).replace(" ", "T")
        output_dir = os.path.join(self.paths["output"], output_dir)
        if not os.path.exists(output_dir):
            os.makedirs(output_dir)
        return output_dir

    @property
    def station_cache(self):
        """
        Kind of like an instance wide StationCache singleton.
        """
        return self._update_station_cache(show_progress=True)

    def _update_station_cache(self, show_progress=True):
        """
        Function actually updating the station cache.

        Separate function from the property so it can be accessed separately if
        the need arises.
        """
        from lasif.tools.station_cache import StationCache
        if hasattr(self, "_station_cache"):
            return self._station_cache
        self._station_cache = StationCache(
            os.path.join(self.paths["cache"], "station_cache.sqlite"),
            self.paths["dataless_seed"], self.paths["resp"],
            show_progress=show_progress)
        return self._station_cache

    def _get_waveform_cache_file(self, event_name, tag, waveform_type="data",
                                 show_progress=True):
        """
        Helper function returning the waveform cache file for the data from a
        specific event and a certain tag.
        Example to return the cache for the original data for 'event_1':
        _get_waveform_cache_file("event_1", "raw", waveform_type="data")

        """
        if waveform_type not in ["data", "synthetics"]:
            msg = "waveform_type must be either 'data' or 'synthetics'."
            raise LASIFException(msg)

        from lasif.tools.waveform_cache import WaveformCache

        waveform_db_file = os.path.join(
            self.paths[waveform_type], event_name, "%s_cache.sqlite" % tag)
        data_path = os.path.join(self.paths[waveform_type], event_name, tag)

        if not os.path.exists(data_path):
            return False
        return WaveformCache(waveform_db_file, data_path, show_progress)

    def get_stations_for_event(self, event_name):
        """
        Returns a dictionary containing a little bit of information about all
        stations available for a given event.

        An available station is defined as a station with an existing station
        file and an existing waveform file.

        Will return an empty dictionary if nothing is found.

        Example return value:
        {"BW.ROTZ": {"latitude": 10, "longitude": 11, "elevation": 12,
                     "local_depth": 13},
         "BW.ROTZ2": ...,
         ...}
        """
        all_events = self.get_event_dict()
        if event_name not in all_events:
            msg = "Event '%s' not found in project." % event_name
            raise ValueError(msg)

        data_path = os.path.join(self.paths["data"], event_name, "raw")
        if not os.path.exists(data_path):
            return {}

        waveforms = self._get_waveform_cache_file(event_name, "raw")

        # Query the station cache for a list of all channels.
        available_channels = self.station_cache.get_channels()
        stations = {}
        for waveform in waveforms.get_values():
            station = "%s.%s" % (waveform["network"], waveform["station"])
            # Do not add if already exists.
            if station in stations:
                continue
            # Check if a corresponding station file exists, otherwise skip.
            chan_id = waveform["channel_id"]
            if chan_id not in available_channels:
                continue
            coordinates = self._get_coordinates_for_channel(
                waveform, available_channels)
            if not coordinates:
                msg = "No coordinates available for waveform file '%s'" % \
                    waveform["filename"]
                warnings.warn(msg)
                continue
            stations[station] = {
                "latitude": coordinates["latitude"],
                "longitude": coordinates["longitude"],
                "elevation": coordinates["elevation"],
                "local_depth": coordinates["local_depth"]}
        return stations

    def _get_coordinates_for_channel(self, waveform_cache_entry,
                                     channels_from_station_cache):
        """
        Internal function used to grab station coordinates from the various
        sources.

        Used to make sure the same functionality is used everywhere.

        :param waveform_cache_entry: The entry of the file in question from the
            waveform cache.
        :param channels_from_station_cache: self.station_cache.get_channels()

        Returns a dictionary containing "latitude", "longitude", "elevation",
            "local_depth". Returns None if no coordinates could be found.
        """
        from lasif.tools.inventory_db import get_station_coordinates
        channel_id = waveform_cache_entry["channel_id"]

        # Now check if the waveform has coordinates (in the case of SAC
        # files).
        if channel_id not in channels_from_station_cache:
            return None
        channel = channels_from_station_cache[channel_id][0]
        if waveform_cache_entry["latitude"]:
            return {
                "latitude": waveform_cache_entry["latitude"],
                "longitude": waveform_cache_entry["longitude"],
                "elevation": waveform_cache_entry["elevation_in_m"],
                "local_depth": waveform_cache_entry["local_depth_in_m"]}
        elif channel["latitude"]:
            return {
                "latitude": channel["latitude"],
                "longitude": channel["longitude"],
                "elevation": channel["elevation_in_m"],
                "local_depth": channel["local_depth_in_m"]}
        else:
            # Now check if the station_coordinates are available in the
            # inventory DB and use those.
            coords = get_station_coordinates(
                self.paths["inv_db_file"], ".".join(channel_id.split(".")[:2]),
                self.paths["cache"],
                self.config["download_settings"]["arclink_username"])
            if coords:
                return {
                    "latitude": coords["latitude"],
                    "longitude": coords["longitude"],
                    "elevation": coords["elevation_in_m"],
                    "local_depth": coords["local_depth_in_m"]}
            else:
                return None

    def validate_data(self, full_check=False):
        """
        Validates all data of the current project.

        This commands walks through all available data and checks it for
        validity.  It furthermore does some sanity checks to detect common
        problems. These should be fixed.

        Event files:
            * Validate against QuakeML 1.2 scheme.
            * Make sure they contain at least one origin, magnitude and focal
              mechanism object.
            * Check for duplicate ids amongst all QuakeML files.
            * Some simply sanity checks so that the event depth is reasonable
              and the moment tensor values as well. This is rather fragile and
              mainly intended to detect values specified in wrong units.
        """
        import sys

        # Shared formatting for all.
        ok_string = " %s[%sOK%s]%s" % (
            colorama.Style.BRIGHT, colorama.Style.NORMAL + colorama.Fore.GREEN,
            colorama.Fore.RESET + colorama.Style.BRIGHT,
            colorama.Style.RESET_ALL)
        fail_string = " %s[%sFAIL%s]%s" % (
            colorama.Style.BRIGHT, colorama.Style.NORMAL + colorama.Fore.RED,
            colorama.Fore.RESET + colorama.Style.BRIGHT,
            colorama.Style.RESET_ALL)

        def flush_point():
            sys.stdout.write(".")
            sys.stdout.flush()

        reports = []
        total_error_count = [0]

        def add_report(message, error_count=1):
            reports.append(message)
            total_error_count[0] += error_count

        # Update the caches.
        self._validate_event_files(ok_string, fail_string,
                                   flush_point, add_report)
        self._update_all_waveform_caches(ok_string, fail_string,
                                         flush_point, add_report)
        print "Updating station cache ...",
        self._update_station_cache(show_progress=False)
        print ok_string

        self._validate_station_files_availability(ok_string, fail_string,
                                                  flush_point, add_report)

        self._validate_coordinate_deduction(ok_string, fail_string,
                                            flush_point, add_report)

        if full_check is True:
            self._validate_raypaths_in_domain(ok_string, fail_string,
                                              flush_point, add_report)
        else:
            print "Skipping raypath check. Perform a full check for it."

        if not reports:
            print("\n%sALL CHECKS PASSED%s\n"
                  "The data seems to be valid. If we missed something please "
                  "contact the developers." % (colorama.Fore.GREEN,
                                               colorama.Fore.RESET))
        else:
            filename = os.path.join(self.get_output_folder(
                "DATA_INTEGRITY_REPORT"), "report.txt")
            seperator_string = "\n" + 80 * "=" + "\n" + 80 * "=" + "\n"
            with open(filename, "wt") as fh:
                for report in reports:
                    fh.write(report.strip())
                    fh.write(seperator_string)
            print("\n%sFAILED%s\nEncountered %i errors!\n"
                  "A report has been created at '%s'.\n" %
                  (colorama.Fore.RED, colorama.Fore.RESET,
                   total_error_count[0], os.path.relpath(filename)))

    def _validate_raypaths_in_domain(self, ok_string, fail_string, flush_point,
                                     add_report):
        """
        Checks that all raypaths are within the specified domain boundaries.
        """
        print "Making sure raypaths are within boundaries ",

        all_good = True

        for event in self.get_event_dict().iterkeys():
            waveform_files_for_event = \
                self._get_waveform_cache_file(event, "raw").get_values()
            flush_point()
            for station_id, value in \
                    self.get_stations_for_event(event).iteritems():
                network, station = station_id.split(".")
                value["latitude"], value["longitude"]
                # Check if the whole path of the event-station pair is within
                # the domain boundaries.
                if self.is_event_station_raypath_within_boundaries(
                        event, value["latitude"], value["longitude"],
                        raypath_steps=12):
                    continue
                # Otherwise get all waveform files for that station.
                waveform_files = [_i["filename"]
                                  for _i in waveform_files_for_event
                                  if (_i["network"] == network) and
                                  (_i["station"] == station)]
                if not waveform_files:
                    continue
                all_good = False
                for filename in waveform_files:
                    add_report(
                        "WARNING: "
                        "The event-station raypath for the file\n\t'{f}'\n "
                        "does not fully lay within the domain. You might want "
                        "to remove the file or change the domain "
                        "specifications.".format(f=os.path.relpath(filename)))
        if all_good:
            print ok_string
        else:
            print fail_string

    def _update_all_waveform_caches(self, ok_string, fail_string,
                                    flush_point, add_report):
        """
        Update all waveform caches.
        """
        print "Updating all raw waveform caches ",
        for event_name in self.get_event_dict().iterkeys():
            flush_point()
            self._get_waveform_cache_file(event_name, "raw",
                                          show_progress=False)
        print ok_string

    def _validate_coordinate_deduction(self, ok_string, fail_string,
                                       flush_point, add_report):
        """
        Function validating that coordinates for all stations can be found.

        This is essentially only important for the combination of MiniSEED and
        RESP files. Otherwise either a SAC file or other station files will
        contain the coordinates.
        """
        print ("Confirming that station metainformation files exist for "
               "all waveforms "),
        #channels_from_station_cache = self.station_cache.get_channels()
        all_good = True
        for event_name in self.get_event_dict().iterkeys():
            flush_point()
            waveform_cache = self._get_waveform_cache_file(event_name, "raw",
                                                           show_progress=False)
            if not waveform_cache:
                continue
            #for channel in waveform_cache.get_values():
                #coordinates = self._get_coordinates_for_channel(
                    #channel, channels_from_station_cache)

        if all_good is True:
            print ok_string
        else:
            print fail_string

    def _validate_station_files_availability(self, ok_string, fail_string,
                                             flush_point, add_report):
        """
        Checks that all waveform files have an associated station file.
        """
        from obspy import UTCDateTime

        print ("Confirming that station metainformation files exist for "
               "all waveforms "),
        station_cache = self.station_cache
        all_good = True
        for event_name in self.get_event_dict().iterkeys():
            flush_point()
            waveform_cache = self._get_waveform_cache_file(event_name, "raw",
                                                           show_progress=False)
            if not waveform_cache:
                continue
            for channel in waveform_cache.get_values():
                station_file = station_cache.get_station_filename(
                    channel["channel_id"],
                    UTCDateTime(channel["starttime_timestamp"]))
                if station_file is not None:
                    continue
                add_report(
                    "WARNING: "
                    "No station metainformation available for the waveform "
                    "file\n\t'{waveform_file}'\n"
                    "If you have a station file for that channel make sure "
                    "it actually covers the time span of the data.\n"
                    "Otherwise contact the developers...".format(
                        waveform_file=os.path.relpath(channel["filename"])))
                all_good = False
            break
        if all_good:
            print ok_string
        else:
            print fail_string

    def _validate_event_files(self, ok_string, fail_string, flush_point,
                              add_report):
        """
        Validates all event files in the currently active project.

        The following tasks are performed:
            * Validate against QuakeML 1.2 scheme.
            * Check for duplicate ids amongst all QuakeML files.
            * Make sure they contain at least one origin, magnitude and focal
              mechanism object.
            * Some simply sanity checks so that the event depth is reasonable
              and the moment tensor values as well. This is rather fragile and
              mainly intended to detect values specified in wrong units.
            * Events that are too close in time. Events that are less then one
              hour apart can in general not be used for adjoint tomography.
              This will naturally also detect duplicate events.
        """
        import collections
        import itertools
        import math
        from obspy import readEvents
        from obspy.core.event import ResourceIdentifier
        from obspy.core.quakeml import _validate as validate_quakeml
        from lasif import utils
        from lxml import etree

        event_files = self.get_event_dict().values()

        print "Validating %i event files..." % len(event_files)

        # Start with the schema validation.
        print "\tValidating against QuakeML 1.2 schema ",
        all_valid = True
        for filename in event_files:
            flush_point()
            if validate_quakeml(filename) is not True:
                all_valid = False
                msg = (
                    "ERROR: "
                    "The QuakeML file '{basename}' did not validate against "
                    "the QuakeML 1.2 schema. Unfortunately the error messages "
                    "delivered by lxml are not useful at all. To get useful "
                    "error messages make sure jing is installed "
                    "('brew install jing' (OSX) or "
                    "'sudo apt-get install jing' (Debian/Ubuntu)) and "
                    "execute the following command:\n\n"
                    "\tjing http://quake.ethz.ch/schema/rng/QuakeML-1.2.rng "
                    "{filename}\n\n"
                    "Alternatively you could also use the "
                    "'lasif add_spud_event' command to redownload the event "
                    "if it is in the GCMT "
                    "catalog.\n\n").format(
                    basename=os.path.basename(filename),
                    filename=os.path.relpath(filename))
                add_report(msg)
        if all_valid is True:
            print ok_string
        else:
            print fail_string

        # Now check for duplicate public IDs.
        print "\tChecking for duplicate public IDs ",
        ids = collections.defaultdict(list)
        for filename in event_files:
            flush_point()
            # Now walk all files and collect all public ids. Each should be
            # unique!
            with open(filename, "rt") as fh:
                for event, elem in etree.iterparse(fh, events=("start",)):
                    if "publicID" not in elem.keys():
                        continue
                    ids[elem.get("publicID")].append(filename)
        ids = {key: list(set(value)) for (key, value) in ids.iteritems()
               if len(value) > 1}
        if not ids:
            print ok_string
        else:
            print fail_string
            add_report(
                "Found the following duplicate publicIDs:\n" +
                "\n".join(["\t%s in files: %s" % (
                    id_string,
                    ", ".join([os.path.basename(i) for i in faulty_files]))
                    for id_string, faulty_files in ids.iteritems()]),
                error_count=len(ids))

        def print_warning(filename, message):
            add_report("WARNING: File '{event_name}' "
                       "contains {msg}.\n".format(
                           event_name=os.path.basename(filename),
                           msg=message))

        # Performing simple sanity checks.
        print "\tPerforming some basic sanity checks ",
        all_good = True
        for filename in event_files:
            flush_point()
            cat = readEvents(filename)
            filename = os.path.basename(filename)
            # Check that all files contain exactly one event!
            if len(cat) != 1:
                all_good = False
                print_warning(filename, "%i events instead of only one." %
                              len(cat))
            event = cat[0]

            # Sanity checks related to the origin.
            if not event.origins:
                all_good = False
                print_warning(filename, "no origin")
                continue
            origin = event.preferred_origin() or event.origins[0]
            if (origin.depth % 100.0):
                all_good = False
                print_warning(
                    filename, "a depth of %.1f meters. This kind of "
                    "accuracy seems unrealistic. The depth in the QuakeML "
                    "file has to be specified in meters. Checking all other "
                    "QuakeML files for the correct units might be a good idea"
                    % origin.depth)
            if (origin.depth > (800.0 * 1000.0)):
                all_good = False
                print_warning(filename, "a depth of more than 800 km. This is"
                              " likely wrong.")

            # Sanity checks related to the magnitude.
            if not event.magnitudes:
                all_good = False
                print_warning(filename, "no magnitude")
                continue

            # Sanity checks related to the focal mechanism.
            if not event.focal_mechanisms:
                all_good = False
                print_warning(filename, "no focal mechanism")
                continue

            focmec = event.preferred_focal_mechanism() or \
                event.focal_mechanisms[0]
            if not hasattr(focmec, "moment_tensor") or \
                    not focmec.moment_tensor:
                all_good = False
                print_warning(filename, "no moment tensor")
                continue

            mt = focmec.moment_tensor
            if not hasattr(mt, "tensor") or \
                    not mt.tensor:
                all_good = False
                print_warning(filename, "no actual moment tensor")
                continue
            tensor = mt.tensor

            # Convert the moment tensor to a magnitude and see if it is
            # reasonable.
            mag_in_file = event.preferred_magnitude() or event.magnitudes[0]
            mag_in_file = mag_in_file.mag
            M_0 = 1.0 / math.sqrt(2.0) * math.sqrt(
                tensor.m_rr ** 2 + tensor.m_tt ** 2 + tensor.m_pp ** 2)
            magnitude = 2.0 / 3.0 * math.log10(M_0) - 6.0
            # Use some buffer to account for different magnitudes.
            if not (mag_in_file - 1.0) < magnitude < (mag_in_file + 1.0):
                all_good = False
                print_warning(
                    filename, "a moment tensor that would result in "
                    "a moment magnitude of %.2f. The magnitude specified in "
                    "the file is %.2f. "
                    "Please check that all components of the tensor are in "
                    "Newton * meter"
                    % (magnitude, mag_in_file))

        # HACKISH! Reset the dictionary collecting the id references! This is
        # done to be able to read the same file twice.
        ResourceIdentifier._ResourceIdentifier__resource_id_weak_dict.clear()

        if all_good is True:
            print ok_string
        else:
            print fail_string

        # Collect event times
        event_infos = []
        for filename in event_files:
            event_info = self.get_event_info(os.path.splitext(
                os.path.basename(filename))[0])
            event_info["filename"] = os.path.basename(filename)
            event_infos.append(event_info)

        # Now check the time distribution of events.
        print "\tChecking for duplicates and events too close in time %s" % \
            (len(event_files) * "."),
        all_good = True
        # Sort the events by time.
        event_infos = sorted(event_infos, key=lambda x: x["origin_time"])
        # Loop over adjacent indices.
        a, b = itertools.tee(event_infos)
        next(b, None)
        for event_1, event_2 in itertools.izip(a, b):
            time_diff = abs(event_2["origin_time"] - event_1["origin_time"])
            # If time difference is under one hour, it could be either a
            # duplicate event or interfering events.
            if time_diff <= 3600.0:
                all_good = False
                add_report(
                    "WARNING: "
                    "The time difference between events '{file_1}' and "
                    "'{file_2}' is only {diff:.1f} minutes. This could "
                    "be either due to a duplicate event or events that have "
                    "interfering waveforms.\n".format(
                        file_1=event_1["filename"],
                        file_2=event_2["filename"],
                        diff=time_diff / 60.0))
        if all_good is True:
            print ok_string
        else:
            print fail_string

        # Check that all events fall within the chosen boundaries.
        print "\tAssure all events are in chosen domain %s" % \
            (len(event_files) * "."),
        all_good = True
        for event in event_infos:
            if utils.point_in_domain(
                    event["latitude"],
                    event["longitude"], self.domain["bounds"],
                    self.domain["rotation_axis"],
                    self.domain["rotation_angle"]) is True:
                continue
            all_good = False
            add_report(
                "\nWARNING: "
                "Event '{filename}' is out of bounds of the chosen domain."
                "\n".format(filename=event["filename"]))
        if all_good is True:
            print ok_string
        else:
            print fail_string

    def is_event_station_raypath_within_boundaries(
            self, event_name, station_latitude, station_longitude,
            raypath_steps=25):
        """
        Checks if the full station-event raypath is within the project's domain
        boundaries.

        Returns True if this is the case, False if not.

        :type event_name: string
        :param event_name: The project internal event name.
        :type station_latitude: float
        :param station_latitude: The station latitude.
        :type station_longitude: float
        :param station_longitude: The station longitude.
        :type raypath_steps: int, optional
        :param raypath_steps: The number of discrete points along the raypath
            that will be checked.
        """
        from lasif.utils import greatcircle_points, Point, point_in_domain

        # Get the event information.
        ev = self.get_event_info(event_name)
        event_latitude = ev["latitude"]
        event_longitude = ev["longitude"]

        for point in greatcircle_points(
                Point(station_latitude, station_longitude),
                Point(event_latitude, event_longitude),
                max_npts=raypath_steps):

            if not point_in_domain(
                    point.lat, point.lng, self.domain["bounds"],
                    rotation_axis=self.domain["rotation_axis"],
                    rotation_angle_in_degree=self.domain["rotation_angle"]):
                return False
        return True

    def finalize_adjoint_sources(self, iteration_name, event_name):
        """
        Finalizes the adjoint sources.
        """

        from itertools import izip
        import numpy as np

        from lasif import rotations
        from lasif.window_manager import MisfitWindowManager
        from lasif.adjoint_src_manager import AdjointSourceManager

        #=====================================================================
        #- initialisations
        #=====================================================================

        iteration = self._get_iteration(iteration_name)
        long_iteration_name = self._get_long_iteration_name(iteration_name)

        window_directory = os.path.join(self.paths["windows"], event_name,
                                        long_iteration_name)
        ad_src_directory = os.path.join(self.paths["adjoint_sources"],
                                        event_name, long_iteration_name)
        window_manager = MisfitWindowManager(window_directory,
                                             long_iteration_name, event_name)
        adj_src_manager = AdjointSourceManager(ad_src_directory)

        this_event = iteration.events[event_name]

        event_weight = this_event["event_weight"]
        all_stations = self.get_stations_for_event(event_name)

        all_coordinates = []
        _i = 0

        output_folder = self.get_output_folder(
            "adjoint_sources__ITERATION_%s__%s" % (iteration_name, event_name))

        #======================================================================
        #- loop through all the stations of this event
        #======================================================================

        for station_name, station in this_event["stations"].iteritems():

            try:
                this_station = all_stations[station_name]
            except KeyError:
                continue

            station_weight = station["station_weight"]
            windows = window_manager.get_windows_for_station(station_name)

            if not windows:
                msg = "No adjoint sources for station '%s'." % station_name
                warnings.warn(msg)
                continue

            all_channels = {}

            #- loop through all channels for that station --------------------
            for channel_windows in windows:

                channel_id = channel_windows["channel_id"]
                cumulative_weight = 0
                all_data = []

                #- loop through all windows of one channel -------------------
                for window in channel_windows["windows"]:

                    #- get window properties
                    window_weight = window["weight"]
                    starttime = window["starttime"]
                    endtime = window["endtime"]
                    #- load previously stored adjoint source
                    data = adj_src_manager.get_adjoint_src(channel_id,
                                                           starttime, endtime)
                    # lump all adjoint sources together
                    all_data.append(window_weight * data)
                    # compute cumulative weight of all windows for that channel
                    cumulative_weight += window_weight

                #- apply weights for that channel -----------------------------
                data = all_data.pop()
                for d in all_data:
                    data += d
                data /= cumulative_weight
                data *= station_weight * event_weight
                all_channels[channel_id[-1]] = data

            length = len(all_channels.values()[0])
            # Use zero for empty ones.
            for component in ["N", "E", "Z"]:
                if component in all_channels:
                    continue
                all_channels[component] = np.zeros(length)

            #- Rotate. if needed ----------------------------------------------

            rec_lat = this_station["latitude"]
            rec_lng = this_station["longitude"]

            if self.domain["rotation_angle"]:
                # Rotate the adjoint source location.
                r_rec_lat, r_rec_lng = rotations.rotate_lat_lon(
                    rec_lat, rec_lng, self.domain["rotation_axis"],
                    -self.domain["rotation_angle"])
                # Rotate the adjoint sources.
                all_channels["N"], all_channels["E"], all_channels["Z"] = \
                    rotations.rotate_data(
                        all_channels["N"], all_channels["E"],
                        all_channels["Z"], rec_lat, rec_lng,
                        self.domain["rotation_axis"],
                        self.domain["rotation_angle"])
            else:
                r_rec_lat = rec_lat
                r_rec_lng = rec_lng
            r_rec_depth = 0.0
            r_rec_colat = rotations.lat2colat(r_rec_lat)

            CHANNEL_MAPPING = {"X": "N", "Y": "E", "Z": "Z"}

            _i += 1

            adjoint_src_filename = os.path.join(output_folder,
                                                "ad_src_%i" % _i)

            all_coordinates.append((r_rec_colat, r_rec_lng, r_rec_depth))

            #- Actually write the adjoint source file in SES3D specific format.

            with open(adjoint_src_filename, "wt") as open_file:
                open_file.write("-- adjoint source ------------------\n")
                open_file.write("-- source coordinates (colat,lon,depth)\n")
                open_file.write("%f %f %f\n" % (r_rec_colat, r_rec_lng,
                                                r_rec_depth))
                open_file.write("-- source time function (x, y, z) --\n")
                for x, y, z in izip(-1.0 * all_channels[CHANNEL_MAPPING["X"]],
                                    all_channels[CHANNEL_MAPPING["Y"]],
                                    -1.0 * all_channels[CHANNEL_MAPPING["Z"]]):
                    open_file.write("%e %e %e\n" % (x, y, z))
                open_file.write("\n")

        # Write the final file.
        with open(os.path.join(output_folder, "ad_srcfile"), "wt") as fh:
            fh.write("%i\n" % _i)
            for line in all_coordinates:
                fh.write("%.6f %.6f %.6f\n" % (line[0], line[1], line[2]))
            fh.write("\n")

        print "Wrote %i adjoint sources to %s." % (_i, output_folder)

    def data_synthetic_iterator(self, event_name, iteration_name):

        from lasif import rotations
        from obspy import read, Stream

        #======================================================================
        # Retrieve information on the event, iteration and waveforms
        #======================================================================

        event_info = self.get_event_info(event_name)
        iteration = self._get_iteration(iteration_name)

        iteration_stations = iteration.events[event_name]["stations"].keys()

        stations = {key: value for key, value in
                    self.get_stations_for_event(event_name).iteritems()
                    if key in iteration_stations}

        waveforms = self._get_waveform_cache_file(
            event_name, iteration.get_processing_tag()).get_values()

        synthetic_files = self._get_synthetic_waveform_filenames(
            event_name, iteration_name)

        if not synthetic_files:
            msg = "Could not find suitable synthetic files."
            raise ValueError(msg)

        SYNTH_MAPPING = {"X": "N", "Y": "E", "Z": "Z"}

        class TwoWayIter(object):
            def __init__(self, rot_angle=0.0, rot_axis=[0.0, 0.0, 1.0]):
                self.items = stations.items()
                self.current_index = -1
                self.rot_angle = rot_angle
                self.rot_axis = rot_axis
                self.highpass_period = \
                    iteration.data_preprocessing["highpass_period"]
                self.lowpass_period = \
                    iteration.data_preprocessing["lowpass_period"]

            def next(self):
                self.current_index += 1
                if self.current_index > (len(self.items) - 1):
                    self.current_index = len(self.items) - 1
                    raise StopIteration
                return self.get_value()

            def prev(self):
                self.current_index -= 1
                if self.current_index < 0:
                    self.current_index = 0
                    raise StopIteration
                return self.get_value()

            def __iter__(self):
                return self

            def get_value(self):

                station_id, coordinates = self.items[self.current_index]
                data = Stream()

                # Now get the actual waveform files. Also find the
                # corresponding station file and check the coordinates.
                this_waveforms = {
                    _i["channel_id"]: _i for _i in waveforms
                    if _i["channel_id"].startswith(station_id + ".")}

                for key, value in this_waveforms.iteritems():
                    data += read(value["filename"])[0]
                if not this_waveforms:
                    msg = "Could not retrieve data for station '%s'." % \
                        station_id
                    warnings.warn(msg)
                    return None

                # Now attempt to get the synthetics.
                if station_id not in synthetic_files:
                    msg = "No synthetics found for station '%s'" % station_id
                    warnings.warn(msg)
                    return None

                station_synthetics = synthetic_files[station_id]

                if len(station_synthetics) != 3:
                    msg = "Found %i not 3 synthetics for station '%s'." % (
                        len(station_synthetics), station_id)
                    warnings.warn(msg)
                    return None

                synthetics = Stream()

                # Read all synthetics.
                for filename in station_synthetics.itervalues():
                    synthetics += read(filename)
                for synth in synthetics:
                    if synth.stats.channel in ["X", "Z"]:
                        synth.data *= -1.0
                    synth.stats.channel = SYNTH_MAPPING[synth.stats.channel]
                    synth.stats.starttime = event_info["origin_time"]

                # Scale the data
                try:
                    n_d_trace = data.select(component="N")[0]
                except:
                    n_d_trace = None
                try:
                    e_d_trace = data.select(component="E")[0]
                except:
                    e_d_trace = None
                try:
                    z_d_trace = data.select(component="Z")[0]
                except Exception:
                    z_d_trace = None
                n_s_trace = synthetics.select(component="N")[0]
                e_s_trace = synthetics.select(component="E")[0]
                z_s_trace = synthetics.select(component="Z")[0]

                #- Rotate the synthetics if nessesary. ------------------------
                if self.rot_angle:
                    # First rotate the station back to see, where it was
                    # recorded.
                    lat, lng = rotations.rotate_lat_lon(
                        coordinates["latitude"], coordinates["longitude"],
                        self.rot_axis, -self.rot_angle)
                    # Rotate the synthetics.
                    n, e, z = rotations.rotate_data(
                        n_s_trace.data, e_s_trace.data, z_s_trace.data, lat,
                        lng, self.rot_axis, self.rot_angle)
                    n_s_trace.data = n
                    e_s_trace.data = e
                    z_s_trace.data = z

                #- Scale the data to the synthetics. --------------------------
                if n_d_trace:
                    scaling_factor = n_s_trace.data.ptp() / \
                        n_d_trace.data.ptp()
                    n_d_trace.stats.scaling_factor = scaling_factor
                    n_d_trace.data *= scaling_factor
                if e_d_trace:
                    scaling_factor = e_s_trace.data.ptp() / \
                        e_d_trace.data.ptp()
                    e_d_trace.stats.scaling_factor = scaling_factor
                    e_d_trace.data *= scaling_factor
                if z_d_trace:
                    scaling_factor = z_s_trace.data.ptp() / \
                        z_d_trace.data.ptp()
                    z_d_trace.stats.scaling_factor = scaling_factor
                    z_d_trace.data *= scaling_factor

                return {"data": data, "synthetics": synthetics,
                        "coordinates": coordinates}

        return TwoWayIter(self.domain["rotation_angle"],
                          self.domain["rotation_axis"])

    def get_debug_information_for_file(self, filename):
        """
        Helper function returning a string with information LASIF knows about
        the file.

        Currently only works with waveform and station files.
        """
        from obspy import read, UTCDateTime

        err_msg = "LASIF cannot gather any information from the file."
        filename = os.path.abspath(filename)

        # Data file.
        if os.path.commonprefix([filename, self.paths["data"]]) == \
                self.paths["data"]:
            # Now split the path in event_name, tag, and filename. Any deeper
            # paths should not be allowed.
            rest, _ = os.path.split(os.path.relpath(filename,
                                                    self.paths["data"]))
            event_name, rest = os.path.split(rest)
            rest, tag = os.path.split(rest)
            # Now rest should not be existant anymore
            if rest:
                msg = "File is nested too deep in the data directory."
                raise LASIFException(msg)
            if tag.startswith("preprocessed_"):
                return ("The waveform file is a preprocessed file. LASIF will "
                        "not use it to extract any metainformation.")
            elif tag == "raw":
                # Get the corresponding waveform cache file.
                waveforms = self._get_waveform_cache_file(event_name, "raw")
                if not waveforms:
                    msg = "LASIF could not read the waveform file."
                    raise LASIFException(msg)
                details = waveforms.get_details(filename)
                if not details:
                    msg = "LASIF could not read the waveform file."
                    raise LASIFException(msg)
                filetype = read(filename)[0].stats._format
                # Now assemble the final return string.
                return (
                    "The {typ} file contains {c} channel{p}:\n"
                    "{channels}".format(
                        typ=filetype, c=len(details),
                        p="s" if len(details) != 1 else "",
                        channels="\n".join([
                            "\t{chan} | {start} - {end} | "
                            "Lat/Lng/Ele/Dep: {lat}/{lng}/"
                            "{ele}/{dep}".format(
                                chan=_i["channel_id"],
                                start=str(UTCDateTime(
                                    _i["starttime_timestamp"])),
                                end=str(UTCDateTime(_i["endtime_timestamp"])),
                                lat="%.2f" % _i["latitude"]
                                if _i["latitude"] is not None else "--",
                                lng="%.2f" % _i["longitude"]
                                if _i["longitude"] is not None else "--",
                                ele="%.2f" % _i["elevation_in_m"]
                                if _i["elevation_in_m"] is not None else "--",
                                dep="%.2f" % _i["local_depth_in_m"]
                                if _i["local_depth_in_m"]
                                is not None else "--",
                                ) for _i in details])))
            else:
                msg = "The waveform tag '%s' is not used by LASIF." % tag
                raise LASIFException(msg)

        # Station files.
        elif os.path.commonprefix([filename, self.paths["stations"]]) == \
                self.paths["stations"]:
            # Get the station cache
            details = self.station_cache.get_details(filename)
            if not details:
                raise LASIFException(err_msg)
            if filename in self.station_cache.files["resp"]:
                filetype = "RESP"
            elif filename in self.station_cache.files["seed"]:
                filetype = "SEED"
            else:
                # This really should not happen.
                raise NotImplementedError
            # Now assemble the final return string.
            return (
                "The {typ} file contains information about {c} channel{p}:\n"
                "{channels}".format(
                    typ=filetype, c=len(details),
                    p="s" if len(details) != 1 else "",
                    channels="\n".join([
                        "\t{chan} | {start} - {end} | "
                        "Lat/Lng/Ele/Dep: {lat}/{lng}/"
                        "{ele}/{dep}".format(
                            chan=_i["channel_id"],
                            start=str(UTCDateTime(_i["start_date"])),
                            end=str(UTCDateTime(_i["end_date"]))
                            if _i["end_date"] else "--",
                            lat="%.2f" % _i["latitude"]
                            if _i["latitude"] is not None else "--",
                            lng="%.2f" % _i["longitude"]
                            if _i["longitude"] is not None else "--",
                            ele="%.2f" % _i["elevation_in_m"]
                            if _i["elevation_in_m"] is not None else "--",
                            dep="%.2f" % _i["local_depth_in_m"]
                            if _i["local_depth_in_m"] is not None else "--",
                            ) for _i in details])))
        else:
            raise LASIFException(err_msg)

    def has_station_file(self, channel_id, time):
        """
        Simple function returning True or False, if the channel specified with
        it's filename actually has a corresponding station file.
        """
        return self.station_cache.station_info_available(channel_id, time)

    def is_event_in_project(self, event_name):
        """
        Convenience function. Returns true if the event is in the project,
        False otherwise.
        """
        if event_name in self.get_event_dict().keys():
            return True
        return False

    def _get_all_raw_waveform_files_for_iteration(self, iteration_name):
        """
        Helper method returning a list of all raw waveform files for one
        iteration.
        """
        iteration = self._get_iteration(iteration_name)
        all_files = []
        for event_name, event in iteration.events.iteritems():
            waveforms = self._get_waveform_cache_file(event_name, "raw")
            if not waveforms:
                continue
            stations = event["stations"].keys()
            all_files.extend(
                [_i["filename"] for _i in waveforms.get_values()
                 if (_i["network"] + "." + _i["station"]) in stations])

        return all_files

    def _get_long_iteration_name(self, short_iteration_name):
        """
        Helper function for creating a long iteration name.

        Used for filenames and folder structure. Very simple and just used for
        consistencies sake.
        """
        return "ITERATION_%s" % short_iteration_name

    def _get_synthetic_waveform_filenames(self, event_name, iteration_name):
        """
        Helper function finding all stations for one simulation, e.g. one event
        and iteration combination.

        Currently only uses the filenames for distinction as the current SES3D
        version does not write that information in the file. Will have to be
        updated in due time as new solver are incorporated.
        """
        # First step is to get the folder.
        folder_name = os.path.join(self.paths["synthetics"], event_name,
                                   self._get_long_iteration_name(
                                       iteration_name))
        stations = {}
        for filename in glob.iglob(os.path.join(folder_name, "*")):
            network, station, _, component = [
                _i.replace("_", "")
                for _i in os.path.basename(filename).split(".")]
            station_name = "%s.%s" % (network, station)
            stations.setdefault(station_name, {})
            stations[station_name][component.upper()] = \
                os.path.abspath(filename)
        return stations

    def get_iteration_status(self, iteration_name):
        """
        Return a dictionary with information about the current status of an
        iteration.
        """
        iteration = self._get_iteration(iteration_name)
        proc_tag = iteration.get_processing_tag()

        # Dictionary collecting all the information.
        status = {}
        status["channels_not_yet_preprocessed"] = []
        status["stations_in_iteration_that_do_not_exist"] = []
        status["synthetic_data_missing"] = {}

        # Now check which events and stations are supposed to be part of the
        # iteration and try to find them and their corresponding preprocessed
        # counterparts.
        for event_name, event_info in iteration.events.iteritems():
            # Events with a weight of 0 are not considered.
            if event_info["event_weight"] == 0.0:
                continue
            # Get the existing files.
            raw_waveforms = self._get_waveform_cache_file(event_name, "raw")
            proc_waveforms = self._get_waveform_cache_file(event_name,
                                                           proc_tag)
            # Extract the channels if some exist.
            raw_channels = {}
            if raw_waveforms:
                # Extract the channels.
                temp = [_i["channel_id"] for _i in raw_waveforms.get_values()]
                # Create a dictionary of all the channels sorted by station.
                for channel in temp:
                    station_name = ".".join(channel.split(".")[:2])
                    raw_channels.setdefault(station_name, [])
                    raw_channels[station_name].append(channel)
            # Extract the processed channels if some exist.
            if proc_waveforms:
                proc_channels = [_i["channel_id"] for _i in
                                 proc_waveforms.get_values()]
            else:
                proc_channels = []

            # Get the synthetics.
            synthetics = self._get_synthetic_waveform_filenames(event_name,
                                                                iteration_name)

            for station_name, station_info \
                    in event_info["stations"].iteritems():
                # Stations with a weight of zero are not considered.
                if station_info["station_weight"] == 0.0:
                    continue

                # Get all raw channels that have the current station.
                try:
                    current_chans = raw_channels[station_name]
                except KeyError:
                    current_chans = []

                # There should be at least one, otherwise the iteration xml
                # file is wrong.
                if not current_chans:
                    status["stations_in_iteration_that_do_not_exist"].append(
                        "Event '%s': '%s'" % (event_name, station_name))
                    continue
                for chan in current_chans:
                    if chan in proc_channels:
                        continue
                    status["channels_not_yet_preprocessed"].append(
                        "Event '%s': '%s'" % (event_name, chan))

                # Each station requires all three synthetic components. This is
                # necessary for rotations.
                if (station_name not in synthetics) or \
                        (len(synthetics[station_name]) != 3):
                    status["synthetic_data_missing"].setdefault(event_name, [])
                    status["synthetic_data_missing"][event_name].append(
                        station_name)
        return status
