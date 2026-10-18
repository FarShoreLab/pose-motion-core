import {spawnSync} from 'node:child_process';
const checks=[['node',['--check','public/app.js']],['node',['--check','public/joint-policy.js']],['node',['--check','public/pose-worker.js']],['node',['audit_v4/test_joint_policy_independent.mjs']],['python3',['-m','unittest','discover','-s','audit_v4','-p','test_*.py','-v']],['python3',['scripts/test_range.py']]];
for(const [cmd,args]of checks){const p=spawnSync(cmd,args,{stdio:'inherit'});if(p.status!==0)process.exit(p.status||1);}console.log('All v4 syntax, policy, audit and Range checks passed. Runtime logs audited separately.');
