#!/usr/bin/env python3
"""Fail the image build if the installed CPU preparation stack is incomplete."""
import importlib.metadata
import json
from pathlib import Path
import os
import shutil
import sys

os.environ['PATH'] = str(Path(sys.executable).parent) + os.pathsep + os.environ.get('PATH', '')
from openff.toolkit import ForceField, Molecule
from openff.toolkit.utils import AmberToolsToolkitWrapper, RDKitToolkitWrapper
import openff.interchange
import openmm

assert AmberToolsToolkitWrapper.is_available(), 'AmberTools charge backend missing'
assert RDKitToolkitWrapper.is_available(), 'RDKit chemistry backend missing'
assert shutil.which('antechamber'), 'antechamber missing'
assert shutil.which('sqm'), 'sqm missing'
ForceField('openff-2.2.1.offxml')
assert Molecule.from_smiles('CCO').n_atoms == 9
assert openmm.Platform.getPlatformByName('Reference').getName() == 'Reference'
print(json.dumps({'interpreter': sys.executable, 'gpu_required': False,
                  'force_field': 'openff-2.2.1.offxml',
                  'versions': {name: importlib.metadata.version(name) for name in
                               ('openff-toolkit', 'openff-interchange', 'openmm', 'rdkit')}}))
