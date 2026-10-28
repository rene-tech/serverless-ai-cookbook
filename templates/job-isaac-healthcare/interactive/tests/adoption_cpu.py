"""Run as PID1 in a dedicated CPU container with installed package, private PID/IPC and four controller capabilities."""
import asyncio
import json
import os
from pathlib import Path
import signal
import sys
import time

from i4h_interactive import isolation
import i4h_interactive.process as candidate

RUNTIME = [str(Path(__file__).resolve().parent)] + [p for p in ('/opt/i4h', '/opt/python', '/opt/isaac-healthcare', '/opt/i4h-assets') if Path(p).is_dir()]
CHILD = r'''
import json,os,sys,time
from pathlib import Path
root=Path(sys.argv[1]);mode=sys.argv[2]
pid=os.fork()
if pid==0:
 if mode=='live':os.setsid()
 fields=Path('/proc/self/stat').read_text().rsplit(')',1)[1].split()
 (root/'orphan.json').write_text(json.dumps({'pid':os.getpid(),'uid':os.getuid(),'start_ticks':int(fields[19])}))
 if mode=='live':
  while True:time.sleep(.1)
 os._exit(0)
time.sleep(.1)
os._exit(0)
'''


async def run_case(name, cls, mode='zombie', identity_race=False):
    root = Path('/work') / name
    root.mkdir(mode=0o711)
    uid = isolation.new_identity('/work')
    project = root / 'project'
    project.mkdir(mode=0o770)
    project.chmod(0o770)
    os.chown(project, 0, uid)
    cfg = {'session_id': name, 'command': [sys.executable, '-I', '-B', '-c', CHILD, str(project), mode],
           'work_dir': str(project / 'process'), 'log_file': str(root / 'execution.log'),
           'closeout_file': str(root / 'process-closeout.json'), 'browser_origin': 'https://synthetic.invalid',
           'media_host': '127.0.0.1', 'signal_port': 49100, 'media_port': 47998, 'proxy_port': 49200,
           'deadline_at': time.time() + 30, 'stop_grace_seconds': 1,
           'startup_timeout_seconds': 1, 'network_mode': 'turn-relay',
           'turn_url': 'turns:synthetic.invalid:5349?transport=tcp', 'pid_namespace_guard': True,
           'isolation': {'root': str(project), 'uid': uid, 'runtime_roots': RUNTIME}}
    p = cls(cfg)
    await p.start()
    await asyncio.wait_for(p.child.wait(), 5)
    assert p.child.returncode == 0, Path(cfg['log_file']).read_text()
    os.chown(project / 'orphan.json', 0, 0, follow_symlinks=False)  # exact test-only PID witness
    orphan = json.loads((project / 'orphan.json').read_bytes())
    pid = orphan['pid']
    for _ in range(100):
        record = candidate._process_identity(pid)
        if record['parent'] == os.getpid() and (mode == 'live' or record['state'] == 'Z'):
            break
        await asyncio.sleep(.01)
    assert record['parent'] == os.getpid() and record['uids'] == (uid,) * 4
    assert record['start_ticks'] == orphan['start_ticks']
    original_identity = candidate._process_identity
    counts = [0]
    if identity_race:
        def changed(number):
            value = original_identity(number)
            if number == pid:
                counts[0] += 1
                if counts[0] == 2:
                    value['start_ticks'] += 1
            return value
        candidate._process_identity = changed
    try:
        await p.stop('cpu-proof')
    finally:
        candidate._process_identity = original_identity
    expected = 'stopped' if cls is candidate.SessionProcess and mode == 'zombie' and not identity_race else 'cleanup_unknown'
    assert p.state == expected, p.status()
    reaped = getattr(p, '_reaped_adopted_zombies', [])
    if expected == 'stopped':
        assert len(reaped) == 1 and reaped[0]['pid'] == pid
        assert reaped[0]['start_ticks'] == orphan['start_ticks']
        assert not Path('/proc', str(pid)).exists()
    else:
        current = original_identity(pid)
        assert current['start_ticks'] == orphan['start_ticks'] and current['uids'] == (uid,) * 4
        # Test-owned cleanup only, after the negative witness; product did not
        # signal an escaped live orphan or reap an uncertain identity.
        if mode == 'live':
            os.kill(pid, signal.SIGKILL)
        assert os.waitpid(pid, 0)[0] == pid
    return {'state': p.state, 'mode': mode, 'identity_race': identity_race,
            'reaped_count': len(reaped), 'original_managed_returncode': p.child.returncode}


async def main():
    assert os.getpid() == 1, 'Real container PID1 is required for adopted orphan proof'
    isolation.controller_boundary(runtime_roots=RUNTIME, work_roots=['/work'], authority_roots=[])
    result = {}
    # A separate direct child of another UID is deliberately left as a zombie.
    # It must remain waitable by this test after the successor cleanup.
    foreign_uid = isolation.new_identity('/work')
    foreign = os.fork()
    if foreign == 0:
        os.setgroups([])
        os.setgid(foreign_uid)
        os.setuid(foreign_uid)
        os._exit(31)
    for _ in range(100):
        if candidate._process_identity(foreign)['state'] == 'Z':
            break
        await asyncio.sleep(.01)
    managed = await asyncio.create_subprocess_exec(sys.executable, '-I', '-c', 'import time;time.sleep(.2);raise SystemExit(23)')
    result['candidate_zombie_join'] = await run_case('candidate-zombie', candidate.SessionProcess)
    assert os.waitpid(foreign, os.WNOHANG) == (foreign, 31 << 8)
    assert await managed.wait() == 23
    result['foreign_uid_unreaped_and_managed_Popen_status_preserved'] = True
    result['live_orphan_quarantined'] = await run_case('live-orphan', candidate.SessionProcess, 'live')
    result['changed_identity_quarantined'] = await run_case('identity-race', candidate.SessionProcess, identity_race=True)
    isolation.empty_ipc()
    print(json.dumps({'status': 'PASS_EXACT_OWNED_ADOPTED_ZOMBIE_CPU', 'cases': result,
                      'PID1': os.getpid(), 'landlock_abi': isolation.abi(),
                      'GPU_initialization': False, 'network': 'none'}, sort_keys=True))


if __name__ == '__main__':
    asyncio.run(main())
