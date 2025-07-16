from io import BytesIO

from pathlib import Path

import numpy as np
from dimod import BinaryQuadraticModel, SPIN
import h5py


from veloxq_sdk.api.problems import InstanceDict, File
from veloxq_sdk.api.jobs import VeloxSampleSet


INSTANCE_H5 = Path(__file__).parent / 'test.h5'

INSTANCE_DIMOD = BinaryQuadraticModel(
    {0: 0.0, 1: 1.0},
    {(0, 1): 0.5},
    SPIN,
)


BIASES_TYPES = {
    'ndarray': np.array([0.0, 1.0]),
    'list': [0.0, 1.0],
    'dict': {0: 0.0, 1: 1.0},
    'linear': INSTANCE_DIMOD.spin.linear,
}

COUPLINGS_TYPES = {
    'ndarray': np.array([[0, 0.5], [0.5, 0]]),
    'list': [[0, 0.5], [0.5, 0]],
    'dict': {(0, 1): 0.5},
    'quadratic': INSTANCE_DIMOD.spin.quadratic,
}

INSTANCES_DICT = [
    InstanceDict(biases=BIASES_TYPES['ndarray'], couplings=COUPLINGS_TYPES['ndarray']),
    InstanceDict(biases=BIASES_TYPES['list'], couplings=COUPLINGS_TYPES['list']),
    InstanceDict(biases=BIASES_TYPES['dict'], couplings=COUPLINGS_TYPES['dict']),
    InstanceDict(biases=BIASES_TYPES['linear'], couplings=COUPLINGS_TYPES['quadratic']),
]

INSTANCES_TUPLE = [
    (BIASES_TYPES['ndarray'], COUPLINGS_TYPES['ndarray']),
    (BIASES_TYPES['list'], COUPLINGS_TYPES['list']),
    (BIASES_TYPES['dict'], COUPLINGS_TYPES['dict']),
    (BIASES_TYPES['linear'], COUPLINGS_TYPES['quadratic']),
]

INSTANCES = [
    *INSTANCES_DICT,
    *INSTANCES_TUPLE,
    INSTANCE_DIMOD,
    INSTANCE_H5,
]

def assert_correct_h5(h5_file: h5py.File) -> None:
    """
    Assert that the HDF5 file contains the correct structure and data for the given instance.
    """
    biases: np.ndarray = h5_file['/Ising/biases'][:]
    couplings: np.ndarray = h5_file['/Ising/couplings'][:]

    assert np.all(biases == BIASES_TYPES['ndarray'])
    assert np.all(couplings == COUPLINGS_TYPES['ndarray'])


def check_h5_file(file: File) -> None:
    buffer = BytesIO()
    file.download(buffer)
    buffer.seek(0)
    with h5py.File(buffer, 'r') as h5_file:
        assert_correct_h5(h5_file)


def check_result(result: VeloxSampleSet) -> None:
    """Check that the result is correct."""
    assert result.first.energy == INSTANCE_DIMOD.spin.energy(result.first.sample)

    assert result.first.sample[0] == 1
    assert result.first.sample[1] == -1

    assert result.variables == [0, 1]
    assert result.vartype == SPIN

def check_result_h5(result_file: h5py.File) -> None:
    """Check that the result in HDF5 format is correct."""
    sample = result_file['Spectrum/samples'][0]
    energy = result_file['Spectrum/energies'][0]

    assert sample[0] == 1
    assert sample[1] == -1

    assert energy == INSTANCE_DIMOD.spin.energy(sample)
