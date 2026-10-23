"""Native grammar/projection regressions; these fixtures do not execute MD."""
import hashlib
from pathlib import Path

import pytest

import native_md_report as report
from test_native_md_report import bind_result, observed_openmm, recorded_run


def recovery(tmp_path, engine, command, texts):
    folder = tmp_path / 'renamed-recovery'
    native, manifest = recorded_run(folder, engine)
    command = {'step_id': 'dynamics', 'exit_code': 0, 'wall_seconds': 12.3,
               'log': 'wrapper.log', **command}
    texts = {'wrapper.log': 'wrapper output without scientific measurements\n', **texts}
    native['commands'] = [command]
    native['completed_steps'] = ['dynamics']
    for name, text in texts.items():
        path = folder / 'native/result-00' / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(text)
        metadata = {'size_bytes': path.stat().st_size, 'sha256': hashlib.sha256(path.read_bytes()).hexdigest()}
        native['files'].append({'path': name, **metadata})
        manifest['results'][0]['files'].append({'path': str(path), 'native_path': name, **metadata})
    bind_result(folder, native, manifest)
    return folder


def gromacs_log(first=10, last=25, end=2.03):
    return f'''Input Parameters:
   integrator = md
   dt = 0.002
   nsteps = 9000
There are: 127 Atoms
Started mdrun on rank 0
           Step           Time
{first:15d}        2.00000
      Potential    Kinetic En.    Temperature
    -1.2e+03       2.0e+02       299.5
           Step           Time
{last:15d}        {end}
      Potential    Kinetic En.    Temperature
    -1.1e+03       2.2e+02       301.25
  A V E R A G E S
      Potential    Kinetic En.    Temperature
    -1.1e+03       2.2e+02       290.0
       Time:       28.0        3.5       800.0
Finished mdrun on rank 0
'''


def gromacs_command(**overrides):
    return {'command': ['gmx', 'mdrun', '-deffnm', 'trial.with.dots'],
            'directory': 'nested space', 'segment': 2,
            'checkpoint_step': 25, 'performance_ns_per_day': 123.0, **overrides}


def test_gromacs_renamed_resumed_part_uses_observed_interval_not_requested_target(tmp_path):
    name = 'nested space/trial.with.dots.part0007.log'
    folder = recovery(tmp_path, 'gromacs', gromacs_command(), {name: gromacs_log()})
    before = {str(p): p.read_bytes() for p in folder.rglob('*') if p.is_file()}
    value = report.collect(folder, tmp_path)
    row, observed = value['timing_rows'][0], value['observations'][0]
    assert value['complete'] and row['requested_steps'] == 9000
    assert row['executed_steps'] == 15 and row['durably_completed_steps'] is None
    assert observed['initial_step'] == 10 and observed['final_step'] == 25
    assert observed['segment_physical_time_ps'] == pytest.approx(.03)
    assert observed['simulation_time_ps'] == 2.03
    assert observed['atom_count'] == 127
    assert (observed['temperature_k'], observed['temperature_step'], observed['temperature_time_ps']) == (301.25, 25, 2.03)
    assert observed['native_run_seconds'] == 3.5 and observed['integration_seconds'] is None
    html = report.html_report(value, tmp_path)
    assert 'verified native log' in html and 'Wall t accounting' in html
    assert 'Integration time (s)</dt><dd>unknown' in html
    assert before == {str(p): p.read_bytes() for p in folder.rglob('*') if p.is_file()}


def test_gromacs_multiple_parts_select_only_unique_matching_checkpoint(tmp_path):
    folder = recovery(tmp_path, 'gromacs', gromacs_command(), {
        'nested space/trial.with.dots.part0006.log': gromacs_log(last=20),
        'nested space/trial.with.dots.part0007.log': gromacs_log(),
    })
    observed = report.collect(folder, tmp_path)['observations'][0]
    assert observed['executed_steps'] == 15
    assert observed['temperature_file'].endswith('.part0007.log')


@pytest.mark.parametrize('logs', [
    {'trial.with.dots.log': gromacs_log(), 'trial.with.dots.part0007.log': gromacs_log()},
    {'trial.with.dots.log': gromacs_log() + gromacs_log()},
    {'trial.with.dots.log': 'unrecognized native output'},
])
def test_ambiguous_or_unrecognized_gromacs_log_never_invents_scientific_values(tmp_path, logs):
    folder = recovery(tmp_path, 'gromacs', gromacs_command(), {'nested space/' + k: v for k, v in logs.items()})
    value = report.collect(folder, tmp_path)
    assert value['complete']  # Existing wrapper timing is still measured.
    assert value['timing_rows'][0]['executed_steps'] is None
    assert value['observations'][0]['temperature_k'] is None
    assert value['observations'][0]['notes']


def test_explicit_gromacs_log_and_rerun_do_not_claim_integrated_steps(tmp_path):
    command = gromacs_command(command=['gmx', 'mdrun', '-g', 'unusual-name', '-rerun', 'frames.xtc'])
    folder = recovery(tmp_path, 'gromacs', command, {'nested space/unusual-name.log': gromacs_log()})
    value = report.collect(folder, tmp_path)
    assert value['observations'][0]['atom_count'] == 127
    assert value['timing_rows'][0]['executed_steps'] is None
    assert value['observations'][0]['segment_physical_time_ps'] is None


def test_invalid_gromacs_step_cannot_relabel_temperature_with_previous_step(tmp_path):
    text = gromacs_log().replace('             25        2.03', '             25        NaN')
    path = tmp_path / 'native.log'; path.write_text(text)
    observed = report.gromacs_observations(path)
    assert observed['temperature_step'] == 10
    assert observed['temperature_k'] == 299.5


def test_namd_projects_observed_endpoints_and_periodic_temperature_without_target_or_durability(tmp_path):
    command = {'command': ['namd3', 'renamed.in'], 'atoms': 321, 'performance_ns_per_day': 80.0,
               'observed_dynamics': {'initial_step': 100, 'observed_step': 150, 'target_step': 99999, 'timestep_ps': .001},
               'last_output_step': 150, 'last_energy': {'TS': 148, 'TEMP': 305.2, 'TEMPAVG': 300.0},
               'first_energy_log_observed_seconds': .4}
    folder = recovery(tmp_path, 'namd', command, {'wrapper.log': 'TIMING: 150 CPU: 9, 0.01/step Wall: 8.75, 0.01/step\n'})
    value = report.collect(folder, tmp_path)
    row, observed = value['timing_rows'][0], value['observations'][0]
    assert row['executed_steps'] == 50 and row['requested_steps'] is None
    assert row['durably_completed_steps'] is None and row['checkpoint_step'] is None
    assert observed['atom_count'] == 321 and observed['segment_physical_time_ps'] == .05
    assert observed['simulation_time_ps'] == .15
    assert (observed['temperature_k'], observed['temperature_step'], observed['temperature_time_ps']) == (305.2, 148, .148)
    assert observed['native_run_seconds'] == 8.75
    assert observed['integration_seconds'] is observed['setup_seconds'] is None


def test_namd_missing_initial_observation_does_not_turn_final_step_into_executed_work(tmp_path):
    folder = recovery(tmp_path, 'namd', {'command': ['namd3', 'input.namd'], 'last_output_step': 500,
        'first_energy_step': 100, 'timestep_fs': 2, 'observed_dynamics': {'target_step': 900},
        'performance_ns_per_day': 20.0, 'last_energy': {'TS': 490, 'TEMPAVG': 300.0}}, {})
    value = report.collect(folder, tmp_path)
    assert value['timing_rows'][0]['executed_steps'] is None
    assert value['observations'][0]['segment_physical_time_ps'] is None
    assert value['observations'][0]['temperature_k'] is None


def test_namd_published_observed_rate_is_used_when_wrapper_rate_is_absent(tmp_path):
    folder = recovery(tmp_path, 'namd', {'command': ['namd3', 'input.namd'],
        'observed_dynamics': {'ns_per_day': 47.5}}, {})
    value = report.collect(folder, tmp_path)
    assert value['complete'] and value['timing_rows'][0]['performance_ns_per_day'] == 47.5


AMBER_LOG = ''' NSTEP = 475 TIME(PS) = 17.375 TEMP(K) = 299.75 PRESS = 1.0
 A V E R A G E S O V E R 20 S T E P S
 NSTEP = 500 TIME(PS) = 17.500 TEMP(K) = 300.5 PRESS = 1.0
 R M S  F L U C T U A T I O N S
 NSTEP = 500 TIME(PS) = 17.500 TEMP(K) = 1.5 PRESS = 1.0
| Average timings for last 100 steps:
| Elapsed(s) = 0.2 Per Step(ms) = 2.0
| ns/day = 1.0D+02 seconds/ns = 864
| Average timings for all steps:
| Elapsed(s) = 3.4D+00 Per Step(ms) = 6.8
| ns/day = 6.3529D+01 seconds/ns = 1360
'''


def amber_command(**overrides):
    return {'kind': 'pmemd', 'argv': ['pmemd.cuda', '-o', 'report.results'], 'directory': 'nested',
            'validation': {'completion': {'task': 'dynamics', 'native_completion': True, 'natom': 456,
                'nstlim': 500, 'completed_native_steps': 500, 'dt_ps': .005, 'final_time_ps': 17.5}}, **overrides}


def test_amber_native_output_supplies_rate_before_timing_completeness_and_preserves_clock(tmp_path):
    folder = recovery(tmp_path, 'amber', amber_command(), {'nested/report.results': AMBER_LOG})
    value = report.collect(folder, tmp_path)
    row, observed = value['timing_rows'][0], value['observations'][0]
    assert value['complete'] and row['performance_ns_per_day'] == 63.529
    assert row['executed_steps'] == row['requested_steps'] == 500
    assert observed['atom_count'] == 456
    assert observed['segment_physical_time_ps'] == 2.5 and observed['simulation_time_ps'] == 17.5
    assert observed['temperature_k'] == 299.75 and observed['temperature_step'] == 475
    assert observed['final_step'] == 500 and observed['initial_step'] is None
    assert observed['native_run_seconds'] == 3.4 and observed['integration_seconds'] is None
    assert row['durably_completed_steps'] is None


@pytest.mark.parametrize('text', ['', '| ns/day = 3000\n', AMBER_LOG.replace('6.3529D+01', 'NaN')])
def test_missing_or_unscoped_amber_rate_stays_unknown(tmp_path, text):
    folder = recovery(tmp_path, 'amber', amber_command(), {'nested/report.results': text})
    value = report.collect(folder, tmp_path)
    assert not value['complete']
    assert value['timing_rows'][0]['performance_ns_per_day'] is None


def test_native_observation_hash_failure_blocks_publication(tmp_path):
    folder = recovery(tmp_path, 'amber', amber_command(), {'nested/report.results': AMBER_LOG})
    path = folder / 'native/result-00/nested/report.results'
    path.write_text(path.read_text().replace('299.75', '399.75'))
    with pytest.raises(ValueError, match='differ'):
        report.write_report(folder, tmp_path / 'new-report', tmp_path)
    assert not (tmp_path / 'new-report').exists()


def test_amber_minimization_is_not_a_dynamics_timing_row():
    assert not report.is_simulation('amber', amber_command(validation={'completion': {'task': 'minimize'}}))


def test_openmm_measurements_and_existing_report_contract_remain_unchanged(tmp_path):
    folder = tmp_path / 'openmm'; observed_openmm(folder)
    value = report.collect(folder, tmp_path)
    observed = value['observations'][0]
    assert observed['atom_count'] == 123 and observed['integration_seconds'] == 1.25
    assert observed['setup_seconds'] == .5 and observed['temperature_k'] == 299.75
    assert observed['segment_physical_time_ps'] == .1
    assert 'measurement_sources' not in observed and 'native_run_seconds' not in observed
    assert 'verified state CSV' in report.html_report(value, tmp_path)


def lammps_command(dt=.004, rate=17.6):
    return {'argv': ['lmp', '-in', 'renamed.in'],
            'observed_dynamics': {'initial_step': 100, 'observed_step': 125,
                                  'target_step': 99999, 'timestep_ps': dt, 'ns_per_day': rate}}


def test_lammps_multi_thermo_projects_measured_rate_and_loop_work_not_requested_target(tmp_path):
    text = '''Setting up Verlet run ...
  Unit style : real
  Current step : 100
  Time step : 4
------------ Step 100 ----- CPU = 0 (sec) -------------
TotEng = -10 Temp = 298.2
------------ Step 120 ----- CPU = 1 (sec) -------------
TotEng = -11 Temp = 299.6
Loop time of 1.25 on 2 procs for 25 steps with 777 atoms
'''
    folder = recovery(tmp_path, 'lammps', lammps_command(), {'wrapper.log': text})
    value = report.collect(folder, tmp_path)
    row, observed = value['timing_rows'][0], value['observations'][0]
    assert value['complete'] and row['performance_ns_per_day'] == 17.6
    assert row['executed_steps'] == 25 and row['requested_steps'] is None
    assert row['durably_completed_steps'] is None and row['checkpoint_step'] is None
    assert observed['atom_count'] == 777 and observed['segment_physical_time_ps'] == .1
    assert (observed['temperature_k'], observed['temperature_step']) == (299.6, 120)
    assert observed['temperature_time_ps'] is observed['simulation_time_ps'] is None
    assert observed['native_run_seconds'] == 1.25 and observed['integration_seconds'] is None


@pytest.mark.parametrize('units,clock,expected', [('real', 1234, 1.234), ('metal', 1.234, 1.234)])
def test_lammps_reordered_table_preserves_explicit_physical_clock(tmp_path, units, clock, expected):
    text = f'''Setting up rRESPA run ...
  Unit style : {units}
Temp Step Time PotEng
298.1 100 {clock} -20
Loop time of 1.2 on 1 procs for 25 steps with 777 atoms
'''
    folder = recovery(tmp_path, 'lammps', lammps_command(), {'wrapper.log': text})
    observed = report.collect(folder, tmp_path)['observations'][0]
    assert observed['simulation_time_ps'] == expected
    assert observed['temperature_time_ps'] == expected
    assert observed['temperature_k'] == 298.1


def test_lammps_reduced_units_do_not_become_kelvin_or_picoseconds(tmp_path):
    text = '''Setting up Verlet run ...
Unit style : lj
Step Temp
100 1.2
125 1.3
Loop time of 0.1 on 1 procs for 25 steps with 777 atoms
'''
    folder = recovery(tmp_path, 'lammps', lammps_command(dt=None, rate=None), {'wrapper.log': text})
    value = report.collect(folder, tmp_path)
    assert value['timing_rows'][0]['executed_steps'] == 25
    assert value['observations'][0]['temperature_k'] is None
    assert value['observations'][0]['segment_physical_time_ps'] is None
    assert value['timing_rows'][0]['performance_ns_per_day'] is None


def test_lammps_completed_loop_counts_survive_reset_and_skip_minimization(tmp_path):
    text = '''Setting up Verlet run ...
Unit style : real
Step Temp
100 299
Loop time of 1 on 1 procs for 25 steps with 777 atoms
Setting up cg style minimization ...
Step Temp
125 999
Loop time of 8 on 1 procs for 700 steps with 777 atoms
Setting up Verlet run ...
Unit style : real
Step Temp
0 300
10 301
Loop time of 2 on 1 procs for 10 steps with 777 atoms
'''
    folder = recovery(tmp_path, 'lammps', lammps_command(dt=None, rate=None), {'wrapper.log': text})
    value = report.collect(folder, tmp_path)
    observed = value['observations'][0]
    assert value['timing_rows'][0]['executed_steps'] == 35
    assert observed['native_run_seconds'] == 3
    assert observed['temperature_k'] == 301 and observed['temperature_step'] == 10
    assert observed['segment_physical_time_ps'] is None
