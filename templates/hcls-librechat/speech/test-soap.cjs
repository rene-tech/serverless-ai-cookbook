const test = require('node:test');
const assert = require('node:assert/strict');
const { buildSoap, hash, UNKNOWN } = require('./soap.cjs');
function build(text, details = {}) {
  const source_attribution = details.source_attribution || 'patient_reported';
  const fact = { id: 'F0001', section: 'history', uncertain: false, source_attribution,
    source_attribution_extraction: source_attribution, source_attribution_review: source_attribution,
    source_phrases: [{quote:text,spans:[{start:0,end:[...text].length}]}], ...details };
  return buildSoap({transcript_sha256:hash(text),facts:[fact],rejected:[]},text,{job_id:'a'.repeat(32)});
}
test('SOAP keeps negation literal and objective/assessment unknown',()=>{
  const value=build('I do not have chest pain.');
  assert.equal(value.sections.S.facts[0].text,'I do not have chest pain.');
  assert.equal(value.sections.O.notice,UNKNOWN); assert.equal(value.sections.A.status,'not_documented');
  assert.equal(value.handoff.length,0); assert.equal(value.clinical_signoff,false);
  assert.equal(value.sections.S.facts[0].source[0].source_file,`/api/scientific-demos/clinical/${'a'.repeat(32)}/files/transcript.txt`);
});
test('patient reported measurement is never converted into objective findings',()=>{
  const value=build('My temperature was 38 degrees.',{section:'findings'});
  assert.equal(value.sections.S.facts.length,1); assert.equal(value.sections.O.facts.length,0);
});
test('missing dose stays unknown and handoff cannot execute',()=>{
  const value=build('Continue metformin.',{section:'plan',source_attribution:'clinician_statement',medication_or_dose:true,
    source_anchors:[{kind:'medication',surface:'metformin'}]});
  assert.equal(value.sections.P.facts[0].text,'Continue metformin.');
  assert.match(value.sections.P.facts[0].dose_policy,/remain unknown/);
  assert.equal(value.handoff[0].execution_authorized,false); assert.equal(value.handoff[0].assignee,'not_assigned');
});
test('attribution disagreement, uncertainty and teaching are not forced into SOAP',()=>{
  for(const changes of [{source_attribution_review:'unclear'},{uncertain:true},{source_attribution:'teaching_narration'}]){
    const value=build('A patient reports pain.',changes);
    assert.equal(value.unassigned.length,1);assert.equal(value.sections.S.facts.length,0);
  }
});
test('Unicode source offsets are Python code points, with mismatches failing closed',()=>{
  assert.equal(build('🙂 No fever.').sections.S.facts[0].source[0].spans[0].end,11);
  assert.throws(()=>build('unchanged',{source_phrases:[{quote:'invented',spans:[{start:0,end:8}]}]}),/does not match/);
  assert.throws(()=>buildSoap({transcript_sha256:'wrong'},'text',{}),/hash differs/);
});
test('bounded generation warnings remain visible without fabricating SOAP facts',()=>{
  const warnings=[{code:'bounded_generation_capacity_reached',detail:'Extraction reached its eight-fact limit; source coverage may be incomplete.'}];
  const value=buildSoap({transcript_sha256:hash('No fever.'),facts:[],rejected:[],generation_warnings:warnings},'No fever.',{});
  assert.deepEqual(value.generation_warnings,warnings);
  assert.equal(value.sections.S.facts.length,0);
  assert.equal(value.sections.O.notice,UNKNOWN);
  assert.equal(value.clinical_signoff,false);
});
