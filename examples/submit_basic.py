# -*- coding: utf-8 -*-
"""Submit a test calculation on localhost.

Usage: verdi run submit.py

Note: This script assumes you have set up computer and code as in README.md.
"""
import os

import aiida_crystal17.tests as tests
from aiida.orm import DataFactory

# get code
code = tests.get_code(
    entry_point='crystal17.basic')

# Prepare input parameters
SinglefileData = DataFactory("singlefile")
infile = SinglefileData(file=os.path.join(tests.TEST_DIR, "input_files", 'mgo_sto3g_scf.crystal.d12'))

# set up calculation
calc = code.new_calc()
calc.label = "aiida_crystal17 test"
calc.description = "Test job submission with the aiida_crystal17 plugin"
calc.set_max_wallclock_seconds(30)
calc.set_withmpi(False)
calc.set_resources({"num_machines": 1, "num_mpiprocs_per_machine": 1})

calc.use_input_file(infile)

calc.store_all()

calc.submit()
print("submitted calculation; calc=Calculation(PK={})".format(calc.dbnode.pk))
