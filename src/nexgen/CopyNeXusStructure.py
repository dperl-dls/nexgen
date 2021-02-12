#!/usr/bin/env python

import os
import numpy
import h5py
from h5py import AttributeManager


def create_attributes(obj, names, values):
    for n, v in zip(names, values):
        if type(v) is str:
            v = numpy.string_(v)
        AttributeManager.create(obj, name=n, data=v)


def get_nexus_tree(nxs_in, nxs_out):
    " Copy the whole tree from the original nexus file except for nxdata. Returns nxentry."
    nxentry = nxs_out.create_group("entry")
    create_attributes(nxentry, ("NX_class",), ("NXentry",))
    # Copy all of the nexus tree as it is except for /entry/data
    for k in nxs_in["entry"].keys():
        if k == "data":
            continue
        nxs_in["entry"].copy(k, nxentry)
    return nxentry


def timepix_axis(fin, nxdata, nxsample, step):
    # Timepix data have an array with start and stop value for rotation
    # instead of the full list.
    # If dealing with stills, start == stop
    nxdata_grp = fin["entry/data"]
    for k in nxdata_grp.keys():
        try:
            if type(nxdata_grp[k]) is h5py.Dataset:
                ax = k
                # Get the attributes
                ax_attr = nxdata_grp[k].attrs.items()
                (start, stop) = nxdata_grp[k][()]
        except KeyError:
            continue
    # (start, stop) = ax[()]
    if start == stop:
        ax_range = start
    else:
        ax_range = numpy.array([round(p, 1) for p in numpy.arange(start, stop, step)])
    # del nxdata[ax]
    # nxdata[ax] = ax_range
    nxdata.create_dataset(ax, data=ax_range)
    # Get the atributes
    for key, value in ax_attr:
        nxdata[ax].attrs.create(key, value)
    # Now modify nxsample
    del nxsample["transformations/" + ax]
    nxsample["transformations/" + ax] = nxdata[ax]
    name = "sample_" + ax + "/" + ax
    del nxsample[name]
    nxsample[name] = nxdata[ax]
    return ax


def copy_nexus_from_timepix(data_file, timepix_nexus, step=0.1):
    """
    Copy nexus tree and all metadata from event-mode Tristan detector.
    """
    nxs_filename = os.path.splitext(data_file)[0] + ".nxs"
    with h5py.File(timepix_nexus, "r") as nxs_in, h5py.File(
        nxs_filename, "x"
    ) as nxs_out:
        # Copy the whole tree except for nxdata
        nxentry = get_nexus_tree(nxs_in, nxs_out)
        # Create nxdata group
        nxdata = nxentry.create_group("data")
        # Get nxsample group to be modified with the correct axis
        nxsample = nxentry["sample"]
        # Compute and write axis information
        _ax = timepix_axis(nxs_in, nxdata, nxsample, step)
        create_attributes(
            nxdata, ("NX_class", "axes", "signal"), ("NXdata", _ax, "data")
        )
        # Add link to data
        with h5py.File(data_file, "r") as fh:
            nxdata["data"] = h5py.ExternalLink(fh.filename, "data")


def copy_nexus(data_file, original_nexus, event_mode=False, flip=False):
    """
    Copy nexus tree.
    """
    nxs_filename = os.path.splitext(data_file)[0] + ".nxs"
    with h5py.File(original_nexus, "r") as nxs_in, h5py.File(
        nxs_filename, "x"
    ) as nxs_out:
        # Copy the whole tree except for nxdata
        # Copy the whole tree except for nxdata
        nxentry = get_nexus_tree(nxs_in, nxs_out)
        # Create nxdata group
        nxdata = nxentry.create_group("data")
        # Find and copy only scan axis information
        for k in nxs_in["entry/data"].keys():
            # This operates under the assumption that only axis has attributes
            if nxs_in["entry/data"][k].attrs.keys():
                nxs_in["entry/data"].copy(k, nxdata)
                _ax = k
        create_attributes(
            nxdata, ("NX_class", "axes", "signal"), ("NXdata", _ax, "data")
        )
        # Add link to data
        try:
            # Temporary thing, I don't like this way.
            # This is just for copying the whole file.
            fout = h5py.File(data_file, "x")
            nxs_in["entry/data"].copy("data", fout)
        except OSError:
            fout = h5py.File(data_file, "r")
        if event_mode is True:
            for k in fout.keys():
                nxdata[k] = h5py.ExternalLink(fout.filename, k)
        else:
            nxdata["data"] = h5py.ExternalLink(fout.filename, "data")
        fout.close()

        # Flip data_size if prompted to do so
        # This is because in some Eiger HDF5 files "entry/instrument/detector/module/data_size" is flipped
        if flip is True:
            data_size = nxs_out["entry/instrument/detector/module/data_size"]
            data_size[...] = data_size[()][::-1]


"""
def CopyNexusStructure(h5_out, h5_in, step=0.1, event_mode=False, flip=False):
    #
    #Copy nexus tree from one file to another.
    #
    nxs_filename = os.path.splitext(h5_out)[0] + ".nxs"
    with h5py.File(h5_in, "r") as fin, h5py.File(nxs_filename, "x") as nxs:
        # Create first level with attributes
        nxentry = nxs.create_group("entry")
        create_attributes(nxentry, ("NX_class",), ("NXentry",))
        # Copy all of the nexus tree as it is except for /entry/data
        for k in fin["entry"].keys():
            if k == "data":
                continue
            fin["entry"].copy(k, nxentry)

        # Get description to decide what needs to be done with nxdata and scan axis
        description = fin["entry/instrument/detector/description"][()]
        # Write NXdata group
        nxdata = nxentry.create_group("data")
        nxsample = nxs["entry/sample"]
        # Scan axis
        if "Timepix" in description:
            _ax = timepix_axis(fin, nxdata, nxsample, step)
        else:
            for k in fin["entry/data"].keys():
                if fin["entry/data"][k].attrs.keys():
                    fin["entry/data"].copy(k, nxdata)
                    _ax = k
        create_attributes(
            nxdata, ("NX_class", "axes", "signal"), ("NXdata", _ax, "data")
        )
        # Add link to data
        try:
            fout = h5py.File(h5_out, "x")
            # img_to_h5(fout, fin)
            fin["entry/data"].copy("data", fout)  # Temporary fix
        except OSError:
            fout = h5py.File(h5_out, "r")

        if event_mode is True:
            for k in fout.keys():
                nxdata[k] = h5py.ExternalLink(fout.filename, k)
        else:
            nxdata["data"] = h5py.ExternalLink(fout.filename, "data")
        fout.close()

        # Flip data_size if prompted to do so
        # This is because in some Eiger HDF5 files "entry/instrument/detector/module/data_size" is flipped
        if flip is True:
            data_size = nxs["entry/instrument/detector/module/data_size"]
            data_size[...] = data_size[()][::-1]
"""
