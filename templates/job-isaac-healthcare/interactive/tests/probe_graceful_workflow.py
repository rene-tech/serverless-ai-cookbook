"""CPU-only deterministic overlap of the actual wrapper and a real HDF5 writer."""

import argparse
import hashlib
import io
import json
import os
import signal
import subprocess
import sys
import time
from pathlib import Path

WRAPPER = r"""
import contextlib,importlib.util,json,os,signal,subprocess,sys,time,types
from pathlib import Path
root=Path(sys.argv[2]);source=Path(sys.argv[1])
for name in ('isaac_healthcare_runtime','isaac_healthcare_runtime.contract','isaac_healthcare_runtime.project','isaac_healthcare_runtime.inspection','isaac_healthcare_runtime.runtime'):
 sys.modules[name]=types.ModuleType(name)
sys.modules['isaac_healthcare_runtime.contract'].parameters=lambda v:v
sys.modules['isaac_healthcare_runtime.project'].prepare_project=lambda *args:{'effective_root':str(root)}
sys.modules['isaac_healthcare_runtime.project'].apply_project_defaults=lambda v,c:v
sys.modules['isaac_healthcare_runtime.inspection'].inspect_context=lambda *args:{'selected':{'mode':'teleop'}}
@contextlib.contextmanager
def command(*args,**kwargs):yield [sys.executable,str(root/'writer.py'),str(root)],dict(os.environ)
sys.modules['isaac_healthcare_runtime.runtime'].interactive_command=command
spec=importlib.util.spec_from_file_location('actual_workflow',source);module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module)
original=subprocess.Popen
class Proxy:
 def __init__(self,*args,**kwargs):self.value=original(*args,**kwargs)
 def __getattr__(self,name):return getattr(self.value,name)
 def send_signal(self,number):
  # Force the competing graceful-close interleaving, not any fake HDF5 behavior.
  if number==signal.SIGINT:
   end=time.monotonic()+2
   while not (root/'closing').exists() and time.monotonic()<end:time.sleep(.005)
  return self.value.send_signal(number)
subprocess.Popen=Proxy
try:
 result=module.run({'root':str(root),'base_root':str(root),'archive':str(root/'unused.tar'),'parameters':{'replay_episodes':[0],'seed':7},'session_id':'cpu-interrupt-proof','kit_arguments':[],'stop_grace_seconds':3})
except KeyboardInterrupt:result=130
sys.exit(result)
"""

WRITER = r"""
import json,os,signal,sys,time
from pathlib import Path
import h5py
root=Path(sys.argv[1]);count=0
def interrupted(number,frame):
 global count
 count+=1
 (root/'signals.json').write_text(json.dumps({'count':count}))
 raise KeyboardInterrupt
signal.signal(signal.SIGINT,interrupted)
f=h5py.File(root/'recorded.hdf5','w');f.create_dataset('measurements',data=[1.,2.,3.])
(root/'signals.json').write_text(json.dumps({'count':count}))
(root/'ready').write_text(str(os.getpid()))
if os.environ['I4H_CPU_WRITER_MODE'] != 'interrupt':
 f.close();(root/'closed').write_text('writer-closed')
 sys.exit(7 if os.environ['I4H_CPU_WRITER_MODE']=='failure' else 0)
try:
 try:
  while True:time.sleep(.01)
 except KeyboardInterrupt:pass
 finally:
  (root/'closing').write_text('writer-draining')
  time.sleep(.75)
  f.close()
  (root/'closed').write_text('writer-closed')
except BaseException:
 # Exact Arena launch failure semantics: atexit must not mask the failure.
 os._exit(77)
"""


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--source", type=Path, required=True)
    p.add_argument("--out", type=Path, required=True)
    p.add_argument(
        "--mode", choices=["interrupt", "natural", "failure"], default="interrupt"
    )
    a = p.parse_args()
    a.out.mkdir(mode=0o700, parents=True, exist_ok=False)
    (a.out / "wrapper.py").write_text(WRAPPER)
    (a.out / "writer.py").write_text(WRITER)
    env = dict(os.environ)
    env["CUDA_VISIBLE_DEVICES"] = ""
    env["PYTHONDONTWRITEBYTECODE"] = "1"
    env["I4H_CPU_WRITER_MODE"] = a.mode
    with (
        (a.out / "stdout").open("xb") as stdout,
        (a.out / "stderr").open("xb") as stderr,
    ):
        child = subprocess.Popen(
            [sys.executable, str(a.out / "wrapper.py"), str(a.source), str(a.out)],
            stdout=stdout,
            stderr=stderr,
            start_new_session=True,
            env=env,
        )
        try:
            end = time.monotonic() + 30
            while not (a.out / "ready").exists():
                if child.poll() is not None or time.monotonic() > end:
                    raise RuntimeError("CPU writer never became ready")
                time.sleep(0.01)
            if a.mode == "interrupt":
                os.killpg(child.pid, signal.SIGINT)
            code = child.wait(timeout=10)
        finally:
            if child.poll() is None:
                os.killpg(child.pid, signal.SIGKILL)
                child.wait()
    import h5py

    path = a.out / "recorded.hdf5"
    valid = False
    error = None
    values = None
    try:
        with h5py.File(io.BytesIO(path.read_bytes()), "r") as f:
            values = f["measurements"][:].tolist()
            valid = True
    except OSError as e:
        error = str(e)
    result = {
        "mode": a.mode,
        "source": str(a.source),
        "source_sha256": hashlib.sha256(a.source.read_bytes()).hexdigest(),
        "wrapper_exit_code": code,
        "signals": json.loads((a.out / "signals.json").read_text()),
        "hdf5_bytes": path.stat().st_size,
        "hdf5_valid": valid,
        "hdf5_error": error,
        "values": values,
        "closed_witness": (a.out / "closed").exists(),
        "h5py": h5py.__version__,
        "scope": "Real CPU subprocess/group signals and real HDF5; deterministic scheduling of the observed source race, not proof of the original GPU failure cause.",
        "gpu_work": 0,
        "network_calls": 0,
        "scope_limits": "CPU stub project/context, real wrapper, subprocess and h5py. Does not qualify Kit/GPU or authored backend drain capacity.",
    }
    (a.out / "receipt.json").write_text(json.dumps(result, indent=2) + "\n")
    print(json.dumps(result))
    expected = {"interrupt": (130, 1), "natural": (0, 0), "failure": (7, 0)}[a.mode]
    assert (code, result["signals"]["count"]) == expected, result
    assert valid and result["closed_witness"] and values == [1.0, 2.0, 3.0], result
    witness = json.loads((a.out / "workflow-closeout.json").read_text())
    assert witness["children_joined"] and witness["wrapper_exit_code"] == code, witness


if __name__ == "__main__":
    main()
