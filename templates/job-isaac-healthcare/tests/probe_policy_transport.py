import importlib.util,json,tempfile,time,sys,os
from pathlib import Path
import zenoh
from isaac_healthcare_runtime.runtime import policy_bus_directory
spec=importlib.util.spec_from_file_location('offline',str(Path(__file__).resolve().parents[1] / 'provider/offline_exec.py')); mod=importlib.util.module_from_spec(spec);spec.loader.exec_module(mod)
proof=mod.restrict_network()
with policy_bus_directory() as tmp:
 endpoint='unixsock-stream/'+tmp+'/bus.sock'
 def config(listen=False):
  value=zenoh.Config();value.insert_json5('mode',json.dumps('router' if listen else 'client'));value.insert_json5('scouting/multicast/enabled','false');value.insert_json5('scouting/gossip/enabled','false');value.insert_json5('listen/endpoints' if listen else 'connect/endpoints',json.dumps([endpoint]));value.insert_json5('listen/endpoints' if not listen else 'connect/endpoints','[]');return value
 server=zenoh.open(config(True)); client=zenoh.open(config(False)); received=[]
 sub=server.declare_subscriber('isaac/cpu_probe',lambda msg:received.append(msg.payload.to_bytes()))
 publisher=client.declare_publisher('isaac/cpu_probe')
 until=time.monotonic()+5
 while not received and time.monotonic()<until:
  publisher.put(b'actual-unix-transport');time.sleep(.1)
 if not received or any(x!=b'actual-unix-transport' for x in received):
  print(json.dumps({'failed':True,'received':str(received)}),flush=True);os._exit(1)
 publisher.undeclare();sub.undeclare();client.close();server.close()
 bus_parent=str(Path(tmp).parent)
print(json.dumps({'transport':'unixsock-stream','sent_and_received':True,'internet_socket_families_denied':proof['denied_socket_families'],'bus_parent':bus_parent,'private_directory_removed':not Path(tmp).exists()}))
